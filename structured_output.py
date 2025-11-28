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


class CommentQualityValidator:
    """
    Multi-layer validator for comment quality and accuracy.

    Validates that comments are:
    1. Syntactically correct (language-specific syntax via handler)
    2. Relevant to the actual code
    3. Complete (has header and inline comments)
    4. References business terms from Phase 1 context
    """

    def __init__(self, handler=None):
        """
        Initialize validator with language handler.

        Args:
            handler: Language handler (VFPHandler, CSharpHandler, etc.) for syntax validation
        """
        self.handler = handler

    def _get_header_comment_text(self, file_header) -> str:
        """
        Get comment text from file header in a language-aware way.

        Args:
            file_header: FileHeaderComment or CSharpFileHeaderComment

        Returns:
            Comment text as string
        """
        # Try C# method first
        if hasattr(file_header, 'to_csharp_comment'):
            return file_header.to_csharp_comment()
        # Fall back to VFP method
        elif hasattr(file_header, 'to_vfp_comment'):
            return file_header.to_vfp_comment()
        else:
            # Fallback: return empty string if neither method exists
            return ""

    def validate_comments(
        self,
        original_code: str,
        chunk_comments: ChunkComments,
        file_context: Optional[FileAnalysis] = None
    ) -> tuple[bool, List[str]]:
        """
        Comprehensive validation of comment quality.

        Args:
            original_code: The original VFP code being commented
            chunk_comments: The comments generated by LLM
            file_context: Optional Phase 1 context for business logic validation

        Returns:
            Tuple of (is_valid, list_of_issues)
        """
        issues = []

        # Layer 1: Syntax validation (language-specific via handler)
        syntax_issues = self._validate_comment_syntax(chunk_comments)
        issues.extend(syntax_issues)

        # Layer 2: Relevance validation
        relevance_issues = self._validate_relevance(original_code, chunk_comments)
        issues.extend(relevance_issues)

        # Layer 3: Completeness validation
        completeness_issues = self._validate_completeness(chunk_comments)
        issues.extend(completeness_issues)

        # Layer 4: Business logic validation (if context available)
        if file_context:
            business_issues = self._validate_business_terms(chunk_comments, file_context)
            issues.extend(business_issues)

        is_valid = len(issues) == 0
        return is_valid, issues

    def _validate_comment_syntax(self, chunk_comments) -> List[str]:
        """
        Validate all comments use correct language-specific syntax.

        Delegates to the language handler for syntax validation.
        Falls back to VFP validation if no handler provided (backward compatibility).
        """
        if self.handler and hasattr(self.handler, 'validate_chunk_comments_syntax'):
            # Use language handler for validation
            return self.handler.validate_chunk_comments_syntax(chunk_comments)

        # Fallback to VFP validation for backward compatibility
        issues = []

        # Check file header
        header_text = chunk_comments.file_header.to_vfp_comment()
        for line in header_text.split('\n'):
            if line.strip() and not line.strip().startswith('*'):
                issues.append(f"Header line missing *: {line[:50]}")

        # Check inline comments
        for idx, comment_block in enumerate(chunk_comments.inline_comments):
            for line in comment_block.comment_lines:
                if line.strip() and not line.strip().startswith('*'):
                    issues.append(f"Inline comment {idx} missing *: {line[:50]}")

        return issues

    def _validate_relevance(self, original_code: str, chunk_comments) -> List[str]:
        """Validate comments reference actual code terms"""
        issues = []

        # Extract significant terms from code (function names, variables, keywords)
        code_lower = original_code.lower()
        code_terms = set()

        # Extract keywords and identifiers (language-agnostic)
        for line in original_code.split('\n'):
            stripped = line.strip()
            # Skip comment lines (works for VFP *, C# //, ///)
            if stripped and not stripped.startswith('*') and not stripped.startswith('//'):
                # Extract potential identifiers (simplified)
                tokens = stripped.replace('(', ' ').replace(')', ' ').replace(',', ' ').split()
                code_terms.update(t.lower() for t in tokens if len(t) > 2)

        # Get all comment text (language-aware)
        all_comments = self._get_header_comment_text(chunk_comments.file_header)
        for comment_block in chunk_comments.inline_comments:
            all_comments += '\n'.join(comment_block.comment_lines)

        comments_lower = all_comments.lower()

        # Count how many code terms appear in comments
        referenced_terms = sum(1 for term in code_terms if term in comments_lower)

        if code_terms and referenced_terms < len(code_terms) * 0.1:  # Less than 10% coverage
            issues.append(f"Low code term coverage: only {referenced_terms}/{len(code_terms)} terms mentioned")

        return issues

    def _validate_completeness(self, chunk_comments: ChunkComments) -> List[str]:
        """Validate comments are complete (has header and inline comments)"""
        issues = []

        # Check header has purpose
        if not chunk_comments.file_header.purpose:
            issues.append("Header missing purpose section")

        # Check header purpose is meaningful (not too short)
        if chunk_comments.file_header.purpose:
            total_purpose_length = sum(len(p) for p in chunk_comments.file_header.purpose)
            if total_purpose_length < 50:
                issues.append("Header purpose too brief (< 50 chars)")

        # Check inline comments exist
        if not chunk_comments.inline_comments:
            issues.append("No inline comments provided")

        return issues

    def _validate_business_terms(
        self,
        chunk_comments,
        file_context
    ) -> List[str]:
        """Validate comments mention dependencies from Phase 1"""
        issues = []

        # Gather all comment text (language-aware)
        all_comments = self._get_header_comment_text(chunk_comments.file_header)
        for comment_block in chunk_comments.inline_comments:
            all_comments += '\n'.join(comment_block.comment_lines)

        comments_lower = all_comments.lower()

        # Check if dependencies are mentioned
        if hasattr(file_context, 'dependencies') and file_context.dependencies:
            mentioned_deps = 0
            for dep in file_context.dependencies:
                # Extract key term from dependency (e.g., "Table: USERS" -> "users")
                dep_terms = dep.lower().split()
                if any(term in comments_lower for term in dep_terms if len(term) > 3):
                    mentioned_deps += 1

            if mentioned_deps < len(file_context.dependencies) * 0.5:  # Less than 50% mentioned
                issues.append(
                    f"Dependencies not well documented: only {mentioned_deps}/{len(file_context.dependencies)} mentioned"
                )

        return issues


class CommentInsertionValidator:
    """
    Validates that comments will be inserted correctly into code.

    Performs pre-insertion and post-insertion validation to ensure:
    1. Line numbers are valid
    2. No duplicate insertions (language-dependent)
    3. Comments are sorted correctly
    4. Original code is preserved
    """

    def __init__(self, handler=None):
        """
        Initialize validator with optional language handler.

        Args:
            handler: Language handler for language-specific validation rules
                     If None, uses default strict validation (no duplicates)
        """
        self.handler = handler

    def validate_insertion(
        self,
        original_code: str,
        chunk_comments: ChunkComments
    ) -> tuple[bool, List[str]]:
        """
        Pre-insertion validation.

        Args:
            original_code: The original VFP code
            chunk_comments: The comments to be inserted

        Returns:
            Tuple of (is_valid, list_of_issues)
        """
        issues = []

        code_lines = original_code.split('\n')
        total_lines = len(code_lines)

        # Validate line numbers are within bounds
        for idx, comment_block in enumerate(chunk_comments.inline_comments):
            line_num = comment_block.insert_before_line
            if line_num < 1:
                issues.append(f"Comment {idx}: line number {line_num} < 1")
            elif line_num > total_lines + 1:  # Allow insert after last line
                issues.append(f"Comment {idx}: line number {line_num} > {total_lines + 1}")

        # Check for duplicate line numbers (language-dependent)
        # Some languages (C#) allow multiple comments at same line, others (VFP) don't
        line_numbers = [c.insert_before_line for c in chunk_comments.inline_comments]
        if len(line_numbers) != len(set(line_numbers)):
            # Check if language allows duplicates
            allows_duplicates = (
                self.handler.allows_duplicate_insertion_points()
                if self.handler else False
            )

            if not allows_duplicates:
                duplicates = [ln for ln in line_numbers if line_numbers.count(ln) > 1]
                issues.append(f"Duplicate insertion points: {set(duplicates)}")

        # NOTE: We don't fail on unsorted comments because insert_comments_into_code()
        # automatically sorts them anyway. This is just informational.
        # Unsorted comments are handled gracefully, so not a validation failure.

        is_valid = len(issues) == 0
        return is_valid, issues

    def validate_post_insertion(
        self,
        original_code: str,
        commented_code: str,
        expected_comment_count: int
    ) -> tuple[bool, List[str]]:
        """
        Post-insertion validation.

        Args:
            original_code: The original VFP code
            commented_code: The code after comment insertion
            expected_comment_count: Number of comment blocks that should be inserted

        Returns:
            Tuple of (is_valid, list_of_issues)
        """
        issues = []

        # Extract non-comment, non-blank lines from both versions
        # (Ignore blank lines added for readability around comments)
        original_lines = [
            line for line in original_code.split('\n')
            if line.strip() and not line.strip().startswith('*')
        ]

        commented_lines = [
            line for line in commented_code.split('\n')
            if line.strip() and not line.strip().startswith('*')
        ]

        # Validate code preservation (should have same non-blank code lines)
        if len(original_lines) != len(commented_lines):
            issues.append(
                f"Code line count mismatch: original={len(original_lines)}, "
                f"commented={len(commented_lines)}"
            )
        else:
            # Check each line matches
            mismatches = 0
            for idx, (orig, comm) in enumerate(zip(original_lines, commented_lines), 1):
                if orig.strip() != comm.strip():
                    mismatches += 1
                    if mismatches <= 3:  # Report first 3 mismatches
                        issues.append(f"Line {idx} mismatch: '{orig[:30]}' != '{comm[:30]}'")

            if mismatches > 3:
                issues.append(f"... and {mismatches - 3} more mismatches")

        # Count comment blocks in output
        comment_blocks = 0
        in_comment_block = False
        for line in commented_code.split('\n'):
            is_comment = line.strip().startswith('*')
            if is_comment and not in_comment_block:
                comment_blocks += 1
                in_comment_block = True
            elif not is_comment:
                in_comment_block = False

        # Allow some variance (header + inline comments)
        if comment_blocks < expected_comment_count:
            issues.append(
                f"Comment count too low: expected ~{expected_comment_count}, "
                f"found {comment_blocks}"
            )

        is_valid = len(issues) == 0
        return is_valid, issues


class CommentMetrics:
    """
    Calculate quality metrics for commented code.

    Provides quantitative measures of comment quality:
    1. Comment ratio (comments per 100 lines of code)
    2. Keyword coverage (% of key terms mentioned)
    3. Procedure coverage (% of procedures with comments)
    4. Average comment length
    """

    def __init__(self):
        pass

    def calculate_metrics(
        self,
        original_code: str,
        commented_code: str,
        file_context: Optional[FileAnalysis] = None
    ) -> dict:
        """
        Calculate all comment quality metrics.

        Args:
            original_code: The original VFP code
            commented_code: The code with comments
            file_context: Optional Phase 1 context

        Returns:
            Dictionary of metrics
        """
        metrics = {}

        # Count code lines and comment lines
        code_line_count = self._count_code_lines(original_code)
        comment_line_count = self._count_comment_lines(commented_code)

        # Comment ratio: comments per 100 lines of code
        if code_line_count > 0:
            metrics['comment_ratio'] = (comment_line_count / code_line_count) * 100
        else:
            metrics['comment_ratio'] = 0

        # Keyword coverage
        if file_context:
            metrics['keyword_coverage'] = self._calculate_keyword_coverage(
                commented_code,
                file_context
            )

        # Procedure/method coverage (works with both VFP procedures and C# methods)
        if file_context:
            # Check for either 'procedures' (VFP) or 'methods' (C#)
            has_procs_or_methods = (hasattr(file_context, 'procedures') and file_context.procedures) or \
                                   (hasattr(file_context, 'methods') and file_context.methods)
            if has_procs_or_methods:
                metrics['procedure_coverage'] = self._calculate_procedure_coverage(
                    commented_code,
                    file_context
                )

        # Average comment length
        metrics['avg_comment_length'] = self._calculate_avg_comment_length(commented_code)

        # Total metrics
        metrics['total_code_lines'] = code_line_count
        metrics['total_comment_lines'] = comment_line_count

        return metrics

    def _count_code_lines(self, code: str) -> int:
        """Count non-comment, non-blank lines"""
        count = 0
        for line in code.split('\n'):
            stripped = line.strip()
            if stripped and not stripped.startswith('*'):
                count += 1
        return count

    def _count_comment_lines(self, code: str) -> int:
        """Count comment lines"""
        count = 0
        for line in code.split('\n'):
            if line.strip().startswith('*'):
                count += 1
        return count

    def _calculate_keyword_coverage(
        self,
        commented_code: str,
        file_context
    ) -> float:
        """
        Calculate % of dependencies mentioned in comments.

        Works with both VFP (dependencies) and C# (external_dependencies) models.
        """
        # Get dependencies list - check for both VFP and C# field names
        deps = getattr(file_context, 'dependencies', None) or getattr(file_context, 'external_dependencies', None)

        if not deps:
            return 100.0

        comments_lower = commented_code.lower()
        mentioned = 0

        for dep in deps:
            # Extract key terms from dependency
            dep_terms = dep.lower().split()
            if any(term in comments_lower for term in dep_terms if len(term) > 3):
                mentioned += 1

        return (mentioned / len(deps)) * 100

    def _calculate_procedure_coverage(
        self,
        commented_code: str,
        file_context
    ) -> float:
        """
        Calculate % of procedures/methods mentioned in comments.

        Works with both VFP (procedures) and C# (methods) models.
        """
        # Get procedures/methods list - check for both VFP and C# field names
        procs = getattr(file_context, 'procedures', None) or getattr(file_context, 'methods', None)

        if not procs:
            return 100.0

        comments_lower = commented_code.lower()
        mentioned = 0

        for proc in procs:
            proc_name = proc.name.lower()
            if proc_name in comments_lower:
                mentioned += 1

        return (mentioned / len(procs)) * 100

    def _calculate_avg_comment_length(self, commented_code: str) -> float:
        """Calculate average length of comment lines"""
        comment_lines = [
            line for line in commented_code.split('\n')
            if line.strip().startswith('*')
        ]

        if not comment_lines:
            return 0.0

        total_length = sum(len(line.strip()) for line in comment_lines)
        return total_length / len(comment_lines)


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
