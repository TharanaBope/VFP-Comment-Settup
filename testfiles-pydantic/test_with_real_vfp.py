"""
Test Instructor Client with Real VFP File
=========================================
This script tests the Instructor-based commenting on an actual VFP file.
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
    print("REAL VFP FILE TEST - Instructor Client")
    print("=" * 70)

    # Test file path
    test_file = Path("test_sample.prg")

    if not test_file.exists():
        print(f"\n[ERROR] Test file not found: {test_file}")
        print("Expected location: test_sample.prg in current directory")
        return 1

    try:
        # Read the test file
        print(f"\n1. Reading VFP file: {test_file}")
        vfp_code = read_vfp_file(str(test_file))
        line_count = len(vfp_code.splitlines())
        char_count = len(vfp_code)
        print(f"   [OK] File read: {line_count} lines, {char_count} characters")

        # Show original code
        print(f"\n2. Original VFP Code:")
        print("   " + "=" * 66)
        for i, line in enumerate(vfp_code.split('\n'), 1):
            print(f"   {i:3d} | {line}")
        print("   " + "=" * 66)

        # Initialize client
        print(f"\n3. Initializing Instructor client...")
        config = ConfigManager()
        client = InstructorLLMClient(config)
        print("   [OK] Client initialized")

        # Generate comments
        print(f"\n4. Generating structured comments...")
        print("   This may take 30-90 seconds depending on your LLM...")
        print("   Please wait...")

        result = client.generate_comments_for_vfp(
            vfp_code=vfp_code,
            filename=test_file.name,
            relative_path=str(test_file)
        )

        if not result:
            print("   [FAIL] Failed to generate comments")
            print("\n   Troubleshooting:")
            print("   1. Ensure LM Studio is running")
            print("   2. Check that a model is loaded")
            print("   3. Verify config.json endpoint matches LM Studio")
            print("   4. Check LM Studio logs for errors")
            return 1

        print("   [OK] Comments generated!")

        # Validate code preservation
        print(f"\n5. Validating code preservation...")
        if result.validate_code_preservation(vfp_code):
            print("   [OK] Original code preserved exactly - NO modifications!")
        else:
            print("   [FAIL] Code was modified - this should not happen!")
            return 1

        # Show file header
        print(f"\n6. Generated File Header:")
        print("   " + "-" * 66)
        for line in result.file_header.to_vfp_comment().split('\n'):
            print(f"   {line}")
        print("   " + "-" * 66)

        # Show inline comments
        print(f"\n7. Generated {len(result.inline_comments)} Inline Comments:")
        for i, comment in enumerate(result.inline_comments, 1):
            print(f"\n   Comment #{i}:")
            print(f"   Position: Before line {comment.insert_before_line}")
            if comment.context:
                print(f"   Context: {comment.context}")
            print(f"   Lines:")
            for line in comment.comment_lines:
                print(f"      {line}")

        # Show final assembled code
        print(f"\n8. Final Commented Code:")
        print("   " + "=" * 66)
        assembled = result.assemble_commented_code()
        for i, line in enumerate(assembled.split('\n'), 1):
            print(f"   {i:3d} | {line}")
        print("   " + "=" * 66)

        # Save to output file
        output_file = test_file.stem + "_instructor_commented" + test_file.suffix
        print(f"\n9. Saving to: {output_file}")

        with open(output_file, 'w', encoding='utf-8') as f:
            f.write(assembled)

        print(f"   [OK] Saved successfully!")

        # Statistics
        original_lines = len(vfp_code.splitlines())
        commented_lines = len(assembled.splitlines())
        added_lines = commented_lines - original_lines

        print(f"\n10. Statistics:")
        print(f"    Original lines:  {original_lines}")
        print(f"    Commented lines: {commented_lines}")
        print(f"    Lines added:     {added_lines}")
        print(f"    Comments added:  {len(result.inline_comments)}")

        print("\n" + "=" * 70)
        print("SUCCESS - Real VFP file commented successfully!")
        print("=" * 70)
        print(f"\nYou can now:")
        print(f"  1. Review the output file: {output_file}")
        print(f"  2. Compare with original: {test_file}")
        print(f"  3. Verify code functionality is preserved")
        print("=" * 70)

        return 0

    except Exception as e:
        print(f"\n[ERROR] Test failed: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
