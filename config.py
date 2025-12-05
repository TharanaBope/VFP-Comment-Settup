"""
Configuration Management for VFP Commenting Tool
================================================
Handles loading and validation of configuration settings with emphasis on
code preservation settings and safety parameters.

CRITICAL: All configuration defaults are set to maximize code preservation
and minimize risk of any modifications to original VFP code.
"""

import json
import logging
from pathlib import Path
from typing import Dict, Any, Optional
import os

class ConfigManager:
    """Configuration manager with strict validation and code preservation focus."""
    
    def __init__(self, config_file: Optional[str] = None):
        """
        Initialize configuration manager.
        
        Args:
            config_file: Path to configuration file, defaults to 'config.json'
        """
        self.config_file = config_file or 'config.json'
        self.logger = self._setup_logger()
        self.config = self._load_default_config()
        
        # Load user config if file exists
        if os.path.exists(self.config_file):
            self._load_config_file()
        else:
            self.logger.info(f"Config file {self.config_file} not found, using defaults")
            self._save_default_config()
    
    def _setup_logger(self) -> logging.Logger:
        """Setup logging for configuration operations."""
        logger = logging.getLogger('config')
        logger.setLevel(logging.INFO)
        
        if not logger.handlers:
            handler = logging.StreamHandler()
            formatter = logging.Formatter(
                '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
            )
            handler.setFormatter(formatter)
            logger.addHandler(handler)
            
        return logger
    
    def _load_default_config(self) -> Dict[str, Any]:
        """
        Load default configuration with maximum safety settings for code preservation.
        
        Returns:
            Dictionary containing default configuration
        """
        return {
            "llm": {
                "endpoint": "http://127.0.0.1:1234/v1/chat/completions",
                "model": "local-model",
                "temperature": 0.1,  # Low temperature for consistency
                "max_tokens": 4000,
                "timeout": 120,  # Increased timeout for safety
                "retry_attempts": 3,
                "retry_delay": 5
            },
            "processing": {
                "root_directory": "D:/Medical Wizard/VFP Entire Codebase/VFP Comment Settup/VFP_Files_Copy",
                "file_extensions": [".prg", ".PRG", ".spr", ".SPR", ".sc2", ".SC2", ".fr2", ".FR2", ".mn2", ".MN2", ".lb2", ".LB2"],
                "output_suffix": "_commented",
                "batch_size": 1,  # Process one file at a time for maximum safety
                "retry_attempts": 3,
                "preserve_structure": True,  # CRITICAL: Always preserve structure
                "skip_patterns": ["_commented", "_pretty", "_backup", "_temp"],
                "parallel_workers": 1,  # Single-threaded for maximum safety
                "validate_before_save": True,  # CRITICAL: Always validate
                "create_backups": True,  # Create backups before processing
                "strict_validation": True  # CRITICAL: Strictest validation
            },
            "prompts": {
                "system_prompt": self._get_default_system_prompt(),
                "user_prompt_template": self._get_default_user_prompt_template(),
                "comment_style": "comprehensive",
                "code_preservation": "strict",  # CRITICAL: Strictest preservation mode
                "max_retries_for_validation": 3  # Retry if validation fails
            },
            "logging": {
                "log_level": "INFO",
                "log_file": "vfp_commenting.log",
                "progress_file": "processing_progress.json",
                "enable_console_logging": True,
                "enable_file_logging": True,
                "log_validation_details": True  # CRITICAL: Log all validation steps
            },
            "safety": {
                "require_code_hash_match": True,  # CRITICAL: Require exact hash match
                "require_line_count_match": True,  # CRITICAL: Require exact line count
                "require_manual_confirmation": False,  # Set to True for extra safety
                "max_file_size_mb": 10,  # Skip very large files
                "backup_before_processing": True,  # CRITICAL: Always backup
                "validate_vfp_syntax": True,  # Validate VFP syntax in output
                "halt_on_validation_failure": True  # CRITICAL: Stop if validation fails
            }
        }
    
    def _get_default_system_prompt(self) -> str:
        """
        Get the default system prompt with maximum emphasis on code preservation.
        
        Returns:
            System prompt string with multiple warnings about code preservation
        """
        return """You are an expert Visual FoxPro (VFP) programmer tasked with adding comprehensive comments to legacy VFP code.

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

Return the EXACT original code with ONLY comments added."""
    
    def _get_default_user_prompt_template(self) -> str:
        """
        Get the default user prompt template with code preservation emphasis.
        
        Returns:
            User prompt template string
        """
        return """🚨 CRITICAL: DO NOT MODIFY ANY ORIGINAL CODE - ONLY ADD COMMENTS 🚨

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

Return the same code with comprehensive comments added in VFP syntax."""
    
    def _load_config_file(self) -> None:
        """Load configuration from file and merge with defaults."""
        try:
            with open(self.config_file, 'r', encoding='utf-8') as f:
                user_config = json.load(f)
            
            # Recursively merge user config with defaults
            self.config = self._merge_configs(self.config, user_config)
            self.logger.info(f"Loaded configuration from {self.config_file}")
            
            # Validate critical safety settings
            self._validate_safety_settings()
            
        except json.JSONDecodeError as e:
            self.logger.error(f"Invalid JSON in config file {self.config_file}: {e}")
            self.logger.info("Using default configuration")
        except Exception as e:
            self.logger.error(f"Error loading config file {self.config_file}: {e}")
            self.logger.info("Using default configuration")
    
    def _merge_configs(self, default: Dict[str, Any], user: Dict[str, Any]) -> Dict[str, Any]:
        """
        Recursively merge user configuration with defaults.
        
        Args:
            default: Default configuration dictionary
            user: User configuration dictionary
            
        Returns:
            Merged configuration dictionary
        """
        merged = default.copy()
        
        for key, value in user.items():
            if key in merged and isinstance(merged[key], dict) and isinstance(value, dict):
                merged[key] = self._merge_configs(merged[key], value)
            else:
                merged[key] = value
                
        return merged
    
    def _validate_safety_settings(self) -> None:
        """
        Validate that critical safety settings are properly configured.
        Logs warnings if safety settings are disabled.
        """
        safety = self.config.get('safety', {})
        processing = self.config.get('processing', {})
        
        critical_settings = [
            ('require_code_hash_match', True, "Code hash validation"),
            ('require_line_count_match', True, "Line count validation"),
            ('backup_before_processing', True, "Backup creation"),
            ('validate_vfp_syntax', True, "VFP syntax validation"),
            ('halt_on_validation_failure', True, "Halt on validation failure")
        ]
        
        for setting, expected, description in critical_settings:
            if not safety.get(setting, expected):
                self.logger.warning(f"SAFETY WARNING: {description} is DISABLED")
        
        if processing.get('validate_before_save', True) is False:
            self.logger.warning("SAFETY WARNING: Pre-save validation is DISABLED")
        
        if processing.get('strict_validation', True) is False:
            self.logger.warning("SAFETY WARNING: Strict validation is DISABLED")
    
    def _save_default_config(self) -> None:
        """Save the default configuration to file."""
        try:
            with open(self.config_file, 'w', encoding='utf-8') as f:
                json.dump(self.config, f, indent=2, ensure_ascii=False)
            self.logger.info(f"Saved default configuration to {self.config_file}")
        except Exception as e:
            self.logger.error(f"Error saving default config to {self.config_file}: {e}")
    
    def get(self, key_path: str, default: Any = None) -> Any:
        """
        Get configuration value using dot notation.
        
        Args:
            key_path: Dot-separated path to configuration value (e.g., 'llm.temperature')
            default: Default value if key not found
            
        Returns:
            Configuration value or default
        """
        keys = key_path.split('.')
        value = self.config
        
        for key in keys:
            if isinstance(value, dict) and key in value:
                value = value[key]
            else:
                return default
                
        return value
    
    def set(self, key_path: str, value: Any) -> None:
        """
        Set configuration value using dot notation.
        
        Args:
            key_path: Dot-separated path to configuration value
            value: Value to set
        """
        keys = key_path.split('.')
        target = self.config
        
        for key in keys[:-1]:
            if key not in target or not isinstance(target[key], dict):
                target[key] = {}
            target = target[key]
            
        target[keys[-1]] = value
    
    def save(self, file_path: Optional[str] = None) -> bool:
        """
        Save current configuration to file.
        
        Args:
            file_path: Optional path to save to, defaults to config_file
            
        Returns:
            True if saved successfully, False otherwise
        """
        save_path = file_path or self.config_file
        
        try:
            with open(save_path, 'w', encoding='utf-8') as f:
                json.dump(self.config, f, indent=2, ensure_ascii=False)
            self.logger.info(f"Configuration saved to {save_path}")
            return True
        except Exception as e:
            self.logger.error(f"Error saving configuration to {save_path}: {e}")
            return False
    
    def validate_llm_config(self) -> bool:
        """
        Validate LLM configuration settings.
        
        Returns:
            True if configuration is valid, False otherwise
        """
        llm_config = self.config.get('llm', {})
        
        required_fields = ['endpoint', 'model', 'max_tokens']
        for field in required_fields:
            if field not in llm_config:
                self.logger.error(f"Missing required LLM config field: {field}")
                return False
        
        # Validate endpoint format
        endpoint = llm_config['endpoint']
        if not endpoint.startswith(('http://', 'https://')):
            self.logger.error(f"Invalid LLM endpoint format: {endpoint}")
            return False
        
        # Validate numeric fields
        if llm_config.get('temperature', 0) < 0 or llm_config.get('temperature', 0) > 2:
            self.logger.warning("LLM temperature should be between 0 and 2")
        
        if llm_config.get('max_tokens', 0) <= 0:
            self.logger.error("LLM max_tokens must be positive")
            return False
        
        return True
    
    def get_processing_config(self) -> Dict[str, Any]:
        """Get processing configuration with validation."""
        processing = self.config.get('processing', {})
        
        # Validate root directory
        root_dir = processing.get('root_directory')
        if root_dir and not Path(root_dir).exists():
            self.logger.warning(f"Root directory does not exist: {root_dir}")
        
        return processing
    
    def print_config_summary(self) -> None:
        """Print a summary of current configuration settings."""
        print("\n" + "="*60)
        print("VFP COMMENTING TOOL CONFIGURATION")
        print("="*60)
        
        # LLM Settings
        llm = self.config.get('llm', {})
        print(f"LLM Endpoint: {llm.get('endpoint', 'Not set')}")
        print(f"Model: {llm.get('model', 'Not set')}")
        print(f"Temperature: {llm.get('temperature', 'Not set')}")
        print(f"Max Tokens: {llm.get('max_tokens', 'Not set')}")
        
        # Processing Settings
        processing = self.config.get('processing', {})
        print(f"\nRoot Directory: {processing.get('root_directory', 'Not set')}")
        print(f"File Extensions: {processing.get('file_extensions', [])}")
        print(f"Output Suffix: {processing.get('output_suffix', 'Not set')}")
        print(f"Batch Size: {processing.get('batch_size', 'Not set')}")
        
        # Safety Settings
        safety = self.config.get('safety', {})
        print(f"\n🛡️  SAFETY SETTINGS:")
        print(f"Code Hash Validation: {'✓ ENABLED' if safety.get('require_code_hash_match') else '✗ DISABLED'}")
        print(f"Line Count Validation: {'✓ ENABLED' if safety.get('require_line_count_match') else '✗ DISABLED'}")
        print(f"Backup Creation: {'✓ ENABLED' if safety.get('backup_before_processing') else '✗ DISABLED'}")
        print(f"Strict Validation: {'✓ ENABLED' if processing.get('strict_validation') else '✗ DISABLED'}")
        print(f"Halt on Validation Failure: {'✓ ENABLED' if safety.get('halt_on_validation_failure') else '✗ DISABLED'}")
        
        print("="*60)

def main():
    """Test the configuration manager."""
    print("Testing Configuration Manager...")
    
    config = ConfigManager()
    config.print_config_summary()
    
    # Test validation
    if config.validate_llm_config():
        print("\n✓ LLM configuration is valid")
    else:
        print("\n✗ LLM configuration validation failed")
    
    # Test getting and setting values
    temp = config.get('llm.temperature', 0.1)
    print(f"\nCurrent temperature: {temp}")
    
    config.set('llm.temperature', 0.05)
    new_temp = config.get('llm.temperature')
    print(f"New temperature: {new_temp}")

if __name__ == "__main__":
    main()