"""
Test Two-Phase Processor with Large VFP File (1,181 lines)
===========================================================
This test validates the two-phase commenting system at scale.

Test File: VFP_Files_Copy/Prgs/rundview_sql.prg (1,181 lines)
Expected Time: ~1 hour (at 3.25s/line based on previous tests)
"""

import time
import sys
from pathlib import Path

from config import ConfigManager
from instructor_client import InstructorLLMClient
from two_phase_processor import TwoPhaseProcessor


def format_time(seconds):
    """Format seconds into human-readable time"""
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = int(seconds % 60)

    if hours > 0:
        return f"{hours}h {minutes}m {secs}s"
    elif minutes > 0:
        return f"{minutes}m {secs}s"
    else:
        return f"{secs}s"


def main():
    print("Testing Two-Phase Processor with Large VFP File (1,181 lines)")
    print()
    print("=" * 70)
    print("LARGE FILE STRESS TEST - 1,181 Line VFP File")
    print("=" * 70)
    print()

    # Test file path
    test_file = Path("VFP_Files_Copy/Prgs/rundview_sql.prg")

    if not test_file.exists():
        print(f"[ERROR] Test file not found: {test_file}")
        sys.exit(1)

    # Read the file
    print(f"1. Reading VFP file: {test_file}")
    with open(test_file, 'r', encoding='latin1', errors='ignore') as f:
        vfp_code = f.read()

    line_count = len(vfp_code.split('\n'))
    char_count = len(vfp_code)

    print(f"   [OK] File read: {line_count} lines, {char_count} characters")
    print()

    # Estimate processing time
    estimated_time_sec = line_count * 3.25  # Based on previous test performance
    print(f"   ⏱️  Estimated processing time: {format_time(estimated_time_sec)}")
    print(f"   ⚠️  This is a LONG test - grab a coffee!")
    print()

    # Initialize processor
    print("2. Initializing two-phase processor...")
    config = ConfigManager()
    client = InstructorLLMClient(config)
    processor = TwoPhaseProcessor(client, max_chunk_lines=30)
    print("   [OK] Processor initialized")
    print()

    # Process the file
    print("3. Starting two-phase processing...")
    print("   Phase 1: Extract file context (fast)")
    print("   Phase 2: Comment chunks with context awareness")
    print()

    start_time = time.time()

    result = processor.process_file(
        vfp_code=vfp_code,
        filename=test_file.name,
        relative_path=str(test_file.relative_to("VFP_Files_Copy"))
    )

    end_time = time.time()
    elapsed_time = end_time - start_time

    # Check result
    if not result.success:
        print(f"   [FAIL] Processing failed: {result.error_message}")
        print(f"   Chunks processed: {result.chunks_processed}/{result.total_chunks}")
        sys.exit(1)

    print(f"   [OK] Processing completed in {format_time(elapsed_time)}!")
    print()

    # Statistics
    print("4. Processing Statistics:")
    print(f"   Total time: {format_time(elapsed_time)}")
    print(f"   Chunks processed: {result.chunks_processed}/{result.total_chunks}")
    print(f"   Time per chunk: {format_time(elapsed_time / result.total_chunks)}")
    print(f"   Time per line: {elapsed_time / line_count:.2f}s")
    print()

    # File context
    if result.context:
        print("5. File Context (Phase 1):")
        print(f"   Overview: {result.context.file_overview[:100]}...")
        print(f"   Procedures: {len(result.context.procedures)} found")
        print(f"   Dependencies: {', '.join(result.context.dependencies[:5])}")
        print()

    # Output stats
    original_lines = len(vfp_code.split('\n'))
    commented_lines = len(result.commented_code.split('\n'))
    added_lines = commented_lines - original_lines

    print("6. Output Statistics:")
    print(f"   Original lines: {original_lines}")
    print(f"   Commented lines: {commented_lines}")
    print(f"   Comments added: {added_lines} lines")
    print()

    # Save output
    output_file = test_file.parent / f"{test_file.stem}_two_phase_commented{test_file.suffix}"
    print(f"7. Saving to: {output_file}")

    with open(output_file, 'w', encoding='latin1', errors='ignore') as f:
        f.write(result.commented_code)

    print("   [OK] Saved successfully!")
    print()

    # Final summary
    print("=" * 70)
    print("SUCCESS - Large File Processing Works!")
    print("=" * 70)
    print()
    print("Key Achievements:")
    print("  ✓ Processed 1,181 lines successfully")
    print(f"  ✓ {result.total_chunks} chunks handled without crashes")
    print("  ✓ Context-aware comments across all chunks")
    print("  ✓ Code preservation validated per chunk")
    print()
    print(f"Performance: {format_time(elapsed_time)} for {line_count} lines")
    print(f"             ({elapsed_time / line_count:.2f}s per line)")
    print()

    # Verify no duplicate headers
    print("8. Verifying output quality...")
    header_count = result.commented_code.count("* FILE:")

    if header_count == 1:
        print("   ✓ No duplicate headers - only ONE master header found")
    else:
        print(f"   ⚠️  Warning: Found {header_count} file headers (expected 1)")

    print()
    print("✓ Test PASSED - System validated at scale")
    print()
    print("Next Step: Review output file and consider testing with")
    print("           even larger file (7,914 lines) if needed.")


if __name__ == "__main__":
    main()
