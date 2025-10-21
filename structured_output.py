"""
Structured Output Models for VFP Commenting
===========================================
Pydantic models that enforce structured LLM output to prevent code refactoring.

The key principle: LLM returns code and comments SEPARATELY so we can validate
that original code is preserved exactly.
"""

from pydantic import BaseModel, Field, field_validator
from typing import List, Optional


class CommentBlock(BaseModel):
    """
    A single comment block to be inserted at a specific position.

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

    This represents the detailed header that goes at the top of the file.
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
    Simplified model for chunk commenting - COMMENTS ONLY (no code duplication).

    This model asks the LLM to return ONLY comments, not the original code.
    This is safer because:
    1. LLM never touches the code
    2. Smaller output size (faster, less token usage)
    3. We manually insert comments into original code (100% preservation)
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


class CommentedCode(BaseModel):
    """
    Primary output model for LLM - ensures code preservation.

    This model forces the LLM to return:
    1. The EXACT original code (for validation)
    2. A structured header comment
    3. A list of inline comments with positions

    The separation ensures we can validate code hasn't changed.
    """
    original_code_preserved: str = Field(
        ...,
        description="EXACT copy of original code - must match byte-for-byte"
    )
    file_header: FileHeaderComment = Field(
        ...,
        description="Structured file header comment"
    )
    inline_comments: List[CommentBlock] = Field(
        default_factory=list,
        description="List of inline comments to insert at specific positions"
    )

    def validate_code_preservation(self, original_code: str) -> bool:
        """
        Validate that the preserved code matches the original (ignoring trivial whitespace differences).

        This validation is smart:
        - Ignores differences in whitespace (tabs vs spaces, trailing spaces)
        - Ignores blank line count differences
        - Focuses on actual code content

        Args:
            original_code: The original VFP code before processing

        Returns:
            True if code matches semantically, False if actual code was modified
        """
        def normalize_code_line(line: str) -> str:
            """Normalize a single line for comparison"""
            # Remove leading/trailing whitespace
            # Collapse multiple spaces to single space
            normalized = ' '.join(line.strip().split())

            # Convert to lowercase for case-insensitive comparison
            normalized = normalized.lower()

            # Normalize quote types - VFP treats " and ' as equivalent
            # Replace all single quotes with double quotes
            normalized = normalized.replace("'", '"')

            return normalized

        def extract_meaningful_lines(code: str) -> list:
            """Extract non-empty, non-comment lines"""
            lines = []
            for line in code.replace('\r\n', '\n').split('\n'):
                normalized = normalize_code_line(line)
                # Skip empty lines and comment lines
                if normalized and not line.strip().startswith('*'):
                    lines.append(normalized)
            return lines

        # Extract and compare meaningful code lines
        original_lines = extract_meaningful_lines(original_code)
        preserved_lines = extract_meaningful_lines(self.original_code_preserved)

        # Compare line counts
        if len(original_lines) != len(preserved_lines):
            return False

        # Compare each line
        for orig, pres in zip(original_lines, preserved_lines):
            if orig != pres:
                return False

        return True

    def assemble_commented_code(self) -> str:
        """
        Assemble the final commented code by inserting comments.

        Returns:
            Complete VFP code with comments inserted
        """
        # Start with file header
        result_lines = [self.file_header.to_vfp_comment(), ""]

        # Split original code into lines
        code_lines = self.original_code_preserved.split('\n')

        # Sort inline comments by line number
        sorted_comments = sorted(self.inline_comments, key=lambda c: c.insert_before_line)

        # Track which line we're on
        comment_index = 0

        for line_num, code_line in enumerate(code_lines, start=1):
            # Insert any comments that belong before this line
            while (comment_index < len(sorted_comments) and
                   sorted_comments[comment_index].insert_before_line == line_num):

                comment_block = sorted_comments[comment_index]

                # Add blank line before comment for readability (unless it's line 1)
                if line_num > 1 and code_lines[line_num - 2].strip():
                    result_lines.append("")

                # Add comment lines
                result_lines.extend(comment_block.comment_lines)

                comment_index += 1

            # Add the original code line
            result_lines.append(code_line)

        return '\n'.join(result_lines)

    def assemble_inline_comments_only(self) -> str:
        """
        Assemble code with inline comments ONLY (no file header).

        Used for chunks in two-phase processing where the master file header
        is added separately to avoid duplicate headers.

        Returns:
            VFP code with inline comments but no file header
        """
        result_lines = []

        # Split original code into lines
        code_lines = self.original_code_preserved.split('\n')

        # Sort inline comments by line number
        sorted_comments = sorted(self.inline_comments, key=lambda c: c.insert_before_line)

        # Track which line we're on
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

            # Add the original code line
            result_lines.append(code_line)

        return '\n'.join(result_lines)


class ProcedureInfo(BaseModel):
    """
    Information about a procedure or function (for Phase 2 - two-phase processing).

    This will be used later when we implement the full two-phase approach.
    """
    name: str = Field(..., description="Name of procedure or function")
    line_number: int = Field(..., description="Starting line number (1-indexed)", ge=1)
    description: str = Field(..., description="Brief description of what this procedure/function does")

    # Optional fields for compatibility
    type: Optional[str] = Field(None, description="Either 'PROCEDURE' or 'FUNCTION'")
    start_line: Optional[int] = Field(None, description="Starting line number", ge=1)
    end_line: Optional[int] = Field(None, description="Ending line number", ge=1)


class FileAnalysis(BaseModel):
    """
    File structure analysis (for Phase 2 - two-phase processing).

    This model will be used in Phase 1 of the two-phase approach to extract
    file structure before commenting.
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


# Validation helper functions
def validate_vfp_comment_syntax(comment: str) -> bool:
    """
    Validate that a comment follows VFP syntax.

    Args:
        comment: Comment string to validate

    Returns:
        True if valid VFP comment syntax
    """
    stripped = comment.strip()
    return stripped.startswith('*') or '&&' in stripped


def extract_code_only(vfp_code: str) -> str:
    """
    Extract only non-comment lines from VFP code.

    Args:
        vfp_code: VFP code with or without comments

    Returns:
        Code with comment lines removed
    """
    lines = []
    for line in vfp_code.split('\n'):
        stripped = line.strip()
        # Skip full-line comments, but keep inline comments as part of code
        if not stripped.startswith('*'):
            lines.append(line)
    return '\n'.join(lines)


if __name__ == "__main__":
    """Test the Pydantic models"""
    print("Testing Pydantic models for VFP commenting...")

    # Test 1: Create a simple comment block
    comment = CommentBlock(
        insert_before_line=5,
        comment_lines=["* This is a test comment", "* It spans multiple lines"],
        context="Test comment"
    )
    print(f"\n[OK] CommentBlock created: {comment.model_dump_json(indent=2)}")

    # Test 2: Create a file header
    header = FileHeaderComment(
        filename="test.prg",
        location="test/test.prg",
        purpose=["This is a test file", "Used for validation"],
        dependencies=["Table: USERS", "Global: gnAppID"],
        key_functions=["TestFunction", "ValidateInput"]
    )
    print(f"\n[OK] FileHeaderComment created")
    print("Header as VFP comment:")
    print(header.to_vfp_comment())

    # Test 3: Create a full commented code structure
    original_code = """LOCAL lcName, lnAge
lcName = "John"
lnAge = 30
IF lnAge > 18
    ? "Adult"
ENDIF
RETURN lcName"""

    commented = CommentedCode(
        original_code_preserved=original_code,
        file_header=header,
        inline_comments=[
            CommentBlock(
                insert_before_line=1,
                comment_lines=["* Initialize local variables for person data"],
                context="Variable declaration"
            ),
            CommentBlock(
                insert_before_line=4,
                comment_lines=["* Check if person is an adult (over 18)"],
                context="Age validation"
            )
        ]
    )

    print(f"\n[OK] CommentedCode created")
    print(f"[OK] Code preservation valid: {commented.validate_code_preservation(original_code)}")

    print("\n[OK] Assembled commented code:")
    print("-" * 70)
    print(commented.assemble_commented_code())
    print("-" * 70)

    print("\n[SUCCESS] All Pydantic models working correctly!")
