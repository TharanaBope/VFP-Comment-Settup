"""
Two-Phase VFP Comment Processor
================================
Implements a two-phase approach for commenting large VFP files:

Phase 1: Context Extraction
- Analyzes the entire file to extract high-level metadata
- Identifies purpose, tables, procedures, dependencies
- Low token usage, fast processing

Phase 2: Chunk-Based Commenting
- Splits code at procedural boundaries
- Comments each chunk with full context awareness
- Validates code preservation per chunk
- Assembles commented chunks into final output

This approach prevents LLM crashes on large files and maintains code integrity.
"""

import logging
from typing import List, Optional
from dataclasses import dataclass

from instructor_client import InstructorLLMClient
from vfp_chunker import VFPChunker, CodeChunk
from structured_output import FileAnalysis, CommentedCode, FileHeaderComment, CommentBlock


@dataclass
class ProcessingResult:
    """Result of two-phase processing"""
    success: bool
    commented_code: Optional[str]
    context: Optional[FileAnalysis]
    chunks_processed: int
    total_chunks: int
    error_message: Optional[str] = None


class TwoPhaseProcessor:
    """
    Two-phase processor for large VFP files.

    This processor splits the commenting task into two phases:
    1. Extract file-level context (metadata only)
    2. Comment code chunks with context awareness
    """

    def __init__(self, instructor_client: InstructorLLMClient, max_chunk_lines: int = 100):
        """
        Initialize the two-phase processor.

        Args:
            instructor_client: Instructor client for LLM communication
            max_chunk_lines: Maximum lines per chunk
        """
        self.client = instructor_client
        self.chunker = VFPChunker(max_chunk_lines=max_chunk_lines)
        self.logger = logging.getLogger(__name__)

    def process_file(self, vfp_code: str, filename: str, relative_path: str) -> ProcessingResult:
        """
        Process a VFP file using two-phase approach.

        Args:
            vfp_code: The VFP code to comment
            filename: Name of the file
            relative_path: Relative path from root

        Returns:
            ProcessingResult with commented code or error
        """
        self.logger.info(f"Starting two-phase processing for: {filename}")
        self.logger.info(f"File size: {len(vfp_code)} chars, {len(vfp_code.split(chr(10)))} lines")

        # Phase 1: Extract context
        self.logger.info("Phase 1: Extracting file context...")
        context = self._extract_context(vfp_code, filename, relative_path)

        if not context:
            return ProcessingResult(
                success=False,
                commented_code=None,
                context=None,
                chunks_processed=0,
                total_chunks=0,
                error_message="Failed to extract file context"
            )

        self.logger.info(f"[OK] Context extracted: {context.file_overview[:100]}...")

        # Phase 2: Chunk and comment
        self.logger.info("Phase 2: Chunking code...")
        chunks = self.chunker.chunk_code(vfp_code)
        self.logger.info(f"Created {len(chunks)} chunks")
        self.logger.info(self.chunker.get_chunk_summary(chunks))

        # Comment each chunk
        commented_chunks = []
        for i, chunk in enumerate(chunks):
            self.logger.info(f"Processing chunk {i+1}/{len(chunks)}: {chunk.name} ({chunk.line_count} lines)")

            commented_chunk = self._comment_chunk(chunk, context, filename, relative_path)

            if not commented_chunk:
                return ProcessingResult(
                    success=False,
                    commented_code=None,
                    context=context,
                    chunks_processed=i,
                    total_chunks=len(chunks),
                    error_message=f"Failed to comment chunk: {chunk.name}"
                )

            commented_chunks.append(commented_chunk)
            self.logger.info(f"[OK] Chunk {i+1}/{len(chunks)} commented successfully")

        # Assemble final commented file
        self.logger.info("Assembling commented file...")
        final_code = self._assemble_file(context, commented_chunks, filename, relative_path)

        return ProcessingResult(
            success=True,
            commented_code=final_code,
            context=context,
            chunks_processed=len(chunks),
            total_chunks=len(chunks)
        )

    def _extract_context(self, vfp_code: str, filename: str, relative_path: str) -> Optional[FileAnalysis]:
        """
        Phase 1: Extract file-level context without commenting.

        Args:
            vfp_code: The VFP code to analyze
            filename: Name of the file
            relative_path: Relative path from root

        Returns:
            FileAnalysis object or None on failure
        """
        try:
            context = self.client.analyze_vfp_file(
                vfp_code=vfp_code,
                filename=filename,
                relative_path=relative_path
            )
            return context
        except Exception as e:
            self.logger.error(f"Context extraction failed: {e}")
            return None

    def _comment_chunk(
        self,
        chunk: CodeChunk,
        context: FileAnalysis,
        filename: str,
        relative_path: str
    ) -> Optional[str]:
        """
        Phase 2: Comment a single code chunk with context awareness.

        Args:
            chunk: The code chunk to comment
            context: File-level context from Phase 1
            filename: Name of the file
            relative_path: Relative path from root

        Returns:
            Commented code string or None on failure
        """
        try:
            # Generate comments for this chunk
            result = self.client.generate_comments_for_chunk(
                vfp_code=chunk.content,
                chunk_name=chunk.name,
                chunk_type=chunk.chunk_type,
                file_context=context,
                filename=filename,
                relative_path=relative_path
            )

            if not result:
                self.logger.error(f"Failed to generate comments for chunk: {chunk.name}")
                return None

            # Validate code preservation against sanitized version
            # (tabs converted to spaces for JSON compatibility)
            sanitized_chunk = chunk.content.replace('\t', '    ')
            if not result.validate_code_preservation(sanitized_chunk):
                self.logger.error(f"Code preservation failed for chunk: {chunk.name}")
                return None

            # Assemble the commented chunk WITHOUT file header
            # (master header is added in _assemble_file to avoid duplicates)
            return result.assemble_inline_comments_only()

        except Exception as e:
            self.logger.error(f"Chunk commenting failed: {e}")
            import traceback
            traceback.print_exc()
            return None

    def _assemble_file(
        self,
        context: FileAnalysis,
        commented_chunks: List[str],
        filename: str,
        relative_path: str
    ) -> str:
        """
        Assemble the final commented file from context and chunks.

        Args:
            context: File-level context
            commented_chunks: List of commented code chunks
            filename: Name of the file
            relative_path: Relative path from root

        Returns:
            Complete commented file as string
        """
        lines = []

        # Add file header
        lines.append("* " + "=" * 68)
        lines.append(f"* FILE: {filename}")
        lines.append(f"* LOCATION: {relative_path}")
        lines.append("* " + "=" * 68)
        lines.append("*")
        lines.append(f"* OVERVIEW: {context.file_overview}")
        lines.append("*")

        if context.procedures:
            lines.append("* PROCEDURES/FUNCTIONS:")
            for proc in context.procedures:
                lines.append(f"*   - {proc.name} (Line {proc.line_number}): {proc.description}")
            lines.append("*")

        if context.dependencies:
            lines.append("* DEPENDENCIES:")
            for dep in context.dependencies:
                lines.append(f"*   - {dep}")
            lines.append("*")

        lines.append(f"* TOTAL LINES: {context.total_lines}")
        lines.append("* " + "=" * 68)
        lines.append("")

        # Add all commented chunks
        for i, chunk in enumerate(commented_chunks):
            if i > 0:
                lines.append("")  # Blank line between chunks
            lines.append(chunk)

        return '\n'.join(lines)


def test_two_phase():
    """Test the two-phase processor with sample code"""
    from config import ConfigManager

    sample_code = """If NewPatCou>0
    Return ""
Endif

Local calias
calias=Alias()

Select patient_no From LSTTHRTR Group By patient_no Into Cursor curreptot Readwrite

NewPatCou=Reccount("curreptot")

Use In curreptot

If !Empty(calias) And Used(calias)
    Select (calias)
Endif

Return ""
"""

    print("Two-Phase Processor Test")
    print("=" * 70)

    config = ConfigManager()
    client = InstructorLLMClient(config)
    processor = TwoPhaseProcessor(client)

    result = processor.process_file(
        vfp_code=sample_code,
        filename="test.prg",
        relative_path="test/test.prg"
    )

    if result.success:
        print("[OK] Processing successful!")
        print(f"Chunks processed: {result.chunks_processed}/{result.total_chunks}")
        print("\nCommented code:")
        print("-" * 70)
        print(result.commented_code)
    else:
        print(f"[FAIL] Processing failed: {result.error_message}")


if __name__ == "__main__":
    test_two_phase()
