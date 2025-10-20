"""
Main Entry Point for VFP Commenting Tool - LEGACY ARCHITECTURE
=============================================================
Command-line interface for the Visual FoxPro legacy code commenting automation tool.
This tool processes VFP files (.prg and .spr) using direct LLM interaction with
comprehensive validation and chunking strategies for optimal comment quality.

FEATURES:
- Direct LLM processing for high-quality, contextual comments
- Context-aware chunking for large files
- Multiple validation layers for code preservation
- Session persistence for resumable processing
- Comprehensive logging and progress tracking
"""
import time
import click
import logging
import sys
import os
from pathlib import Path
from typing import List, Dict, Optional

# Import our modules
from config import ConfigManager
from file_scanner import VFPFileScanner
from llm_client import LLMClient
from vfp_processor import VFPProcessor
from progress_tracker import ProgressTracker, FileProcessingResult
from utils import CodePreservationValidator

# Version info
__version__ = "1.0.0"

def setup_logging(log_level: str = "INFO", log_file: Optional[str] = None) -> None:
    """
    Setup comprehensive logging for the application.

    Args:
        log_level: Logging level (DEBUG, INFO, WARNING, ERROR)
        log_file: Optional log file path
    """
    # Convert string level to logging constant
    numeric_level = getattr(logging, log_level.upper(), logging.INFO)

    # Create formatter
    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )

    # Setup root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(numeric_level)

    # Clear any existing handlers
    root_logger.handlers.clear()

    # Console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(formatter)
    root_logger.addHandler(console_handler)

    # File handler if specified
    if log_file:
        try:
            file_handler = logging.FileHandler(log_file, encoding='utf-8')
            file_handler.setFormatter(formatter)
            root_logger.addHandler(file_handler)
            print(f"Logging to file: {log_file}")
        except Exception as e:
            print(f"Warning: Could not setup file logging: {e}")

@click.group(invoke_without_command=True)
@click.option('--version', is_flag=True, help='Show version information')
@click.pass_context
def cli(ctx, version):
    """
    VFP Legacy Code Commenting Tool

    Automatically adds comprehensive comments to Visual FoxPro (.prg and .spr) files
    using a local LLM while preserving original code structure and functionality.

    CRITICAL: This tool NEVER modifies original code - it only adds comments.
    """
    if version:
        click.echo(f"VFP Commenting Tool v{__version__}")
        return

    if ctx.invoked_subcommand is None:
        # Show help if no command provided
        click.echo(ctx.get_help())

@cli.command()
@click.option('--root', '-r', required=True, type=click.Path(exists=True, file_okay=False, path_type=Path),
              help='Root directory containing VFP files to process')
@click.option('--config', '-c', type=click.Path(exists=True, path_type=Path),
              help='Configuration file path (default: config.json)')
@click.option('--dry-run', is_flag=True,
              help='Preview files that would be processed without making changes')
@click.option('--resume', is_flag=True,
              help='Resume interrupted processing session')
@click.option('--verbose', '-v', is_flag=True,
              help='Enable verbose logging')
def batch(root, config, dry_run, resume, verbose):
    """
    Process all VFP files in the root directory and subdirectories.

    This command recursively scans for .prg and .spr files, processes each one
    to add comprehensive comments, and saves the results with '_commented' suffix.

    Example:
        python main.py batch --root "D:/VFP_Files_Copy" --verbose
    """
    try:
        # Initialize configuration
        config_path = config or Path("config.json")
        if not config_path.exists():
            click.echo(f"❌ Configuration file not found: {config_path}", err=True)
            sys.exit(1)

        config_manager = ConfigManager(str(config_path))

        # Setup logging
        log_level = "DEBUG" if verbose else "INFO"
        log_file = config_manager.get('logging.log_file', 'vfp_commenting.log')
        setup_logging(log_level, log_file)

        logger = logging.getLogger(__name__)
        logger.info(f"Starting VFP batch processing v{__version__}")
        logger.info(f"Root directory: {root}")
        logger.info(f"Mode: {'DRY RUN' if dry_run else 'PROCESSING'}")

        if resume:
            logger.info("Resume mode enabled - will continue from previous session")

        # Display configuration summary
        click.echo(f"\n🔧 VFP COMMENTING TOOL v{__version__}")
        click.echo(f"Root directory: {root}")
        click.echo(f"Config file: {config_path}")
        click.echo(f"Mode: {'🔍 DRY RUN' if dry_run else '🚀 PROCESSING'}")

        # Initialize components
        logger.info("Initializing system components...")

        # Initialize LLM client
        logger.info("Initializing LLM client...")
        llm_client = LLMClient(config_manager)
        logger.info("✓ LLM client initialized")

        # Initialize VFP processor
        logger.info("Initializing VFP processor...")
        vfp_processor = VFPProcessor(config_manager)
        logger.info("✓ VFP processor initialized")

        # Initialize file scanner
        logger.info("Initializing file scanner...")
        scanner = VFPFileScanner(str(root))
        logger.info("✓ File scanner initialized")

        # Initialize progress tracker
        progress_file = config_manager.get('logging.progress_file', 'processing_progress.json')
        tracker = ProgressTracker(progress_file)

        if resume and tracker.load_progress():
            logger.info(f"✓ Resumed session: {tracker.get_session_summary()}")
        else:
            tracker.start_new_session(str(root))
            logger.info("✓ Started new processing session")

        # Scan for VFP files
        click.echo(f"\n📂 Scanning for VFP files in: {root}")
        vfp_files = scanner.scan_vfp_files()

        if not vfp_files:
            click.echo("❌ No VFP files found to process", err=True)
            sys.exit(1)

        logger.info(f"Found {len(vfp_files)} VFP files total")
        scanner.print_scan_report(vfp_files)

        # Filter files based on resume mode
        if resume:
            files_to_process = tracker.get_remaining_files(vfp_files)
            logger.info(f"Resume mode: {len(files_to_process)} files remaining to process")
        else:
            files_to_process = [f for f in vfp_files if not scanner.is_already_commented(f['filename'])]
            logger.info(f"Found {len(files_to_process)} files to process (skipping already commented)")

        if not files_to_process:
            click.echo("✅ All files already processed or no files to process")
            return

        # Display processing summary
        click.echo(f"\n📊 PROCESSING SUMMARY")
        click.echo(f"Total files found: {len(vfp_files)}")
        click.echo(f"Files to process: {len(files_to_process)}")
        click.echo(f"Already processed: {len(vfp_files) - len(files_to_process)}")

        if dry_run:
            click.echo(f"\n🔍 DRY RUN - Files that would be processed:")
            for i, file_info in enumerate(files_to_process[:10], 1):
                size_kb = file_info.get('file_size', 0) / 1024
                click.echo(f"  {i:3d}. {file_info['relative_path']} ({size_kb:.1f} KB)")

            if len(files_to_process) > 10:
                click.echo(f"  ... and {len(files_to_process) - 10} more files")

            click.echo(f"\nTo actually process files, run without --dry-run")
            return

        # Confirm processing
        if not click.confirm(f"\n🚀 Process {len(files_to_process)} VFP files?"):
            click.echo("❌ Processing cancelled by user")
            return

        # Process files
        click.echo(f"\n🔄 Processing {len(files_to_process)} VFP files...")

        start_time = time.time()
        successful_files = 0
        failed_files = 0

        for i, file_info in enumerate(files_to_process, 1):
            filename = file_info['filename']
            relative_path = file_info['relative_path']

            click.echo(f"\n📄 [{i}/{len(files_to_process)}] Processing: {filename}")
            logger.info(f"Processing file {i}/{len(files_to_process)}: {filename}")

            file_start_time = time.time()

            try:
                # Process file with LLM
                commented_content = vfp_processor.process_file_with_llm(file_info, llm_client)

                if commented_content:
                    # Save commented file
                    success = vfp_processor.save_commented_file(file_info, commented_content)

                    if success:
                        file_duration = time.time() - file_start_time

                        # Get processing statistics
                        original_content = vfp_processor.read_vfp_file(file_info['full_path'])
                        if original_content:
                            stats = vfp_processor.get_processing_stats(original_content, commented_content)

                            click.echo(f"  ✅ Success ({file_duration:.1f}s)")
                            click.echo(f"     Lines: {stats['original_lines']} → {stats['commented_lines']} (+{stats['added_comments']} comments)")
                            click.echo(f"     Size: {stats['original_size']} → {stats['commented_size']} bytes")

                            # Record success in tracker
                            result = FileProcessingResult(
                                filename=filename,
                                success=True,
                                processing_time=file_duration,
                                original_lines=stats['original_lines'],
                                commented_lines=stats['commented_lines'],
                                comments_added=stats['added_comments']
                            )
                            tracker.record_file_result(result)
                            successful_files += 1
                        else:
                            click.echo(f"  ⚠️  Processed but cannot verify statistics")
                            successful_files += 1
                    else:
                        click.echo(f"  ❌ Failed to save commented file")
                        result = FileProcessingResult(filename=filename, success=False, error_message="Save failed")
                        tracker.record_file_result(result)
                        failed_files += 1
                else:
                    click.echo(f"  ❌ LLM processing failed")
                    result = FileProcessingResult(filename=filename, success=False, error_message="LLM processing failed")
                    tracker.record_file_result(result)
                    failed_files += 1

            except Exception as e:
                logger.error(f"Error processing {filename}: {str(e)}")
                click.echo(f"  ❌ Error: {str(e)}")
                result = FileProcessingResult(filename=filename, success=False, error_message=str(e))
                tracker.record_file_result(result)
                failed_files += 1

            # Save progress after each file
            tracker.save_progress()

        # Final summary
        total_time = time.time() - start_time
        success_rate = (successful_files / len(files_to_process)) * 100 if files_to_process else 0

        click.echo(f"\n🏁 PROCESSING COMPLETE")
        click.echo(f"Total time: {total_time:.1f} seconds")
        click.echo(f"Successful: {successful_files}/{len(files_to_process)} ({success_rate:.1f}%)")
        click.echo(f"Failed: {failed_files}")

        if successful_files > 0:
            avg_time = total_time / len(files_to_process)
            click.echo(f"Average time per file: {avg_time:.1f} seconds")

        # Log final summary
        logger.info(f"Batch processing completed: {successful_files} successful, {failed_files} failed")
        logger.info(f"Success rate: {success_rate:.1f}%")
        logger.info(f"Total processing time: {total_time:.1f} seconds")

        if failed_files > 0:
            logger.warning(f"Some files failed processing. Check logs for details.")
            sys.exit(1)
        else:
            logger.info("✓ All files processed successfully")
            click.echo(f"✅ All files processed successfully!")

    except Exception as e:
        logger.error(f"Batch processing failed: {e}")
        click.echo(f"❌ Batch processing failed: {e}", err=True)
        sys.exit(1)

@cli.command()
@click.option('--file', '-f', required=True, type=click.Path(exists=True, dir_okay=False, path_type=Path),
              help='Single VFP file to process')
@click.option('--config', '-c', type=click.Path(exists=True, path_type=Path),
              help='Configuration file path (default: config.json)')
@click.option('--verbose', '-v', is_flag=True,
              help='Enable verbose logging')
def process_file(file, config, verbose):
    """
    Process a single VFP file to add comprehensive comments.

    This command processes a single .prg or .spr file, adds comprehensive
    comments using the LLM, and saves the result with '_commented' suffix.

    Example:
        python main.py process-file --file "example.prg" --verbose
    """
    try:
        # Initialize configuration
        config_path = config or Path("config.json")
        if not config_path.exists():
            click.echo(f"❌ Configuration file not found: {config_path}", err=True)
            sys.exit(1)

        config_manager = ConfigManager(str(config_path))

        # Setup logging
        log_level = "DEBUG" if verbose else "INFO"
        log_file = config_manager.get('logging.log_file', 'vfp_commenting.log')
        setup_logging(log_level, log_file)

        logger = logging.getLogger(__name__)
        logger.info(f"Starting single file processing v{__version__}")
        logger.info(f"Target file: {file}")
        logger.info(f"Mode: PROCESSING")

        # Validate file extension
        if file.suffix.lower() not in ['.prg', '.spr']:
            click.echo(f"❌ Invalid file type: {file.suffix}. Expected .prg or .spr", err=True)
            sys.exit(1)

        # Check if file already commented
        if '_commented' in file.stem:
            click.echo(f"⚠️  File appears to already be commented: {file.name}")
            if not click.confirm("Process anyway?"):
                return

        # Display file information
        file_size = file.stat().st_size
        click.echo(f"\n📄 SINGLE FILE PROCESSING")
        click.echo(f"Input file:  {file}")
        click.echo(f"Output file: {file.parent / (file.stem + '_commented' + file.suffix)}")
        click.echo(f"File size:   {file_size} bytes")

        # Initialize components
        logger.info("Initializing LLM client...")
        llm_client = LLMClient(config_manager)

        logger.info("Initializing VFP processor...")
        vfp_processor = VFPProcessor(config_manager)

        # Create file info dictionary
        file_info = {
            'full_path': str(file),
            'filename': file.name,
            'relative_path': file.name,  # For single file, relative path is just filename
            'file_size': file_size
        }

        # Confirm processing
        click.echo(f"\n⚡ ABOUT TO PROCESS SINGLE FILE")
        click.echo(f"This will:")
        click.echo(f"• Process {file.name} using LLM for comprehensive commenting")
        click.echo(f"• Apply validation to ensure original code integrity")
        click.echo(f"• Create new file: {file.stem}_commented{file.suffix}")
        click.echo(f"• Strong safety measures with quality prioritization")

        if not click.confirm("\nProceed with processing? [y/N]: "):
            click.echo("❌ Processing cancelled by user")
            return

        # Process the file
        click.echo(f"\n🚀 Processing file: {file.name}")

        start_time = time.time()

        try:
            # Process with LLM
            commented_content = vfp_processor.process_file_with_llm(file_info, llm_client)

            if commented_content:
                # Save commented file
                success = vfp_processor.save_commented_file(file_info, commented_content)

                if success:
                    processing_time = time.time() - start_time

                    # Get processing statistics
                    original_content = vfp_processor.read_vfp_file(str(file))
                    if original_content:
                        stats = vfp_processor.get_processing_stats(original_content, commented_content)

                        click.echo(f"\n✅ SUCCESS!")
                        click.echo(f"Processing time: {processing_time:.1f} seconds")
                        click.echo(f"Original size: {stats['original_size']} characters")
                        click.echo(f"Commented size: {stats['commented_size']} characters")
                        click.echo(f"Added content: {stats['size_increase']} characters")
                        click.echo(f"")
                        click.echo(f"📁 Commented file saved: {file.parent / (file.stem + '_commented' + file.suffix)}")

                        logger.info(f"✓ Successfully processed: {file.name}")
                    else:
                        click.echo(f"✅ Processing completed, but cannot read statistics")
                else:
                    click.echo(f"❌ Failed to save commented file")
                    logger.error(f"Failed to save commented file for: {file.name}")
                    sys.exit(1)
            else:
                click.echo(f"❌ LLM processing failed")
                logger.error(f"LLM processing failed for: {file.name}")
                sys.exit(1)

        except Exception as e:
            logger.error(f"Error processing {file.name}: {str(e)}")
            click.echo(f"❌ Processing failed: {str(e)}", err=True)
            sys.exit(1)

    except Exception as e:
        logger.error(f"Single file processing failed: {e}")
        click.echo(f"❌ Single file processing failed: {e}", err=True)
        sys.exit(1)

@cli.command()
@click.option('--root', '-r', required=True, type=click.Path(exists=True, file_okay=False, path_type=Path),
              help='Root directory to analyze')
@click.option('--config', '-c', type=click.Path(exists=True, path_type=Path),
              help='Configuration file path (default: config.json)')
def analyze(root, config):
    """
    Analyze the directory structure and show processing statistics.

    This command scans the directory structure, counts VFP files,
    identifies already processed files, and provides detailed statistics
    without performing any processing.

    Example:
        python main.py analyze --root "D:/VFP_Files_Copy"
    """
    try:
        # Initialize configuration
        config_path = config or Path("config.json")
        if not config_path.exists():
            click.echo(f"❌ Configuration file not found: {config_path}", err=True)
            sys.exit(1)

        config_manager = ConfigManager(str(config_path))

        # Initialize file scanner
        scanner = VFPFileScanner(str(root))

        # Scan for files
        click.echo(f"📊 DIRECTORY ANALYSIS")
        click.echo(f"Root: {root}")
        click.echo(f"\n🔍 Scanning for VFP files...")

        vfp_files = scanner.scan_vfp_files()

        if not vfp_files:
            click.echo("❌ No VFP files found")
            return

        # Categorize files
        unprocessed_files = []
        processed_files = []

        for file_info in vfp_files:
            if scanner.is_already_commented(file_info['filename']):
                processed_files.append(file_info)
            else:
                unprocessed_files.append(file_info)

        # Display results
        click.echo(f"\n📈 ANALYSIS RESULTS")
        click.echo(f"Total VFP files found: {len(vfp_files)}")
        click.echo(f"Unprocessed files: {len(unprocessed_files)}")
        click.echo(f"Already commented: {len(processed_files)}")

        # Size statistics
        total_size = sum(f.get('file_size', 0) for f in vfp_files)
        unprocessed_size = sum(f.get('file_size', 0) for f in unprocessed_files)
        processed_size = sum(f.get('file_size', 0) for f in processed_files)

        click.echo(f"\n💾 SIZE STATISTICS")
        click.echo(f"Total size: {total_size / 1024:.1f} KB")
        click.echo(f"Unprocessed: {unprocessed_size / 1024:.1f} KB")
        click.echo(f"Processed: {processed_size / 1024:.1f} KB")

        # Show detailed scan report
        scanner.print_scan_report(vfp_files)

        # Show sample unprocessed files
        if unprocessed_files:
            click.echo(f"\n📋 SAMPLE UNPROCESSED FILES (first 10):")
            for i, file_info in enumerate(unprocessed_files[:10], 1):
                size_kb = file_info.get('file_size', 0) / 1024
                click.echo(f"  {i:2d}. {file_info['relative_path']} ({size_kb:.1f} KB)")

            if len(unprocessed_files) > 10:
                click.echo(f"     ... and {len(unprocessed_files) - 10} more")

        click.echo(f"\n✅ Analysis complete")

    except Exception as e:
        click.echo(f"❌ Analysis failed: {e}", err=True)
        sys.exit(1)

if __name__ == "__main__":
    cli()