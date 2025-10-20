"""
Simple test script for Instructor-based VFP commenting
======================================================
This script tests the basic functionality before running on actual VFP files.
"""

import sys
from config import ConfigManager
from instructor_client import InstructorLLMClient

def main():
    print("=" * 70)
    print("INSTRUCTOR CLIENT - SIMPLE TEST")
    print("=" * 70)

    try:
        # Initialize configuration
        print("\n1. Loading configuration...")
        config = ConfigManager()
        print("   [OK] Configuration loaded")

        # Initialize Instructor client
        print("\n2. Initializing Instructor client...")
        client = InstructorLLMClient(config)
        print("   [OK] Instructor client initialized")

        # Display configuration
        print("\n3. Client Configuration:")
        stats = client.get_stats()
        for key, value in stats.items():
            print(f"   {key}: {value}")

        # Simple VFP test code
        test_code = """LOCAL lcName, lnAge
lcName = "John Doe"
lnAge = 30
IF lnAge > 18
    ? "Adult"
ENDIF
RETURN lcName"""

        print("\n4. Test VFP Code:")
        print("   " + "-" * 66)
        for line in test_code.split('\n'):
            print(f"   {line}")
        print("   " + "-" * 66)

        # Test structured output generation
        print("\n5. Generating structured comments (this may take 30-60 seconds)...")
        print("   Note: First request to LLM is usually slower")

        result = client.generate_comments_for_vfp(
            vfp_code=test_code,
            filename="test.prg",
            relative_path="test/test.prg"
        )

        if result:
            print("   [OK] Comments generated successfully!")

            # Validate code preservation
            if result.validate_code_preservation(test_code):
                print("   [OK] Code preservation validated - no code was modified")
            else:
                print("   [FAIL] Code preservation check failed!")
                return 1

            # Show results
            print("\n6. Generated File Header:")
            print("   " + "-" * 66)
            for line in result.file_header.to_vfp_comment().split('\n'):
                print(f"   {line}")
            print("   " + "-" * 66)

            print(f"\n7. Generated {len(result.inline_comments)} Inline Comments:")
            for i, comment in enumerate(result.inline_comments, 1):
                print(f"   {i}. Before line {comment.insert_before_line}:")
                for line in comment.comment_lines:
                    print(f"      {line}")

            print("\n8. Final Commented Code:")
            print("   " + "=" * 66)
            for line in result.assemble_commented_code().split('\n'):
                print(f"   {line}")
            print("   " + "=" * 66)

            print("\n" + "=" * 70)
            print("TEST PASSED - Instructor client working correctly!")
            print("=" * 70)
            return 0

        else:
            print("   [FAIL] Failed to generate comments")
            print("\nPossible issues:")
            print("  - LM Studio might not be running")
            print("  - Check if model is loaded in LM Studio")
            print("  - Verify endpoint in config.json matches LM Studio")
            return 1

    except Exception as e:
        print(f"\n[ERROR] Test failed: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
