"""
C# File Discovery Utility
==========================

Standalone tool to discover and validate C# source files for commenting.

This utility implements the file filtering logic specified in:
eRx_Project_Analysis_and_Enhancement_Specification.md

Key Features:
- Recursively scans C# project directories
- Excludes auto-generated files (.Designer.cs, .g.cs, .g.i.cs)
- Excludes assembly metadata (AssemblyInfo.cs, AssemblyAttributes.cs)
- Excludes build artifacts (bin/, obj/, Debug/, Release/)
- Excludes IDE settings (.vs/, packages/, TestResults/)
- Provides detailed statistics and validation

Expected Results (for eRx root directory):
- Total files: 122 (42 eRx main + 38 eRxClient + 42 eRxEClient)
- Excluded: 157 files (auto-generated, build artifacts)
- Total .cs files in directory: 279

Usage:
    python csharp_file_discovery.py --path "MHRandeRx/eRx"
    python csharp_file_discovery.py --path "MHRandeRx/eRx/eRxClient"
    python csharp_file_discovery.py --path "MHRandeRx/eRx" --export results.json
    python csharp_file_discovery.py --path "MHRandeRx/eRx" --validate
"""

import os
import sys
import json
import argparse
from pathlib import Path
from typing import List, Dict, Set
from collections import defaultdict

# Add parent directory to path to import project modules
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from file_scanner import CodeFileScanner
from language_handlers import get_handler


class CSharpFileDiscovery:
    """
    C# file discovery and validation utility.

    Implements filtering logic from eRx Project Analysis specification.
    """

    def __init__(self, root_path: str):
        """
        Initialize the C# file discovery utility.

        Args:
            root_path: Root directory to scan (e.g., "MHRandeRx/eRx")
        """
        self.root_path = Path(root_path).resolve()

        # Get C# handler for skip patterns and extensions
        self.handler = get_handler('csharp')

        # Initialize scanner with C# handler
        self.scanner = CodeFileScanner(str(self.root_path), handler=self.handler)

    def discover_files(self) -> List[Dict[str, str]]:
        """
        Discover all C# files that need commenting.

        Returns:
            List of file information dictionaries
        """
        print(f"\n{'='*70}")
        print(f"C# FILE DISCOVERY")
        print(f"{'='*70}")
        print(f"Scanning: {self.root_path}")
        print(f"Language: C#")
        print(f"File extensions: {', '.join(self.handler.get_file_extensions())}")
        print(f"\nApplying {len(self.handler.get_skip_patterns())} exclusion patterns...")

        files = self.scanner.scan_code_files()

        return files

    def analyze_by_project(self, files: List[Dict[str, str]]) -> Dict[str, List[Dict]]:
        """
        Analyze files and group by project (eRx, eRxClient, eRxEClient).

        Args:
            files: List of discovered files

        Returns:
            Dictionary mapping project names to file lists
        """
        projects = {
            'eRx (main)': [],
            'eRxClient': [],
            'eRxEClient': [],
            'Other': []
        }

        for file_info in files:
            rel_path = file_info['relative_path']

            # Categorize by project
            if 'eRxEClient' in rel_path:
                projects['eRxEClient'].append(file_info)
            elif 'eRxClient' in rel_path:
                projects['eRxClient'].append(file_info)
            elif rel_path.startswith('eRx'):
                # Files in eRx root or eRx subdirectories (not eRxClient/eRxEClient)
                if not ('eRxClient' in rel_path or 'eRxEClient' in rel_path):
                    projects['eRx (main)'].append(file_info)
                else:
                    projects['Other'].append(file_info)
            else:
                projects['Other'].append(file_info)

        return projects

    def validate_exclusions(self, files: List[Dict[str, str]]) -> Dict[str, List[str]]:
        """
        Validate that excluded file patterns are NOT in the results.

        Args:
            files: List of discovered files

        Returns:
            Dictionary of validation issues (empty if all passed)
        """
        issues = defaultdict(list)

        # Patterns that should NEVER appear in results
        forbidden_patterns = [
            ('.Designer.cs', 'Designer-generated files'),
            ('.g.cs', 'WPF/UWP generated files'),
            ('.g.i.cs', 'Auto-generated interop files'),
            ('AssemblyInfo.cs', 'Assembly metadata'),
            ('AssemblyAttributes.cs', 'Assembly attributes'),
            ('GlobalUsings.g.cs', 'Global usings'),
            ('TemporaryGeneratedFile_', 'Temporary files'),
        ]

        forbidden_folders = [
            ('bin/', 'Build output'),
            ('obj/', 'Build intermediates'),
            ('.vs/', 'IDE settings'),
            ('Debug/', 'Debug build'),
            ('Release/', 'Release build'),
            ('packages/', 'NuGet packages'),
            ('TestResults/', 'Test output'),
        ]

        for file_info in files:
            filename = file_info['filename']
            full_path = file_info['full_path'].replace('\\', '/')

            # Check forbidden file patterns
            for pattern, description in forbidden_patterns:
                if pattern in filename:
                    issues[f"❌ {description}"].append(filename)

            # Check forbidden folders
            for folder, description in forbidden_folders:
                if f'/{folder}' in full_path or full_path.startswith(folder):
                    issues[f"❌ {description} in path"].append(file_info['relative_path'])

        return dict(issues)

    def print_detailed_report(self, files: List[Dict[str, str]]):
        """
        Print comprehensive discovery report.

        Args:
            files: List of discovered files
        """
        projects = self.analyze_by_project(files)

        print(f"\n{'='*70}")
        print("DISCOVERY RESULTS")
        print(f"{'='*70}")

        # Overall statistics
        print(f"\n[Overall Statistics]")
        print(f"   Total C# files to comment: {len(files)}")
        print(f"   Root directory: {self.root_path}")

        # Breakdown by project
        print(f"\n[Breakdown by Project]")
        total_project_files = 0
        for project_name, project_files in projects.items():
            if len(project_files) > 0:
                print(f"   {project_name}: {len(project_files)} files")
                total_project_files += len(project_files)

        # Expected vs actual (for eRx root)
        if 'eRx' in self.root_path.name or self.root_path.name == 'eRx':
            print(f"\n[Expected Results - eRx specification]")
            print(f"   eRx (main): 42 files")
            print(f"   eRxClient: 38 files")
            print(f"   eRxEClient: 42 files")
            print(f"   TOTAL: 122 files")

            print(f"\n[Comparison: Expected vs Actual]")
            expected = {'eRx (main)': 42, 'eRxClient': 38, 'eRxEClient': 42}
            for project_name, expected_count in expected.items():
                actual_count = len(projects.get(project_name, []))
                status = "[PASS]" if actual_count == expected_count else "[WARN]"
                diff = actual_count - expected_count
                diff_str = f"({diff:+d})" if diff != 0 else ""
                print(f"   {status} {project_name}: {actual_count} files {diff_str}")

        # File type statistics
        extensions = defaultdict(int)
        for file_info in files:
            ext = Path(file_info['filename']).suffix
            extensions[ext] += 1

        print(f"\n[File Extensions]")
        for ext, count in sorted(extensions.items()):
            print(f"   {ext}: {count} files")

        # Sample files from each project
        print(f"\n[Sample Files by Project]")
        for project_name, project_files in projects.items():
            if len(project_files) > 0:
                print(f"\n   {project_name} ({len(project_files)} files):")
                sample_files = sorted([f['filename'] for f in project_files[:5]])
                for filename in sample_files:
                    print(f"      - {filename}")
                if len(project_files) > 5:
                    print(f"      ... and {len(project_files) - 5} more files")

        # Validation
        print(f"\n[Validation Checks]")
        issues = self.validate_exclusions(files)

        if not issues:
            print("   [PASS] All exclusion patterns working correctly")
            print("   [PASS] No Designer.cs files found")
            print("   [PASS] No .g.cs generated files found")
            print("   [PASS] No bin/, obj/, or .vs/ folders found")
            print("   [PASS] No assembly metadata files found")
        else:
            print("   [FAIL] ISSUES FOUND:")
            for issue_type, issue_files in issues.items():
                print(f"\n   {issue_type}: {len(issue_files)} files")
                for filename in issue_files[:5]:
                    print(f"      - {filename}")
                if len(issue_files) > 5:
                    print(f"      ... and {len(issue_files) - 5} more")

        print(f"\n{'='*70}")
        print(f"Discovery complete. {len(files)} files ready for commenting.")
        print(f"{'='*70}\n")

    def export_results(self, files: List[Dict[str, str]], output_file: str):
        """
        Export discovery results to JSON file.

        Args:
            files: List of discovered files
            output_file: Path to output JSON file
        """
        projects = self.analyze_by_project(files)
        validation = self.validate_exclusions(files)

        results = {
            'root_directory': str(self.root_path),
            'total_files': len(files),
            'projects': {
                name: {
                    'file_count': len(file_list),
                    'files': [f['relative_path'] for f in file_list]
                }
                for name, file_list in projects.items() if len(file_list) > 0
            },
            'validation_issues': validation,
            'all_files': files
        }

        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(results, f, indent=2, ensure_ascii=False)

        print(f"[EXPORT] Results exported to: {output_file}")


def main():
    """Main entry point for CLI."""
    parser = argparse.ArgumentParser(
        description='Discover C# files for commenting in eRx/MHR projects',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Scan eRx root directory (expect 122 files)
  python csharp_file_discovery.py --path "MHRandeRx/eRx"

  # Scan specific project (expect 38 files)
  python csharp_file_discovery.py --path "MHRandeRx/eRx/eRxClient"

  # Export results to JSON
  python csharp_file_discovery.py --path "MHRandeRx/eRx" --export results.json

  # Validate only (no detailed output)
  python csharp_file_discovery.py --path "MHRandeRx/eRx" --validate
        """
    )

    parser.add_argument(
        '--path', '-p',
        required=True,
        help='Path to C# project directory (e.g., "MHRandeRx/eRx")'
    )

    parser.add_argument(
        '--export', '-e',
        metavar='FILE',
        help='Export results to JSON file'
    )

    parser.add_argument(
        '--validate', '-v',
        action='store_true',
        help='Run validation checks only (minimal output)'
    )

    args = parser.parse_args()

    # Check if path exists
    if not os.path.exists(args.path):
        print(f"[ERROR] Path does not exist: {args.path}")
        sys.exit(1)

    # Run discovery
    discovery = CSharpFileDiscovery(args.path)
    files = discovery.discover_files()

    if args.validate:
        # Validation mode - just check and exit
        issues = discovery.validate_exclusions(files)
        if not issues:
            print(f"[PASS] Validation passed! {len(files)} files found, all exclusions working correctly.")
            sys.exit(0)
        else:
            print(f"[FAIL] Validation failed! Found {len(issues)} issue types:")
            for issue_type, issue_files in issues.items():
                print(f"   {issue_type}: {len(issue_files)} files")
            sys.exit(1)
    else:
        # Full report mode
        discovery.print_detailed_report(files)

    # Export if requested
    if args.export:
        discovery.export_results(files, args.export)


if __name__ == "__main__":
    main()
