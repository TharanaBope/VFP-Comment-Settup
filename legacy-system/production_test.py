#!/usr/bin/env python3
"""
Production Test Script for Two-Phase VFP Commenting Architecture

This script tests the two-phase architecture with larger, production VFP files
to validate performance, scalability, and comment quality before full deployment.

Test Scenarios:
1. Small batch test (5-10 files)
2. Medium file test (1000-5000 lines)
3. Complex structure test (multiple procedures/classes)
4. Performance benchmarking
5. Comment quality validation
"""

import os
import sys
import logging
import time
from pathlib import Path
from typing import List, Dict, Any

# Add current directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from config import ConfigManager
from llm_client import LLMClient
from vfp_processor import VFPProcessor
from file_scanner import VFPFileScanner
from progress_tracker import ProgressTracker, FileProcessingResult


def setup_logging():
    """Setup logging for production testing."""
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )


def find_test_files(vfp_files: List[Dict], criteria: str) -> List[Dict]:
    """Find files matching specific test criteria."""
    if criteria == "small":
        # Small files: 100-1000 bytes
        return [f for f in vfp_files if 100 <= f.get('file_size', 0) <= 1000][:5]

    elif criteria == "medium":
        # Medium files: 1000-5000 bytes
        return [f for f in vfp_files if 1000 <= f.get('file_size', 0) <= 5000][:3]

    elif criteria == "large":
        # Large files: 5000+ bytes
        return [f for f in vfp_files if f.get('file_size', 0) >= 5000][:2]

    elif criteria == "mixed":
        # Mixed batch for comprehensive testing
        small = [f for f in vfp_files if f.get('file_size', 0) <= 1000][:3]
        medium = [f for f in vfp_files if 1000 <= f.get('file_size', 0) <= 5000][:3]
        large = [f for f in vfp_files if f.get('file_size', 0) >= 5000][:2]
        return small + medium + large

    else:
        return vfp_files[:10]  # Default: first 10 files


def analyze_comment_quality(original_content: str, commented_content: str) -> Dict[str, Any]:
    """Analyze the quality of generated comments."""
    original_lines = original_content.split('\n')
    commented_lines = commented_content.split('\n')

    # Count different types of content
    original_code_lines = [line for line in original_lines if line.strip() and not line.strip().startswith('*')]
    commented_code_lines = [line for line in commented_lines if line.strip() and not line.strip().startswith('*')]

    original_comment_lines = [line for line in original_lines if line.strip().startswith('*')]
    new_comment_lines = [line for line in commented_lines if line.strip().startswith('*')]

    # Calculate metrics
    code_preservation_ratio = len(commented_code_lines) / len(original_code_lines) if original_code_lines else 0
    comments_added = len(new_comment_lines) - len(original_comment_lines)
    comment_density = comments_added / len(original_code_lines) if original_code_lines else 0

    # Check for header comment
    has_header = any('=' in line or '-' in line for line in new_comment_lines[:10])

    # Check for structured comments
    has_procedure_comments = any('PROCEDURE' in line.upper() for line in original_lines) and \
                           any('procedure' in line.lower() for line in new_comment_lines)

    return {
        'total_lines': len(commented_lines),
        'original_lines': len(original_lines),
        'code_lines_original': len(original_code_lines),
        'code_lines_commented': len(commented_code_lines),
        'comments_added': comments_added,
        'comment_density': round(comment_density, 2),
        'code_preservation_ratio': round(code_preservation_ratio, 2),
        'has_header': has_header,
        'has_procedure_comments': has_procedure_comments,
        'quality_score': calculate_quality_score(comment_density, code_preservation_ratio, has_header)
    }


def calculate_quality_score(comment_density: float, preservation_ratio: float, has_header: bool) -> float:
    """Calculate overall comment quality score (0-100)."""
    score = 0

    # Code preservation (40 points) - must be perfect
    if preservation_ratio >= 0.99:
        score += 40

    # Comment density (30 points) - optimal range 0.2-0.5
    if 0.2 <= comment_density <= 0.5:
        score += 30
    elif 0.1 <= comment_density < 0.2:
        score += 20
    elif comment_density > 0.5:
        score += 25  # Good but maybe too verbose

    # Header presence (15 points)
    if has_header:
        score += 15

    # Base functionality (15 points) - if we got this far, basic processing worked
    score += 15

    return min(score, 100)


def run_production_test():
    """Run comprehensive production testing."""
    print("=" * 80)
    print("VFP TWO-PHASE ARCHITECTURE - PRODUCTION TESTING")
    print("=" * 80)
    print("Testing two-phase architecture with production VFP files")
    print("for scalability, performance, and comment quality validation.\n")

    try:
        # Initialize configuration
        print("1. Initializing system components...")
        config = ConfigManager()

        # Initialize components
        llm_client = LLMClient(config)
        vfp_processor = VFPProcessor(config)
        scanner = VFPFileScanner(config.get('processing.root_directory'))

        print("✓ All components initialized successfully")

        # Scan for VFP files
        print("\n2. Scanning for VFP files...")
        vfp_files = scanner.scan_vfp_files()

        if not vfp_files:
            print("❌ No VFP files found for testing")
            return False

        print(f"✓ Found {len(vfp_files)} VFP files total")
        scanner.print_scan_report(vfp_files)

        # Test different file categories
        test_categories = [
            ("small", "Small Files (100-1000 bytes)"),
            ("medium", "Medium Files (1000-5000 bytes)"),
            ("large", "Large Files (5000+ bytes)"),
        ]

        overall_results = {
            'total_files_tested': 0,
            'successful_files': 0,
            'failed_files': 0,
            'total_processing_time': 0,
            'quality_scores': [],
            'performance_metrics': []
        }

        for category, description in test_categories:
            print(f"\n" + "="*60)
            print(f"TESTING CATEGORY: {description}")
            print("="*60)

            # Find test files for this category
            test_files = find_test_files(vfp_files, category)

            if not test_files:
                print(f"⚠️  No files found for category: {category}")
                continue

            print(f"Selected {len(test_files)} files for testing:")
            for i, file_info in enumerate(test_files, 1):
                size_kb = file_info.get('file_size', 0) / 1024
                print(f"  {i}. {file_info['filename']} ({size_kb:.1f} KB)")

            # Process each test file
            category_results = {
                'processed': 0,
                'successful': 0,
                'failed': 0,
                'total_time': 0,
                'quality_scores': [],
                'files': []
            }

            for file_info in test_files:
                print(f"\n📄 Processing: {file_info['filename']}")
                start_time = time.time()

                try:
                    # Use two-phase processing
                    commented_content = vfp_processor.process_file_two_phase(file_info, llm_client)
                    processing_time = time.time() - start_time

                    if commented_content:
                        # Read original content for analysis
                        original_content = vfp_processor.read_vfp_file(file_info['full_path'])

                        if original_content:
                            # Analyze comment quality
                            quality_analysis = analyze_comment_quality(original_content, commented_content)

                            # Save results
                            file_result = {
                                'filename': file_info['filename'],
                                'status': 'success',
                                'processing_time': processing_time,
                                'original_size': len(original_content),
                                'commented_size': len(commented_content),
                                'quality_analysis': quality_analysis
                            }

                            print(f"  ✓ Success - {processing_time:.1f}s")
                            print(f"    {quality_analysis['original_lines']} → {quality_analysis['total_lines']} lines")
                            print(f"    Comments added: {quality_analysis['comments_added']}")
                            print(f"    Quality score: {quality_analysis['quality_score']}/100")

                            category_results['successful'] += 1
                            category_results['quality_scores'].append(quality_analysis['quality_score'])
                        else:
                            file_result = {'filename': file_info['filename'], 'status': 'failed', 'error': 'Could not read original file'}
                            print(f"  ❌ Failed - Could not read original file")
                            category_results['failed'] += 1
                    else:
                        file_result = {'filename': file_info['filename'], 'status': 'failed', 'error': 'Two-phase processing failed'}
                        print(f"  ❌ Failed - Two-phase processing failed")
                        category_results['failed'] += 1

                except Exception as e:
                    processing_time = time.time() - start_time
                    file_result = {'filename': file_info['filename'], 'status': 'failed', 'error': str(e)}
                    print(f"  ❌ Failed - {str(e)}")
                    category_results['failed'] += 1

                category_results['processed'] += 1
                category_results['total_time'] += processing_time
                category_results['files'].append(file_result)

            # Print category summary
            print(f"\n📊 CATEGORY SUMMARY: {description}")
            print(f"Files processed: {category_results['processed']}")
            print(f"Successful: {category_results['successful']}")
            print(f"Failed: {category_results['failed']}")
            if category_results['successful'] > 0:
                success_rate = (category_results['successful'] / category_results['processed']) * 100
                avg_time = category_results['total_time'] / category_results['processed']
                avg_quality = sum(category_results['quality_scores']) / len(category_results['quality_scores'])
                print(f"Success rate: {success_rate:.1f}%")
                print(f"Average processing time: {avg_time:.1f}s per file")
                print(f"Average quality score: {avg_quality:.1f}/100")

            # Update overall results
            overall_results['total_files_tested'] += category_results['processed']
            overall_results['successful_files'] += category_results['successful']
            overall_results['failed_files'] += category_results['failed']
            overall_results['total_processing_time'] += category_results['total_time']
            overall_results['quality_scores'].extend(category_results['quality_scores'])

        # Final summary
        print(f"\n" + "="*80)
        print("🏁 PRODUCTION TEST RESULTS")
        print("="*80)
        print(f"Total files tested: {overall_results['total_files_tested']}")
        print(f"Successful: {overall_results['successful_files']}")
        print(f"Failed: {overall_results['failed_files']}")

        if overall_results['total_files_tested'] > 0:
            success_rate = (overall_results['successful_files'] / overall_results['total_files_tested']) * 100
            avg_time = overall_results['total_processing_time'] / overall_results['total_files_tested']
            print(f"Overall success rate: {success_rate:.1f}%")
            print(f"Average processing time: {avg_time:.1f}s per file")

        if overall_results['quality_scores']:
            avg_quality = sum(overall_results['quality_scores']) / len(overall_results['quality_scores'])
            min_quality = min(overall_results['quality_scores'])
            max_quality = max(overall_results['quality_scores'])
            print(f"Quality scores: {avg_quality:.1f}/100 avg (range: {min_quality}-{max_quality})")

        # Production readiness assessment
        print(f"\n🎯 PRODUCTION READINESS ASSESSMENT:")

        if success_rate >= 95:
            print("✅ SUCCESS RATE: EXCELLENT (≥95%)")
        elif success_rate >= 80:
            print("⚠️  SUCCESS RATE: GOOD (80-95%)")
        else:
            print("❌ SUCCESS RATE: NEEDS IMPROVEMENT (<80%)")

        if overall_results['quality_scores'] and avg_quality >= 80:
            print("✅ COMMENT QUALITY: EXCELLENT (≥80/100)")
        elif overall_results['quality_scores'] and avg_quality >= 60:
            print("⚠️  COMMENT QUALITY: GOOD (60-80/100)")
        else:
            print("❌ COMMENT QUALITY: NEEDS IMPROVEMENT (<60/100)")

        if avg_time <= 30:
            print("✅ PERFORMANCE: EXCELLENT (≤30s per file)")
        elif avg_time <= 60:
            print("⚠️  PERFORMANCE: ACCEPTABLE (30-60s per file)")
        else:
            print("❌ PERFORMANCE: SLOW (>60s per file)")

        # Final recommendation
        if success_rate >= 90 and (not overall_results['quality_scores'] or avg_quality >= 70):
            print("\n🚀 RECOMMENDATION: READY FOR FULL PRODUCTION DEPLOYMENT")
            print("   The two-phase architecture is performing excellently.")
        elif success_rate >= 80:
            print("\n⚡ RECOMMENDATION: READY FOR LIMITED PRODUCTION DEPLOYMENT")
            print("   Monitor results and address any quality issues.")
        else:
            print("\n⚠️  RECOMMENDATION: FURTHER TESTING NEEDED")
            print("   Address failure causes before full deployment.")

        return success_rate >= 80

    except Exception as e:
        print(f"\n❌ PRODUCTION TEST FAILED: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """Run production testing."""
    setup_logging()
    success = run_production_test()
    return 0 if success else 1


if __name__ == "__main__":
    sys.exit(main())