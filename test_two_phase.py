#!/usr/bin/env python3
"""
Test Two-Phase Processor with Large VFP File
=============================================
Tests the two-phase context-aware chunking system with the 200-line
getpaymenthistory_sql.prg file that failed with the single-pass approach.
"""

import os
import sys
import time
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

from config import ConfigManager
from instructor_client import InstructorLLMClient
from two_phase_processor import TwoPhaseProcessor


def test_two_phase_large_file():
    """Test two-phase processing with the 200-line file"""

    print("=" * 70)
    print("TWO-PHASE PROCESSOR TEST - 200+ Line VFP File")
    print("=" * 70)
    print()

    # The file that crashed with single-pass approach
    test_file = "VFP_Files_Copy/Forms/getpaymenthistory_sql.prg"

    # 1. Read the file
    print(f"1. Reading VFP file: {test_file}")
    try:
        with open(test_file, 'r', encoding='utf-8', errors='ignore') as f:
            vfp_code = f.read()

        line_count = len(vfp_code.split('\n'))
        char_count = len(vfp_code)
        print(f"   [OK] File read: {line_count} lines, {char_count} characters")
    except Exception as e:
        print(f"   [FAIL] Error reading file: {e}")
        return False

    print()

    # 2. Initialize components
    print("2. Initializing two-phase processor...")
    try:
        config = ConfigManager()
        client = InstructorLLMClient(config)
        processor = TwoPhaseProcessor(client, max_chunk_lines=100)
        print("   [OK] Processor initialized")
    except Exception as e:
        print(f"   [FAIL] Initialization error: {e}")
        return False

    print()

    # 3. Process with two-phase approach
    print("3. Starting two-phase processing...")
    print("   Phase 1: Extract file context (fast)")
    print("   Phase 2: Comment chunks with context awareness")
    print()

    start_time = time.time()

    try:
        result = processor.process_file(
            vfp_code=vfp_code,
            filename="getpaymenthistory_sql.prg",
            relative_path="Forms/getpaymenthistory_sql.prg"
        )

        elapsed_time = time.time() - start_time

        if result.success:
            print(f"   [OK] Processing completed in {elapsed_time:.1f}s!")
        else:
            print(f"   [FAIL] Processing failed: {result.error_message}")
            print(f"   Processed {result.chunks_processed}/{result.total_chunks} chunks")
            return False

    except Exception as e:
        elapsed_time = time.time() - start_time
        print(f"   [FAIL] Error after {elapsed_time:.1f}s: {e}")
        import traceback
        traceback.print_exc()
        return False

    print()

    # 4. Show statistics
    print("4. Processing Statistics:")
    print(f"   Total time: {elapsed_time:.1f}s")
    print(f"   Chunks processed: {result.chunks_processed}/{result.total_chunks}")
    print(f"   Time per chunk: {elapsed_time/result.chunks_processed:.1f}s")
    print()

    # 5. Show context extracted
    print("5. File Context (Phase 1):")
    print(f"   Overview: {result.context.file_overview[:100]}...")
    if result.context.procedures:
        proc_names = [p.name for p in result.context.procedures[:5]]
        print(f"   Procedures: {', '.join(proc_names)}")
    if result.context.dependencies:
        print(f"   Dependencies: {', '.join(result.context.dependencies[:5])}")
    print()

    # 6. Show commented code statistics
    print("6. Output Statistics:")
    original_lines = len(vfp_code.split('\n'))
    commented_lines = len(result.commented_code.split('\n'))
    print(f"   Original lines: {original_lines}")
    print(f"   Commented lines: {commented_lines}")
    print(f"   Comments added: {commented_lines - original_lines} lines")
    print()

    # 7. Save the result
    output_file = test_file.replace('.prg', '_two_phase_commented.prg')
    print(f"7. Saving to: {output_file}")
    try:
        with open(output_file, 'w', encoding='utf-8') as f:
            f.write(result.commented_code)
        print("   [OK] Saved successfully!")
    except Exception as e:
        print(f"   [FAIL] Save error: {e}")
        return False

    print()
    print("=" * 70)
    print("SUCCESS - Two-Phase Processing Works!")
    print("=" * 70)
    print()
    print("Key Advantages:")
    print("  ✓ No LLM crashes (smaller chunks)")
    print("  ✓ Context-aware comments (Phase 1 context)")
    print("  ✓ Code preservation validated per chunk")
    print("  ✓ Handles 200+ line files successfully")
    print()
    print(f"Performance: {elapsed_time:.1f}s for {original_lines} lines")
    print(f"             ({elapsed_time/original_lines:.2f}s per line)")
    print()

    return True


def main():
    """Main entry point"""
    print("Testing Two-Phase Processor with Large VFP File")
    print()

    success = test_two_phase_large_file()

    if success:
        print("✓ Test PASSED - Ready for production integration")
        sys.exit(0)
    else:
        print("✗ Test FAILED - Check logs above")
        sys.exit(1)


if __name__ == "__main__":
    main()
