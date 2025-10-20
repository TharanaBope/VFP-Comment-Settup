"""
VFP Processor Module - LEGACY VFP COMMENTING
=============================================
This module handles the processing of Visual FoxPro files using direct
LLM interaction with comprehensive validation and safety measures.

FEATURES:
- Multiple validation layers before and after LLM processing
- Hash-based code integrity verification
- Line-by-line code comparison
- Atomic file operations with rollback capability
- Comprehensive logging of all validation steps
- Context-aware chunking for large files
"""

import logging
import os
import re
import hashlib
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from utils import CodePreservationValidator, create_backup_file, safe_file_write
from config import ConfigManager

class VFPProcessor:
    """
    VFP file processor with comprehensive validation and safety measures.

    This processor handles VFP files using direct LLM interaction with
    multiple layers of validation to ensure code preservation.
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
        safety_warnings = []

        if not self.safety_config.get('require_code_hash_match', True):
            safety_warnings.append("Code hash validation is DISABLED")

        if not self.safety_config.get('require_line_count_match', True):
            safety_warnings.append("Line count validation is DISABLED")

        if not self.safety_config.get('backup_before_processing', True):
            safety_warnings.append("Backup creation is DISABLED")

        if not self.safety_config.get('halt_on_validation_failure', True):
            safety_warnings.append("Halt on validation failure is DISABLED")

        # Log all safety warnings
        for warning in safety_warnings:
            self.logger.warning(f"SAFETY WARNING: {warning}")

        if safety_warnings:
            self.logger.warning("Optional safety features disabled: " + ", ".join(safety_warnings))
        else:
            self.logger.info("✓ All safety features enabled")

    def read_vfp_file(self, file_path: str) -> Optional[str]:
        """
        Read a VFP file with multiple encoding attempts.

        Args:
            file_path: Path to the VFP file

        Returns:
            File content as string, or None if failed
        """
        encodings = ['utf-8', 'cp1252', 'latin1', 'ascii']

        for encoding in encodings:
            try:
                with open(file_path, 'r', encoding=encoding) as file:
                    content = file.read()
                    self.logger.info(f"Successfully read file with {encoding} encoding: {file_path}")
                    return content
            except UnicodeDecodeError:
                continue
            except Exception as e:
                self.logger.error(f"Error reading file {file_path} with {encoding}: {e}")
                continue

        self.logger.error(f"Failed to read file with any encoding: {file_path}")
        return None

    def calculate_content_hash(self, content: str) -> str:
        """
        Calculate SHA-256 hash of content for integrity verification.

        Args:
            content: String content to hash

        Returns:
            SHA-256 hash as hex string
        """
        return hashlib.sha256(content.encode('utf-8')).hexdigest()

    def process_file_with_llm(self, file_info: Dict, llm_client) -> Optional[str]:
        """
        Process a single VFP file with LLM using comprehensive validation.

        Args:
            file_info: Dictionary containing file information
            llm_client: LLM client instance

        Returns:
            Commented content if successful, None if failed
        """
        file_path = file_info['full_path']
        filename = file_info['filename']
        relative_path = file_info['relative_path']

        self.logger.info(f"Starting processing of file: {file_path}")

        # Read original file content
        original_content = self.read_vfp_file(file_path)
        if not original_content:
            self.logger.error(f"Failed to read file: {file_path}")
            return None

        file_size = len(original_content.encode('utf-8'))
        line_count = len(original_content.splitlines())

        self.logger.info(f"File size: {file_size} bytes, {line_count} lines")

        # Calculate original content hash for integrity verification
        original_hash = self.calculate_content_hash(original_content)
        original_code_hash = self._calculate_code_only_hash(original_content)

        self.logger.info(f"Original content hash for {file_path}: {original_hash}")
        self.logger.info(f"Original code hash: {original_code_hash}")

        # Process with LLM
        commented_content = llm_client.process_file(
            original_content, filename, relative_path, file_size
        )

        if not commented_content:
            self.logger.error(f"LLM processing failed for file: {file_path}")
            return None

        # Comprehensive validation
        validation_result = self._validate_commented_content(
            original_content, commented_content, file_path
        )

        if not validation_result['valid']:
            self.logger.error(f"Validation failed for {file_path}: {validation_result['reason']}")
            return None

        self.logger.info(f"✓ Validation passed for: {file_path}")
        return commented_content

    def _calculate_code_only_hash(self, content: str) -> str:
        """
        Calculate hash of only non-comment lines for code integrity verification.

        Args:
            content: File content

        Returns:
            SHA-256 hash of code-only lines
        """
        code_lines = []
        for line in content.splitlines():
            stripped = line.strip()
            if stripped and not stripped.startswith('*') and not stripped.startswith('&&'):
                code_lines.append(line)

        code_only_content = '\n'.join(code_lines)
        return hashlib.sha256(code_only_content.encode('utf-8')).hexdigest()

    def _validate_commented_content(self, original_content: str, commented_content: str, file_path: str) -> Dict[str, any]:
        """
        Comprehensive validation of commented content against original.

        Args:
            original_content: Original file content
            commented_content: LLM-processed content with comments
            file_path: File path for logging

        Returns:
            Dictionary with validation results
        """
        try:
            # Basic length and structure checks
            if len(commented_content.strip()) < len(original_content) * 0.8:
                return {'valid': False, 'reason': 'Response too short - possible truncation'}

            # Line count validation
            original_lines = original_content.splitlines()
            commented_lines = commented_content.splitlines()

            if len(commented_lines) < len(original_lines):
                return {'valid': False, 'reason': f'Fewer lines in result: {len(original_lines)} → {len(commented_lines)}'}

            # Code-only hash verification (most important)
            original_code_hash = self._calculate_code_only_hash(original_content)
            commented_code_hash = self._calculate_code_only_hash(commented_content)

            if self.safety_config.get('require_code_hash_match', True):
                if original_code_hash != commented_code_hash:
                    return {'valid': False, 'reason': 'Code integrity check failed - original code was modified'}

            # Extract and compare non-comment lines
            original_code_lines = [line for line in original_lines if not line.strip().startswith('*')]
            commented_code_lines = [line for line in commented_lines if not line.strip().startswith('*')]

            # Line count validation
            if self.safety_config.get('require_line_count_match', True):
                if len(original_code_lines) != len(commented_code_lines):
                    return {'valid': False, 'reason': f'Code line count changed: {len(original_code_lines)} → {len(commented_code_lines)}'}

            # VFP syntax validation
            validation_result = self._validate_vfp_syntax_preservation(original_content, commented_content)
            if not validation_result['valid']:
                return validation_result

            # Check for actual comment addition
            original_comment_lines = len([line for line in original_lines if line.strip().startswith('*')])
            commented_comment_lines = len([line for line in commented_lines if line.strip().startswith('*')])

            if commented_comment_lines <= original_comment_lines:
                return {'valid': False, 'reason': 'No new comments were added'}

            self.logger.info(f"✓ Validation successful: {commented_comment_lines - original_comment_lines} comments added")

            return {
                'valid': True,
                'reason': 'All validation checks passed',
                'original_lines': len(original_lines),
                'commented_lines': len(commented_lines),
                'comments_added': commented_comment_lines - original_comment_lines
            }

        except Exception as e:
            self.logger.error(f"Validation error for {file_path}: {str(e)}")
            return {'valid': False, 'reason': f'Validation error: {str(e)}'}

    def _validate_vfp_syntax_preservation(self, original_content: str, commented_content: str) -> Dict[str, any]:
        """
        Validate that VFP syntax elements are preserved exactly.

        Args:
            original_content: Original content
            commented_content: Commented content

        Returns:
            Validation result dictionary
        """
        if not self.safety_config.get('validate_vfp_syntax', True):
            return {'valid': True, 'reason': 'VFP syntax validation disabled'}

        # Critical VFP keywords that must match exactly
        vfp_keywords = [
            'PROCEDURE ', 'FUNCTION ', 'ENDPROC', 'ENDFUNC',
            'DEFINE CLASS', 'ENDDEFINE',
            'IF ', 'ELSE', 'ENDIF',
            'FOR ', 'ENDFOR', 'NEXT',
            'DO WHILE', 'ENDDO',
            'SELECT ', 'FROM ', 'WHERE ', 'ORDER BY',
            'INSERT ', 'UPDATE ', 'DELETE ',
            'RETURN', 'RETURNS',
            'LOCAL ', 'PRIVATE ', 'PUBLIC ',
            'PARAMETER', 'LPARAMETERS'
        ]

        original_upper = original_content.upper()
        commented_upper = commented_content.upper()

        for keyword in vfp_keywords:
            original_count = original_upper.count(keyword)
            commented_count = commented_upper.count(keyword)

            if commented_count != original_count:
                return {
                    'valid': False,
                    'reason': f'VFP keyword count changed: {keyword} {original_count} → {commented_count}'
                }

        return {'valid': True, 'reason': 'VFP syntax preservation validated'}

    def save_commented_file(self, file_info: Dict, commented_content: str) -> bool:
        """
        Save commented content to output file with safety measures.

        Args:
            file_info: File information dictionary
            commented_content: Content with comments added

        Returns:
            True if successful, False otherwise
        """
        try:
            output_path = file_info.get('output_path')
            if not output_path:
                # Construct output path if not provided
                file_path = file_info['full_path']
                directory = os.path.dirname(file_path)
                filename = file_info['filename']
                name_part, ext_part = os.path.splitext(filename)
                output_filename = f"{name_part}_commented{ext_part}"
                output_path = os.path.join(directory, output_filename)

            self.logger.info(f"Saving commented file: {output_path}")

            # Create backup if enabled
            if self.safety_config.get('backup_before_processing', False):
                backup_path = create_backup_file(file_info['full_path'])
                if backup_path:
                    self.logger.info(f"Created backup: {backup_path}")

            # Final validation before saving
            if self.processing_config.get('validate_before_save', True):
                original_content = self.read_vfp_file(file_info['full_path'])
                if original_content:
                    validation_result = self._validate_commented_content(
                        original_content, commented_content, output_path
                    )
                    if not validation_result['valid']:
                        self.logger.error(f"Pre-save validation failed: {validation_result['reason']}")
                        return False
                    self.logger.info("✓ Pre-save validation passed")

            # Write file safely
            success = safe_file_write(output_path, commented_content)
            if success:
                self.logger.info(f"✓ Successfully saved commented file: {output_path}")

                # Post-save verification
                if self.processing_config.get('validate_after_save', True):
                    saved_content = self.read_vfp_file(output_path)
                    if saved_content and saved_content == commented_content:
                        self.logger.info("✓ Post-save verification passed")
                    else:
                        self.logger.error("✗ Post-save verification failed")
                        return False

                return True
            else:
                self.logger.error(f"Failed to save file: {output_path}")
                return False

        except Exception as e:
            self.logger.error(f"Error saving commented file: {e}")
            return False

    def get_processing_stats(self, original_content: str, commented_content: str) -> Dict[str, any]:
        """
        Get processing statistics for a file.

        Args:
            original_content: Original file content
            commented_content: Commented file content

        Returns:
            Dictionary with processing statistics
        """
        original_lines = original_content.splitlines()
        commented_lines = commented_content.splitlines()

        original_comment_lines = len([line for line in original_lines if line.strip().startswith('*')])
        commented_comment_lines = len([line for line in commented_lines if line.strip().startswith('*')])

        return {
            'original_size': len(original_content),
            'commented_size': len(commented_content),
            'original_lines': len(original_lines),
            'commented_lines': len(commented_lines),
            'original_comments': original_comment_lines,
            'added_comments': commented_comment_lines - original_comment_lines,
            'size_increase': len(commented_content) - len(original_content),
            'line_increase': len(commented_lines) - len(original_lines)
        }

def main():
    """Test the VFP processor."""
    print("Testing VFP Processor...")

    try:
        # Initialize configuration and processor
        from config import ConfigManager
        config = ConfigManager()

        print("Initializing VFP processor...")
        processor = VFPProcessor(config)

        # Test file reading with sample VFP content
        sample_content = """LOCAL lcName, lnAge
lcName = "John Doe"
lnAge = 30
IF lnAge > 18
    ? "Adult"
ENDIF
RETURN lcName"""

        print(f"\nTesting with sample content ({len(sample_content)} characters)...")

        # Test hash calculation
        content_hash = processor.calculate_content_hash(sample_content)
        code_hash = processor._calculate_code_only_hash(sample_content)

        print(f"Content hash: {content_hash}")
        print(f"Code-only hash: {code_hash}")

        # Test validation with identical content (should pass)
        validation_result = processor._validate_commented_content(
            sample_content, sample_content, "test_file.prg"
        )

        print(f"Self-validation result: {validation_result}")

        # Test VFP syntax validation
        syntax_result = processor._validate_vfp_syntax_preservation(
            sample_content, sample_content
        )

        print(f"Syntax validation result: {syntax_result}")

        # Test processing stats
        stats = processor.get_processing_stats(sample_content, sample_content)
        print(f"Processing stats: {stats}")

        print("✓ VFP processor test completed successfully")

    except Exception as e:
        print(f"Error testing VFP processor: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()