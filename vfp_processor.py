"""
VFP Processor Module - STRICT CODE PRESERVATION
===============================================
This module handles the processing of Visual FoxPro files with ABSOLUTE
commitment to preserving original code. Any modification to original code
will trigger immediate failure and halt processing.

CRITICAL SAFETY FEATURES:
- Multiple validation layers before and after LLM processing
- Hash-based code integrity verification
- Line-by-line code comparison
- Atomic file operations with rollback capability
- Comprehensive logging of all validation steps
"""

import logging
import os
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from utils import CodePreservationValidator, create_backup_file, safe_file_write
from config import ConfigManager

class VFPProcessor:
    """
    VFP file processor with MAXIMUM emphasis on code preservation.
    
    This class implements multiple safety layers to ensure that original
    VFP code is never modified during the commenting process.
    """
    
    def __init__(self, config_manager: ConfigManager):
        """
        Initialize the VFP processor with configuration.
        
        Args:
            config_manager: Configuration manager instance
        """
        self.config = config_manager
        self.validator = CodePreservationValidator()
        self.logger = self._setup_logger()
        
        # Load processing configuration
        self.processing_config = self.config.get_processing_config()
        self.safety_config = self.config.get('safety', {})
        
        # Validate critical safety settings
        self._validate_safety_configuration()
    
    def _setup_logger(self) -> logging.Logger:
        """Setup comprehensive logging for VFP processing."""
        logger = logging.getLogger('vfp_processor')
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
            log_file = self.config.get('logging.log_file', 'vfp_processing.log')
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
    
    def _validate_safety_configuration(self) -> None:
        """
        Validate that essential safety settings are properly configured.
        Warns about disabled safety features but allows processing to continue.
        """
        # Essential safety settings that should remain enabled
        essential_safety_settings = [
            ('require_code_hash_match', 'Code hash validation')
        ]

        # Optional safety settings that can be disabled
        optional_safety_settings = [
            ('require_line_count_match', 'Line count validation'),
            ('backup_before_processing', 'Backup creation'),
            ('halt_on_validation_failure', 'Halt on validation failure')
        ]

        # Check essential settings
        for setting, description in essential_safety_settings:
            if not self.safety_config.get(setting, True):
                error_msg = f"ESSENTIAL SAFETY FEATURE DISABLED: {description}"
                self.logger.critical(error_msg)
                raise ValueError(error_msg)

        # Warn about optional settings (only once during initialization)
        disabled_features = []
        for setting, description in optional_safety_settings:
            if not self.safety_config.get(setting, True):
                disabled_features.append(description)

        if disabled_features:
            self.logger.warning(f"Optional safety features disabled: {', '.join(disabled_features)}")

        self.logger.info("✓ Safety configuration validated")
    
    def read_vfp_file(self, file_path: str) -> Optional[str]:
        """
        Safely read a VFP file with encoding detection and validation.
        
        Args:
            file_path: Path to the VFP file to read
            
        Returns:
            File content as string, or None if reading failed
        """
        try:
            file_path_obj = Path(file_path)
            
            # Validate file exists and is readable
            if not file_path_obj.exists():
                self.logger.error(f"File does not exist: {file_path}")
                return None
            
            if not file_path_obj.is_file():
                self.logger.error(f"Path is not a file: {file_path}")
                return None
            
            # Check file size limits
            max_size_mb = self.safety_config.get('max_file_size_mb', 10)
            file_size = file_path_obj.stat().st_size
            max_size_bytes = max_size_mb * 1024 * 1024
            
            if file_size > max_size_bytes:
                self.logger.warning(f"File exceeds size limit ({max_size_mb}MB): {file_path}")
                return None
            
            # Try reading with different encodings
            encodings = ['utf-8', 'cp1252', 'latin-1', 'utf-8-sig']
            
            for encoding in encodings:
                try:
                    with open(file_path, 'r', encoding=encoding) as f:
                        content = f.read()
                    
                    self.logger.info(f"Successfully read file with {encoding} encoding: {file_path}")
                    self.logger.info(f"File size: {file_size} bytes, {len(content.splitlines())} lines")
                    
                    return content
                    
                except UnicodeDecodeError:
                    continue
                except Exception as e:
                    self.logger.error(f"Error reading file with {encoding}: {e}")
                    continue
            
            self.logger.error(f"Could not read file with any supported encoding: {file_path}")
            return None
            
        except Exception as e:
            self.logger.error(f"Unexpected error reading file {file_path}: {e}")
            return None
    
    def validate_original_content(self, content: str, file_path: str) -> bool:
        """
        Validate original file content before processing.
        
        Args:
            content: File content to validate
            file_path: Path to the file for context
            
        Returns:
            True if content is valid for processing, False otherwise
        """
        try:
            # Basic content validation
            if not content or not content.strip():
                self.logger.warning(f"File is empty or contains only whitespace: {file_path}")
                return False
            
            # Check for suspicious content that might indicate already processed file
            if '_commented' in Path(file_path).name:
                self.logger.info(f"Skipping already commented file: {file_path}")
                return False
            
            # Basic VFP syntax validation if enabled
            if self.safety_config.get('validate_vfp_syntax', True):
                is_valid, warnings = self.validator.validate_vfp_syntax(content)
                if warnings:
                    for warning in warnings:
                        self.logger.warning(f"VFP syntax warning in {file_path}: {warning}")
            
            # Calculate and log content hash for tracking
            content_hash = self.validator.calculate_code_hash(content)
            self.logger.info(f"Original content hash for {file_path}: {content_hash}")
            
            return True
            
        except Exception as e:
            self.logger.error(f"Error validating original content for {file_path}: {e}")
            return False
    
    def process_file_with_llm(self, file_info: Dict[str, str], llm_client) -> Optional[str]:
        """
        Process a single VFP file with the LLM, with full validation.
        
        Args:
            file_info: Dictionary containing file information
            llm_client: LLM client instance for processing
            
        Returns:
            Commented content if successful, None if failed
        """
        file_path = file_info['full_path']
        filename = file_info['filename']
        relative_path = file_info['relative_path']
        
        self.logger.info(f"Starting processing of file: {file_path}")
        
        try:
            # Step 1: Read original file
            original_content = self.read_vfp_file(file_path)
            if original_content is None:
                self.logger.error(f"Failed to read file: {file_path}")
                return None
            
            # Step 2: Validate original content
            if not self.validate_original_content(original_content, file_path):
                self.logger.error(f"Original content validation failed: {file_path}")
                return None
            
            # Step 3: Create backup if enabled
            backup_path = None
            if self.safety_config.get('backup_before_processing', True):
                backup_path = create_backup_file(file_path)
                if backup_path:
                    self.logger.info(f"Created backup: {backup_path}")
                else:
                    self.logger.warning(f"Failed to create backup for: {file_path}")
            
            # Step 4: Calculate original content hash for validation
            original_hash = self.validator.calculate_code_hash(original_content)
            self.logger.info(f"Original code hash: {original_hash}")
            
            # Step 5: Process with LLM with retries
            max_retries = self.config.get('prompts.max_retries_for_validation', 3)
            commented_content = None
            
            for attempt in range(1, max_retries + 1):
                self.logger.info(f"LLM processing attempt {attempt}/{max_retries}")
                
                try:
                    # Call LLM to add comments
                    commented_content = llm_client.process_file(
                        original_content, filename, relative_path, file_info.get('file_size', 0)
                    )
                    
                    if commented_content is None:
                        self.logger.warning(f"LLM returned None for attempt {attempt}")
                        continue
                    
                    # Step 6: CRITICAL VALIDATION - Ensure code preservation
                    is_valid, errors = self.validator.validate_code_preservation(
                        original_content, commented_content
                    )
                    
                    if is_valid:
                        self.logger.info(f"✓ Code preservation validation PASSED on attempt {attempt}")
                        break
                    else:
                        self.logger.critical(f"✗ Code preservation validation FAILED on attempt {attempt}")
                        for error in errors:
                            self.logger.critical(f"  Validation error: {error}")
                        
                        if attempt == max_retries:
                            self.logger.critical(f"ABORTING: All {max_retries} attempts failed validation")
                            return None
                        
                        # Generate diff report for debugging
                        if self.config.get('logging.log_validation_details', True):
                            diff_report = self.validator.generate_diff_report(original_content, commented_content)
                            self.logger.debug(f"Diff report for attempt {attempt}:\n{diff_report}")
                        
                        commented_content = None  # Reset for retry
                        
                except Exception as e:
                    self.logger.error(f"Error during LLM processing attempt {attempt}: {e}")
                    if attempt == max_retries:
                        return None
                    continue
            
            if commented_content is None:
                self.logger.critical(f"PROCESSING FAILED: Could not generate valid commented version after {max_retries} attempts")
                return None
            
            # Step 7: Final validation before returning
            final_hash = self.validator.calculate_code_hash(commented_content)
            if original_hash != final_hash:
                self.logger.critical(f"CRITICAL: Final hash validation failed!")
                self.logger.critical(f"  Original hash: {original_hash}")
                self.logger.critical(f"  Final hash:    {final_hash}")
                return None
            
            self.logger.info(f"✓ File processing completed successfully: {file_path}")
            self.logger.info(f"✓ Code preservation verified with hash: {final_hash}")
            
            return commented_content
            
        except Exception as e:
            self.logger.critical(f"CRITICAL ERROR during file processing {file_path}: {e}")
            return None
    
    def save_commented_file(self, file_info: Dict[str, str], commented_content: str, original_content: str) -> bool:
        """
        Safely save the commented file with full validation.
        
        Args:
            file_info: Dictionary containing file information
            commented_content: The commented content to save
            original_content: Original content for validation
            
        Returns:
            True if saved successfully, False otherwise
        """
        output_path = file_info['output_path']
        
        try:
            self.logger.info(f"Saving commented file: {output_path}")
            
            # Final pre-save validation if enabled
            if self.processing_config.get('validate_before_save', True):
                is_valid, errors = self.validator.validate_code_preservation(
                    original_content, commented_content
                )
                
                if not is_valid:
                    self.logger.critical("REFUSING TO SAVE: Pre-save validation failed")
                    for error in errors:
                        self.logger.critical(f"  {error}")
                    return False
                
                self.logger.info("✓ Pre-save validation passed")
            
            # Use safe file write with validation
            success = safe_file_write(output_path, commented_content, original_content)
            
            if success:
                self.logger.info(f"✓ Successfully saved commented file: {output_path}")
                
                # Verify the saved file by reading it back
                saved_content = self.read_vfp_file(output_path)
                if saved_content:
                    is_valid, errors = self.validator.validate_code_preservation(
                        original_content, saved_content
                    )
                    if is_valid:
                        self.logger.info("✓ Post-save verification passed")
                        return True
                    else:
                        self.logger.critical("✗ Post-save verification FAILED")
                        for error in errors:
                            self.logger.critical(f"  {error}")
                        
                        # Delete the invalid file
                        try:
                            os.remove(output_path)
                            self.logger.info(f"Deleted invalid file: {output_path}")
                        except Exception as e:
                            self.logger.error(f"Could not delete invalid file: {e}")
                        
                        return False
                else:
                    self.logger.error("Could not read back saved file for verification")
                    return False
            else:
                self.logger.error(f"Failed to save file: {output_path}")
                return False
                
        except Exception as e:
            self.logger.critical(f"CRITICAL ERROR saving file {output_path}: {e}")
            return False
    
    def should_process_file(self, file_info: Dict[str, str]) -> bool:
        """
        Determine if a file should be processed based on various criteria.
        
        Args:
            file_info: Dictionary containing file information
            
        Returns:
            True if file should be processed, False otherwise
        """
        file_path = file_info['full_path']
        output_path = file_info['output_path']
        filename = file_info['filename']
        
        # Check if output file already exists
        if os.path.exists(output_path):
            self.logger.info(f"Skipping - commented version already exists: {output_path}")
            return False
        
        # Check file size limits
        file_size = file_info.get('file_size', 0)
        max_size_mb = self.safety_config.get('max_file_size_mb', 10)
        max_size_bytes = max_size_mb * 1024 * 1024
        
        if file_size > max_size_bytes:
            self.logger.warning(f"Skipping - file exceeds size limit ({max_size_mb}MB): {file_path}")
            return False
        
        # Check skip patterns
        skip_patterns = self.processing_config.get('skip_patterns', [])
        for pattern in skip_patterns:
            if pattern in filename:
                self.logger.info(f"Skipping - filename contains skip pattern '{pattern}': {filename}")
                return False
        
        # Check file accessibility
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                f.read(1)  # Try to read first character
        except Exception as e:
            self.logger.warning(f"Skipping - file not accessible: {file_path} ({e})")
            return False
        
        return True
    
    def get_processing_stats(self) -> Dict[str, int]:
        """
        Get current processing statistics.
        
        Returns:
            Dictionary containing processing statistics
        """
        # This would be implemented with actual tracking in a real implementation
        return {
            'files_processed': 0,
            'files_successful': 0,
            'files_failed': 0,
            'files_skipped': 0,
            'validation_failures': 0
        }

def main():
    """Test the VFP processor."""
    print("Testing VFP Processor...")
    
    # Initialize configuration
    from config import ConfigManager
    config = ConfigManager()
    
    # Initialize processor
    processor = VFPProcessor(config)
    
    # Test with a sample file info (would normally come from file scanner)
    test_file_info = {
        'full_path': r'D:\Medical Wizard\VFP Entire Codebase\VFP Comment Settup\test_sample.prg',
        'relative_path': 'test_sample.prg',
        'directory': r'D:\Medical Wizard\VFP Entire Codebase\VFP Comment Settup',
        'filename': 'test_sample.prg',
        'output_path': r'D:\Medical Wizard\VFP Entire Codebase\VFP Comment Settup\test_sample_commented.prg',
        'file_size': 1024
    }
    
    # Test file processing readiness checks
    print(f"\nTesting processing readiness...")
    should_process = processor.should_process_file(test_file_info)
    print(f"Should process file: {should_process}")
    
    # Test file reading (if file exists)
    test_path = test_file_info['full_path']
    if os.path.exists(test_path):
        content = processor.read_vfp_file(test_path)
        if content:
            print(f"Successfully read test file: {len(content)} characters")
            
            # Test validation
            is_valid = processor.validate_original_content(content, test_path)
            print(f"Content validation result: {is_valid}")
        else:
            print("Could not read test file")
    else:
        print(f"Test file does not exist: {test_path}")
    
    print("\nVFP Processor test completed.")

if __name__ == "__main__":
    main()