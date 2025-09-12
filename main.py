"""
Main Entry Point for VFP Commenting Tool
========================================
Command-line interface for the Visual FoxPro legacy code commenting automation tool.
This tool processes VFP files (.prg and .spr) using a local LLM while maintaining
STRICT code preservation - original code is never modified, only comments are added.

CRITICAL SAFETY FEATURES:
- Multiple validation layers to prevent code modification
- Comprehensive logging and progress tracking
- Atomic file operations with rollback capability
- Session persistence for resumable processing
"""

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
    
    🛡️  CRITICAL: This tool NEVER modifies original code - it only adds comments.
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
              help='Show what would be processed without making changes')
@click.option('--resume', is_flag=True,
              help='Resume interrupted processing from last session')
@click.option('--session-id', type=str,
              help='Specific session ID to resume (used with --resume)')
@click.option('--log-level', type=click.Choice(['DEBUG', 'INFO', 'WARNING', 'ERROR']), default='INFO',
              help='Logging level')
@click.option('--max-files', type=int,
              help='Maximum number of files to process (for testing)')
def process(root, config, dry_run, resume, session_id, log_level, max_files):
    """
    Process VFP files in the specified directory tree.
    
    This command recursively scans for .prg and .spr files and processes them
    with the local LLM to add comprehensive comments while preserving original code.
    """
    try:
        # Initialize configuration
        config_manager = ConfigManager(str(config) if config else None)
        
        # Setup logging
        log_file = config_manager.get('logging.log_file') if not dry_run else None
        setup_logging(log_level, log_file)
        
        logger = logging.getLogger(__name__)
        logger.info(f"Starting VFP Commenting Tool v{__version__}")
        logger.info(f"Root directory: {root}")
        logger.info(f"Mode: {'DRY RUN' if dry_run else 'PROCESSING'}")
        
        # Print configuration summary
        if not dry_run:
            config_manager.print_config_summary()
        
        # Initialize file scanner
        logger.info("Initializing file scanner...")
        scanner = VFPFileScanner(str(root))
        
        # Scan for VFP files
        logger.info("Scanning for VFP files...")
        vfp_files = scanner.scan_vfp_files()
        
        if not vfp_files:
            click.echo("❌ No VFP files found in the specified directory.")
            return
        
        # Print scan report
        scanner.print_scan_report(vfp_files)
        
        # Apply max files limit if specified
        if max_files and max_files > 0:
            vfp_files = vfp_files[:max_files]
            click.echo(f"\n⚠️  Limited to first {max_files} files for testing")
        
        # Dry run - just show what would be processed
        if dry_run:
            click.echo(f"\n🔍 DRY RUN COMPLETE")
            click.echo(f"Would process {len(vfp_files)} files")
            return
        
        # Initialize progress tracker
        progress_session_id = session_id if resume else None
        tracker = ProgressTracker(
            session_id=progress_session_id,
            progress_file=config_manager.get('logging.progress_file', 'processing_progress.json')
        )
        
        # Check if resuming
        if resume and tracker.files_processed > 0:
            click.echo(f"\n📂 Resuming session: {tracker.session_id}")
            click.echo(f"Previously processed: {tracker.files_processed} files")
            
            # Filter out already processed files
            processed_paths = {result.file_path for result in tracker.processing_results}
            vfp_files = [f for f in vfp_files if f['full_path'] not in processed_paths]
            
            if not vfp_files:
                click.echo("✅ All files have been processed in this session.")
                tracker.print_final_report()
                return
            
            click.echo(f"Remaining files to process: {len(vfp_files)}")
        
        # Initialize processing components
        try:
            logger.info("Initializing LLM client...")
            llm_client = LLMClient(config_manager)
            
            logger.info("Initializing VFP processor...")
            processor = VFPProcessor(config_manager)
            
        except Exception as e:
            click.echo(f"❌ Failed to initialize processing components: {e}")
            logger.error(f"Initialization failed: {e}")
            return
        
        # Initialize progress tracking
        all_files = tracker.processing_results + [{'full_path': f['full_path']} for f in vfp_files]
        tracker.initialize_processing(all_files, str(root))
        
        # Confirm processing
        if not resume:
            click.echo(f"\n⚠️  ABOUT TO PROCESS {len(vfp_files)} FILES")
            click.echo("This will:")
            click.echo("• Send file contents to local LLM for comment generation")
            click.echo("• Create new files with '_commented' suffix")
            click.echo("• Validate that original code is never modified")
            
            if not click.confirm("\nProceed with processing?"):
                click.echo("Processing cancelled.")
                return
        
        # Process files
        click.echo(f"\n🚀 Starting processing...")
        successful_files = 0
        failed_files = 0
        
        try:
            for file_info in vfp_files:
                # Start file processing
                tracker.start_file_processing(file_info)
                
                # Check if file should be processed
                if not processor.should_process_file(file_info):
                    result = FileProcessingResult(
                        file_path=file_info['full_path'],
                        status='skipped',
                        processing_time=0.0,
                        error_message="File skipped based on processing criteria",
                        original_size=file_info.get('file_size', 0),
                        validation_passed=True
                    )
                    tracker.complete_file_processing(file_info, result)
                    continue
                
                # Process file with LLM
                start_time = time.time()
                
                try:
                    commented_content = processor.process_file_with_llm(file_info, llm_client)
                    processing_time = time.time() - start_time
                    
                    if commented_content:
                        # Read original content for validation
                        original_content = processor.read_vfp_file(file_info['full_path'])
                        
                        if original_content:
                            # Save commented file with validation
                            if processor.save_commented_file(file_info, commented_content, original_content):
                                result = FileProcessingResult(
                                    file_path=file_info['full_path'],
                                    status='success',
                                    processing_time=processing_time,
                                    original_size=len(original_content),
                                    commented_size=len(commented_content),
                                    validation_passed=True
                                )
                                successful_files += 1
                            else:
                                result = FileProcessingResult(
                                    file_path=file_info['full_path'],
                                    status='failed',
                                    processing_time=processing_time,
                                    error_message="Failed to save commented file",
                                    original_size=len(original_content),
                                    validation_passed=False
                                )
                                failed_files += 1
                        else:
                            result = FileProcessingResult(
                                file_path=file_info['full_path'],
                                status='failed',
                                processing_time=processing_time,
                                error_message="Could not read original file for validation",
                                validation_passed=False
                            )
                            failed_files += 1
                    else:
                        result = FileProcessingResult(
                            file_path=file_info['full_path'],
                            status='failed',
                            processing_time=processing_time,
                            error_message="LLM processing failed",
                            validation_passed=False
                        )
                        failed_files += 1
                
                except Exception as e:
                    processing_time = time.time() - start_time
                    logger.error(f"Error processing file {file_info['full_path']}: {e}")
                    
                    result = FileProcessingResult(
                        file_path=file_info['full_path'],
                        status='failed',
                        processing_time=processing_time,
                        error_message=str(e),
                        validation_passed=False
                    )
                    failed_files += 1
                
                # Complete file processing
                tracker.complete_file_processing(file_info, result)
                
        except KeyboardInterrupt:
            click.echo(f"\n\n⚠️  Processing interrupted by user")
            logger.info("Processing interrupted by user")
        except Exception as e:
            click.echo(f"\n\n❌ Unexpected error during processing: {e}")
            logger.error(f"Unexpected error: {e}")
        
        # Print final report
        click.echo(f"\n" + "="*80)
        tracker.print_final_report()
        
        # Summary
        if successful_files > 0:
            click.echo(f"\n✅ Processing completed successfully!")
            click.echo(f"Successfully processed: {successful_files} files")
        
        if failed_files > 0:
            click.echo(f"❌ Failed files: {failed_files}")
            
        click.echo(f"\n📁 Commented files saved in original directories with '_commented' suffix")
        
    except Exception as e:
        click.echo(f"❌ Fatal error: {e}")
        if 'logger' in locals():
            logger.critical(f"Fatal error: {e}")
        sys.exit(1)

@cli.command()
@click.option('--root', '-r', required=True, type=click.Path(exists=True, file_okay=False, path_type=Path),
              help='Root directory to analyze')
def analyze(root):
    """
    Analyze VFP files and generate a report without processing.
    
    This command scans the directory structure and provides detailed statistics
    about VFP files, folder structure, and processing readiness.
    """
    try:
        click.echo(f"🔍 Analyzing VFP files in: {root}")
        
        # Initialize file scanner
        scanner = VFPFileScanner(str(root))
        
        # Scan for VFP files
        vfp_files = scanner.scan_vfp_files()
        
        # Print detailed report
        scanner.print_scan_report(vfp_files)
        
        if vfp_files:
            # Additional analysis
            total_size = sum(f.get('file_size', 0) for f in vfp_files)
            extensions = {}
            
            for file_info in vfp_files:
                ext = Path(file_info['filename']).suffix.lower()
                extensions[ext] = extensions.get(ext, 0) + 1
            
            click.echo(f"\n📊 DETAILED ANALYSIS")
            click.echo(f"Total files: {len(vfp_files)}")
            click.echo(f"Total size: {total_size:,} bytes ({total_size/1024/1024:.1f} MB)")
            click.echo(f"Extensions: {dict(extensions)}")
            
            # Estimate processing time (rough estimate)
            estimated_time_per_file = 30  # seconds
            total_estimated_time = len(vfp_files) * estimated_time_per_file
            hours = total_estimated_time // 3600
            minutes = (total_estimated_time % 3600) // 60
            
            click.echo(f"\n⏱️  PROCESSING ESTIMATE")
            click.echo(f"Estimated time: {hours:02d}:{minutes:02d} hours")
            click.echo(f"(Based on ~{estimated_time_per_file} seconds per file)")
        else:
            click.echo("\n❌ No VFP files found for analysis.")
            
    except Exception as e:
        click.echo(f"❌ Analysis failed: {e}")
        sys.exit(1)

@cli.command()
@click.option('--config', '-c', type=click.Path(path_type=Path),
              help='Configuration file path (default: config.json)')
def test_llm(config):
    """
    Test LLM connection and processing with a sample VFP file.
    
    This command validates that the LLM client can connect to the local LLM
    and process a sample VFP code snippet successfully.
    """
    try:
        click.echo("🧪 Testing LLM connection and processing...")
        
        # Initialize configuration
        config_manager = ConfigManager(str(config) if config else None)
        
        # Test LLM client
        click.echo("Initializing LLM client...")
        llm_client = LLMClient(config_manager)
        
        # Sample VFP code for testing
        sample_code = """PARAMETERS lcCustomer, lnAmount
LOCAL lcResult, lnDiscount
lcResult = ""
lnDiscount = 0

IF lnAmount > 1000
    lnDiscount = lnAmount * 0.10
    lcResult = "Premium customer discount applied"
ELSE
    lcResult = "Standard pricing"
ENDIF

? "Processing customer: " + lcCustomer
? "Amount: " + TRANSFORM(lnAmount)
? "Discount: " + TRANSFORM(lnDiscount)
? lcResult

RETURN lnAmount - lnDiscount"""

        click.echo(f"\n📝 Testing with sample VFP code ({len(sample_code)} characters)")
        click.echo("Sample code preview:")
        click.echo("-" * 40)
        click.echo(sample_code[:200] + "..." if len(sample_code) > 200 else sample_code)
        click.echo("-" * 40)
        
        # Process sample
        click.echo("\n🤖 Sending to LLM for processing...")
        result = llm_client.process_file(
            sample_code,
            "test_sample.prg",
            "test_sample.prg",
            len(sample_code)
        )
        
        if result:
            click.echo("✅ LLM processing successful!")
            click.echo(f"Response length: {len(result)} characters")
            
            # Validate code preservation
            validator = CodePreservationValidator()
            is_valid, errors = validator.validate_code_preservation(sample_code, result)
            
            if is_valid:
                click.echo("✅ Code preservation validation PASSED")
                click.echo("\n📄 Sample of commented output:")
                click.echo("-" * 40)
                lines = result.split('\n')
                preview_lines = lines[:15]  # Show first 15 lines
                for line in preview_lines:
                    click.echo(line)
                if len(lines) > 15:
                    click.echo("... (output truncated)")
                click.echo("-" * 40)
            else:
                click.echo("❌ Code preservation validation FAILED")
                for error in errors:
                    click.echo(f"   Error: {error}")
        else:
            click.echo("❌ LLM processing failed")
            
    except Exception as e:
        click.echo(f"❌ LLM test failed: {e}")
        sys.exit(1)

@cli.command()
@click.option('--config', '-c', type=click.Path(path_type=Path),
              help='Configuration file path (default: config.json)')
def show_config(config):
    """Show current configuration settings."""
    try:
        config_manager = ConfigManager(str(config) if config else None)
        config_manager.print_config_summary()
    except Exception as e:
        click.echo(f"❌ Failed to load configuration: {e}")
        sys.exit(1)

if __name__ == '__main__':
    import time  # Import needed for main processing
    cli()