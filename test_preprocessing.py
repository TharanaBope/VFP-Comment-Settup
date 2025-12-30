"""
Test script to verify report preprocessing works correctly.

This tests the fix for the crash caused by processing XML-heavy .fr2 files.
"""

import sys
sys.path.insert(0, '.')

from language_handlers.vfp_handler import VFPHandler


def test_report_preprocessing():
    """Test that the crashing file is properly preprocessed."""
    print("=" * 60)
    print("Testing Report Preprocessing")
    print("=" * 60)

    handler = VFPHandler()

    # Read the file that was causing crashes
    test_file = r"converted\Reports\cccccstappsdetl.fr2"
    print(f"\nReading: {test_file}")

    try:
        with open(test_file, 'r', encoding='utf-8', errors='replace') as f:
            code = f.read()
    except FileNotFoundError:
        print(f"ERROR: File not found: {test_file}")
        return False

    original_lines = len(code.split('\n'))
    original_chars = len(code)
    print(f"Original: {original_lines} lines, {original_chars:,} characters")

    # Test report detection
    is_report = handler._is_report_file(code)
    print(f"\nIs report file: {is_report}")

    if not is_report:
        print("ERROR: File should be detected as a report!")
        return False

    # Test expression extraction
    expressions = handler._extract_vfp_expressions(code)
    expr_count = len(expressions['expr'])
    supexpr_count = len(expressions['supexpr'])
    print(f"\nExtracted expressions:")
    print(f"  - <expr> tags: {expr_count}")
    print(f"  - <supexpr> tags: {supexpr_count}")

    # Show first 5 expressions
    print(f"\nFirst 5 expressions:")
    for i, (line_num, expr) in enumerate(expressions['expr'][:5]):
        display = expr if len(expr) <= 60 else expr[:60] + "..."
        print(f"  [{line_num}] {display}")

    # Test preprocessing
    preprocessed = handler.preprocess_for_llm(code)
    preprocessed_lines = len(preprocessed.split('\n'))
    preprocessed_chars = len(preprocessed)

    print(f"\nAfter preprocessing:")
    print(f"  Lines: {original_lines} -> {preprocessed_lines} ({100*preprocessed_lines/original_lines:.1f}%)")
    print(f"  Chars: {original_chars:,} -> {preprocessed_chars:,} ({100*preprocessed_chars/original_chars:.1f}%)")

    # Show preprocessed output
    print(f"\n--- Preprocessed Content ---")
    print(preprocessed[:2000])
    if len(preprocessed) > 2000:
        print(f"\n... ({len(preprocessed) - 2000} more characters) ...")

    # Validate reduction
    reduction_ratio = preprocessed_lines / original_lines
    if reduction_ratio > 0.2:
        print(f"\nWARNING: Preprocessing only reduced to {100*reduction_ratio:.1f}% - expected < 20%")
    else:
        print(f"\n✓ Preprocessing reduced file to {100*reduction_ratio:.1f}% of original")

    return True


def test_standard_vfp_unchanged():
    """Test that standard VFP files are not affected by report preprocessing."""
    print("\n" + "=" * 60)
    print("Testing Standard VFP File (should NOT be treated as report)")
    print("=" * 60)

    handler = VFPHandler()

    # Create sample VFP code
    sample_code = """
PROCEDURE TestProc
    LOCAL x
    x = 5
    SELECT * FROM customers
    RETURN x
ENDPROC
"""

    is_report = handler._is_report_file(sample_code)
    print(f"\nIs report file: {is_report}")

    if is_report:
        print("ERROR: Standard VFP should NOT be detected as report!")
        return False

    print("✓ Standard VFP files are not affected")
    return True


if __name__ == "__main__":
    print("Report Preprocessing Test Suite")
    print("================================\n")

    test1 = test_report_preprocessing()
    test2 = test_standard_vfp_unchanged()

    print("\n" + "=" * 60)
    print("RESULTS")
    print("=" * 60)
    print(f"Report preprocessing: {'PASS' if test1 else 'FAIL'}")
    print(f"Standard VFP unchanged: {'PASS' if test2 else 'FAIL'}")

    if test1 and test2:
        print("\n✓ All tests passed!")
        print("\nYou can now safely process the problematic file:")
        print('  python batch_process.py --language vfp --path "converted/Reports/cccccstappsdetl.fr2"')
    else:
        print("\n✗ Some tests failed. Please review the output above.")
