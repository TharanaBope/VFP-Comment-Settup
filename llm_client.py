"""
LLM Client Module - STRICT CODE PRESERVATION FOCUS
=================================================
This module handles communication with the local LLM (GPTOSS20B via LM Studio)
with MAXIMUM emphasis on code preservation. Every prompt includes multiple
warnings and validation requirements to prevent code modification.

CRITICAL FEATURES:
- Multiple explicit warnings in system and user prompts
- Response validation to ensure code preservation
- Retry logic with stronger emphasis on preservation
- Comprehensive logging of all LLM interactions
- Failure handling that prioritizes safety over success
"""

import requests
import json
import logging
import time
from typing import Optional, Dict, Any
from config import ConfigManager

class LLMClient:
    """
    LLM client with ABSOLUTE focus on code preservation.
    
    This client is designed to communicate with a local LLM running on LM Studio
    with explicit instructions to NEVER modify original VFP code.
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
        
        # Validate LLM configuration
        if not self.config.validate_llm_config():
            raise ValueError("Invalid LLM configuration")
        
        self.endpoint = self.llm_config['endpoint']
        self.model = self.llm_config['model']
        self.temperature = self.llm_config.get('temperature', 0.1)
        self.max_tokens = self.llm_config.get('max_tokens', 4000)
        self.timeout = self.llm_config.get('timeout', 120)
        self.retry_attempts = self.llm_config.get('retry_attempts', 3)
        self.retry_delay = self.llm_config.get('retry_delay', 5)
        
        self.logger.info(f"Initialized LLM client: {self.endpoint}")
        self.logger.info(f"Model: {self.model}, Temperature: {self.temperature}")
        
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
        Build the system prompt with MAXIMUM emphasis on code preservation.
        
        Returns:
            System prompt string with multiple warnings
        """
        return self.prompt_config.get('system_prompt', """You are an expert Visual FoxPro (VFP) programmer tasked with adding comprehensive comments to legacy VFP code.

🚨 CRITICAL REQUIREMENT - READ CAREFULLY 🚨
YOU MUST NEVER MODIFY THE ORIGINAL CODE IN ANY WAY!
- DO NOT change variable names
- DO NOT change function calls
- DO NOT change logic conditions
- DO NOT change string values
- DO NOT change numeric values
- DO NOT add, remove, or modify ANY code lines
- ONLY ADD COMMENT LINES (starting with * or &&)

Your ONLY task is to add explanatory comments while keeping the original code 100% intact.

Comment Guidelines:
1. Add a comprehensive header comment explaining the file's purpose
2. Include the file's location path in the header
3. Add comments before complex logic blocks using (* comment)
4. Use inline comments (&&) for single-line clarifications
5. Document input parameters, return values, and database operations
6. Explain business logic and error handling patterns

Comment Syntax:
- Full-line comments: * This is a full-line comment
- Inline comments: SOME_CODE && This explains the code

🚨 VALIDATION REMINDER 🚨
Your response will be validated to ensure NO original code was changed.
If ANY original code is modified, your response will be REJECTED.

Return the EXACT original code with ONLY comments added.""")
    
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
        template = self.prompt_config.get('user_prompt_template', """🚨 CRITICAL: DO NOT MODIFY ANY ORIGINAL CODE - ONLY ADD COMMENTS 🚨

Please add comprehensive comments to this Visual FoxPro code file:

File: {filename}
Location: {relative_path}
Size: {file_size} bytes

INSTRUCTIONS:
1. Add a header comment block explaining the file's purpose
2. Add section comments for logical code blocks  
3. Add inline comments for complex operations
4. Document any database tables, parameters, or dependencies
5. Keep ALL original code exactly as provided

🚨 VALIDATION WARNING 🚨
The original code will be extracted and compared with your response.
ANY changes to the original code will cause REJECTION of your response.

Original VFP Code:
```foxpro
{code_content}
```

Return the same code with comprehensive comments added in VFP syntax.""")
        
        return template.format(
            filename=filename,
            relative_path=relative_path,
            file_size=file_size,
            code_content=code_content
        )
    
    def _make_llm_request(self, messages: list, attempt: int = 1) -> Optional[str]:
        """
        Make a request to the LLM with comprehensive error handling.
        
        Args:
            messages: List of messages to send to LLM
            attempt: Current attempt number for logging
            
        Returns:
            LLM response content, or None if failed
        """
        payload = {
            "model": self.model,
            "messages": messages,
            "temperature": self.temperature,
            "max_tokens": self.max_tokens
        }
        
        try:
            self.logger.info(f"Making LLM request (attempt {attempt})")
            self.logger.debug(f"Request payload: {json.dumps(payload, indent=2)}")
            
            start_time = time.time()
            
            response = requests.post(
                self.endpoint,
                json=payload,
                timeout=self.timeout,
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
    
    def process_file(self, code_content: str, filename: str, relative_path: str, file_size: int) -> Optional[str]:
        """
        Process a VFP file using the LLM with multiple validation layers.
        
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
        
        # Build messages with MAXIMUM code preservation emphasis
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
            
            # Make LLM request
            response_content = self._make_llm_request(messages, attempt)
            
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