"""
Utility Functions for VFP Code Preservation
==========================================
Critical utilities for ensuring original VFP code is never modified during
the commenting process. This module provides validation functions to guarantee
100% code preservation.

CRITICAL: All functions in this module are designed to DETECT and PREVENT
any changes to original VFP code. If ANY modification is detected, the
processing must be halted immediately.
"""

import hashlib
import re
import difflib
import logging
from typing import List, Tuple, Optional, Dict
from pathlib import Path

class CodePreservationValidator:
    """
    Validator class to ensure original VFP code is never modified.
    This is the most critical component of the entire system.
    """
    
    def __init__(self):
        self.logger = self._setup_logger()
    
    def _setup_logger(self) -> logging.Logger:
        """Setup logging for validation operations."""
        logger = logging.getLogger('code_validator')
        logger.setLevel(logging.INFO)
        
        if not logger.handlers:
            handler = logging.StreamHandler()
            formatter = logging.Formatter(
                '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
            )
            handler.setFormatter(formatter)
            logger.addHandler(handler)
            
        return logger
    
    def extract_code_lines(self, content: str) -> List[str]:
        """
        Extract only the actual VFP code lines (non-comment lines) from content.
        
        This function removes all comment lines to isolate the original code
        for comparison purposes.
        
        Args:
            content: The VFP file content as string
            
        Returns:
            List of code lines with comments stripped
        """
        code_lines = []
        lines = content.split('\n')
        
        for line in lines:
            # Remove leading/trailing whitespace for comparison
            stripped_line = line.strip()
            
            # Skip empty lines
            if not stripped_line:
                continue
                
            # Skip full-line comments (lines starting with *)
            if stripped_line.startswith('*'):
                continue
            
            # For lines with inline comments (&&), extract only the code part
            if '&&' in line:
                code_part = line.split('&&')[0].rstrip()
                if code_part.strip():  # Only add if there's actual code
                    code_lines.append(code_part)
            else:
                # This is a pure code line
                code_lines.append(line.rstrip())  # Remove trailing whitespace
        
        return code_lines
    
    def calculate_code_hash(self, content: str) -> str:
        """
        Calculate a SHA-256 hash of only the code portions of the content.
        
        Args:
            content: The VFP file content as string
            
        Returns:
            SHA-256 hash of the code portions
        """
        code_lines = self.extract_code_lines(content)
        
        # Join code lines with consistent line endings for hashing
        code_text = '\n'.join(code_lines)
        
        # Calculate hash
        return hashlib.sha256(code_text.encode('utf-8')).hexdigest()
    
    def validate_code_preservation(self, original_content: str, commented_content: str) -> Tuple[bool, List[str]]:
        """
        CRITICAL VALIDATION: Ensure the original code is completely preserved.
        
        This function performs multiple levels of validation to guarantee that
        no original VFP code has been modified in any way.
        
        Args:
            original_content: The original VFP file content
            commented_content: The commented VFP file content
            
        Returns:
            Tuple of (is_valid, list_of_errors)
            - is_valid: True if code is preserved, False if ANY changes detected
            - list_of_errors: List of specific validation errors found
        """
        errors = []
        
        try:
            # Extract code lines from both versions
            original_code_lines = self.extract_code_lines(original_content)
            commented_code_lines = self.extract_code_lines(commented_content)
            
            # Validation 1: Hash comparison
            original_hash = self.calculate_code_hash(original_content)
            commented_hash = self.calculate_code_hash(commented_content)
            
            if original_hash != commented_hash:
                errors.append(f"CODE HASH MISMATCH: Original and commented versions have different code content")
                self.logger.critical("CRITICAL: Code preservation validation FAILED - hash mismatch detected")
            
            # Validation 2: Line count comparison
            if len(original_code_lines) != len(commented_code_lines):
                errors.append(f"CODE LINE COUNT MISMATCH: Original has {len(original_code_lines)} code lines, commented has {len(commented_code_lines)}")
                self.logger.critical(f"CRITICAL: Code line count changed from {len(original_code_lines)} to {len(commented_code_lines)}")
            
            # Validation 3: Line-by-line comparison
            for i, (orig_line, comm_line) in enumerate(zip(original_code_lines, commented_code_lines)):
                if orig_line != comm_line:
                    errors.append(f"CODE MODIFICATION DETECTED at line {i+1}:")
                    errors.append(f"  Original: '{orig_line}'")
                    errors.append(f"  Modified: '{comm_line}'")
                    self.logger.critical(f"CRITICAL: Code modification detected at line {i+1}")
            
            # Validation 4: Check for missing lines in commented version
            if len(commented_code_lines) < len(original_code_lines):
                missing_count = len(original_code_lines) - len(commented_code_lines)
                errors.append(f"MISSING CODE LINES: {missing_count} lines from original are missing in commented version")
                self.logger.critical(f"CRITICAL: {missing_count} code lines are missing from commented version")
            
            # Validation 5: Check for extra code lines in commented version
            if len(commented_code_lines) > len(original_code_lines):
                extra_count = len(commented_code_lines) - len(original_code_lines)
                errors.append(f"EXTRA CODE LINES: {extra_count} lines have been added to the code (not just comments)")
                self.logger.critical(f"CRITICAL: {extra_count} extra code lines detected in commented version")
            
        except Exception as e:
            errors.append(f"VALIDATION ERROR: Exception during code preservation validation: {str(e)}")
            self.logger.critical(f"CRITICAL: Exception during validation: {str(e)}")
        
        is_valid = len(errors) == 0
        
        if is_valid:
            self.logger.info("✓ Code preservation validation PASSED - Original code is intact")
        else:
            self.logger.critical("✗ Code preservation validation FAILED - Original code has been modified!")
            for error in errors:
                self.logger.critical(f"  {error}")
        
        return is_valid, errors
    
    def generate_diff_report(self, original_content: str, commented_content: str) -> str:
        """
        Generate a detailed diff report between original and commented content.
        
        Args:
            original_content: The original VFP file content
            commented_content: The commented VFP file content
            
        Returns:
            String containing the diff report
        """
        original_lines = original_content.split('\n')
        commented_lines = commented_content.split('\n')
        
        diff = difflib.unified_diff(
            original_lines,
            commented_lines,
            fromfile='Original',
            tofile='Commented',
            lineterm=''
        )
        
        return '\n'.join(diff)
    
    def validate_vfp_syntax(self, content: str) -> Tuple[bool, List[str]]:
        """
        Basic VFP syntax validation to ensure comments use proper syntax.
        
        Args:
            content: VFP file content to validate
            
        Returns:
            Tuple of (is_valid, list_of_warnings)
        """
        warnings = []
        lines = content.split('\n')
        
        for line_num, line in enumerate(lines, 1):
            stripped = line.strip()
            
            # Check for proper comment syntax
            if stripped and not stripped.startswith('*') and '&&' in line:
                # Inline comment found - check placement
                code_part, comment_part = line.split('&&', 1)
                if not code_part.strip():
                    warnings.append(f"Line {line_num}: Inline comment without preceding code")
            
            # Check for suspicious patterns that might indicate code modification
            if any(keyword in stripped.upper() for keyword in ['DELETE', 'DROP', 'MODIFY STRUCTURE']):
                warnings.append(f"Line {line_num}: Contains potentially destructive command: {stripped}")
        
        return len(warnings) == 0, warnings

def create_backup_file(source_path: str, backup_suffix: str = "_backup") -> Optional[str]:
    """
    Create a backup copy of a file before processing.
    
    Args:
        source_path: Path to the source file
        backup_suffix: Suffix to add to backup filename
        
    Returns:
        Path to backup file if successful, None if failed
    """
    try:
        source_path_obj = Path(source_path)
        
        # Create backup filename
        backup_name = f"{source_path_obj.stem}{backup_suffix}{source_path_obj.suffix}"
        backup_path = source_path_obj.parent / backup_name
        
        # Copy file content
        with open(source_path, 'r', encoding='utf-8') as src, \
             open(backup_path, 'w', encoding='utf-8') as backup:
            backup.write(src.read())
        
        return str(backup_path)
        
    except Exception as e:
        logging.getLogger('utils').error(f"Failed to create backup for {source_path}: {e}")
        return None

def safe_file_write(file_path: str, content: str, validate_against: Optional[str] = None) -> bool:
    """
    Safely write content to a file with optional validation.
    
    Args:
        file_path: Path where to write the file
        content: Content to write
        validate_against: Optional original content for validation
        
    Returns:
        True if write was successful and validation passed, False otherwise
    """
    logger = logging.getLogger('utils')
    
    try:
        # If validation content provided, validate before writing
        if validate_against:
            validator = CodePreservationValidator()
            is_valid, errors = validator.validate_code_preservation(validate_against, content)
            
            if not is_valid:
                logger.critical("REFUSING TO WRITE FILE: Code preservation validation failed")
                for error in errors:
                    logger.critical(f"  {error}")
                return False
        
        # Write file atomically (write to temp file, then rename)
        file_path_obj = Path(file_path)
        temp_path = file_path_obj.with_suffix(file_path_obj.suffix + '.tmp')
        
        with open(temp_path, 'w', encoding='utf-8') as f:
            f.write(content)
        
        # Rename temp file to final name (atomic on most filesystems)
        temp_path.rename(file_path_obj)
        
        logger.info(f"Successfully wrote file: {file_path}")
        return True
        
    except Exception as e:
        logger.error(f"Failed to write file {file_path}: {e}")
        return False

def format_file_size(size_bytes: int) -> str:
    """Format file size in human-readable format."""
    if size_bytes == 0:
        return "0 B"
    
    size_names = ["B", "KB", "MB", "GB"]
    i = 0
    size = float(size_bytes)
    
    while size >= 1024.0 and i < len(size_names) - 1:
        size /= 1024.0
        i += 1
        
    return f"{size:.1f} {size_names[i]}"

def main():
    """Test the utility functions."""
    print("Testing Code Preservation Validator...")
    
    # Test with sample VFP code
    original_code = """* This is a comment
LOCAL lcName, lnAge
lcName = "John Doe"  && Set the name
lnAge = 30
IF lnAge > 18
    ? "Adult"  && Display adult message
ENDIF
RETURN lcName"""
    
    # Valid commented version (only comments added)
    valid_commented = """* ===== FILE HEADER =====
* Program: test.prg
* Purpose: Sample VFP program for testing
* ========================

* This is a comment
* Declare local variables for person information
LOCAL lcName, lnAge
lcName = "John Doe"  && Set the name
lnAge = 30  && Set age to 30 years

* Check if person is an adult
IF lnAge > 18
    ? "Adult"  && Display adult message
ENDIF

* Return the person's name
RETURN lcName"""
    
    # Invalid commented version (code modified)
    invalid_commented = """* ===== FILE HEADER =====
* Program: test.prg
* Purpose: Sample VFP program for testing
* ========================

* This is a comment
LOCAL lcName, lnAge
lcName = "Jane Smith"  && Modified name!
lnAge = 25  && Modified age!
IF lnAge > 21  && Modified condition!
    ? "Adult"  && Display adult message
ENDIF
RETURN lcName"""
    
    validator = CodePreservationValidator()
    
    print("\n=== Testing Valid Commented Version ===")
    is_valid, errors = validator.validate_code_preservation(original_code, valid_commented)
    print(f"Validation Result: {'PASSED' if is_valid else 'FAILED'}")
    if errors:
        for error in errors:
            print(f"Error: {error}")
    
    print("\n=== Testing Invalid Commented Version ===")
    is_valid, errors = validator.validate_code_preservation(original_code, invalid_commented)
    print(f"Validation Result: {'PASSED' if is_valid else 'FAILED'}")
    if errors:
        for error in errors:
            print(f"Error: {error}")
    
    print("\n=== Code Hash Comparison ===")
    original_hash = validator.calculate_code_hash(original_code)
    valid_hash = validator.calculate_code_hash(valid_commented)
    invalid_hash = validator.calculate_code_hash(invalid_commented)
    
    print(f"Original Hash:  {original_hash}")
    print(f"Valid Hash:     {valid_hash}")
    print(f"Invalid Hash:   {invalid_hash}")
    print(f"Valid Match:    {original_hash == valid_hash}")
    print(f"Invalid Match:  {original_hash == invalid_hash}")

if __name__ == "__main__":
    main()