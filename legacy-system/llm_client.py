"""
LLM Client Module - LEGACY VFP COMMENTING
==========================================
This module handles communication with the local LLM (GPTOSS20B via LM Studio)
for adding comprehensive comments to Visual FoxPro legacy code.

FEATURES:
- Direct code commenting with enhanced prompts
- Context-aware chunking for large files
- VFP procedure/function boundary detection
- Intelligent timeout and retry handling
- Comprehensive validation and error handling
- Dynamic processing strategy selection
"""

import requests
import json
import logging
import time
from typing import Optional, Dict, Any, List
from config import ConfigManager
from token_estimator import TokenEstimator, VFPChunker

class LLMClient:
    """
    LLM client for adding comprehensive comments to Visual FoxPro code.

    This client processes VFP files using intelligent chunking strategies
    and enhanced prompts to generate high-quality, contextual comments.
    """

    def __init__(self, config_manager: ConfigManager):
        """
        Initialize the LLM client with configuration.

        Args:
            config_manager: Configuration manager instance
        """
        self.config = config_manager
        self.logger = self._setup_logger()

        # Load LLM configuration
        self.llm_config = self.config.config.get('llm', {})
        self.prompt_config = self.config.config.get('prompts', {})
        self.processing_config = self.config.config.get('processing', {})

        # Validate LLM configuration
        if not self.config.validate_llm_config():
            raise ValueError("Invalid LLM configuration")

        self.endpoint = self.llm_config['endpoint']
        self.model = self.llm_config['model']
        self.temperature = self.llm_config.get('temperature', 0.1)
        self.max_tokens = self.llm_config.get('max_tokens', 4000)

        # Dynamic timeout settings
        self.timeout = self.llm_config.get('timeout', 900)
        self.timeout_small = self.llm_config.get('timeout_small', 120)
        self.timeout_medium = self.llm_config.get('timeout_medium', 300)
        self.timeout_large = self.llm_config.get('timeout_large', 900)

        self.retry_attempts = self.llm_config.get('retry_attempts', 3)
        self.retry_delay = self.llm_config.get('retry_delay', 5)

        # Initialize token estimator and chunker
        self.token_estimator = TokenEstimator()
        chunk_size = self.processing_config.get('chunk_size_target', 3000)
        overlap_lines = self.processing_config.get('chunk_overlap_lines', 5)
        self.chunker = VFPChunker(chunk_size, overlap_lines)

        self.logger.info(f"Initialized LLM client for VFP commenting: {self.endpoint}")
        self.logger.info(f"Model: {self.model}, Temperature: {self.temperature}")
        self.logger.info("✓ VFP commenting client initialized")

        # Test connection
        self._test_connection()

    def _setup_logger(self) -> logging.Logger:
        """Setup comprehensive logging for LLM interactions."""
        logger = logging.getLogger('llm_client')
        logger.setLevel(logging.INFO)

        # Prevent duplicate handlers and propagation to avoid duplicate logs
        logger.handlers.clear()
        logger.propagate = False

        # Console handler
        console_handler = logging.StreamHandler()
        console_formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
        console_handler.setFormatter(console_formatter)
        logger.addHandler(console_handler)

        # File handler if enabled
        if self.config.get('logging.enable_file_logging', True):
            log_file = self.config.get('logging.log_file', 'vfp_commenting.log')
            try:
                file_handler = logging.FileHandler(log_file, encoding='utf-8')
                file_formatter = logging.Formatter(
                    '%(asctime)s - %(name)s - %(levelname)s - %(funcName)s:%(lineno)d - %(message)s'
                )
                file_handler.setFormatter(file_formatter)
                logger.addHandler(file_handler)
            except Exception as e:
                logger.warning(f"Could not setup file logging: {e}")

        return logger

    def _test_connection(self) -> None:
        """
        Test connection to the LLM endpoint.
        Raises exception if connection fails.
        """
        try:
            self.logger.info("Testing LLM connection...")

            test_payload = {
                "model": self.model,
                "messages": [
                    {
                        "role": "user",
                        "content": "Test connection. Please respond with 'Connection OK'."
                    }
                ],
                "temperature": 0.1,
                "max_tokens": 10
            }

            response = requests.post(
                self.endpoint,
                json=test_payload,
                timeout=30,
                headers={'Content-Type': 'application/json'}
            )

            if response.status_code == 200:
                self.logger.info("✓ LLM connection test successful")
            else:
                error_msg = f"LLM connection test failed: HTTP {response.status_code}"
                self.logger.error(error_msg)
                raise ConnectionError(error_msg)

        except requests.exceptions.ConnectionError as e:
            error_msg = f"Cannot connect to LLM endpoint {self.endpoint}: {e}"
            self.logger.error(error_msg)
            raise ConnectionError(error_msg)
        except requests.exceptions.Timeout as e:
            error_msg = f"LLM connection timeout: {e}"
            self.logger.error(error_msg)
            raise ConnectionError(error_msg)
        except Exception as e:
            error_msg = f"Unexpected error testing LLM connection: {e}"
            self.logger.error(error_msg)
            raise ConnectionError(error_msg)

    def _build_system_prompt(self) -> str:
        """
        Build the system prompt for VFP code commenting.

        Returns:
            System prompt string
        """
        return self.prompt_config.get('system_prompt', """You are an expert Visual FoxPro (VFP) programmer tasked with adding comprehensive comments to legacy VFP code.

🚨 CRITICAL REQUIREMENT - READ CAREFULLY 🚨
YOU MUST NEVER MODIFY THE ORIGINAL CODE IN ANY WAY!
- DO NOT change variable names, function calls, logic conditions, string values, or numeric values
- DO NOT add, remove, or modify ANY code lines
- ONLY ADD COMMENT LINES (starting with *)

Your ONLY task is to add explanatory comments while keeping the original code 100% intact.

Comment Guidelines:
1. Add a structured header with dashes, File, Location, Purpose, and Dependencies sections
2. Add single-line * comments ABOVE code blocks (no inline && comments)
3. Keep comments concise and focused on what the code does
4. Document database operations and business logic briefly
5. Use clear, simple explanations without excessive detail

Header Format:
* --------------------------------------------------------------------
* File: [filename]
* Location: [path]
*
* Purpose:
*   [Brief description of what the program does]
*   [Additional context if needed]
*
* Dependencies:
*   - [List any tables, global variables, or external requirements]
* --------------------------------------------------------------------

Comment Style:
- Header: Structured format with sections as shown above
- Code comments: Single-line * comments above blocks only
- NO inline && comments
- Keep explanations brief and practical

🚨 VALIDATION REMINDER 🚨
Your response will be validated to ensure NO original code was changed.
Return the EXACT original code with ONLY * comment lines added.""")

    def _build_user_prompt(self, code_content: str, filename: str, relative_path: str, file_size: int) -> str:
        """
        Build the user prompt with code preservation warnings.

        Args:
            code_content: Original VFP code content
            filename: Name of the file
            relative_path: Relative path of the file
            file_size: Size of the file in bytes

        Returns:
            User prompt string
        """
        template = self.prompt_config.get('user_prompt_template', """🚨 CRITICAL: PRESERVE EXACT FORMATTING - DO NOT MODIFY ANY ORIGINAL CODE 🚨

Add comments to this VFP file while preserving EXACT formatting:

File: {filename}
Location: {relative_path}

RULES:
1. Keep ALL original code lines EXACTLY as written (same spacing, same case, same formatting)
2. Keep ALL blank lines exactly where they are
3. DO NOT add or remove any blank lines
4. DO NOT change any indentation or spacing
5. ONLY add comment lines starting with *
6. Add detailed explanatory comments above code blocks

Required header format (use this EXACT structure):
* --------------------------------------------------------------------
* File: {filename}
* Location: {relative_path}
*
* Purpose:
*   [Detailed multi-line explanation of what this routine does]
*   [Include business context and usage scenarios]
*   [Explain return values and side effects]
*
* Dependencies:
*   - [List tables, cursors, and database requirements]
*   - [List global variables and parameters]
*   - [List any external files or resources]
* --------------------------------------------------------------------

Then add detailed * comments above each logical code block explaining:
- What the code section accomplishes
- Why this logic is needed
- What variables/data it processes
- Any business rules being implemented

EXAMPLE of expected output style:
```
* --------------------------------------------------------------------
* File: example.prg
* Location: modules/example.prg
*
* Purpose:
*   This routine validates user credentials and processes login attempts.
*   It checks existing session status first to avoid duplicate logins.
*   Returns success status and updates global user tracking variables.
*
* Dependencies:
*   - Table or alias: USERS (must be open before calling)
*   - Cursor: curSession (created temporarily in this routine)
*   - Variable: gnUserID (global session identifier)
* --------------------------------------------------------------------

* Check if user is already logged in to avoid duplicate processing
* If gnUserID is already set, exit immediately without further validation
IF gnUserID > 0
	RETURN "Already logged in"
ENDIF

* Query the USERS table to validate credentials and create temporary cursor
* This cursor will contain matching user records for verification
SELECT * FROM USERS WHERE userid = lnID INTO CURSOR curSession
```

🚨 VALIDATION: Your response will be parsed to extract original code and compared byte-for-byte. Any changes will cause rejection.

Original code to preserve exactly:
{code_content}

Return the structured header + exact original code with detailed explanatory comments:""")

        return template.format(
            filename=filename,
            relative_path=relative_path,
            file_size=file_size,
            code_content=code_content
        )

    def _make_llm_request(self, messages: list, attempt: int = 1, strategy: str = 'large') -> Optional[str]:
        """
        Make a request to the LLM with comprehensive error handling.

        Args:
            messages: List of messages to send to LLM
            attempt: Current attempt number for logging
            strategy: Processing strategy (small/medium/large) for timeout selection

        Returns:
            LLM response content, or None if failed
        """
        # Get dynamic timeout based on strategy
        timeout = self.get_dynamic_timeout(strategy)

        payload = {
            "model": self.model,
            "messages": messages,
            "temperature": self.temperature,
            "max_tokens": self.max_tokens
        }

        try:
            self.logger.info(f"Making LLM request (attempt {attempt}) - strategy: {strategy}, timeout: {timeout}s")
            self.logger.debug(f"Request payload: {json.dumps(payload, indent=2)}")

            start_time = time.time()

            response = requests.post(
                self.endpoint,
                json=payload,
                timeout=timeout,
                headers={'Content-Type': 'application/json'}
            )

            end_time = time.time()
            duration = end_time - start_time

            self.logger.info(f"LLM request completed in {duration:.2f} seconds")

            if response.status_code != 200:
                self.logger.error(f"LLM request failed: HTTP {response.status_code}")
                self.logger.error(f"Response: {response.text}")
                return None

            try:
                response_data = response.json()
                self.logger.debug(f"Response data: {json.dumps(response_data, indent=2)}")

                # Extract content from response
                choices = response_data.get('choices', [])
                if not choices:
                    self.logger.error("No choices in LLM response")
                    return None

                message = choices[0].get('message', {})
                content = message.get('content', '')

                if not content:
                    self.logger.error("Empty content in LLM response")
                    return None

                # Log response statistics
                self.logger.info(f"LLM response received: {len(content)} characters")

                # Check for usage statistics if available
                usage = response_data.get('usage', {})
                if usage:
                    prompt_tokens = usage.get('prompt_tokens', 0)
                    completion_tokens = usage.get('completion_tokens', 0)
                    total_tokens = usage.get('total_tokens', 0)
                    self.logger.info(f"Token usage - Prompt: {prompt_tokens}, Completion: {completion_tokens}, Total: {total_tokens}")

                return content

            except json.JSONDecodeError as e:
                self.logger.error(f"Failed to parse LLM response as JSON: {e}")
                self.logger.error(f"Response text: {response.text}")
                return None

        except requests.exceptions.ConnectionError as e:
            self.logger.error(f"Connection error during LLM request: {e}")
            return None
        except requests.exceptions.Timeout as e:
            self.logger.error(f"Timeout during LLM request: {e}")
            return None
        except Exception as e:
            self.logger.error(f"Unexpected error during LLM request: {e}")
            return None

    def determine_processing_strategy(self, code_content: str, file_size: int) -> Dict[str, any]:
        """
        Determine the optimal processing strategy for a file.

        Args:
            code_content: File content
            file_size: File size in bytes

        Returns:
            Strategy information dictionary
        """
        size_small = self.processing_config.get('file_size_small', 5000)
        size_medium = self.processing_config.get('file_size_medium', 15000)

        strategy_info = self.token_estimator.determine_processing_strategy(
            file_size, code_content, size_small, size_medium
        )

        self.logger.info(f"Processing strategy: {strategy_info['strategy']}")
        self.logger.info(f"Needs chunking: {strategy_info['needs_chunking']}")
        self.logger.info(f"Token estimate: {strategy_info['token_info']['total_estimated_tokens']}")

        return strategy_info

    def get_dynamic_timeout(self, strategy: str) -> int:
        """Get timeout based on processing strategy."""
        if strategy == 'small':
            return self.timeout_small
        elif strategy == 'medium':
            return self.timeout_medium
        else:
            return self.timeout_large

    def process_file_chunked(self, code_content: str, filename: str, relative_path: str, file_size: int) -> Optional[str]:
        """
        Process a large VFP file using context-aware chunking strategy.

        Args:
            code_content: Original VFP code content
            filename: Name of the file
            relative_path: Relative path of the file
            file_size: Size of the file in bytes

        Returns:
            Commented content if successful, None if failed
        """
        self.logger.info(f"Processing file with context-aware chunking: {filename}")

        # Create context-aware chunks
        chunks = self.chunker.create_context_aware_chunks(code_content, filename)
        total_chunks = len(chunks)

        self.logger.info(f"File split into {total_chunks} context-aware chunks")

        chunk_results = []

        for chunk in chunks:
            self.logger.info(f"Processing chunk {chunk['chunk_num']}/{total_chunks} "
                           f"({chunk['estimated_tokens']} tokens, {chunk['line_count']} lines)")

            # Build context-aware chunked prompt
            chunked_prompt = self._build_context_aware_prompt(chunk)

            system_prompt = self._build_system_prompt()
            messages = [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": chunked_prompt}
            ]

            # Process chunk with retries
            commented_chunk = None
            for attempt in range(1, self.retry_attempts + 1):
                self.logger.info(f"Chunk {chunk['chunk_num']} attempt {attempt}/{self.retry_attempts}")

                response_content = self._make_llm_request(messages, attempt, strategy='medium')

                if response_content:
                    # Basic validation for chunks (relaxed validation)
                    validation_result = self._validate_chunk_response(chunk['content'], response_content, chunk['chunk_num'])
                    if validation_result['valid']:
                        commented_chunk = response_content
                        break
                    else:
                        self.logger.warning(f"Chunk {chunk['chunk_num']} validation failed: {validation_result['reason']}, retrying...")

                if attempt < self.retry_attempts:
                    time.sleep(self.retry_delay)

            # Create chunk result record
            chunk_result = {
                'chunk_num': chunk['chunk_num'],
                'start_line': chunk.get('start_line', 0),
                'end_line': chunk.get('end_line', 0),
                'content': chunk['content'],
                'success': commented_chunk is not None,
                'commented_content': commented_chunk if commented_chunk else chunk['content']
            }

            chunk_results.append(chunk_result)

            if commented_chunk:
                self.logger.info(f"✓ Chunk {chunk['chunk_num']} processed successfully")
            else:
                self.logger.error(f"✗ Chunk {chunk['chunk_num']} failed after all attempts")

        # Check if we have enough successful chunks
        successful_chunks = [cr for cr in chunk_results if cr['success']]
        failed_chunks = [cr['chunk_num'] for cr in chunk_results if not cr['success']]
        success_rate = len(successful_chunks) / total_chunks

        if success_rate < 0.5:  # At least 50% chunks must succeed (relaxed from 80%)
            self.logger.error(f"Chunked processing failed: only {success_rate:.1%} chunks succeeded")
            self.logger.error(f"Failed chunks: {failed_chunks}")
            return None

        # Reassemble chunks using intelligent reassembly
        self.logger.info(f"Reassembling {len(successful_chunks)} successful chunks (with {len(failed_chunks)} failed chunks using original content)")
        final_content = self.chunker.reassemble_chunks(chunk_results, code_content)

        self.logger.info(f"✓ Chunked processing completed: {len(final_content)} characters")
        return final_content

    def _build_context_aware_prompt(self, chunk: Dict[str, any]) -> str:
        """
        Build an enhanced prompt with full context for chunk processing.

        Args:
            chunk: Context-aware chunk dictionary

        Returns:
            Formatted context-aware prompt
        """
        template = self.prompt_config.get('context_aware_chunked_prompt_template', """🚨 CRITICAL: PRESERVE EXACT CODE - ONLY ADD COMMENTS 🚨

=== FILE OVERVIEW (FOR CONTEXT ONLY) ===
{file_overview}

=== CHUNK CONTEXT ===
File: {filename} (Chunk {chunk_num}/{total_chunks})
Current Section: {current_context}

=== PREVIOUS SECTION CONTEXT (FOR CONTEXT ONLY) ===
{previous_context}

=== NEXT SECTION PREVIEW (FOR CONTEXT ONLY) ===
{next_context}

=== ABSOLUTE REQUIREMENTS ===
❌ DO NOT CREATE any new PROCEDURE, FUNCTION, or CLASS statements
❌ DO NOT ADD any new VFP code lines
❌ DO NOT COMPLETE or EXPAND existing code
❌ DO NOT GENERATE missing procedures or functions
❌ DO NOT MODIFY variable names, function calls, or logic
❌ DO NOT ADD, REMOVE, or CHANGE any existing code lines

✅ ONLY ADD comment lines starting with *
✅ ONLY explain what existing code does
✅ PRESERVE exact spacing, indentation, and formatting

=== YOUR ONLY TASK ===
Add ONLY * comment lines above existing code blocks to explain what they do.
The file overview is for context only - DO NOT try to implement anything mentioned in it.

=== VALIDATION WARNING ===
If you add ANY new VFP keywords (PROCEDURE, FUNCTION, IF, FOR, etc.) beyond what's in the original chunk, your response will be AUTOMATICALLY REJECTED.

=== CURRENT CONTENT TO COMMENT (DO NOT MODIFY) ===
{code_content}

RETURN: Exact original code with ONLY * comment lines added above existing blocks.""".strip())

        return template.format(
            file_overview=chunk.get('file_overview', 'VFP program file'),
            filename=chunk.get('filename', 'unknown'),
            chunk_num=chunk.get('chunk_num', 1),
            total_chunks=chunk.get('total_chunks', 1),
            current_context=chunk.get('current_context', 'Code block'),
            previous_context=chunk.get('previous_context', '(No previous context)'),
            next_context=chunk.get('next_context', '(No next context)'),
            code_content=chunk.get('content', '')
        )

    def _validate_chunk_response(self, original_chunk: str, response_content: str, chunk_num: int) -> Dict[str, any]:
        """
        Basic validation that chunk response preserves original code.

        Args:
            original_chunk: Original chunk content
            response_content: LLM response content
            chunk_num: Chunk number for logging

        Returns:
            Dict with validation result
        """
        try:
            # Basic length check
            if len(response_content.strip()) < len(original_chunk) * 0.8:
                return {'valid': False, 'reason': 'Response too short'}

            # Extract non-comment lines from both (code-only comparison)
            original_code_lines = [line for line in original_chunk.split('\n') if not line.strip().startswith('*')]
            response_code_lines = [line for line in response_content.split('\n') if not line.strip().startswith('*')]

            # Code line count should be similar (allow some flexibility)
            if len(response_code_lines) < len(original_code_lines) * 0.8:
                return {'valid': False, 'reason': f'Too many code lines lost: {len(original_code_lines)} → {len(response_code_lines)}'}

            # Verify comments were actually added
            original_comment_lines = len([line for line in original_chunk.split('\n') if line.strip().startswith('*')])
            response_comment_lines = len([line for line in response_content.split('\n') if line.strip().startswith('*')])

            if response_comment_lines <= original_comment_lines:
                return {'valid': False, 'reason': 'No new comments added'}

            return {'valid': True, 'reason': 'Basic validation passed'}

        except Exception as e:
            self.logger.error(f"Chunk {chunk_num} validation error: {str(e)}")
            return {'valid': False, 'reason': f'Validation error: {str(e)}'}

    def process_file(self, code_content: str, filename: str, relative_path: str, file_size: int) -> Optional[str]:
        """
        Process a VFP file using intelligent strategy selection.

        Args:
            code_content: Original VFP code content
            filename: Name of the file
            relative_path: Relative path of the file
            file_size: Size of the file in bytes

        Returns:
            Commented content if successful, None if failed
        """
        self.logger.info(f"Processing file with LLM: {filename}")
        self.logger.info(f"Original content: {len(code_content)} characters, {len(code_content.splitlines())} lines")

        # Determine processing strategy
        strategy_info = self.determine_processing_strategy(code_content, file_size)

        # Use chunked processing for large files or files that need it
        if strategy_info['needs_chunking'] or self.processing_config.get('enable_chunking', True):
            if strategy_info['needs_chunking']:
                self.logger.info("Using chunked processing due to size/token requirements")
                return self.process_file_chunked(code_content, filename, relative_path, file_size)

        # Use regular processing for smaller files
        self.logger.info(f"Using regular processing (strategy: {strategy_info['strategy']})")
        return self._process_file_regular(code_content, filename, relative_path, file_size, strategy_info['strategy'])

    def _process_file_regular(self, code_content: str, filename: str, relative_path: str,
                             file_size: int, strategy: str) -> Optional[str]:
        """
        Process a VFP file using regular (non-chunked) processing.

        Args:
            code_content: Original VFP code content
            filename: Name of the file
            relative_path: Relative path of the file
            file_size: Size of the file in bytes
            strategy: Processing strategy (small/medium/large)

        Returns:
            Commented content if successful, None if failed
        """
        # Build messages with comprehensive prompts
        system_prompt = self._build_system_prompt()
        user_prompt = self._build_user_prompt(code_content, filename, relative_path, file_size)

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ]

        # Log the prompts (truncated for readability)
        self.logger.debug(f"System prompt length: {len(system_prompt)} characters")
        self.logger.debug(f"User prompt length: {len(user_prompt)} characters")

        # Attempt LLM processing with retries
        for attempt in range(1, self.retry_attempts + 1):
            self.logger.info(f"LLM processing attempt {attempt}/{self.retry_attempts}")

            # Make LLM request with strategy-based timeout
            response_content = self._make_llm_request(messages, attempt, strategy)

            if response_content is None:
                self.logger.warning(f"LLM request failed on attempt {attempt}")
                if attempt < self.retry_attempts:
                    self.logger.info(f"Waiting {self.retry_delay} seconds before retry...")
                    time.sleep(self.retry_delay)
                continue

            # Basic response validation
            if not response_content.strip():
                self.logger.error(f"Empty response from LLM on attempt {attempt}")
                if attempt < self.retry_attempts:
                    self.logger.info("Retrying with stronger emphasis...")
                    # Add more emphasis for retry
                    messages[0]["content"] = system_prompt + "\n\n🚨 RETRY: PREVIOUS RESPONSE WAS INVALID - ENSURE NO CODE IS MODIFIED! 🚨"
                    time.sleep(self.retry_delay)
                continue

            self.logger.info(f"✓ LLM response received: {len(response_content)} characters")
            return response_content

        self.logger.error(f"All {self.retry_attempts} LLM attempts failed for file: {filename}")
        return None

    def validate_llm_response_format(self, response: str, original_content: str) -> bool:
        """
        Basic format validation of LLM response before detailed code validation.

        Args:
            response: LLM response content
            original_content: Original file content

        Returns:
            True if format appears valid, False otherwise
        """
        try:
            # Check if response contains the original content
            original_lines = original_content.strip().splitlines()
            response_lines = response.strip().splitlines()

            # Response should have at least as many lines as original (due to added comments)
            if len(response_lines) < len(original_lines):
                self.logger.warning("Response has fewer lines than original - possible truncation")
                return False

            # Check for VFP comment syntax
            comment_found = False
            for line in response_lines:
                stripped = line.strip()
                if stripped.startswith('*') or '&&' in line:
                    comment_found = True
                    break

            if not comment_found:
                self.logger.warning("No VFP comments found in response")
                return False

            self.logger.info("✓ LLM response format validation passed")
            return True

        except Exception as e:
            self.logger.error(f"Error during format validation: {e}")
            return False

    def get_client_stats(self) -> Dict[str, Any]:
        """
        Get LLM client statistics.

        Returns:
            Dictionary containing client statistics
        """
        return {
            'endpoint': self.endpoint,
            'model': self.model,
            'temperature': self.temperature,
            'max_tokens': self.max_tokens,
            'timeout': self.timeout,
            'retry_attempts': self.retry_attempts
        }

def main():
    """Test the LLM client."""
    print("Testing LLM Client...")

    try:
        # Initialize configuration and client
        from config import ConfigManager
        config = ConfigManager()

        print("Initializing LLM client...")
        client = LLMClient(config)

        # Test with sample VFP code
        sample_code = """LOCAL lcName, lnAge
lcName = "John Doe"
lnAge = 30
IF lnAge > 18
    ? "Adult"
ENDIF
RETURN lcName"""

        print(f"\nTesting with sample VFP code ({len(sample_code)} characters)...")
        print("Sample code:")
        print("-" * 40)
        print(sample_code)
        print("-" * 40)

        # Process the sample
        result = client.process_file(
            sample_code,
            "test_sample.prg",
            "test_sample.prg",
            len(sample_code)
        )

        if result:
            print(f"\n✓ LLM processing successful!")
            print(f"Response length: {len(result)} characters")
            print("Response preview:")
            print("-" * 40)
            print(result[:500] + ("..." if len(result) > 500 else ""))
            print("-" * 40)

            # Test format validation
            is_valid = client.validate_llm_response_format(result, sample_code)
            print(f"Format validation: {'✓ PASSED' if is_valid else '✗ FAILED'}")
        else:
            print("✗ LLM processing failed")

        # Print client stats
        stats = client.get_client_stats()
        print(f"\nClient Statistics:")
        for key, value in stats.items():
            print(f"  {key}: {value}")

    except Exception as e:
        print(f"Error testing LLM client: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()