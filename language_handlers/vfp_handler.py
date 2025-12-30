"""
VFP (Visual FoxPro) Language Handler

This module contains all VFP-specific logic for the code commenting system:
- Pydantic models for structured LLM output
- Adaptive chunking strategy
- LLM prompts (system, Phase 1, Phase 2)
- Comment syntax validation
- File header formatting

This consolidates code from:
- structured_output.py (VFP Pydantic models)
- vfp_chunker.py (AdaptiveVFPChunker)
- instructor_client.py (VFP prompts)
"""

import re
from typing import List, Dict, Type, Optional, Tuple
from dataclasses import dataclass
from pydantic import BaseModel, Field, field_validator

from .base_handler import LanguageHandler


# ===== VFP PYDANTIC MODELS =====

class CommentBlock(BaseModel):
    """
    A single comment block to be inserted at a specific position in VFP code.

    Attributes:
        insert_before_line: Line number to insert comment before (1-indexed)
        comment_lines: List of comment lines (each should start with *)
        context: Brief description of what this comment explains
    """
    insert_before_line: int = Field(
        ...,
        description="Line number where comment should be inserted (1-indexed)",
        ge=1
    )
    comment_lines: List[str] = Field(
        ...,
        description="List of VFP comment lines, each starting with *",
        min_length=1
    )
    context: Optional[str] = Field(
        None,
        description="Brief description of what this comment explains"
    )

    @field_validator('comment_lines')
    @classmethod
    def validate_comment_format(cls, v: List[str]) -> List[str]:
        """Ensure all comment lines start with VFP comment syntax"""
        validated = []
        for line in v:
            stripped = line.strip()
            if not stripped:
                continue  # Skip empty lines
            # Ensure it starts with * (VFP comment syntax)
            if not stripped.startswith('*'):
                stripped = f"* {stripped}"
            validated.append(stripped)
        return validated


class FileHeaderComment(BaseModel):
    """
    Structured file header comment following VFP conventions.
    """
    filename: str = Field(..., description="Name of the VFP file")
    location: str = Field(..., description="Relative path from root")
    purpose: List[str] = Field(
        ...,
        description="Multi-line description of file purpose",
        min_length=1
    )
    dependencies: List[str] = Field(
        default_factory=list,
        description="List of dependencies (tables, files, globals)"
    )
    key_functions: List[str] = Field(
        default_factory=list,
        description="List of main procedures/functions in file"
    )

    def to_vfp_comment(self) -> str:
        """Convert to VFP comment format with proper structure"""
        lines = [
            "* " + "-" * 68,
            f"* File: {self.filename}",
            f"* Location: {self.location}",
            "*",
            "* Purpose:"
        ]

        # Add purpose lines
        for purpose_line in self.purpose:
            lines.append(f"*   {purpose_line}")

        # Add dependencies if present
        if self.dependencies:
            lines.append("*")
            lines.append("* Dependencies:")
            for dep in self.dependencies:
                lines.append(f"*   - {dep}")

        # Add key functions if present
        if self.key_functions:
            lines.append("*")
            lines.append("* Key Functions:")
            for func in self.key_functions:
                lines.append(f"*   - {func}")

        lines.append("* " + "-" * 68)

        return "\n".join(lines)


class ChunkComments(BaseModel):
    """
    Model for chunk commenting - COMMENTS ONLY (no code duplication).

    This model asks the LLM to return ONLY comments, not the original code.
    This is safer because the LLM never touches the code.
    """
    file_header: FileHeaderComment = Field(
        ...,
        description="Structured file header comment for this chunk"
    )
    inline_comments: List[CommentBlock] = Field(
        default_factory=list,
        description="List of inline comments to insert at specific positions"
    )

    def insert_comments_into_code(self, original_code: str, include_header: bool = False) -> str:
        """
        Insert comments into original code WITHOUT modifying the code.

        Args:
            original_code: The original VFP code (100% preserved)
            include_header: Whether to include file header comment

        Returns:
            Original code with comments inserted at specified positions
        """
        result_lines = []

        # Add file header if requested
        if include_header:
            result_lines.append(self.file_header.to_vfp_comment())
            result_lines.append("")

        # Split original code into lines
        code_lines = original_code.split('\n')

        # Sort inline comments by line number
        sorted_comments = sorted(self.inline_comments, key=lambda c: c.insert_before_line)

        # Track which comment we're on
        comment_index = 0

        for line_num, code_line in enumerate(code_lines, start=1):
            # Insert any comments that belong before this line
            while (comment_index < len(sorted_comments) and
                   sorted_comments[comment_index].insert_before_line == line_num):

                comment_block = sorted_comments[comment_index]

                # Add blank line before comment for readability (unless it's the first line)
                if line_num > 1 and result_lines and result_lines[-1].strip():
                    result_lines.append("")

                # Add comment lines
                result_lines.extend(comment_block.comment_lines)

                comment_index += 1

            # Add the original code line (UNMODIFIED)
            result_lines.append(code_line)

        return '\n'.join(result_lines)


class ProcedureInfo(BaseModel):
    """Information about a VFP procedure or function"""
    name: str = Field(..., description="Name of procedure or function")
    line_number: int = Field(..., description="Starting line number (1-indexed)", ge=1)
    description: str = Field(..., description="Brief description of what this procedure/function does")
    type: Optional[str] = Field(None, description="Either 'PROCEDURE' or 'FUNCTION'")


class FileAnalysis(BaseModel):
    """
    File structure analysis for Phase 1 of two-phase processing.

    This model extracts high-level file information to provide context for Phase 2.
    """
    filename: str = Field(..., description="Name of the file")
    file_overview: str = Field(
        ...,
        description="2-3 sentence overview of what this file does"
    )
    procedures: List[ProcedureInfo] = Field(
        default_factory=list,
        description="List of procedures and functions found"
    )
    dependencies: List[str] = Field(
        default_factory=list,
        description="Tables, global variables, external files used"
    )
    total_lines: int = Field(..., description="Total number of lines", ge=1)


# ===== VFP CHUNKING LOGIC =====

@dataclass
class CodeChunk:
    """Represents a chunk of VFP code with metadata"""
    content: str
    start_line: int
    end_line: int
    chunk_type: str  # 'toplevel', 'procedure', 'function'
    name: str  # Procedure/function name, or 'toplevel' for top-level code

    def __len__(self):
        return len(self.content.split('\n'))

    @property
    def line_count(self):
        return len(self.content.split('\n'))


class VFPChunker:
    """
    Intelligent VFP code chunker that splits at procedural boundaries.

    Features:
    - Identifies PROCEDURE and FUNCTION blocks
    - Keeps complete procedures together
    - Handles top-level code (outside procedures)
    - Case-insensitive keyword matching
    """

    def __init__(self, max_chunk_lines: int = 30):
        """
        Initialize the chunker.

        Args:
            max_chunk_lines: Maximum lines per chunk
        """
        self.max_chunk_lines = max_chunk_lines

        # VFP keywords for procedure boundaries (case-insensitive)
        self.proc_start_pattern = re.compile(
            r'^\s*(PROCEDURE|FUNCTION)\s+(\w+)',
            re.IGNORECASE | re.MULTILINE
        )
        self.proc_end_pattern = re.compile(
            r'^\s*(ENDPROC|ENDFUNC)',
            re.IGNORECASE | re.MULTILINE
        )

    def chunk_code(self, vfp_code: str) -> List[CodeChunk]:
        """
        Split VFP code into logical chunks at procedural boundaries.

        Args:
            vfp_code: The complete VFP code to chunk

        Returns:
            List of CodeChunk objects
        """
        lines = vfp_code.split('\n')
        chunks = []

        # Find all procedure/function blocks
        proc_blocks = self._find_procedure_blocks(vfp_code, lines)

        # Handle top-level code (before first procedure)
        if proc_blocks and proc_blocks[0]['start_line'] > 0:
            toplevel_lines = lines[0:proc_blocks[0]['start_line']]
            if any(line.strip() for line in toplevel_lines):  # Only if not empty
                if len(toplevel_lines) <= self.max_chunk_lines:
                    chunks.append(CodeChunk(
                        content='\n'.join(toplevel_lines),
                        start_line=0,
                        end_line=proc_blocks[0]['start_line'] - 1,
                        chunk_type='toplevel',
                        name='toplevel'
                    ))
                else:
                    sub_chunks = self._sub_chunk_procedure(
                        toplevel_lines, 0, 'toplevel', 'toplevel'
                    )
                    chunks.extend(sub_chunks)

        elif not proc_blocks:
            # Entire file is top-level code
            if len(lines) <= self.max_chunk_lines:
                chunks.append(CodeChunk(
                    content=vfp_code,
                    start_line=0,
                    end_line=len(lines) - 1,
                    chunk_type='toplevel',
                    name='toplevel'
                ))
            else:
                sub_chunks = self._sub_chunk_procedure(
                    lines, 0, 'toplevel', 'toplevel'
                )
                chunks.extend(sub_chunks)
            return chunks

        # Add each procedure/function as a chunk
        for block in proc_blocks:
            proc_lines = lines[block['start_line']:block['end_line'] + 1]
            proc_line_count = len(proc_lines)

            if proc_line_count <= self.max_chunk_lines:
                proc_code = '\n'.join(proc_lines)
                chunks.append(CodeChunk(
                    content=proc_code,
                    start_line=block['start_line'],
                    end_line=block['end_line'],
                    chunk_type=block['type'],
                    name=block['name']
                ))
            else:
                # Sub-chunk large procedures
                sub_chunks = self._sub_chunk_procedure(
                    proc_lines,
                    block['start_line'],
                    block['name'],
                    block['type']
                )
                chunks.extend(sub_chunks)

        return chunks

    def _find_procedure_blocks(self, vfp_code: str, lines: List[str]) -> List[Dict]:
        """Find all procedure/function blocks in the code"""
        blocks = []
        i = 0

        while i < len(lines):
            line = lines[i]
            match = self.proc_start_pattern.match(line)

            if match:
                keyword = match.group(1).upper()
                name = match.group(2)
                start_line = i

                end_line = self._find_end_of_procedure(lines, i, keyword)

                if end_line:
                    blocks.append({
                        'type': 'procedure' if keyword == 'PROCEDURE' else 'function',
                        'name': name,
                        'start_line': start_line,
                        'end_line': end_line
                    })
                    i = end_line + 1
                else:
                    blocks.append({
                        'type': 'procedure' if keyword == 'PROCEDURE' else 'function',
                        'name': name,
                        'start_line': start_line,
                        'end_line': len(lines) - 1
                    })
                    break
            else:
                i += 1

        return blocks

    def _find_end_of_procedure(self, lines: List[str], start_line: int, keyword: str) -> Optional[int]:
        """Find the ENDPROC/ENDFUNC that matches a PROCEDURE/FUNCTION"""
        nesting = 1

        for i in range(start_line + 1, len(lines)):
            line = lines[i].strip().upper()

            if line.startswith('PROCEDURE ') or line.startswith('FUNCTION '):
                nesting += 1
            elif line.startswith('ENDPROC') or line.startswith('ENDFUNC'):
                nesting -= 1
                if nesting == 0:
                    return i

        return None

    def _sub_chunk_procedure(
        self,
        proc_lines: List[str],
        start_line: int,
        proc_name: str,
        proc_type: str
    ) -> List[CodeChunk]:
        """Split a large procedure into smaller sub-chunks"""
        sub_chunks = []
        current_start = 0

        while current_start < len(proc_lines):
            current_end = min(current_start + self.max_chunk_lines, len(proc_lines))
            chunk_lines = proc_lines[current_start:current_end]
            chunk_content = '\n'.join(chunk_lines)

            sub_chunk_num = len(sub_chunks) + 1
            sub_chunks.append(CodeChunk(
                content=chunk_content,
                start_line=start_line + current_start,
                end_line=start_line + current_end - 1,
                chunk_type=proc_type,
                name=f"{proc_name}_part{sub_chunk_num}"
            ))

            current_start = current_end

        return sub_chunks

    def get_chunk_summary(self, chunks: List[CodeChunk]) -> str:
        """Get a human-readable summary of the chunks"""
        summary = []
        summary.append(f"Total chunks: {len(chunks)}")
        summary.append(f"Total lines: {sum(chunk.line_count for chunk in chunks)}")
        summary.append("\nChunk breakdown:")

        for i, chunk in enumerate(chunks):
            summary.append(
                f"  [{i+1}] {chunk.chunk_type.capitalize()}: {chunk.name} "
                f"(lines {chunk.start_line+1}-{chunk.end_line+1}, "
                f"{chunk.line_count} lines)"
            )

        return '\n'.join(summary)


class AdaptiveVFPChunker(VFPChunker):
    """
    Hardware-aware VFP chunker that adapts chunk size based on file size.

    For 24GB VRAM systems:
    - Small files (<100 lines): Process whole file (no chunking)
    - Medium files (100-500 lines): 100 line chunks
    - Large files (500-2000 lines): 150 line chunks
    - Very large files (>2000 lines): 200 line chunks
    """

    def __init__(self, config: dict = None):
        """Initialize adaptive chunker with hardware-aware settings"""
        if config is None:
            # Default settings for 24GB VRAM
            self.chunk_small_file = 100
            self.chunk_medium_file = 150
            self.chunk_large_file = 200
        else:
            # Read from config
            processing = config.get('processing', {})
            self.chunk_small_file = processing.get('adaptive_chunk_small_file', 100)
            self.chunk_medium_file = processing.get('adaptive_chunk_medium_file', 150)
            self.chunk_large_file = processing.get('adaptive_chunk_large_file', 200)

        # Initialize with default
        super().__init__(max_chunk_lines=self.chunk_medium_file)

    def chunk_code(self, vfp_code: str) -> List[CodeChunk]:
        """Adaptively chunk code based on file size"""
        total_lines = len(vfp_code.split('\n'))

        # Adapt chunk size based on file size
        if total_lines < 100:
            self.max_chunk_lines = total_lines + 1  # Process whole file
        elif total_lines < 500:
            self.max_chunk_lines = self.chunk_small_file
        elif total_lines < 2000:
            self.max_chunk_lines = self.chunk_medium_file
        else:
            self.max_chunk_lines = self.chunk_large_file

        # Use parent class chunking logic
        return super().chunk_code(vfp_code)

    def get_chunk_summary(self, chunks: List[CodeChunk]) -> str:
        """Get summary with adaptive chunking info"""
        summary = super().get_chunk_summary(chunks)
        total_lines = sum(chunk.line_count for chunk in chunks)

        adaptive_info = [
            "",
            "Adaptive Chunking Settings:",
            f"  File size: {total_lines} lines",
            f"  Chunk size used: {self.max_chunk_lines} lines/chunk",
            f"  Thresholds: <100=whole, 100-500={self.chunk_small_file}, "
            f"500-2000={self.chunk_medium_file}, >2000={self.chunk_large_file}"
        ]

        return summary + '\n' + '\n'.join(adaptive_info)


# ===== VFP HANDLER CLASS =====

class VFPHandler(LanguageHandler):
    """
    Language handler for Visual FoxPro (VFP).

    Encapsulates all VFP-specific logic including:
    - File extensions and skip patterns
    - Adaptive chunking strategy
    - Pydantic models for structured output
    - LLM prompts (system, Phase 1, Phase 2)
    - Comment validation
    """

    def __init__(self, config: dict = None):
        """Initialize VFP handler with optional configuration"""
        self.config = config or {}

    def get_language_name(self) -> str:
        return "vfp"

    def get_file_extensions(self) -> List[str]:
        return ['.prg', '.spr', '.sc2', '.fr2', '.mn2', '.lb2']

    def get_skip_patterns(self) -> List[str]:
        return ['_commented']

    def create_chunker(self, config: dict):
        return AdaptiveVFPChunker(config)

    def get_pydantic_models(self) -> Dict[str, Type[BaseModel]]:
        return {
            'FileAnalysis': FileAnalysis,
            'ChunkComments': ChunkComments,
            'CommentBlock': CommentBlock,
            'FileHeaderComment': FileHeaderComment
        }

    def get_system_prompt(self) -> str:
        """Return VFP system prompt for general commenting"""
        return """You are an expert Visual FoxPro (VFP) code analyst and documentation specialist.

🚨 CRITICAL REQUIREMENTS 🚨
1. You MUST return the EXACT original code in the 'original_code_preserved' field
2. DO NOT modify, refactor, or change ANY code
3. DO NOT add, remove, or alter ANY code lines
4. ONLY generate comment text in the structured format

Your task is to analyze VFP code and generate:
1. A structured file header with purpose and dependencies
2. Inline comments explaining code sections

Return data in the exact Pydantic model structure specified."""

    def get_phase1_prompt(self, code: str, filename: str, relative_path: str) -> str:
        """Generate Phase 1 (structure analysis) prompt"""
        code_for_analysis, was_sampled = self.extract_code_sample(code)
        sampling_note = "\n⚠️ Note: This is a SAMPLE of a large file. Focus on identifying structure and patterns." if was_sampled else ""

        return f"""Analyze the structure of this VFP file.

File: {filename}
Lines: {len(code.splitlines())}{sampling_note}

Return a FileAnalysis object with these fields:
1. filename: "{filename}"
2. file_overview: 2-3 sentence overview of what this file does
3. procedures: List of all PROCEDURE and FUNCTION definitions, each with:
   - name: procedure/function name
   - line_number: starting line (count from 1)
   - description: brief description
4. dependencies: List of tables (SELECT, UPDATE, USE), variables, external files
5. total_lines: {len(code.splitlines())}

VFP Code:
```vfp
{code_for_analysis}
```

Return structured FileAnalysis object with ALL fields filled."""

    def get_phase2_prompt(
        self,
        chunk: str,
        chunk_name: str,
        chunk_type: str,
        file_context,
        filename: str,
        relative_path: str
    ) -> str:
        """Generate Phase 2 (chunk commenting) prompt"""
        line_count = len(chunk.split('\n'))

        # Extract dependencies for display
        dep_str = ', '.join(file_context.dependencies[:5]) if file_context.dependencies else 'None'

        return f"""Generate comments for this VFP code section.

**FILE CONTEXT (for your understanding):**
File: {filename}
Location: {relative_path}
File Overview: {file_context.file_overview}
Dependencies: {dep_str}

**CODE SECTION TO ANALYZE:**
Type: {chunk_type}
Name: {chunk_name}
Lines: {line_count}

Return JSON with TWO fields:

1. "file_header" (object):
   - "filename": "{filename}"
   - "location": "{relative_path}"
   - "purpose": [List of strings describing what THIS section does]
   - "dependencies": [List of tables/cursors/files used in THIS section]
   - "key_functions": []

2. "inline_comments" (array of objects):
   - Each object has:
     - "insert_before_line" (number): Line number where comment goes
     - "comment_lines" (array of strings): VFP comments starting with *
     - "context" (string): Brief note about what this explains

**VFP Code Section to analyze:**
```vfp
{chunk}
```

Return ONLY valid JSON with "file_header" and "inline_comments".
DO NOT return the code itself."""

    def validate_comment_syntax(self, comment: str, comment_type: str = None) -> bool:
        """Validate that comment follows VFP syntax (* or &&)"""
        stripped = comment.strip()
        return stripped.startswith('*') or '&&' in stripped

    def format_file_header(self, header_data: dict) -> str:
        """Format VFP file header comment"""
        header = FileHeaderComment(**header_data)
        return header.to_vfp_comment()

    def extract_code_sample(self, code: str, max_lines: int = 1000) -> Tuple[str, bool]:
        """
        Create representative sample of VFP code for Phase 1 analysis.

        For large files (>1000 lines), extracts:
        - First 500 lines
        - All PROCEDURE/FUNCTION signatures
        - Last 200 lines

        Args:
            code: Full VFP code
            max_lines: Threshold for sampling (default 1000 for 24GB VRAM)

        Returns:
            Tuple of (sampled_code, was_sampled)
        """
        lines = code.splitlines()
        total_lines = len(lines)

        # If file is small enough, return entire file
        if total_lines <= max_lines:
            return code, False

        # Extract procedure/function signatures
        proc_pattern = re.compile(r'^\s*(PROCEDURE|FUNCTION)\s+(\w+)', re.IGNORECASE)
        procedure_lines = []

        for i, line in enumerate(lines, 1):
            match = proc_pattern.match(line)
            if match:
                procedure_lines.append(f"* Line {i}: {line.strip()}")

        # Build representative sample
        first_lines = 500
        last_lines = 200

        sample_parts = [
            "* ===== CODE SAMPLE FOR ANALYSIS (Not complete file) =====",
            f"* Total Lines: {total_lines}",
            f"* Sample includes: First {first_lines} lines + Last {last_lines} lines + All {len(procedure_lines)} signatures",
            "* ==========================================================",
            "",
            f"* ----- FIRST {first_lines} LINES -----",
            *lines[:first_lines],
            "",
            "* ----- ALL PROCEDURE/FUNCTION SIGNATURES -----",
            *procedure_lines,
            "",
            f"* ----- LAST {last_lines} LINES -----",
            *lines[-last_lines:],
            "",
            "* ===== END OF SAMPLE ====="
        ]

        sampled_code = '\n'.join(sample_parts)
        return sampled_code, True

    def preprocess_for_llm(self, code: str, config: dict = None) -> str:
        """
        Preprocess VFP code to avoid llama.cpp tokenizer issues with OLE objects.

        VFP files often contain embedded base64-encoded binary data in two formats:
        1. Form files (.sc2): ActiveX/OLE controls as Value="base64..."
        2. Report/Label files (.fr2, .lb2): Printer config as <![CDATA[base64...]]>

        These long repetitive sequences (4KB-10KB) trigger a documented bug in
        llama.cpp's RE2 regex tokenizer causing "Failed to process regex" errors.

        This method strips both patterns before sending to LLM, replacing them
        with placeholders. The original file is never modified - stripping only
        happens in memory for LLM processing.

        See: https://github.com/ggml-org/llama.cpp/issues/9715

        Args:
            code: VFP source code (potentially with base64 blobs)
            config: Optional config with 'strip_ole_objects' and 'ole_strip_threshold'

        Returns:
            str: Preprocessed code with base64 blobs replaced by placeholders
        """
        # Check if stripping is enabled (default: enabled)
        if config:
            strip_enabled = config.get('strip_ole_objects', True)
            threshold = config.get('ole_strip_threshold', 1000)
        else:
            strip_enabled = True
            threshold = 1000

        if not strip_enabled:
            return code

        cleaned_code = code
        total_bytes_removed = 0
        total_blobs_found = 0

        # Pattern 1: Value="[long base64 string]" (for .sc2 form files)
        # Matches base64 characters (A-Z, a-z, 0-9, +, /, =) of length >= threshold
        pattern1 = r'(Value\s*=\s*)"([A-Za-z0-9+/=]{' + str(threshold) + r',})"'
        replacement1 = r'\1"[OLE_BINARY_DATA_REMOVED_FOR_LLM_PROCESSING]"'

        blobs_pattern1 = re.findall(pattern1, cleaned_code)
        if blobs_pattern1:
            bytes_removed_p1 = sum(len(match[1]) for match in blobs_pattern1)
            cleaned_code = re.sub(pattern1, replacement1, cleaned_code)
            total_bytes_removed += bytes_removed_p1
            total_blobs_found += len(blobs_pattern1)

        # Pattern 2: <![CDATA[[long base64 string]]]> (for .fr2/.lb2 report/label files)
        # Matches CDATA sections with base64 content of length >= threshold
        pattern2 = r'(<!\[CDATA\[)([A-Za-z0-9+/=]{' + str(threshold) + r',})(\]\]>)'
        replacement2 = r'\1[BINARY_DATA_REMOVED_FOR_LLM_PROCESSING]\3'

        blobs_pattern2 = re.findall(pattern2, cleaned_code)
        if blobs_pattern2:
            bytes_removed_p2 = sum(len(match[1]) for match in blobs_pattern2)
            cleaned_code = re.sub(pattern2, replacement2, cleaned_code)
            total_bytes_removed += bytes_removed_p2
            total_blobs_found += len(blobs_pattern2)

        # Log if stripping occurred
        if cleaned_code != code:
            import logging
            logger = logging.getLogger('vfp_handler')
            logger.info(f"Stripped {total_blobs_found} base64 blob(s) containing {total_bytes_removed:,} bytes of data")

        return cleaned_code
