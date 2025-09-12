"""
Progress Tracker Module
======================
Comprehensive progress tracking for VFP file processing with detailed
statistics, folder-level progress, and recovery capabilities.

Features:
- Real-time progress display with folder context
- Processing statistics and error tracking
- Session persistence for resumable processing
- Estimated time calculations
- Detailed reporting and logging
"""

import json
import logging
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Any, Optional
from dataclasses import dataclass, asdict
import threading

@dataclass
class FileProcessingResult:
    """Result of processing a single file."""
    file_path: str
    status: str  # 'success', 'failed', 'skipped'
    processing_time: float
    error_message: Optional[str] = None
    original_size: int = 0
    commented_size: int = 0
    validation_passed: bool = False

@dataclass
class FolderStats:
    """Statistics for a folder."""
    folder_path: str
    total_files: int
    processed_files: int
    successful_files: int
    failed_files: int
    skipped_files: int
    total_processing_time: float
    status: str  # 'pending', 'in_progress', 'completed', 'failed'

class ProgressTracker:
    """
    Comprehensive progress tracker for VFP file processing.
    
    This class provides real-time progress tracking, statistics collection,
    and session persistence for resumable processing.
    """
    
    def __init__(self, session_id: Optional[str] = None, progress_file: str = "processing_progress.json"):
        """
        Initialize the progress tracker.
        
        Args:
            session_id: Unique session identifier, auto-generated if None
            progress_file: Path to progress persistence file
        """
        self.session_id = session_id or self._generate_session_id()
        self.progress_file = progress_file
        self.logger = self._setup_logger()
        
        # Progress data
        self.start_time = time.time()
        self.total_files = 0
        self.current_file_index = 0
        self.files_processed = 0
        self.files_successful = 0
        self.files_failed = 0
        self.files_skipped = 0
        self.validation_failures = 0
        
        # Folder tracking
        self.folder_stats: Dict[str, FolderStats] = {}
        self.current_folder = None
        
        # File results
        self.processing_results: List[FileProcessingResult] = []
        
        # Performance tracking
        self.total_processing_time = 0.0
        self.average_processing_time = 0.0
        
        # Thread safety
        self._lock = threading.Lock()
        
        self.logger.info(f"Progress tracker initialized for session: {self.session_id}")
        
        # Load existing progress if available
        self._load_progress()
    
    def _setup_logger(self) -> logging.Logger:
        """Setup logging for progress tracking."""
        logger = logging.getLogger('progress_tracker')
        logger.setLevel(logging.INFO)
        
        if not logger.handlers:
            handler = logging.StreamHandler()
            formatter = logging.Formatter(
                '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
            )
            handler.setFormatter(formatter)
            logger.addHandler(handler)
            
        return logger
    
    def _generate_session_id(self) -> str:
        """Generate a unique session ID."""
        return datetime.now().strftime("%Y%m%d_%H%M%S")
    
    def initialize_processing(self, files: List[Dict[str, str]], root_directory: str) -> None:
        """
        Initialize processing with the list of files to process.
        
        Args:
            files: List of file information dictionaries
            root_directory: Root directory path for relative path calculation
        """
        with self._lock:
            self.total_files = len(files)
            self.root_directory = root_directory
            
            # Group files by folder
            self.folder_stats = {}
            
            for file_info in files:
                folder_path = str(Path(file_info['directory']).relative_to(root_directory))
                
                if folder_path not in self.folder_stats:
                    self.folder_stats[folder_path] = FolderStats(
                        folder_path=folder_path,
                        total_files=0,
                        processed_files=0,
                        successful_files=0,
                        failed_files=0,
                        skipped_files=0,
                        total_processing_time=0.0,
                        status='pending'
                    )
                
                self.folder_stats[folder_path].total_files += 1
            
            self.logger.info(f"Initialized processing: {self.total_files} files in {len(self.folder_stats)} folders")
            self._save_progress()
    
    def start_file_processing(self, file_info: Dict[str, str]) -> None:
        """
        Mark the start of processing for a file.
        
        Args:
            file_info: File information dictionary
        """
        with self._lock:
            self.current_file_index += 1
            
            # Update current folder
            folder_path = str(Path(file_info['directory']).relative_to(self.root_directory))
            if folder_path != self.current_folder:
                self.current_folder = folder_path
                if folder_path in self.folder_stats:
                    self.folder_stats[folder_path].status = 'in_progress'
                    
            self.logger.info(f"Starting file {self.current_file_index}/{self.total_files}: {file_info['filename']}")
            self._update_display()
    
    def complete_file_processing(self, file_info: Dict[str, str], result: FileProcessingResult) -> None:
        """
        Mark the completion of processing for a file.
        
        Args:
            file_info: File information dictionary
            result: Processing result
        """
        with self._lock:
            self.files_processed += 1
            self.processing_results.append(result)
            self.total_processing_time += result.processing_time
            
            # Update folder statistics
            folder_path = str(Path(file_info['directory']).relative_to(self.root_directory))
            if folder_path in self.folder_stats:
                folder_stat = self.folder_stats[folder_path]
                folder_stat.processed_files += 1
                folder_stat.total_processing_time += result.processing_time
                
                if result.status == 'success':
                    self.files_successful += 1
                    folder_stat.successful_files += 1
                elif result.status == 'failed':
                    self.files_failed += 1
                    folder_stat.failed_files += 1
                elif result.status == 'skipped':
                    self.files_skipped += 1
                    folder_stat.skipped_files += 1
                
                if not result.validation_passed and result.status != 'skipped':
                    self.validation_failures += 1
                
                # Check if folder is complete
                if folder_stat.processed_files >= folder_stat.total_files:
                    if folder_stat.failed_files == 0:
                        folder_stat.status = 'completed'
                    else:
                        folder_stat.status = 'completed_with_errors'
            
            # Update average processing time
            if self.files_processed > 0:
                self.average_processing_time = self.total_processing_time / self.files_processed
            
            self.logger.info(f"Completed file: {result.file_path} [{result.status}] in {result.processing_time:.2f}s")
            self._update_display()
            self._save_progress()
    
    def _update_display(self) -> None:
        """Update the console display with current progress."""
        if self.total_files == 0:
            return
        
        # Calculate progress percentage
        progress_pct = (self.files_processed / self.total_files) * 100
        
        # Calculate estimated time remaining
        elapsed_time = time.time() - self.start_time
        if self.files_processed > 0:
            estimated_total_time = (elapsed_time / self.files_processed) * self.total_files
            estimated_remaining = estimated_total_time - elapsed_time
        else:
            estimated_remaining = 0
        
        # Create progress bar
        bar_width = 30
        filled_width = int((progress_pct / 100) * bar_width)
        bar = '█' * filled_width + '░' * (bar_width - filled_width)
        
        # Format times
        elapsed_str = self._format_time(elapsed_time)
        remaining_str = self._format_time(estimated_remaining) if estimated_remaining > 0 else "--:--"
        
        # Current file info
        current_file = "Starting..." if self.current_file_index == 0 else f"File {self.current_file_index}/{self.total_files}"
        
        # Print progress (using \r to overwrite previous line)
        print(f"\r{current_file} [{bar}] {progress_pct:.1f}% | "
              f"✓{self.files_successful} ✗{self.files_failed} ⊘{self.files_skipped} | "
              f"Time: {elapsed_str} | ETA: {remaining_str}", end='', flush=True)
        
        # Print newline for completed processing or major milestones
        if self.files_processed >= self.total_files or self.files_processed % 10 == 0:
            print()  # Add newline
    
    def _format_time(self, seconds: float) -> str:
        """Format time in seconds to HH:MM:SS format."""
        if seconds < 0:
            return "00:00"
        
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        seconds = int(seconds % 60)
        
        if hours > 0:
            return f"{hours:02d}:{minutes:02d}:{seconds:02d}"
        else:
            return f"{minutes:02d}:{seconds:02d}"
    
    def print_folder_summary(self) -> None:
        """Print a summary of processing by folder."""
        print("\n" + "="*80)
        print("PROCESSING SUMMARY BY FOLDER")
        print("="*80)
        
        for folder_path, stats in sorted(self.folder_stats.items()):
            status_icon = {
                'pending': '⏳',
                'in_progress': '⏳',
                'completed': '✅',
                'completed_with_errors': '⚠️',
                'failed': '❌'
            }.get(stats.status, '❓')
            
            folder_display = folder_path if folder_path != '.' else '[Root]'
            
            print(f"{status_icon} {folder_display}")
            print(f"    Files: {stats.processed_files}/{stats.total_files} processed")
            if stats.processed_files > 0:
                success_rate = (stats.successful_files / stats.processed_files) * 100
                print(f"    Results: ✓{stats.successful_files} ✗{stats.failed_files} ⊘{stats.skipped_files} ({success_rate:.1f}% success)")
                avg_time = stats.total_processing_time / stats.processed_files
                print(f"    Time: {self._format_time(stats.total_processing_time)} total, {avg_time:.2f}s avg")
            print()
        
        print("="*80)
    
    def print_final_report(self) -> None:
        """Print a comprehensive final processing report."""
        elapsed_time = time.time() - self.start_time
        
        print("\n" + "="*80)
        print("FINAL PROCESSING REPORT")
        print("="*80)
        print(f"Session ID: {self.session_id}")
        print(f"Total Processing Time: {self._format_time(elapsed_time)}")
        print(f"Files Processed: {self.files_processed}/{self.total_files}")
        print()
        
        if self.files_processed > 0:
            success_rate = (self.files_successful / self.files_processed) * 100
            print(f"Results:")
            print(f"  ✅ Successful: {self.files_successful} ({success_rate:.1f}%)")
            print(f"  ❌ Failed: {self.files_failed}")
            print(f"  ⊘ Skipped: {self.files_skipped}")
            print(f"  ⚠️  Validation Failures: {self.validation_failures}")
            print()
            
            print(f"Performance:")
            print(f"  Average Processing Time: {self.average_processing_time:.2f} seconds per file")
            files_per_minute = 60 / self.average_processing_time if self.average_processing_time > 0 else 0
            print(f"  Processing Rate: {files_per_minute:.1f} files per minute")
            print()
        
        # Print folder summary
        self.print_folder_summary()
        
        # Print failed files if any
        failed_results = [r for r in self.processing_results if r.status == 'failed']
        if failed_results:
            print("FAILED FILES:")
            print("-" * 40)
            for result in failed_results[:10]:  # Show first 10
                print(f"❌ {result.file_path}")
                if result.error_message:
                    print(f"    Error: {result.error_message}")
            if len(failed_results) > 10:
                print(f"    ... and {len(failed_results) - 10} more failed files")
            print()
        
        print("="*80)
    
    def _save_progress(self) -> None:
        """Save current progress to file for resumability."""
        try:
            progress_data = {
                'session_id': self.session_id,
                'start_time': self.start_time,
                'total_files': self.total_files,
                'current_file_index': self.current_file_index,
                'files_processed': self.files_processed,
                'files_successful': self.files_successful,
                'files_failed': self.files_failed,
                'files_skipped': self.files_skipped,
                'validation_failures': self.validation_failures,
                'total_processing_time': self.total_processing_time,
                'current_folder': self.current_folder,
                'folder_stats': {k: asdict(v) for k, v in self.folder_stats.items()},
                'processing_results': [asdict(r) for r in self.processing_results[-100:]],  # Keep last 100
                'last_updated': datetime.now().isoformat()
            }
            
            with open(self.progress_file, 'w', encoding='utf-8') as f:
                json.dump(progress_data, f, indent=2, ensure_ascii=False)
                
        except Exception as e:
            self.logger.warning(f"Could not save progress: {e}")
    
    def _load_progress(self) -> None:
        """Load progress from file if it exists."""
        try:
            if not Path(self.progress_file).exists():
                return
            
            with open(self.progress_file, 'r', encoding='utf-8') as f:
                progress_data = json.load(f)
            
            # Only load if session IDs match (for resuming)
            if progress_data.get('session_id') == self.session_id:
                self.start_time = progress_data.get('start_time', self.start_time)
                self.total_files = progress_data.get('total_files', 0)
                self.current_file_index = progress_data.get('current_file_index', 0)
                self.files_processed = progress_data.get('files_processed', 0)
                self.files_successful = progress_data.get('files_successful', 0)
                self.files_failed = progress_data.get('files_failed', 0)
                self.files_skipped = progress_data.get('files_skipped', 0)
                self.validation_failures = progress_data.get('validation_failures', 0)
                self.total_processing_time = progress_data.get('total_processing_time', 0.0)
                self.current_folder = progress_data.get('current_folder')
                
                # Load folder stats
                folder_stats_data = progress_data.get('folder_stats', {})
                self.folder_stats = {}
                for folder_path, stats_dict in folder_stats_data.items():
                    self.folder_stats[folder_path] = FolderStats(**stats_dict)
                
                # Load processing results
                results_data = progress_data.get('processing_results', [])
                self.processing_results = []
                for result_dict in results_data:
                    self.processing_results.append(FileProcessingResult(**result_dict))
                
                self.logger.info(f"Loaded progress: {self.files_processed}/{self.total_files} files processed")
            
        except Exception as e:
            self.logger.warning(f"Could not load progress: {e}")
    
    def get_progress_summary(self) -> Dict[str, Any]:
        """
        Get current progress summary as a dictionary.
        
        Returns:
            Dictionary containing progress summary
        """
        elapsed_time = time.time() - self.start_time
        progress_pct = (self.files_processed / self.total_files * 100) if self.total_files > 0 else 0
        
        return {
            'session_id': self.session_id,
            'total_files': self.total_files,
            'files_processed': self.files_processed,
            'files_successful': self.files_successful,
            'files_failed': self.files_failed,
            'files_skipped': self.files_skipped,
            'validation_failures': self.validation_failures,
            'progress_percentage': progress_pct,
            'elapsed_time': elapsed_time,
            'average_processing_time': self.average_processing_time,
            'current_folder': self.current_folder,
            'folders_total': len(self.folder_stats),
            'folders_completed': len([f for f in self.folder_stats.values() if f.status.startswith('completed')])
        }

def main():
    """Test the progress tracker."""
    print("Testing Progress Tracker...")
    
    # Create a test tracker
    tracker = ProgressTracker("test_session")
    
    # Simulate file list
    test_files = [
        {'directory': '/test/folder1', 'filename': 'file1.prg'},
        {'directory': '/test/folder1', 'filename': 'file2.prg'},
        {'directory': '/test/folder2', 'filename': 'file3.prg'},
        {'directory': '/test/folder2', 'filename': 'file4.prg'},
    ]
    
    # Initialize processing
    tracker.initialize_processing(test_files, '/test')
    
    # Simulate processing files
    for i, file_info in enumerate(test_files):
        tracker.start_file_processing(file_info)
        
        # Simulate processing time
        time.sleep(0.5)
        
        # Simulate result
        result = FileProcessingResult(
            file_path=file_info['filename'],
            status='success' if i % 3 != 2 else 'failed',
            processing_time=0.5 + i * 0.1,
            validation_passed=True,
            original_size=1000 + i * 100,
            commented_size=1200 + i * 120
        )
        
        tracker.complete_file_processing(file_info, result)
    
    # Print final report
    tracker.print_final_report()
    
    # Get summary
    summary = tracker.get_progress_summary()
    print(f"\nProgress Summary: {summary}")

if __name__ == "__main__":
    main()