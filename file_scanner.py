"""
Code File Scanner Module
========================
Recursively scans directories for code files based on language handler configuration.

Supports multiple languages:
- Visual FoxPro (.prg, .spr)
- C# (.cs)
- Extensible to other languages via handlers

CRITICAL: This module is designed for CODE PRESERVATION - it identifies files
but NEVER modifies original code structure or content.
"""

import os
import logging
import fnmatch
from pathlib import Path
from typing import List, Dict, Set, Tuple, Optional
import json


class CodeFileScanner:
    """
    Language-agnostic code file scanner.

    Uses language handlers to determine which files to scan and which to skip.
    """

    def __init__(self, root_directory: str, handler=None):
        """
        Initialize the code file scanner.

        Args:
            root_directory: Root directory to scan for code files
            handler: Language handler (optional, for language-specific extensions)
        """
        self.root_directory = Path(root_directory).resolve()
        self.handler = handler

        if handler:
            # Use handler-provided extensions and skip patterns
            self.file_extensions = set(ext.lower() for ext in handler.get_file_extensions())
            self.skip_patterns = set(handler.get_skip_patterns())
            self.language_name = handler.get_language_name()
        else:
            # Default to VFP for backward compatibility
            self.file_extensions = {'.prg', '.spr'}
            self.skip_patterns = {'_commented', '_pretty', '_backup'}
            self.language_name = 'vfp'

        self.logger = self._setup_logger()

    def _setup_logger(self) -> logging.Logger:
        """Setup logging for file scanner operations."""
        logger = logging.getLogger(f'{self.language_name}_scanner')
        logger.setLevel(logging.INFO)

        if not logger.handlers:
            handler = logging.StreamHandler()
            formatter = logging.Formatter(
                '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
            )
            handler.setFormatter(formatter)
            logger.addHandler(handler)

        return logger

    def should_skip_file(self, filename: str, file_path: str = None) -> bool:
        """
        Check if a file should be skipped based on naming patterns.

        Supports wildcard patterns using fnmatch:
        - '*.Designer.cs' matches any file ending with .Designer.cs
        - 'TemporaryGeneratedFile_*' matches any file starting with that prefix
        - 'AssemblyInfo.cs' matches exact filename
        - '.g.cs' matches files containing .g.cs

        Args:
            filename: Name of the file to check
            file_path: Full path (optional, for folder-based exclusions)

        Returns:
            True if file should be skipped, False otherwise
        """
        # Check file-based patterns
        for pattern in self.skip_patterns:
            # Wildcard pattern matching (e.g., *.Designer.cs, Temp*.cs)
            if '*' in pattern:
                if fnmatch.fnmatch(filename, pattern):
                    return True
            # Simple containment check (e.g., .Designer.cs, AssemblyInfo.cs)
            elif pattern in filename:
                return True

        # Check folder-based exclusions if path provided
        if file_path:
            normalized_path = file_path.replace('\\', '/')
            for pattern in self.skip_patterns:
                if pattern.endswith('/'):
                    # Folder pattern - check if path contains this folder
                    folder_name = pattern.rstrip('/')
                    if f'/{folder_name}/' in normalized_path or normalized_path.startswith(f'{folder_name}/'):
                        return True

        return False

    def should_skip_folder(self, folder_path: str) -> bool:
        """
        Check if an entire folder should be skipped during traversal.

        Args:
            folder_path: Path to the folder

        Returns:
            True if folder should be skipped, False otherwise
        """
        normalized_path = folder_path.replace('\\', '/')
        folder_name = Path(folder_path).name

        for pattern in self.skip_patterns:
            if pattern.endswith('/'):
                # Folder exclusion pattern
                excluded_folder = pattern.rstrip('/')
                if folder_name == excluded_folder:
                    return True
                if f'/{excluded_folder}/' in normalized_path:
                    return True

        return False

    def is_code_file(self, filename: str) -> bool:
        """
        Check if a file matches the language file extensions.

        Args:
            filename: Name of the file to check

        Returns:
            True if file matches language extensions, False otherwise
        """
        file_ext = Path(filename).suffix.lower()
        return file_ext in self.file_extensions

    def scan_code_files(self) -> List[Dict[str, str]]:
        """
        Recursively scan for code files in the root directory.

        Returns:
            List of dictionaries containing file information:
            - full_path: Absolute path to the file
            - relative_path: Path relative to root directory
            - directory: Directory containing the file
            - filename: Name of the file
            - output_path: Path where commented version would be saved
            - file_size: Size of the file in bytes
        """
        code_files = []

        if not self.root_directory.exists():
            self.logger.error(f"Root directory does not exist: {self.root_directory}")
            return code_files

        if not self.root_directory.is_dir():
            self.logger.error(f"Root path is not a directory: {self.root_directory}")
            return code_files

        self.logger.info(f"Scanning {self.language_name} files in: {self.root_directory}")

        try:
            for root, dirs, files in os.walk(self.root_directory):
                root_path = Path(root)

                # Filter out directories that should be skipped (modifies dirs in-place)
                dirs[:] = [d for d in dirs if not self.should_skip_folder(str(root_path / d))]

                # Skip if current directory itself should be excluded
                if self.should_skip_folder(str(root_path)):
                    continue

                for filename in files:
                    if self.is_code_file(filename):
                        file_path = root_path / filename
                        full_path_str = str(file_path)

                        # Check file-level skip patterns
                        if self.should_skip_file(filename, full_path_str):
                            continue

                        try:
                            # Generate output filename with _commented suffix
                            name_parts = filename.rsplit('.', 1)
                            if len(name_parts) == 2:
                                output_filename = f"{name_parts[0]}_commented.{name_parts[1]}"
                            else:
                                output_filename = f"{filename}_commented"

                            # Get file size for validation
                            file_size = file_path.stat().st_size

                            file_info = {
                                'full_path': str(file_path),
                                'relative_path': str(file_path.relative_to(self.root_directory)),
                                'directory': str(root_path),
                                'filename': filename,
                                'output_path': str(root_path / output_filename),
                                'file_size': file_size
                            }

                            code_files.append(file_info)

                        except (OSError, ValueError) as e:
                            self.logger.warning(f"Error processing file {file_path}: {e}")
                            continue

        except OSError as e:
            self.logger.error(f"Error walking directory {self.root_directory}: {e}")

        return code_files

    def generate_scan_report(self, files: List[Dict[str, str]]) -> Dict[str, any]:
        """
        Generate a comprehensive scan report.

        Args:
            files: List of scanned code files

        Returns:
            Dictionary containing scan statistics and file information
        """
        if not files:
            return {
                'total_files': 0,
                'total_size': 0,
                'folders': {},
                'extensions': {},
                'summary': f"No {self.language_name} files found"
            }

        # Group files by directory
        folders = {}
        extensions = {}
        total_size = 0

        for file_info in files:
            # Folder statistics
            folder = file_info['directory']
            try:
                relative_folder = str(Path(folder).relative_to(self.root_directory))
            except ValueError:
                relative_folder = folder

            if relative_folder not in folders:
                folders[relative_folder] = {
                    'file_count': 0,
                    'total_size': 0,
                    'files': []
                }

            folders[relative_folder]['file_count'] += 1
            folders[relative_folder]['total_size'] += file_info['file_size']
            folders[relative_folder]['files'].append(file_info['filename'])

            # Extension statistics
            ext = Path(file_info['filename']).suffix
            extensions[ext] = extensions.get(ext, 0) + 1

            total_size += file_info['file_size']

        return {
            'total_files': len(files),
            'total_size': total_size,
            'folders': folders,
            'extensions': extensions,
            'root_directory': str(self.root_directory),
            'language': self.language_name,
            'scan_timestamp': None  # Will be set by caller if needed
        }

    def print_scan_report(self, files: List[Dict[str, str]]) -> None:
        """
        Print a formatted scan report to console.

        Args:
            files: List of scanned code files
        """
        report = self.generate_scan_report(files)

        print("\n" + "="*60)
        print(f"{self.language_name.upper()} FILE SCANNER REPORT")
        print("="*60)
        print(f"Root Directory: {report['root_directory']}")
        print(f"Total {self.language_name.upper()} Files Found: {report['total_files']}")
        print(f"Total Size: {self._format_file_size(report['total_size'])}")

        if report['total_files'] == 0:
            print(f"\nNo {self.language_name} files found in the specified directory.")
            return

        print(f"\nFile Extensions:")
        for ext, count in sorted(report['extensions'].items()):
            print(f"  {ext}: {count} files")

        print(f"\nFolders and File Counts:")
        for folder_path, folder_info in sorted(report['folders'].items()):
            folder_display = folder_path if folder_path != '.' else '[Root]'
            size_str = self._format_file_size(folder_info['total_size'])
            print(f"  {folder_display}: {folder_info['file_count']} files ({size_str})")

            # Show first few files as examples
            files_to_show = folder_info['files'][:3]
            for filename in files_to_show:
                print(f"    - {filename}")
            if len(folder_info['files']) > 3:
                print(f"    ... and {len(folder_info['files']) - 3} more files")

        print(f"\nFiles ready for processing: {report['total_files']}")
        print("="*60)

    def _format_file_size(self, size_bytes: int) -> str:
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


class VFPFileScanner(CodeFileScanner):
    """
    Scanner for Visual FoxPro files (backward compatibility).

    Kept for backward compatibility with existing code.
    New code should use CodeFileScanner with a VFPHandler.
    """

    def __init__(self, root_directory: str):
        """
        Initialize the VFP file scanner.

        Args:
            root_directory: Root directory to scan for VFP files
        """
        # Initialize without handler for backward compatibility
        super().__init__(root_directory, handler=None)
        self.vfp_extensions = self.file_extensions  # Alias for backward compatibility

        # Override with VFP-specific settings
        self.file_extensions = {'.prg', '.spr'}
        self.skip_patterns = {'_commented', '_pretty', '_backup'}
        self.language_name = 'vfp'
        
    def _setup_logger(self) -> logging.Logger:
        """Setup logging for file scanner operations."""
        logger = logging.getLogger('vfp_scanner')
        logger.setLevel(logging.INFO)
        
        if not logger.handlers:
            handler = logging.StreamHandler()
            formatter = logging.Formatter(
                '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
            )
            handler.setFormatter(formatter)
            logger.addHandler(handler)
            
        return logger
    
    def should_skip_file(self, filename: str) -> bool:
        """
        Check if a file should be skipped based on naming patterns.
        
        Args:
            filename: Name of the file to check
            
        Returns:
            True if file should be skipped, False otherwise
        """
        return any(pattern in filename for pattern in self.skip_patterns)
    
    def is_code_file(self, filename: str) -> bool:
        """
        Check if a file matches the language file extensions.

        Args:
            filename: Name of the file to check

        Returns:
            True if file matches language extensions, False otherwise
        """
        file_ext = Path(filename).suffix.lower()
        return file_ext in self.file_extensions

    def is_vfp_file(self, filename: str) -> bool:
        """
        Check if a file is a code file (backward compatibility alias).

        Args:
            filename: Name of the file to check

        Returns:
            True if file matches language extensions, False otherwise
        """
        return self.is_code_file(filename)
    
    def scan_vfp_files(self) -> List[Dict[str, str]]:
        """
        Recursively scan for VFP files in the root directory.
        
        Returns:
            List of dictionaries containing file information:
            - full_path: Absolute path to the file
            - relative_path: Path relative to root directory
            - directory: Directory containing the file
            - filename: Name of the file
            - output_path: Path where commented version would be saved
            - file_size: Size of the file in bytes
        """
        vfp_files = []
        
        if not self.root_directory.exists():
            self.logger.error(f"Root directory does not exist: {self.root_directory}")
            return vfp_files
        
        if not self.root_directory.is_dir():
            self.logger.error(f"Root path is not a directory: {self.root_directory}")
            return vfp_files
            
        self.logger.info(f"Scanning VFP files in: {self.root_directory}")
        
        try:
            for root, dirs, files in os.walk(self.root_directory):
                root_path = Path(root)
                
                for filename in files:
                    if self.is_vfp_file(filename) and not self.should_skip_file(filename):
                        file_path = root_path / filename
                        
                        try:
                            # Generate output filename with _commented suffix
                            name_parts = filename.rsplit('.', 1)
                            if len(name_parts) == 2:
                                output_filename = f"{name_parts[0]}_commented.{name_parts[1]}"
                            else:
                                output_filename = f"{filename}_commented"
                            
                            # Get file size for validation
                            file_size = file_path.stat().st_size
                            
                            file_info = {
                                'full_path': str(file_path),
                                'relative_path': str(file_path.relative_to(self.root_directory)),
                                'directory': str(root_path),
                                'filename': filename,
                                'output_path': str(root_path / output_filename),
                                'file_size': file_size
                            }
                            
                            vfp_files.append(file_info)
                            
                        except (OSError, ValueError) as e:
                            self.logger.warning(f"Error processing file {file_path}: {e}")
                            continue
                            
        except OSError as e:
            self.logger.error(f"Error walking directory {self.root_directory}: {e}")
            
        return vfp_files
    
    def generate_scan_report(self, files: List[Dict[str, str]]) -> Dict[str, any]:
        """
        Generate a comprehensive scan report.
        
        Args:
            files: List of scanned VFP files
            
        Returns:
            Dictionary containing scan statistics and file information
        """
        if not files:
            return {
                'total_files': 0,
                'total_size': 0,
                'folders': {},
                'extensions': {},
                'summary': "No VFP files found"
            }
        
        # Group files by directory
        folders = {}
        extensions = {}
        total_size = 0
        
        for file_info in files:
            # Folder statistics
            folder = file_info['directory']
            relative_folder = str(Path(folder).relative_to(self.root_directory))
            
            if relative_folder not in folders:
                folders[relative_folder] = {
                    'file_count': 0,
                    'total_size': 0,
                    'files': []
                }
            
            folders[relative_folder]['file_count'] += 1
            folders[relative_folder]['total_size'] += file_info['file_size']
            folders[relative_folder]['files'].append(file_info['filename'])
            
            # Extension statistics
            ext = Path(file_info['filename']).suffix
            extensions[ext] = extensions.get(ext, 0) + 1
            
            total_size += file_info['file_size']
        
        return {
            'total_files': len(files),
            'total_size': total_size,
            'folders': folders,
            'extensions': extensions,
            'root_directory': str(self.root_directory),
            'scan_timestamp': None  # Will be set by caller if needed
        }
    
    def print_scan_report(self, files: List[Dict[str, str]]) -> None:
        """
        Print a formatted scan report to console.
        
        Args:
            files: List of scanned VFP files
        """
        report = self.generate_scan_report(files)
        
        print("\n" + "="*60)
        print("VFP FILE SCANNER REPORT")
        print("="*60)
        print(f"Root Directory: {report['root_directory']}")
        print(f"Total VFP Files Found: {report['total_files']}")
        print(f"Total Size: {self._format_file_size(report['total_size'])}")
        
        if report['total_files'] == 0:
            print("\nNo VFP files found in the specified directory.")
            return
        
        print(f"\nFile Extensions:")
        for ext, count in sorted(report['extensions'].items()):
            print(f"  {ext}: {count} files")
        
        print(f"\nFolders and File Counts:")
        for folder_path, folder_info in sorted(report['folders'].items()):
            folder_display = folder_path if folder_path != '.' else '[Root]'
            size_str = self._format_file_size(folder_info['total_size'])
            print(f"  {folder_display}: {folder_info['file_count']} files ({size_str})")
            
            # Show first few files as examples
            files_to_show = folder_info['files'][:3]
            for filename in files_to_show:
                print(f"    - {filename}")
            if len(folder_info['files']) > 3:
                print(f"    ... and {len(folder_info['files']) - 3} more files")
        
        print(f"\nFiles ready for processing: {report['total_files']}")
        print("(Files with '_commented', '_pretty', or '_backup' in name are automatically skipped)")
        print("="*60)
    
    def _format_file_size(self, size_bytes: int) -> str:
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
    """
    Main function for testing the file scanner.
    """
    # Use the VFP_Files_Copy directory as specified in the requirements
    root_dir = r"D:\Medical Wizard\VFP Entire Codebase\VFP Comment Settup\VFP_Files_Copy"
    
    print("Testing VFP File Scanner...")
    print(f"Scanning directory: {root_dir}")
    
    scanner = VFPFileScanner(root_dir)
    files = scanner.scan_vfp_files()
    scanner.print_scan_report(files)
    
    # Save detailed results to JSON for inspection
    report = scanner.generate_scan_report(files)
    report_file = "scan_report.json"
    
    try:
        with open(report_file, 'w', encoding='utf-8') as f:
            json.dump({
                'report': report,
                'file_details': files
            }, f, indent=2, ensure_ascii=False)
        print(f"\nDetailed scan results saved to: {report_file}")
    except Exception as e:
        print(f"Warning: Could not save scan report: {e}")

if __name__ == "__main__":
    main()