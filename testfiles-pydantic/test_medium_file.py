"""
Test Instructor Client with Medium-Sized VFP File
=================================================
Tests the structured commenting approach on a medium-sized file (50-200 lines)
"""

import sys
from pathlib import Path
from config import ConfigManager
from instructor_client import InstructorLLMClient


def read_vfp_file(file_path: str) -> str:
    """Read VFP file with multiple encoding attempts"""
    encodings = ['utf-8', 'cp1252', 'latin1', 'ascii']
    for encoding in encodings:
        try:
            with open(file_path, 'r', encoding=encoding) as f:
                return f.read()
        except UnicodeDecodeError:
            continue
    raise ValueError(f"Could not read file with any encoding: {file_path}")


def main():
    print("=" * 70)
    print("MEDIUM VFP FILE TEST - Instructor Client")
    print("=" * 70)

    # TEST FILE - Change this to test different files
    test_file = Path("VFP_Files_Copy/Custom Prgs/newpatcount.prg")

    if not test_file.exists():
        print(f"\n[ERROR] Test file not found: {test_file}")
        print("\nTry one of these files:")
        print("  - VFP_Files_Copy/Custom Prgs/getdailycomments.prg")
        print("  - VFP_Files_Copy/Custom Prgs/newpatcount.prg")
        print("  - VFP_Files_Copy/Forms/getpaymenthistory_sql.prg")
        return 1

    try:
        # Read the file
        print(f"\n1. Reading VFP file: {test_file}")
        vfp_code = read_vfp_file(str(test_file))
        line_count = len(vfp_code.splitlines())
        char_count = len(vfp_code)
        print(f"   [OK] File read: {line_count} lines, {char_count} characters")

        # Show file stats
        print(f"\n2. File Statistics:")
        print(f"   Size category: ", end="")
        if line_count < 50:
            print("SMALL (< 50 lines)")
        elif line_count < 150:
            print("MEDIUM (50-150 lines)")
        elif line_count < 300:
            print("LARGE (150-300 lines)")
        else:
            print("VERY LARGE (300+ lines) - May need chunking")

        # Initialize client
        print(f"\n3. Initializing Instructor client...")
        config = ConfigManager()
        client = InstructorLLMClient(config)
        print("   [OK] Client initialized")

        # Generate comments
        print(f"\n4. Generating structured comments...")
        print(f"   File size: {line_count} lines")
        print(f"   Expected time: {line_count * 2}-{line_count * 3} seconds")
        print("   Please wait...")

        import time
        start_time = time.time()

        result = client.generate_comments_for_vfp(
            vfp_code=vfp_code,
            filename=test_file.name,
            relative_path=str(test_file)
        )

        elapsed = time.time() - start_time

        if not result:
            print(f"   [FAIL] Failed to generate comments (took {elapsed:.1f}s)")
            print("\n   This might mean:")
            print("   1. File is too large for single-pass processing")
            print("   2. LLM timeout (increase timeout in config.json)")
            print("   3. Token limit exceeded")
            print("\n   --> We need to implement two-phase processing!")
            return 1

        print(f"   [OK] Comments generated in {elapsed:.1f}s!")

        # Validate
        print(f"\n5. Validating code preservation...")
        if result.validate_code_preservation(vfp_code):
            print("   [OK] Original code preserved exactly!")
        else:
            print("   [FAIL] Code was modified!")
            return 1

        # Show stats
        original_lines = len(vfp_code.splitlines())
        commented_lines = len(result.assemble_commented_code().splitlines())

        print(f"\n6. Statistics:")
        print(f"   Original lines:  {original_lines}")
        print(f"   Commented lines: {commented_lines}")
        print(f"   Lines added:     {commented_lines - original_lines}")
        print(f"   Comments added:  {len(result.inline_comments)}")
        print(f"   Processing time: {elapsed:.1f}s")
        print(f"   Time per line:   {elapsed / original_lines:.2f}s")

        # Save output
        output_file = test_file.stem + "_instructor_commented" + test_file.suffix
        output_path = Path(test_file.parent) / output_file

        print(f"\n7. Saving to: {output_path}")
        assembled = result.assemble_commented_code()
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(assembled)
        print(f"   [OK] Saved successfully!")

        print("\n" + "=" * 70)
        print("SUCCESS - Medium file commented successfully!")
        print("=" * 70)
        print(f"\nPerformance: {elapsed:.1f}s for {original_lines} lines")
        print(f"Next step: Try a larger file (200-500 lines) to test limits")

        return 0

    except Exception as e:
        print(f"\n[ERROR] Test failed: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
