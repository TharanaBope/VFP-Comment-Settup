"""
VFP Batch Processor - Production CLI Tool
==========================================
Command-line tool for batch processing Visual FoxPro files with the two-phase
commenting system. Supports processing entire directories, single folders, or
individual files.

Usage Examples:
    # Process entire VFP_Files_Copy directory
    python batch_process_vfp.py --path "VFP_Files_Copy"

    # Process single folder
    python batch_process_vfp.py --path "VFP_Files_Copy/Forms"

    # Process single file
    python batch_process_vfp.py --path "VFP_Files_Copy/Custom Prgs/getdailycomments.prg"

    # Dry run to see what would be processed
    python batch_process_vfp.py --path "VFP_Files_Copy" --dry-run

    # Skip files that already have commented versions
    python batch_process_vfp.py --path "VFP_Files_Copy" --skip-existing
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
from file_scanner import VFPFileScanner
from progress_tracker import ProgressTracker, FileProcessingResult


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


def detect_path_type(path: Path) -> str:
    """
    Detect if path is a file, directory, or invalid.

    Args:
        path: Path to check

    Returns:
        'file', 'directory', or 'invalid'
    """
    if not path.exists():
        return 'invalid'

    if path.is_file():
        # Check if it's a VFP file
        if path.suffix.lower() in ['.prg', '.spr']:
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
    root_directory: Optional[Path] = None
) -> Tuple[bool, FileProcessingResult]:
    """
    Process a single VFP file.

    Args:
        file_path: Path to the file to process
        config_manager: Configuration manager
        client: LLM client
        processor: Two-phase processor
        root_directory: Root directory for relative path calculation

    Returns:
        Tuple of (success, FileProcessingResult)
    """
    start_time = time.time()

    try:
        logger.info(f"Processing file: {file_path}")

        # Read the file
        with open(file_path, 'r', encoding='latin1', errors='ignore') as f:
            vfp_code = f.read()

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
            vfp_code=vfp_code,
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
                original_size=len(vfp_code),
                commented_size=0,
                validation_passed=False
            )

        # Generate output filename
        output_path = file_path.parent / f"{file_path.stem}_commented{file_path.suffix}"

        # Save the commented code
        with open(output_path, 'w', encoding='latin1', errors='ignore') as f:
            f.write(result.commented_code)

        processing_time = time.time() - start_time

        logger.info(f"Successfully processed: {file_path} -> {output_path}")
        logger.info(f"Processing time: {processing_time:.2f}s")

        return True, FileProcessingResult(
            file_path=str(file_path),
            status='success',
            processing_time=processing_time,
            error_message=None,
            original_size=len(vfp_code),
            commented_size=len(result.commented_code),
            validation_passed=True,
            processing_method="two_phase",
            comments_added=len(result.commented_code.split('\n')) - len(vfp_code.split('\n'))
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
    # Adjust output path to use _commented suffix
    directory = Path(file_info['directory'])
    filename = file_info['filename']
    stem = Path(filename).stem
    suffix = Path(filename).suffix
    adjusted_output = directory / f"{stem}_commented{suffix}"

    return adjusted_output.exists()


def process_batch(
    directory_path: Path,
    config_manager: ConfigManager,
    skip_existing: bool = False,
    dry_run: bool = False,
    resume: bool = False
) -> None:
    """
    Process all VFP files in a directory.

    Args:
        directory_path: Directory to process
        config_manager: Configuration manager
        skip_existing: Skip files that already have commented versions
        dry_run: Only show what would be processed
        resume: Resume from previous session
    """
    logger.info(f"Starting batch processing for directory: {directory_path}")

    # Get VFP root directory from config for relative path calculation
    vfp_root = Path(config_manager.config['processing']['root_directory']).resolve()
    logger.info(f"VFP root directory for relative paths: {vfp_root}")

    # Initialize scanner
    scanner = VFPFileScanner(str(directory_path))

    # Scan for VFP files
    print("\nScanning for VFP files...")
    files = scanner.scan_vfp_files()

    if not files:
        print("No VFP files found to process.")
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
    print(f"\nReady to process {len(files)} VFP files.")

    # Initialize progress tracker
    session_id = None if not resume else "resumable_session"
    tracker = ProgressTracker(session_id=session_id)
    tracker.initialize_processing(files, str(vfp_root))

    # Initialize LLM client and processor
    print("\nInitializing two-phase processor...")
    client = InstructorLLMClient(config_manager)
    processor = TwoPhaseProcessor(client, config=config_manager.config)
    print("Processor initialized.\n")

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
            root_directory=vfp_root
        )

        tracker.complete_file_processing(file_info, result)

    print("\n" + "="*80)
    print("Processing complete!")
    print("="*80)

    # Print final report
    tracker.print_final_report()


@click.command()
@click.option(
    '--path', '-p',
    required=True,
    type=click.Path(exists=True),
    help='Path to process (file, folder, or directory). Use forward slashes.'
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
def main(path: str, config: str, skip_existing: bool, dry_run: bool, resume: bool):
    """
    VFP Batch Processor - Process Visual FoxPro files with two-phase commenting.

    This tool can process:
    - Entire directories (recursively)
    - Single folders
    - Individual files

    Examples:

        # Process entire VFP_Files_Copy directory
        python batch_process_vfp.py --path "VFP_Files_Copy"

        # Process single folder
        python batch_process_vfp.py --path "VFP_Files_Copy/Forms"

        # Process single file
        python batch_process_vfp.py --path "VFP_Files_Copy/Custom Prgs/getdailycomments.prg"

        # Dry run
        python batch_process_vfp.py --path "VFP_Files_Copy" --dry-run
    """
    print("="*80)
    print("VFP Batch Processor - Two-Phase Commenting System")
    print("="*80)
    print()

    # Load configuration
    try:
        config_manager = ConfigManager(config)
        print(f"Configuration loaded from: {config}")
        print(f"LLM Endpoint: {config_manager.config['llm']['endpoint']}")
        print(f"Model: {config_manager.config['llm']['model']}")
        print()
    except Exception as e:
        print(f"Error loading configuration: {e}")
        sys.exit(1)

    # Detect path type
    path_obj = Path(path)
    path_type = detect_path_type(path_obj)

    if path_type == 'invalid':
        print(f"Error: Invalid path or not a VFP file: {path}")
        print("Path must be a directory or a VFP file (.prg or .spr)")
        sys.exit(1)

    # Route to appropriate processing mode
    if path_type == 'file':
        print(f"Mode: Single File Processing")
        print(f"File: {path_obj}")
        print()

        # Initialize LLM client and processor
        client = InstructorLLMClient(config_manager)
        processor = TwoPhaseProcessor(client, config=config_manager.config)

        # Process the file
        success, result = process_single_file(
            path_obj,
            config_manager,
            client,
            processor
        )

        if success:
            print("\n" + "="*80)
            print("SUCCESS - File processed successfully!")
            print("="*80)
            print(f"Original size: {result.original_size} bytes")
            print(f"Commented size: {result.commented_size} bytes")
            print(f"Processing time: {result.processing_time:.2f} seconds")
            print(f"Comments added: {result.comments_added} lines")

            # Show output location
            output_path = path_obj.parent / f"{path_obj.stem}_commented{path_obj.suffix}"
            print(f"\nOutput saved to: {output_path}")
        else:
            print("\n" + "="*80)
            print("FAILED - Error processing file")
            print("="*80)
            print(f"Error: {result.error_message}")
            sys.exit(1)

    elif path_type == 'directory':
        print(f"Mode: Batch Processing")
        print(f"Directory: {path_obj}")
        print(f"Skip existing: {skip_existing}")
        print(f"Dry run: {dry_run}")
        print(f"Resume: {resume}")
        print()

        # Process batch
        process_batch(
            path_obj,
            config_manager,
            skip_existing=skip_existing,
            dry_run=dry_run,
            resume=resume
        )


if __name__ == "__main__":
    main()
