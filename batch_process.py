"""
Multi-Language Batch Processor - Production CLI Tool
=====================================================
Command-line tool for batch processing code files with the two-phase commenting system.

Supports:
- Visual FoxPro (VFP) - .prg, .spr files
- C# - .cs files

Usage Examples:
    # Process VFP files
    python batch_process.py --language vfp --path "VFP_Files_Copy"

    # Process C# files
    python batch_process.py --language csharp --path "CSharp_Projects/eRx"

    # Process single file
    python batch_process.py --language vfp --path "VFP_Files_Copy/Forms/main.prg"

    # Dry run to see what would be processed
    python batch_process.py --language csharp --path "CSharp_Projects/eRx" --dry-run

    # Skip files that already have commented versions
    python batch_process.py --language vfp --path "VFP_Files_Copy" --skip-existing
"""

import sys
import time
import logging
from pathlib import Path
from typing import Optional, Tuple, List, Dict
import click

from config import ConfigManager
from instructor_client import InstructorLLMClient
from two_phase_processor import TwoPhaseProcessor
from file_scanner import CodeFileScanner
from progress_tracker import ProgressTracker, FileProcessingResult
from language_handlers import get_handler, list_supported_languages


# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('batch_processing.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger('batch_processor')


def detect_path_type(path: Path, handler) -> str:
    """
    Detect if path is a file, directory, or invalid.

    Args:
        path: Path to check
        handler: Language handler for file extension validation

    Returns:
        'file', 'directory', or 'invalid'
    """
    if not path.exists():
        return 'invalid'

    if path.is_file():
        # Check if it's a valid file for this language
        valid_extensions = handler.get_file_extensions()
        if path.suffix.lower() in [ext.lower() for ext in valid_extensions]:
            return 'file'
        else:
            return 'invalid'

    if path.is_dir():
        return 'directory'

    return 'invalid'


def process_single_file(
    file_path: Path,
    config_manager: ConfigManager,
    client: InstructorLLMClient,
    processor: TwoPhaseProcessor,
    handler,
    root_directory: Optional[Path] = None
) -> Tuple[bool, FileProcessingResult]:
    """
    Process a single code file.

    Args:
        file_path: Path to the file to process
        config_manager: Configuration manager
        client: LLM client
        processor: Two-phase processor
        handler: Language handler
        root_directory: Root directory for relative path calculation

    Returns:
        Tuple of (success, FileProcessingResult)
    """
    start_time = time.time()

    try:
        logger.info(f"Processing file: {file_path}")

        # Determine encoding based on language
        encoding = 'latin1' if handler.get_language_name() == 'vfp' else 'utf-8'

        # Read the file
        with open(file_path, 'r', encoding=encoding, errors='ignore') as f:
            code = f.read()

        # Calculate relative path
        if root_directory:
            try:
                relative_path = str(file_path.relative_to(root_directory))
            except ValueError:
                relative_path = str(file_path)
        else:
            relative_path = file_path.name

        # Process the file
        result = processor.process_file(
            code=code,
            filename=file_path.name,
            relative_path=relative_path
        )

        if not result.success:
            processing_time = time.time() - start_time
            return False, FileProcessingResult(
                file_path=str(file_path),
                status='failed',
                processing_time=processing_time,
                error_message=result.error_message or "Unknown error",
                original_size=len(code),
                commented_size=0,
                validation_passed=False
            )

        # Generate output filename
        output_path = file_path.parent / f"{file_path.stem}_commented{file_path.suffix}"

        # Save the commented code
        with open(output_path, 'w', encoding=encoding, errors='ignore') as f:
            f.write(result.commented_code)

        processing_time = time.time() - start_time

        logger.info(f"Successfully processed: {file_path} -> {output_path}")
        logger.info(f"Processing time: {processing_time:.2f}s")

        return True, FileProcessingResult(
            file_path=str(file_path),
            status='success',
            processing_time=processing_time,
            error_message=None,
            original_size=len(code),
            commented_size=len(result.commented_code),
            validation_passed=True,
            processing_method="two_phase",
            comments_added=len(result.commented_code.split('\n')) - len(code.split('\n'))
        )

    except Exception as e:
        processing_time = time.time() - start_time
        logger.error(f"Error processing {file_path}: {e}", exc_info=True)

        return False, FileProcessingResult(
            file_path=str(file_path),
            status='failed',
            processing_time=processing_time,
            error_message=str(e),
            original_size=0,
            commented_size=0,
            validation_passed=False
        )


def should_skip_existing(file_info: Dict[str, str]) -> bool:
    """
    Check if the output file already exists.

    Args:
        file_info: File information dictionary

    Returns:
        True if output file exists, False otherwise
    """
    output_path = Path(file_info['output_path'])
    directory = Path(file_info['directory'])
    filename = file_info['filename']
    stem = Path(filename).stem
    suffix = Path(filename).suffix
    adjusted_output = directory / f"{stem}_commented{suffix}"

    return adjusted_output.exists()


def process_batch(
    directory_path: Path,
    config_manager: ConfigManager,
    handler,
    skip_existing: bool = False,
    dry_run: bool = False,
    resume: bool = False
) -> None:
    """
    Process all code files in a directory for the specified language.

    Args:
        directory_path: Directory to process
        config_manager: Configuration manager
        handler: Language handler
        skip_existing: Skip files that already have commented versions
        dry_run: Only show what would be processed
        resume: Resume from previous session
    """
    language = handler.get_language_name()
    logger.info(f"Starting batch processing for directory: {directory_path}")
    logger.info(f"Language: {language}")

    # Get root directory from config for relative path calculation
    root_dir = Path(config_manager.config['processing']['root_directory']).resolve()
    logger.info(f"Root directory for relative paths: {root_dir}")

    # Initialize scanner with language handler
    scanner = CodeFileScanner(str(directory_path), handler=handler)

    # Scan for code files
    print(f"\nScanning for {language.upper()} files...")
    files = scanner.scan_code_files()

    if not files:
        print(f"No {language.upper()} files found to process.")
        return

    # Print scan report
    scanner.print_scan_report(files)

    # Filter files if skip_existing is enabled
    if skip_existing:
        original_count = len(files)
        files = [f for f in files if not should_skip_existing(f)]
        skipped_count = original_count - len(files)
        if skipped_count > 0:
            print(f"\nSkipping {skipped_count} files that already have commented versions")
            print(f"Files to process: {len(files)}")

    if dry_run:
        print("\n" + "="*60)
        print("DRY RUN MODE - No files will be processed")
        print("="*60)
        print(f"\nWould process {len(files)} files:")
        for file_info in files[:10]:  # Show first 10
            print(f"  - {file_info['relative_path']}")
        if len(files) > 10:
            print(f"  ... and {len(files) - 10} more files")
        return

    # Confirm processing
    print(f"\nReady to process {len(files)} {language.upper()} files.")

    # Initialize progress tracker
    session_id = None if not resume else "resumable_session"
    tracker = ProgressTracker(session_id=session_id)
    tracker.initialize_processing(files, str(root_dir))

    # Initialize LLM client and processor
    print("\nInitializing two-phase processor...")
    client = InstructorLLMClient(config_manager)
    processor = TwoPhaseProcessor(client, handler, config=config_manager.config)
    print(f"Processor initialized for {language.upper()}.\n")

    # Process files
    print("Starting file processing...\n")
    print("="*80)

    for file_info in files:
        tracker.start_file_processing(file_info)

        file_path = Path(file_info['full_path'])

        # Check if we should skip this file
        if skip_existing and should_skip_existing(file_info):
            result = FileProcessingResult(
                file_path=str(file_path),
                status='skipped',
                processing_time=0.0,
                error_message="Output file already exists",
                original_size=file_info['file_size'],
                commented_size=0,
                validation_passed=False
            )
            tracker.complete_file_processing(file_info, result)
            continue

        # Process the file
        success, result = process_single_file(
            file_path,
            config_manager,
            client,
            processor,
            handler,
            root_directory=root_dir
        )

        tracker.complete_file_processing(file_info, result)

    print("\n" + "="*80)
    print("Processing complete!")
    print("="*80)

    # Print final report
    tracker.print_final_report()


@click.command()
@click.option(
    '--language', '-l',
    required=True,
    type=click.Choice(['vfp', 'csharp'], case_sensitive=False),
    help='Programming language to process (vfp or csharp)'
)
@click.option(
    '--path', '-p',
    required=True,
    type=click.Path(exists=True),
    help='Path to process (file, folder, or directory)'
)
@click.option(
    '--config', '-c',
    default='config.json',
    type=click.Path(exists=True),
    help='Path to configuration file (default: config.json)'
)
@click.option(
    '--skip-existing',
    is_flag=True,
    default=False,
    help='Skip files that already have _commented versions'
)
@click.option(
    '--dry-run',
    is_flag=True,
    default=False,
    help='Show what would be processed without actually processing'
)
@click.option(
    '--resume',
    is_flag=True,
    default=False,
    help='Resume from previous processing session'
)
def main(language: str, path: str, config: str, skip_existing: bool, dry_run: bool, resume: bool):
    """
    Multi-Language Batch Processor - Process code files with two-phase commenting.

    Supports VFP (.prg, .spr) and C# (.cs) files.

    This tool can process:
    - Entire directories (recursively)
    - Single folders
    - Individual files

    Examples:

        # Process VFP files
        python batch_process.py --language vfp --path "VFP_Files_Copy"

        # Process C# files in eRx project
        python batch_process.py --language csharp --path "CSharp_Projects/eRx"

        # Process single VFP file
        python batch_process.py --language vfp --path "VFP_Files_Copy/Forms/main.prg"

        # Dry run for C# files
        python batch_process.py --language csharp --path "CSharp_Projects/MHR" --dry-run

        # Skip already commented files
        python batch_process.py --language vfp --path "VFP_Files_Copy" --skip-existing
    """
    print("="*80)
    print(f"{language.upper()} Batch Processor - Two-Phase Commenting System")
    print("="*80)
    print()

    # Load configuration
    try:
        config_manager = ConfigManager(config)
        print(f"Configuration loaded from: {config}")
        print(f"LLM Endpoint: {config_manager.config['llm']['endpoint']}")
        print(f"Model: {config_manager.config['llm']['model']}")
        print(f"Language: {language.upper()}")
        print()
    except Exception as e:
        print(f"Error loading configuration: {e}")
        sys.exit(1)

    # Get language handler
    try:
        handler = get_handler(language, config=config_manager.config)
        print(f"Language handler loaded: {handler.get_language_name()}")
        print(f"File extensions: {', '.join(handler.get_file_extensions())}")
        print()
    except ValueError as e:
        print(f"Error: {e}")
        print(f"Supported languages: {', '.join(list_supported_languages())}")
        sys.exit(1)

    # Detect path type
    path_obj = Path(path)
    path_type = detect_path_type(path_obj, handler)

    if path_type == 'invalid':
        valid_exts = ', '.join(handler.get_file_extensions())
        print(f"Error: Invalid path or not a {language.upper()} file: {path}")
        print(f"Path must be a directory or a file with extension: {valid_exts}")
        sys.exit(1)

    # Route to appropriate processing mode
    if path_type == 'file':
        print(f"Mode: Single File Processing")
        print(f"File: {path_obj}")
        print()

        # Initialize LLM client and processor
        client = InstructorLLMClient(config_manager)
        processor = TwoPhaseProcessor(client, handler, config=config_manager.config)

        # Process the file
        success, result = process_single_file(
            path_obj,
            config_manager,
            client,
            processor,
            handler,
            root_directory=None
        )

        if success:
            print(f"\n✓ File processed successfully!")
            print(f"  Processing time: {result.processing_time:.2f}s")
            print(f"  Comments added: {result.comments_added} lines")
        else:
            print(f"\n✗ File processing failed:")
            print(f"  Error: {result.error_message}")
            sys.exit(1)

    elif path_type == 'directory':
        print(f"Mode: Batch Directory Processing")
        print(f"Directory: {path_obj}")
        print()

        process_batch(
            path_obj,
            config_manager,
            handler,
            skip_existing=skip_existing,
            dry_run=dry_run,
            resume=resume
        )


if __name__ == '__main__':
    main()
