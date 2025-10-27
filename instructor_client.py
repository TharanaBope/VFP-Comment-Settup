"""
Instructor-Based LLM Client for VFP Commenting
==============================================
This module provides a wrapper around the Instructor library to enforce
structured output from the local LLM, preventing code refactoring.

Key Features:
- Structured output using Pydantic models
- Code preservation validation
- Compatible with LM Studio's OpenAI-compatible API
- Retry logic with exponential backoff
"""

import logging
import time
from typing import Type, TypeVar, Optional, Dict, Any
from pydantic import BaseModel, ValidationError
import instructor
from openai import OpenAI

from config import ConfigManager
from structured_output import (
    CommentedCode,
    ChunkComments,
    FileHeaderComment,
    CommentBlock,
    FileAnalysis
)

T = TypeVar('T', bound=BaseModel)


class InstructorLLMClient:
    """
    Instructor-based LLM client that enforces structured output.

    This client wraps the OpenAI client with Instructor to ensure the LLM
    returns properly structured data according to Pydantic models, preventing
    code refactoring issues.
    """

    def __init__(self, config_manager: ConfigManager):
        """
        Initialize the Instructor LLM client.

        Args:
            config_manager: Configuration manager instance
        """
        self.config = config_manager
        self.logger = self._setup_logger()

        # Load LLM configuration
        llm_config = self.config.config.get('llm', {})

        # Validate configuration
        if not self.config.validate_llm_config():
            raise ValueError("Invalid LLM configuration")

        self.endpoint = llm_config['endpoint']
        self.model = llm_config.get('model', 'local-model')
        self.temperature = llm_config.get('temperature', 0.1)
        self.max_tokens = llm_config.get('max_tokens', 4000)
        self.timeout = llm_config.get('timeout', 300)
        self.retry_attempts = llm_config.get('retry_attempts', 3)
        self.retry_delay = llm_config.get('retry_delay', 5)

        # Initialize OpenAI client for LM Studio
        self.logger.info(f"Connecting to LM Studio endpoint: {self.endpoint}")

        try:
            base_client = OpenAI(
                base_url=self.endpoint,
                api_key="not-needed"  # LM Studio doesn't require API key
            )

            # Patch with Instructor for structured output
            # Use MD_JSON mode for better compatibility with LM Studio
            self.client = instructor.from_openai(
                base_client,
                mode=instructor.Mode.MD_JSON  # More compatible with local models like LM Studio
            )

            self.logger.info("Successfully initialized Instructor client")

        except Exception as e:
            self.logger.error(f"Failed to initialize Instructor client: {e}")
            raise

        # Test connection
        self._test_connection()

    def _setup_logger(self) -> logging.Logger:
        """Setup logging for the Instructor client"""
        logger = logging.getLogger('instructor_client')
        logger.setLevel(logging.INFO)

        # Prevent duplicate handlers
        logger.handlers.clear()
        logger.propagate = False

        # Console handler
        console_handler = logging.StreamHandler()
        console_formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
        console_handler.setFormatter(console_formatter)
        logger.addHandler(console_handler)

        return logger

    def _test_connection(self) -> None:
        """Test connection to LM Studio"""
        try:
            self.logger.info("Testing connection to LM Studio...")

            # Use a simple Pydantic model for the test
            from pydantic import BaseModel

            class SimpleResponse(BaseModel):
                message: str

            # Test with structured output
            response = self.client.chat.completions.create(
                model=self.model,
                response_model=SimpleResponse,
                messages=[
                    {
                        "role": "user",
                        "content": "Respond with a message saying 'Connection OK'"
                    }
                ],
                max_tokens=200,  # Increased for structured output
                temperature=0.1
            )

            if response and response.message:
                self.logger.info("[OK] LM Studio connection test successful")
            else:
                raise ValueError("Empty response from LLM")

        except Exception as e:
            error_msg = f"LM Studio connection test failed: {e}"
            self.logger.error(error_msg)
            raise ConnectionError(error_msg)

    def generate_structured(
        self,
        prompt: str,
        response_model: Type[T],
        system_prompt: str = None,
        max_retries: Optional[int] = None,
        **kwargs
    ) -> Optional[T]:
        """
        Generate structured output using Instructor.

        Args:
            prompt: User prompt for the LLM
            response_model: Pydantic model class for the response
            system_prompt: Optional system prompt
            max_retries: Number of retry attempts (defaults to config value)
            **kwargs: Additional parameters for the completion

        Returns:
            Instance of response_model if successful, None if failed
        """
        if max_retries is None:
            max_retries = self.retry_attempts

        if system_prompt is None:
            system_prompt = "You are a helpful assistant that provides structured responses."

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": prompt}
        ]

        for attempt in range(1, max_retries + 1):
            try:
                self.logger.info(f"Generating structured output (attempt {attempt}/{max_retries})")
                self.logger.debug(f"Response model: {response_model.__name__}")

                start_time = time.time()

                # Use Instructor to enforce structured output
                result = self.client.chat.completions.create(
                    model=self.model,
                    response_model=response_model,
                    messages=messages,
                    temperature=self.temperature,
                    max_tokens=self.max_tokens,
                    timeout=self.timeout,
                    max_retries=1,  # Let our retry logic handle retries
                    **kwargs
                )

                duration = time.time() - start_time
                self.logger.info(f"[OK] Structured output generated in {duration:.2f}s")

                return result

            except ValidationError as e:
                self.logger.error(f"Pydantic validation failed on attempt {attempt}: {e}")
                if attempt < max_retries:
                    self.logger.info(f"Retrying in {self.retry_delay} seconds...")
                    time.sleep(self.retry_delay)
                else:
                    self.logger.error("Max retries reached, validation still failing")
                    return None

            except Exception as e:
                self.logger.error(f"Error generating structured output on attempt {attempt}: {e}")
                if attempt < max_retries:
                    self.logger.info(f"Retrying in {self.retry_delay} seconds...")
                    time.sleep(self.retry_delay)
                else:
                    self.logger.error("Max retries reached")
                    return None

        return None

    def generate_comments_for_vfp(
        self,
        vfp_code: str,
        filename: str,
        relative_path: str
    ) -> Optional[CommentedCode]:
        """
        Generate structured comments for VFP code.

        This is the main method for commenting VFP files using structured output.

        Args:
            vfp_code: Original VFP code
            filename: Name of the file
            relative_path: Relative path from root

        Returns:
            CommentedCode instance if successful, None if failed
        """
        self.logger.info(f"Generating comments for: {filename}")
        self.logger.info(f"Code length: {len(vfp_code)} chars, {len(vfp_code.splitlines())} lines")

        system_prompt = """You are an expert Visual FoxPro (VFP) code analyst and documentation specialist.

🚨 CRITICAL REQUIREMENTS 🚨
1. You MUST return the EXACT original code in the 'original_code_preserved' field
2. DO NOT modify, refactor, or change ANY code
3. DO NOT add, remove, or alter ANY code lines
4. ONLY generate comment text in the structured format

Your task is to analyze VFP code and generate:
1. A structured file header with purpose and dependencies
2. Inline comments explaining code sections

Return data in the exact Pydantic model structure specified."""

        user_prompt = f"""Analyze and add comments to this VFP code file.

File: {filename}
Location: {relative_path}

🚨 CRITICAL INSTRUCTION - YOUR ONLY TASK 🚨
You must return a JSON structure with THREE fields:

1. "original_code_preserved":
   - COPY the VFP code below EXACTLY as written
   - DO NOT modify, reformat, or change ANY code
   - Keep ALL blank lines, spacing, and indentation EXACTLY as is

2. "file_header":
   - filename: "{filename}"
   - location: "{relative_path}"
   - purpose: [List of 2-3 sentences explaining what this code does]
   - dependencies: [List of tables/variables/files this code uses]
   - key_functions: [List of procedures/functions if any]

3. "inline_comments":
   - List of comments to insert at specific line numbers
   - Each comment has: insert_before_line (number), comment_lines (list of strings starting with *)

VALIDATION:
Your response will be checked line-by-line. If ANY code line is different,
your response will be REJECTED and you'll need to try again.

VFP Code (copy this EXACTLY to original_code_preserved):
```vfp
{vfp_code}
```

Return JSON with: original_code_preserved, file_header, inline_comments"""

        result = self.generate_structured(
            prompt=user_prompt,
            response_model=CommentedCode,
            system_prompt=system_prompt
        )

        if result:
            # Validate code preservation
            if result.validate_code_preservation(vfp_code):
                self.logger.info("[OK] Code preservation validated")
                return result
            else:
                self.logger.error("[FAIL] Code was modified by LLM - rejecting response")
                return None

        return None

    def _create_code_sample_for_analysis(self, vfp_code: str, max_lines: int = 1000) -> tuple[str, bool]:
        """
        Create a representative sample of VFP code for structure analysis.

        For large files, this prevents LLM crashes by sending a representative sample
        instead of the entire file during Phase 1 context extraction.

        OPTIMIZED FOR 24GB VRAM: Increased thresholds for better context capture:
        - max_lines: 1000 (from 500)
        - first_lines: 500 (from 300)
        - last_lines: 200 (from 100)

        Args:
            vfp_code: Full VFP code
            max_lines: Threshold for sampling (default 1000 lines for 24GB VRAM)

        Returns:
            Tuple of (sampled_code, was_sampled)
        """
        lines = vfp_code.splitlines()
        total_lines = len(lines)

        # If file is small enough, send entire file
        if total_lines <= max_lines:
            return vfp_code, False

        self.logger.info(f"File has {total_lines} lines - creating representative sample...")

        # Extract procedure/function signatures for complete structural view
        import re
        proc_pattern = re.compile(r'^\s*(PROCEDURE|FUNCTION)\s+(\w+)', re.IGNORECASE)
        procedure_lines = []

        for i, line in enumerate(lines, 1):
            match = proc_pattern.match(line)
            if match:
                procedure_lines.append(f"* Line {i}: {line.strip()}")

        # Build representative sample with increased sampling for better context
        # Hardware upgrade (24GB VRAM) allows larger samples
        first_lines = 500  # Increased from 300
        last_lines = 200   # Increased from 100

        sample_parts = [
            "* ===== CODE SAMPLE FOR ANALYSIS (Not complete file) =====",
            f"* Total Lines: {total_lines}",
            f"* Sample includes: First {first_lines} lines + Last {last_lines} lines + All {len(procedure_lines)} PROCEDURE/FUNCTION signatures",
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
        self.logger.info(f"Sample created: {len(sampled_code)} chars (original: {len(vfp_code)} chars)")

        return sampled_code, True

    def analyze_vfp_file(
        self,
        vfp_code: str,
        filename: str,
        relative_path: str
    ) -> Optional[FileAnalysis]:
        """
        Analyze VFP file structure without commenting (Phase 1 of two-phase approach).

        Args:
            vfp_code: VFP code to analyze
            filename: Name of the file
            relative_path: Relative path from root

        Returns:
            FileAnalysis instance if successful, None if failed
        """
        self.logger.info(f"Analyzing structure of: {filename}")

        # Create code sample for analysis (prevents LLM crashes on large files)
        code_for_analysis, was_sampled = self._create_code_sample_for_analysis(vfp_code)

        if was_sampled:
            self.logger.info("Using sampled code for analysis to prevent model overload")

        system_prompt = """You are an expert VFP code structure analyzer.
Extract high-level information from VFP code to provide context for commenting.
DO NOT generate comments or modify code - only extract metadata."""

        sampling_note = "\n⚠️ Note: This is a SAMPLE of a large file. Focus on identifying structure and patterns." if was_sampled else ""

        user_prompt = f"""Analyze the structure of this VFP file.

File: {filename}
Lines: {len(vfp_code.splitlines())}{sampling_note}

Return a FileAnalysis object with these fields:
1. filename: "{filename}"
2. file_overview: 2-3 sentence overview of what this file does
3. procedures: List of all PROCEDURE and FUNCTION definitions, each with:
   - name: procedure/function name
   - line_number: starting line (count from 1)
   - description: brief description
4. dependencies: List of tables (SELECT, UPDATE, USE), variables, external files
5. total_lines: {len(vfp_code.splitlines())}

VFP Code:
```vfp
{code_for_analysis}
```

Return structured FileAnalysis object with ALL fields filled."""

        return self.generate_structured(
            prompt=user_prompt,
            response_model=FileAnalysis,
            system_prompt=system_prompt
        )

    def _sanitize_code_for_json(self, code: str) -> tuple[str, dict]:
        """
        Sanitize VFP code for JSON transmission by replacing problematic characters.

        Returns:
            Tuple of (sanitized_code, replacements_dict)
        """
        # Replace tabs with spaces to avoid JSON control character issues
        sanitized = code.replace('\t', '    ')  # 4 spaces per tab
        replacements = {'tabs_replaced': code.count('\t')}
        return sanitized, replacements

    def _restore_code_formatting(self, code: str, replacements: dict) -> str:
        """
        Restore original formatting after JSON transmission.

        Note: Currently we keep the space replacement as it's semantically equivalent
        and avoids JSON escaping issues.
        """
        # For now, keep spaces instead of restoring tabs
        # This is semantically equivalent in VFP
        return code

    def generate_comments_for_chunk(
        self,
        vfp_code: str,
        chunk_name: str,
        chunk_type: str,
        file_context: FileAnalysis,
        filename: str,
        relative_path: str
    ) -> Optional[ChunkComments]:
        """
        Generate comments for a specific code chunk with file context awareness.
        (Phase 2 of two-phase approach)

        Uses simplified ChunkComments model that only returns comments, not code.
        This ensures 100% code preservation - the LLM never touches the code.

        Args:
            vfp_code: The code chunk to comment
            chunk_name: Name of the chunk (procedure name or 'toplevel')
            chunk_type: Type of chunk ('procedure', 'function', 'toplevel')
            file_context: File-level context from Phase 1
            filename: Name of the file
            relative_path: Relative path from root

        Returns:
            ChunkComments instance if successful, None if failed
        """
        self.logger.info(f"Generating comments for chunk: {chunk_name} ({chunk_type})")

        # Count lines for context
        line_count = len(vfp_code.split('\n'))
        self.logger.info(f"Chunk has {line_count} lines")

        system_prompt = """You are an expert Visual FoxPro (VFP) code documentation specialist.

🚨 CRITICAL REQUIREMENT 🚨
You will analyze VFP code and return ONLY comments - NOT the code itself.
DO NOT copy or return any code in your response.
ONLY return structured comment information.

Your task is to generate helpful comments that explain the code logic."""

        # Extract dependencies for display
        dep_str = ', '.join(file_context.dependencies[:5]) if file_context.dependencies else 'None'

        user_prompt = f"""Generate comments for this VFP code section.

**FILE CONTEXT (for your understanding):**
File: {filename}
Location: {relative_path}
File Overview: {file_context.file_overview}
Dependencies: {dep_str}

**CODE SECTION TO ANALYZE:**
Type: {chunk_type}
Name: {chunk_name}
Lines: {line_count}

🚨 CRITICAL JSON FORMAT REQUIREMENTS 🚨
You MUST return valid JSON. DO NOT use asterisks or any markdown formatting in JSON keys.

CORRECT JSON format example:
{{
  "file_header": {{
    "filename": "example.prg",
    "location": "path/example.prg",
    "purpose": ["Description here"],
    "dependencies": ["Table1", "Table2"],
    "key_functions": []
  }},
  "inline_comments": [
    {{
      "insert_before_line": 5,
      "comment_lines": ["* This is a VFP comment"],
      "context": "Brief description"
    }}
  ]
}}

⚠️ JSON KEY RULES ⚠️
- ALL keys must be in double quotes: "insert_before_line", "comment_lines", "context"
- NEVER use asterisks around keys: *comment_lines* is WRONG
- NEVER use markdown formatting in keys
- Keys are plain strings: "key_name" not *key_name* or _key_name_

Return JSON with TWO fields:

1. "file_header" (object):
   - "filename": "{filename}"
   - "location": "{relative_path}"
   - "purpose": [List of strings describing what THIS section does]
   - "dependencies": [List of tables/cursors/files used in THIS section]
   - "key_functions": []

2. "inline_comments" (array of objects):
   - Each object MUST have these THREE keys (in double quotes):
     - "insert_before_line" (number): Line number where comment goes
     - "comment_lines" (array of strings): VFP comments starting with *
     - "context" (string): Brief note about what this explains

**VFP Code Section to analyze:**
```vfp
{vfp_code}
```

Return ONLY valid JSON with "file_header" and "inline_comments".
DO NOT use asterisks in JSON key names.
DO NOT return the code itself."""

        result = self.generate_structured(
            prompt=user_prompt,
            response_model=ChunkComments,
            system_prompt=system_prompt
        )

        return result

    def get_stats(self) -> Dict[str, Any]:
        """Get client statistics"""
        return {
            'endpoint': self.endpoint,
            'model': self.model,
            'temperature': self.temperature,
            'max_tokens': self.max_tokens,
            'timeout': self.timeout,
            'retry_attempts': self.retry_attempts,
            'mode': 'Instructor with JSON mode'
        }


def main():
    """Test the Instructor client"""
    print("Testing Instructor LLM Client...")

    try:
        from config import ConfigManager

        # Initialize configuration
        config = ConfigManager()

        print("\nInitializing Instructor client...")
        client = InstructorLLMClient(config)

        print("\n[OK] Instructor client initialized successfully")

        # Print stats
        stats = client.get_stats()
        print("\nClient Configuration:")
        for key, value in stats.items():
            print(f"  {key}: {value}")

        # Test with simple VFP code
        sample_vfp = """LOCAL lcName, lnAge
lcName = "John Doe"
lnAge = 30
IF lnAge > 18
    ? "Adult"
ENDIF
RETURN lcName"""

        print(f"\n{'='*70}")
        print("Testing with sample VFP code:")
        print(f"{'='*70}")
        print(sample_vfp)
        print(f"{'='*70}")

        print("\nGenerating structured comments...")
        result = client.generate_comments_for_vfp(
            vfp_code=sample_vfp,
            filename="test_sample.prg",
            relative_path="test/test_sample.prg"
        )

        if result:
            print("\n[SUCCESS] Structured comments generated!")

            print(f"\n{'='*70}")
            print("File Header:")
            print(f"{'='*70}")
            print(result.file_header.to_vfp_comment())

            print(f"\n{'='*70}")
            print("Inline Comments:")
            print(f"{'='*70}")
            for i, comment in enumerate(result.inline_comments, 1):
                print(f"{i}. Before line {comment.insert_before_line}:")
                for line in comment.comment_lines:
                    print(f"   {line}")

            print(f"\n{'='*70}")
            print("Final Assembled Code:")
            print(f"{'='*70}")
            print(result.assemble_commented_code())
            print(f"{'='*70}")

            print("\n[SUCCESS] Instructor client test passed!")

        else:
            print("\n[FAIL] Failed to generate structured comments")

    except Exception as e:
        print(f"\n[ERROR] Test failed: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()
