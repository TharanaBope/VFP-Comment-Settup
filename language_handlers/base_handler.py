"""
Base handler abstraction for language-specific commenting logic.

This module defines the abstract LanguageHandler class that all language-specific
handlers must implement. This enables a pluggable architecture where new languages
can be added without modifying core processing logic.
"""

from abc import ABC, abstractmethod
from typing import List, Dict, Type, Tuple
from pydantic import BaseModel


class LanguageHandler(ABC):
    """
    Abstract base class for language-specific handlers.

    Each language (VFP, C#, Java, Python, etc.) implements this interface
    to provide language-specific:
    - File extensions and skip patterns
    - Code chunking strategies
    - Pydantic models for structured LLM output
    - LLM prompts (system, Phase 1, Phase 2)
    - Comment syntax validation
    - Code formatting utilities
    """

    @abstractmethod
    def get_language_name(self) -> str:
        """
        Return the language identifier.

        Returns:
            str: Language name (e.g., 'vfp', 'csharp', 'java')
        """
        pass

    @abstractmethod
    def get_file_extensions(self) -> List[str]:
        """
        Return list of file extensions to process.

        Returns:
            List[str]: File extensions including the dot (e.g., ['.prg', '.spr'])
        """
        pass

    @abstractmethod
    def get_skip_patterns(self) -> List[str]:
        """
        Return patterns to skip during file scanning.

        Patterns can be:
        - Filename patterns (e.g., '_commented', '.Designer.cs')
        - Directory patterns (e.g., 'obj/', 'bin/', 'node_modules/')

        Returns:
            List[str]: Patterns to skip
        """
        pass

    @abstractmethod
    def create_chunker(self, config: dict):
        """
        Create and return a language-specific chunker instance.

        The chunker is responsible for splitting files into manageable chunks
        while respecting language-specific boundaries (classes, methods, etc.).

        Args:
            config: Configuration dictionary containing chunking parameters

        Returns:
            Chunker instance (AdaptiveVFPChunker, AdaptiveCSharpChunker, etc.)
        """
        pass

    @abstractmethod
    def get_pydantic_models(self) -> Dict[str, Type[BaseModel]]:
        """
        Return dictionary of Pydantic models used by this language.

        These models enforce structured output from the LLM and validate
        that responses match expected schemas.

        Required keys:
        - 'FileAnalysis': Model for Phase 1 context extraction
        - 'ChunkComments': Model for Phase 2 chunk commenting
        - 'CommentBlock': Model for individual comment blocks
        - 'FileHeaderComment': Model for file header comments

        Returns:
            Dict[str, Type[BaseModel]]: Dictionary mapping model names to Pydantic classes
        """
        pass

    @abstractmethod
    def get_system_prompt(self) -> str:
        """
        Return the LLM system prompt for this language.

        The system prompt sets the overall behavior and constraints for the LLM,
        including critical rules about code preservation and comment syntax.

        Returns:
            str: System prompt text
        """
        pass

    @abstractmethod
    def get_phase1_prompt(self, code: str, filename: str, relative_path: str) -> str:
        """
        Generate Phase 1 (context extraction) prompt.

        Phase 1 analyzes the file structure without adding comments.
        It extracts high-level information like classes, methods, dependencies,
        and business logic to provide context for Phase 2.

        Args:
            code: Full source code to analyze
            filename: Name of the file
            relative_path: Relative path from project root

        Returns:
            str: Formatted prompt string for Phase 1 analysis
        """
        pass

    @abstractmethod
    def get_phase2_prompt(
        self,
        chunk: str,
        chunk_name: str,
        chunk_type: str,
        file_context,
        filename: str,
        relative_path: str
    ) -> str:
        """
        Generate Phase 2 (chunk commenting) prompt.

        Phase 2 generates comments for specific code chunks using context
        from Phase 1 to ensure contextually aware, accurate documentation.

        Args:
            chunk: Code chunk to comment
            chunk_name: Name/identifier of the chunk
            chunk_type: Type of chunk ('class', 'method', 'procedure', 'function', etc.)
            file_context: FileAnalysis object from Phase 1 (Pydantic model)
            filename: Name of the file
            relative_path: Relative path from project root

        Returns:
            str: Formatted prompt string for Phase 2 commenting
        """
        pass

    @abstractmethod
    def validate_comment_syntax(self, comment: str, comment_type: str = None) -> bool:
        """
        Validate that comment follows language-specific syntax rules.

        This ensures generated comments are syntactically correct for the
        target language (e.g., VFP uses '*', C# uses '///' for XML docs).

        Args:
            comment: Comment text to validate
            comment_type: Optional type hint ('xml_doc', 'single_line', 'multi_line', etc.)

        Returns:
            bool: True if valid, False otherwise
        """
        pass

    @abstractmethod
    def format_file_header(self, header_data: dict) -> str:
        """
        Format file header comment from structured data.

        Creates a standardized file header with metadata like filename,
        purpose, dependencies, etc. formatted according to language conventions.

        Args:
            header_data: Dictionary with header information
                Example keys: 'filename', 'purpose', 'dependencies', 'location'

        Returns:
            str: Formatted header comment as string (ready to insert)
        """
        pass

    @abstractmethod
    def extract_code_sample(self, code: str, max_lines: int = 1000) -> Tuple[str, bool]:
        """
        Create representative code sample for large files (used in Phase 1).

        For very large files (>1000 lines), Phase 1 doesn't need the entire file.
        This method extracts key sections (classes, methods, imports) to provide
        enough context without overwhelming the LLM.

        Args:
            code: Full source code
            max_lines: Maximum lines before sampling is needed

        Returns:
            Tuple[str, bool]: (sampled_code, was_sampled)
                - sampled_code: Code to analyze (full or sampled)
                - was_sampled: True if sampling occurred, False if full code returned
        """
        pass

    def allows_duplicate_insertion_points(self) -> bool:
        """
        Specify whether this language allows multiple comment blocks at the same line.

        Some languages (like C#) may need multiple comment blocks at the same insertion
        point (e.g., XML documentation followed by an inline comment). Other languages
        (like VFP) typically use one comment per line, and duplicates indicate LLM errors.

        This is a concrete method (not abstract) with a default implementation.
        Override in language handlers to customize behavior.

        Returns:
            bool: True if language allows duplicates, False for strict validation

        Default: False (strict validation - no duplicate insertion points allowed)
        """
        return False
