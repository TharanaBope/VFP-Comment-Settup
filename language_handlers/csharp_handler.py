"""
C# Language Handler

This module contains all C#-specific logic for the code commenting system:
- Pydantic models for structured LLM output
- Adaptive chunking strategy (class/method/namespace aware)
- LLM prompts (system, Phase 1, Phase 2)
- Comment syntax validation (XML docs, single-line, multi-line)
- File header formatting

Target Projects:
- eRx: Electronic prescription management
- MHR: Medical health records
"""

import re
from typing import List, Dict, Type, Optional, Tuple, Literal
from dataclasses import dataclass
from pydantic import BaseModel, Field, field_validator

from .base_handler import LanguageHandler


# ===== C# PYDANTIC MODELS =====

class CSharpMethodInfo(BaseModel):
    """Information about a C# method"""
    name: str = Field(description="Method name")
    return_type: str = Field(description="Return type (void, Task, string, etc.)")
    parameters: List[str] = Field(
        default_factory=list,
        description="Parameter declarations with types"
    )
    access_modifier: str = Field(
        default="private",
        description="public, private, protected, internal"
    )
    is_async: bool = Field(default=False, description="Is async method")
    is_static: bool = Field(default=False, description="Is static method")
    line_number: int = Field(description="Line where method is defined")
    description: str = Field(default="", description="Brief method description")


class CSharpPropertyInfo(BaseModel):
    """Information about a C# property"""
    name: str = Field(description="Property name")
    property_type: str = Field(description="Property data type")
    has_getter: bool = Field(default=True)
    has_setter: bool = Field(default=True)
    access_modifier: str = Field(default="public")
    line_number: int = Field(description="Line where property is defined")
    description: str = Field(default="", description="Brief property description")


class CSharpClassInfo(BaseModel):
    """Information about a C# class/interface/struct/enum"""
    name: str = Field(description="Class name")
    class_type: Literal["class", "interface", "struct", "enum"] = Field(
        default="class",
        description="Type of class definition"
    )
    access_modifier: str = Field(default="public", description="Access level")
    base_classes: List[str] = Field(
        default_factory=list,
        description="Inherited classes and implemented interfaces"
    )
    line_number: int = Field(description="Line where class is defined")
    description: str = Field(default="", description="Brief class description")


class CSharpFileAnalysis(BaseModel):
    """
    Phase 1: High-level C# file analysis

    This model extracts structural information from C# files including
    classes, methods, Entity Framework entities, and design patterns.
    """
    file_overview: str = Field(description="Overall file purpose (2-3 sentences)")

    namespace: Optional[str] = Field(
        default=None,
        description="Primary namespace"
    )

    using_statements: List[str] = Field(
        default_factory=list,
        description="Using directives (e.g., System.Linq, Microsoft.EntityFrameworkCore)"
    )

    classes: List[CSharpClassInfo] = Field(
        default_factory=list,
        description="Classes, interfaces, structs, enums in the file"
    )

    methods: List[CSharpMethodInfo] = Field(
        default_factory=list,
        description="All methods across all classes"
    )

    properties: List[CSharpPropertyInfo] = Field(
        default_factory=list,
        description="Properties across all classes"
    )

    database_entities: List[str] = Field(
        default_factory=list,
        description="Entity Framework entities (DbSet<Entity>)"
    )

    external_dependencies: List[str] = Field(
        default_factory=list,
        description="External services, APIs, libraries referenced"
    )

    design_patterns: List[str] = Field(
        default_factory=list,
        description="Design patterns used (Repository, Factory, Singleton, etc.)"
    )

    key_business_logic: List[str] = Field(
        default_factory=list,
        description="Main business operations (3-5 items)"
    )


class CSharpFileHeaderComment(BaseModel):
    """
    C# file header comment

    Standard header format for C# files in eRx/MHR projects.
    """
    file_name: str = Field(description="Name of the C# file")
    project_name: Literal["eRx", "MHR", "Unknown"] = Field(
        default="Unknown",
        description="Project name (eRx or MHR)"
    )
    purpose: str = Field(description="What this file does")
    dependencies: List[str] = Field(
        default_factory=list,
        description="External dependencies and services"
    )
    database_entities: List[str] = Field(
        default_factory=list,
        description="Database entities used"
    )
    key_classes: List[str] = Field(
        default_factory=list,
        description="Main classes in the file"
    )

    def to_csharp_comment(self) -> str:
        """Convert to C# file header comment format"""
        lines = [
            "// =====================================================",
            f"// File: {self.file_name}",
            f"// Project: {self.project_name}",
            f"// Purpose: {self.purpose}",
        ]

        if self.dependencies:
            lines.append(f"// Dependencies: {', '.join(self.dependencies)}")

        if self.database_entities:
            lines.append(f"// Database: {', '.join(self.database_entities)}")

        if self.key_classes:
            lines.append(f"// Key Classes: {', '.join(self.key_classes)}")

        lines.append("// =====================================================")
        lines.append("")

        return '\n'.join(lines)


class CSharpCommentBlock(BaseModel):
    """
    Individual comment block for C#

    Supports three comment types:
    - xml_doc: XML documentation (///)
    - single_line: Single-line comments (//)
    - multi_line: Multi-line comments (/* */)
    """
    insert_before_line: int = Field(
        ...,
        ge=1,
        description="Line number to insert before (1-indexed)"
    )
    comment_lines: List[str] = Field(
        ...,
        min_length=1,
        description="Comment text lines"
    )
    comment_type: Literal["xml_doc", "single_line", "multi_line"] = Field(
        description="Type of comment format"
    )
    context: str = Field(
        description="Explanation of why this comment is needed"
    )

    @field_validator('comment_lines')
    @classmethod
    def validate_csharp_syntax(cls, v: List[str], info):
        """Validate C# comment syntax based on comment type"""
        comment_type = info.data.get('comment_type')
        validated = []

        for line in v:
            stripped = line.strip()
            if not stripped:
                continue

            # Validate based on comment type
            if comment_type == "xml_doc":
                # XML doc comments must start with ///
                if not (stripped.startswith('///') or stripped.startswith('<')):
                    # Auto-fix: add /// prefix
                    if not stripped.startswith('///'):
                        stripped = f"/// {stripped}"
            elif comment_type == "single_line":
                # Single-line comments must start with //
                if not stripped.startswith('//'):
                    stripped = f"// {stripped}"
            elif comment_type == "multi_line":
                # Multi-line comments use /* */ format
                # Note: Opening/closing handled in the list as a whole
                pass

            validated.append(stripped)

        return validated


class CSharpChunkComments(BaseModel):
    """
    Comments for C# code chunk (Phase 2 output)

    Contains file header and inline comments to be inserted into code.
    """
    file_header: CSharpFileHeaderComment = Field(
        description="File header comment"
    )
    inline_comments: List[CSharpCommentBlock] = Field(
        default_factory=list,
        description="Comment blocks to insert at specific line numbers"
    )

    def insert_comments_into_code(self, original_code: str, include_header: bool = False) -> str:
        """
        Insert comments into original code WITHOUT modifying the code.

        Args:
            original_code: The original C# code (100% preserved)
            include_header: Whether to include file header comment

        Returns:
            Original code with comments inserted at specified positions
        """
        result_lines = []

        # Add file header if requested
        if include_header:
            result_lines.append(self.file_header.to_csharp_comment())

        # Split original code into lines
        code_lines = original_code.split('\n')

        # Sort inline comments by line number
        sorted_comments = sorted(self.inline_comments, key=lambda c: c.insert_before_line)

        comment_index = 0

        for line_num, code_line in enumerate(code_lines, start=1):
            # Insert any comments that belong before this line
            while (comment_index < len(sorted_comments) and
                   sorted_comments[comment_index].insert_before_line == line_num):

                comment_block = sorted_comments[comment_index]

                # Add blank line before comment for readability
                if line_num > 1 and result_lines and result_lines[-1].strip():
                    result_lines.append("")

                # Add comment lines
                result_lines.extend(comment_block.comment_lines)

                comment_index += 1

            # Add the original code line (UNMODIFIED)
            result_lines.append(code_line)

        return '\n'.join(result_lines)


# ===== C# CHUNKING LOGIC =====

@dataclass
class CodeChunk:
    """Represents a chunk of C# code with metadata"""
    content: str
    start_line: int
    end_line: int
    chunk_type: str  # 'class', 'method', 'namespace', 'toplevel'
    name: str

    @property
    def line_count(self):
        return len(self.content.split('\n'))


class AdaptiveCSharpChunker:
    """
    C#-aware chunker that respects class/method/namespace boundaries.

    Features:
    - Identifies namespace, class, interface, struct, enum boundaries
    - Detects method boundaries
    - Respects #region/#endregion directives
    - Adaptive chunk sizing based on file size
    """

    def __init__(self, config: dict = None):
        """Initialize adaptive C# chunker"""
        if config is None:
            # Default settings for 24GB VRAM
            self.chunk_small_file = 100
            self.chunk_medium_file = 150
            self.chunk_large_file = 200
        else:
            processing = config.get('processing', {})
            self.chunk_small_file = processing.get('adaptive_chunk_small_file', 100)
            self.chunk_medium_file = processing.get('adaptive_chunk_medium_file', 150)
            self.chunk_large_file = processing.get('adaptive_chunk_large_file', 200)

        # Regex patterns for C# boundaries
        self.namespace_pattern = re.compile(
            r'^\s*namespace\s+([\w.]+)',
            re.IGNORECASE
        )

        self.class_pattern = re.compile(
            r'^\s*(?:public|private|internal|protected)?\s*(?:static|abstract|sealed|partial)?\s*'
            r'(class|interface|struct|enum)\s+(\w+)',
            re.IGNORECASE
        )

        self.method_pattern = re.compile(
            r'^\s*(?:public|private|internal|protected)?\s*(?:static|virtual|override|async)?\s+'
            r'[\w<>]+\s+(\w+)\s*\(',
            re.IGNORECASE
        )

        self.region_start_pattern = re.compile(r'^\s*#region\s+(.+)', re.IGNORECASE)
        self.region_end_pattern = re.compile(r'^\s*#endregion', re.IGNORECASE)

    def chunk_code(self, csharp_code: str) -> List[CodeChunk]:
        """
        Split C# code at class/method/namespace boundaries.

        Args:
            csharp_code: The complete C# code to chunk

        Returns:
            List of CodeChunk objects optimized for file size
        """
        lines = csharp_code.split('\n')
        total_lines = len(lines)

        # Determine chunk size based on file size (adaptive)
        if total_lines < 100:
            max_chunk_lines = total_lines + 1  # Whole file
        elif total_lines < 500:
            max_chunk_lines = self.chunk_small_file
        elif total_lines < 2000:
            max_chunk_lines = self.chunk_medium_file
        else:
            max_chunk_lines = self.chunk_large_file

        # Find all structural boundaries
        boundaries = self._find_csharp_boundaries(lines)

        # Create chunks respecting boundaries
        chunks = self._create_chunks_from_boundaries(
            lines, boundaries, max_chunk_lines
        )

        return chunks

    def _find_csharp_boundaries(self, lines: List[str]) -> dict:
        """
        Find all structural boundaries in C# code.

        Returns:
            Dictionary with namespaces, classes, methods, regions
        """
        boundaries = {
            'namespaces': [],
            'classes': [],
            'methods': [],
            'regions': []
        }

        # Track braces for determining block ends
        brace_stack = []

        for i, line in enumerate(lines):
            # Namespace detection
            ns_match = self.namespace_pattern.match(line)
            if ns_match:
                boundaries['namespaces'].append({
                    'start': i,
                    'name': ns_match.group(1),
                    'level': len(brace_stack)
                })

            # Class/interface/struct/enum detection
            class_match = self.class_pattern.match(line)
            if class_match:
                boundaries['classes'].append({
                    'start': i,
                    'type': class_match.group(1),
                    'name': class_match.group(2),
                    'level': len(brace_stack)
                })

            # Method detection
            method_match = self.method_pattern.match(line)
            if method_match:
                boundaries['methods'].append({
                    'start': i,
                    'name': method_match.group(1),
                    'level': len(brace_stack)
                })

            # Region detection
            region_start = self.region_start_pattern.match(line)
            if region_start:
                boundaries['regions'].append({
                    'start': i,
                    'name': region_start.group(1).strip(),
                    'level': len(brace_stack)
                })

            # Track braces
            brace_stack.extend([i] * line.count('{'))
            brace_stack = brace_stack[:len(brace_stack) - line.count('}')]

        return boundaries

    def _create_chunks_from_boundaries(
        self,
        lines: List[str],
        boundaries: dict,
        target_size: int
    ) -> List[CodeChunk]:
        """
        Create chunks that respect C# structural boundaries.

        Priority: namespace > class > method > target_size
        """
        chunks = []

        # Simplified implementation: Split at class boundaries
        if boundaries['classes']:
            current_start = 0

            for class_info in boundaries['classes']:
                class_start = class_info['start']

                # Add chunk before class (using statements, namespace opening)
                if class_start > current_start:
                    if class_start - current_start > 0:
                        chunks.append(CodeChunk(
                            content='\n'.join(lines[current_start:class_start]),
                            start_line=current_start,
                            end_line=class_start - 1,
                            chunk_type='toplevel',
                            name='toplevel'
                        ))

                current_start = class_start

                # Determine class end (simplified: use target_size)
                class_end = min(class_start + target_size, len(lines))

                chunks.append(CodeChunk(
                    content='\n'.join(lines[class_start:class_end]),
                    start_line=class_start,
                    end_line=class_end - 1,
                    chunk_type='class',
                    name=class_info['name']
                ))

                current_start = class_end

            # Add remaining lines
            if current_start < len(lines):
                chunks.append(CodeChunk(
                    content='\n'.join(lines[current_start:]),
                    start_line=current_start,
                    end_line=len(lines) - 1,
                    chunk_type='toplevel',
                    name='toplevel_end'
                ))
        else:
            # No classes - split by target_size
            for i in range(0, len(lines), target_size):
                end = min(i + target_size, len(lines))
                chunks.append(CodeChunk(
                    content='\n'.join(lines[i:end]),
                    start_line=i,
                    end_line=end - 1,
                    chunk_type='toplevel',
                    name=f'chunk_{i//target_size + 1}'
                ))

        return chunks

    def get_chunk_summary(self, chunks: List[CodeChunk]) -> str:
        """Get human-readable summary of chunks"""
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

        total_lines = sum(chunk.line_count for chunk in chunks)
        summary.append("")
        summary.append("Adaptive Chunking Settings:")
        summary.append(f"  File size: {total_lines} lines")

        return '\n'.join(summary)


# ===== C# HANDLER CLASS =====

class CSharpHandler(LanguageHandler):
    """
    Language handler for C#.

    Encapsulates all C#-specific logic for eRx and MHR projects.
    """

    def __init__(self, config: dict = None):
        """Initialize C# handler with optional configuration"""
        self.config = config or {}

    def get_language_name(self) -> str:
        return "csharp"

    def get_file_extensions(self) -> List[str]:
        return ['.cs']

    def get_skip_patterns(self) -> List[str]:
        """
        Return comprehensive list of C# files/folders to skip.

        Based on eRx Project Analysis specification:
        - Excludes auto-generated files (.Designer.cs, .g.cs, .g.i.cs)
        - Excludes assembly metadata (AssemblyInfo.cs, AssemblyAttributes.cs)
        - Excludes build artifacts (bin/, obj/, Debug/, Release/)
        - Excludes IDE settings (.vs/)
        - Excludes package folders and test results
        - Excludes temporary generated files
        - Excludes already-commented files
        """
        return [
            # Already commented files
            '_commented',

            # Auto-generated designer files
            '.Designer.cs',

            # Auto-generated code files
            '.g.cs',           # WPF/UWP generated files (e.g., App.g.cs)
            '.g.i.cs',         # Auto-generated interop files

            # Assembly metadata
            'AssemblyInfo.cs',
            'AssemblyAttributes.cs',

            # Global usings (C# 10+)
            'GlobalUsings.g.cs',

            # Temporary files (prefix pattern)
            'TemporaryGeneratedFile_',

            # Build output folders
            'bin/',
            'obj/',
            'Debug/',
            'Release/',

            # IDE and tooling folders
            '.vs/',

            # Package folders
            'packages/',

            # Test output
            'TestResults/',

            # JavaScript dependencies (if any in hybrid projects)
            'node_modules/'
        ]

    def create_chunker(self, config: dict):
        return AdaptiveCSharpChunker(config)

    def get_pydantic_models(self) -> Dict[str, Type[BaseModel]]:
        return {
            'FileAnalysis': CSharpFileAnalysis,
            'ChunkComments': CSharpChunkComments,
            'CommentBlock': CSharpCommentBlock,
            'FileHeaderComment': CSharpFileHeaderComment
        }

    def get_system_prompt(self) -> str:
        """Return C# system prompt"""
        return """You are an expert C# developer tasked with adding comprehensive XML documentation to C# code.

🚨 CRITICAL RULES 🚨
1. DO NOT CHANGE ANY ORIGINAL CODE - ONLY ADD COMMENTS
2. Use C# documentation standards:
   - XML documentation (///) for classes, methods, properties
   - Use proper XML tags: <summary>, <param>, <returns>, <exception>, <remarks>
   - Single-line comments (//) for inline explanations
   - Multi-line comments (/* */) for complex logic blocks
3. Document:
   - All public and protected members
   - LINQ queries and lambda expressions
   - Async/await patterns
   - Entity Framework operations
   - Dependency injection
   - Business logic and validation
4. Reference design patterns (Repository, Factory, Singleton, etc.)
5. Note database operations and entity relationships

OUTPUT FORMAT:
- Return ONLY comment blocks with exact line insertion points
- Do NOT duplicate the original code
- Use proper XML documentation for methods and classes"""

    def get_phase1_prompt(self, code: str, filename: str, relative_path: str) -> str:
        """Generate Phase 1 (structure analysis) prompt for C#"""
        code_for_analysis, was_sampled = self.extract_code_sample(code)
        sampling_note = "\n⚠️ Note: This is a SAMPLE of a large file." if was_sampled else ""

        # Try to detect project (eRx or MHR) from path
        project = "eRx" if "erx" in relative_path.lower() else "MHR" if "mhr" in relative_path.lower() else "Unknown"

        return f"""Analyze this C# file and extract high-level information.

File: {filename}
Project: {project}
Location: {relative_path}
Lines: {len(code.splitlines())}{sampling_note}

Provide:
1. file_overview: Overall purpose (2-3 sentences)
2. namespace: Primary namespace
3. using_statements: All using directives
4. classes: All classes/interfaces/structs/enums with:
   - name, class_type, access_modifier, base_classes, line_number, description
5. methods: All methods with:
   - name, return_type, parameters, access_modifier, is_async, is_static, line_number, description
6. properties: Key properties
7. database_entities: Entity Framework entities (DbSet<T>)
8. external_dependencies: Services, APIs, libraries
9. design_patterns: Repository, Factory, DI, etc.
10. key_business_logic: Main operations (3-5 items)

C# Code:
```csharp
{code_for_analysis}
```

Return structured CSharpFileAnalysis object."""

    def get_phase2_prompt(
        self,
        chunk: str,
        chunk_name: str,
        chunk_type: str,
        file_context,
        filename: str,
        relative_path: str
    ) -> str:
        """Generate Phase 2 (chunk commenting) prompt for C#"""
        line_count = len(chunk.split('\n'))

        # Add line numbers to chunk for easier reference
        chunk_lines = chunk.split('\n')
        numbered_chunk = '\n'.join([f"{i+1:4d} | {line}" for i, line in enumerate(chunk_lines)])

        # Build context summary
        context_summary = f"""FILE CONTEXT:
- Purpose: {file_context.file_overview}
- Namespace: {file_context.namespace}
- Classes: {', '.join([c.name for c in file_context.classes]) if file_context.classes else 'None'}
- Entities: {', '.join(file_context.database_entities) if file_context.database_entities else 'None'}
- Patterns: {', '.join(file_context.design_patterns) if file_context.design_patterns else 'None'}"""

        # Detect project
        project = "eRx" if "erx" in relative_path.lower() else "MHR" if "mhr" in relative_path.lower() else "Unknown"

        return f"""Generate C# XML documentation for this code chunk.

{context_summary}

CHUNK TO DOCUMENT:
Type: {chunk_type}
Name: {chunk_name}
Lines: {line_count}

CODE WITH LINE NUMBERS (use these line numbers for insert_before_line):
```csharp
{numbered_chunk}
```

Add comprehensive C# documentation:

1. Classes/Interfaces: XML documentation with <summary> and <remarks>
2. Methods: Complete XML documentation
   - <summary>Method purpose</summary>
   - <param name="paramName">Parameter description</param>
   - <returns>Return value description</returns>
   - <exception cref="ExceptionType">When thrown</exception>
3. Properties: XML documentation with <summary> and <value>
4. CRITICAL: Add inline comments (//) throughout the code explaining:
   - Complex conditionals (if/switch statements with business logic)
   - LINQ queries and lambda expressions
   - Async/await operations
   - Entity Framework queries (DbContext, DbSet operations)
   - Business rules and validation logic
   - API calls and external service interactions
   - Loop logic and iterations
   - String manipulations and transformations
   - Error handling and exception cases
   - Variable assignments with non-obvious purposes
   - Mathematical calculations or algorithms
   AIM FOR: At least one inline comment every 5-10 lines of code
5. Database Operations: Document DbContext usage, entity queries, transactions
6. Design Patterns: Note Repository, Factory, Singleton, DI usage
7. File I/O Operations: Document file reads, writes, path manipulations
8. Configuration Loading: Document settings and configuration access

Return JSON with two fields:
1. "file_header": {{
     "file_name": "{filename}",
     "project_name": "{project}",
     "purpose": "...",
     "dependencies": [...],
     "database_entities": [...],
     "key_classes": [...]
   }}
2. "inline_comments": [
     {{
       "insert_before_line": line_number,
       "comment_lines": ["/// <summary>...", "/// </summary>"],
       "comment_type": "xml_doc" | "single_line" | "multi_line",
       "context": "Explanation"
     }}
   ]

IMPORTANT LINE NUMBERING RULES:
- Line numbers are 1-based (first line = 1)
- For XML documentation (///) before methods/classes: Place IMMEDIATELY before the declaration
- For inline comments (//): Place BEFORE the code line being explained
- Example: To comment a method starting at line 15, use "insert_before_line": 15
- For code inside a method at line 20, use "insert_before_line": 20
- ALWAYS verify line numbers match the actual code lines in the chunk above

DO NOT return the code itself."""

    def validate_comment_syntax(self, comment: str, comment_type: str = None) -> bool:
        """Validate C# comment syntax"""
        stripped = comment.strip()

        if comment_type == "xml_doc":
            return stripped.startswith('///')
        elif comment_type == "single_line":
            return stripped.startswith('//')
        elif comment_type == "multi_line":
            return stripped.startswith('/*') or stripped.endswith('*/') or '*' in stripped
        else:
            # Generic validation: any C# comment format
            return stripped.startswith('//') or stripped.startswith('/*') or '*' in stripped

    def validate_chunk_comments_syntax(self, chunk_comments) -> List[str]:
        """
        Validate all comments in a chunk use correct C# syntax.

        Args:
            chunk_comments: CSharpChunkComments object with file_header and inline_comments

        Returns:
            List of validation issues (empty if all valid)
        """
        issues = []

        # Check file header - convert to string and validate each line
        header_text = chunk_comments.file_header.to_csharp_comment()
        for line in header_text.split('\n'):
            if line.strip() and not line.strip().startswith('//'):
                issues.append(f"Header line missing //: {line[:50]}")

        # Check inline comments
        for idx, comment_block in enumerate(chunk_comments.inline_comments):
            for line in comment_block.comment_lines:
                stripped = line.strip()
                if stripped:
                    # C# comments should start with //, ///, or /*
                    if not (stripped.startswith('//') or stripped.startswith('/*') or '*' in stripped):
                        issues.append(f"Inline comment {idx} missing C# syntax: {line[:50]}")

        return issues

    def format_file_header(self, header_data: dict) -> str:
        """Format C# file header comment"""
        header = CSharpFileHeaderComment(**header_data)
        return header.to_csharp_comment()

    def extract_code_sample(self, code: str, max_lines: int = 1000) -> Tuple[str, bool]:
        """
        Create representative sample of C# code for Phase 1 analysis.

        For large files (>1000 lines), extracts:
        - First 500 lines (using statements, namespace, class declarations)
        - All class/interface/enum signatures
        - All method signatures
        - Last 200 lines

        Args:
            code: Full C# code
            max_lines: Threshold for sampling (default 1000 for 24GB VRAM)

        Returns:
            Tuple of (sampled_code, was_sampled)
        """
        lines = code.splitlines()
        total_lines = len(lines)

        # If file is small enough, return entire file
        if total_lines <= max_lines:
            return code, False

        # Extract class/method signatures
        class_pattern = re.compile(
            r'^\s*(?:public|private|internal|protected)?\s*(?:static|abstract|sealed|partial)?\s*'
            r'(class|interface|struct|enum)\s+(\w+)',
            re.IGNORECASE
        )

        method_pattern = re.compile(
            r'^\s*(?:public|private|internal|protected)?\s*(?:static|virtual|override|async)?\s+'
            r'[\w<>]+\s+(\w+)\s*\(',
            re.IGNORECASE
        )

        signatures = []

        for i, line in enumerate(lines, 1):
            class_match = class_pattern.match(line)
            method_match = method_pattern.match(line)

            if class_match:
                signatures.append(f"// Line {i}: {line.strip()}")
            elif method_match:
                signatures.append(f"// Line {i}: {line.strip()}")

        # Build representative sample
        first_lines = 500
        last_lines = 200

        sample_parts = [
            "// ===== CODE SAMPLE FOR ANALYSIS (Not complete file) =====",
            f"// Total Lines: {total_lines}",
            f"// Sample includes: First {first_lines} lines + Last {last_lines} lines + All signatures",
            "// ==========================================================",
            "",
            f"// ----- FIRST {first_lines} LINES -----",
            *lines[:first_lines],
            "",
            "// ----- ALL CLASS/METHOD SIGNATURES -----",
            *signatures,
            "",
            f"// ----- LAST {last_lines} LINES -----",
            *lines[-last_lines:],
            "",
            "// ===== END OF SAMPLE ====="
        ]

        sampled_code = '\n'.join(sample_parts)
        return sampled_code, True

    def allows_duplicate_insertion_points(self) -> bool:
        """
        C# allows multiple comment blocks at the same insertion point.

        This is necessary for C# documentation patterns where you might have:
        - XML documentation (///) for a method
        - Plus an inline comment (//) explaining a specific aspect

        Both comments can be inserted before the same line.

        Returns:
            bool: True (C# allows duplicate insertion points)
        """
        return True
