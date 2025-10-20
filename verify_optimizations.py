"""
Optimization Verification Script
=================================
Verifies that all code-side optimizations are properly configured before testing.
Run this BEFORE making LM Studio changes to ensure the Python code is ready.
"""

import json
import sys
from pathlib import Path

def verify_config():
    """Verify config.json has correct optimization settings"""
    print("\n" + "="*70)
    print("VERIFYING CONFIG.JSON OPTIMIZATIONS")
    print("="*70)

    with open('config.json', 'r') as f:
        config = json.load(f)

    checks = []

    # LLM settings
    llm = config.get('llm', {})
    checks.append(("Temperature", llm.get('temperature'), 0.05, llm.get('temperature') == 0.05))
    checks.append(("Max tokens", llm.get('max_tokens'), 8000, llm.get('max_tokens') == 8000))
    checks.append(("Timeout", llm.get('timeout'), 1200, llm.get('timeout') == 1200))
    checks.append(("Timeout small", llm.get('timeout_small'), 180, llm.get('timeout_small') == 180))
    checks.append(("Timeout medium", llm.get('timeout_medium'), 600, llm.get('timeout_medium') == 600))
    checks.append(("Timeout large", llm.get('timeout_large'), 1200, llm.get('timeout_large') == 1200))

    # Processing settings
    proc = config.get('processing', {})
    checks.append(("Chunk size target", proc.get('chunk_size_target'), 600, proc.get('chunk_size_target') == 600))
    checks.append(("Max chunk lines", proc.get('max_chunk_lines'), 30, proc.get('max_chunk_lines') == 30))
    checks.append(("Chunk overlap", proc.get('chunk_overlap_lines'), 3, proc.get('chunk_overlap_lines') == 3))

    all_passed = True
    for name, actual, expected, passed in checks:
        status = "✅ PASS" if passed else "❌ FAIL"
        print(f"{status} | {name:20s} | Expected: {expected:6} | Actual: {actual}")
        if not passed:
            all_passed = False

    return all_passed

def verify_chunker():
    """Verify VFPChunker has correct default settings"""
    print("\n" + "="*70)
    print("VERIFYING VFP_CHUNKER.PY")
    print("="*70)

    from vfp_chunker import VFPChunker

    chunker = VFPChunker()

    expected_max = 30
    actual_max = chunker.max_chunk_lines
    passed = actual_max == expected_max

    status = "✅ PASS" if passed else "❌ FAIL"
    print(f"{status} | Default max_chunk_lines | Expected: {expected_max} | Actual: {actual_max}")

    # Test sub-chunking with large code
    test_code = "\n".join([f"line {i}" for i in range(50)])
    chunks = chunker.chunk_code(test_code)

    all_chunks_valid = all(chunk.line_count <= 30 for chunk in chunks)
    print(f"{'✅ PASS' if all_chunks_valid else '❌ FAIL'} | Sub-chunking works | 50 lines → {len(chunks)} chunks (all ≤30 lines)")

    return passed and all_chunks_valid

def verify_pydantic_models():
    """Verify Pydantic models are properly configured"""
    print("\n" + "="*70)
    print("VERIFYING STRUCTURED_OUTPUT.PY (PYDANTIC MODELS)")
    print("="*70)

    from structured_output import ProcedureInfo, FileAnalysis, CommentedCode

    # Test ProcedureInfo with LLM-style output (name, line_number, description)
    try:
        proc = ProcedureInfo(
            name="TestProc",
            line_number=10,
            description="Test procedure"
        )
        print("✅ PASS | ProcedureInfo accepts LLM output format (name, line_number, description)")
    except Exception as e:
        print(f"❌ FAIL | ProcedureInfo validation error: {e}")
        return False

    # Test ProcedureInfo with optional fields
    try:
        proc_full = ProcedureInfo(
            name="TestProc",
            line_number=10,
            description="Test procedure",
            type="PROCEDURE",
            start_line=10,
            end_line=20
        )
        print("✅ PASS | ProcedureInfo accepts optional fields (type, start_line, end_line)")
    except Exception as e:
        print(f"❌ FAIL | ProcedureInfo with optional fields error: {e}")
        return False

    # Test FileAnalysis
    try:
        analysis = FileAnalysis(
            filename="test.prg",
            file_overview="Test file",
            procedures=[proc],
            dependencies=["Table: TEST"],
            total_lines=100
        )
        print("✅ PASS | FileAnalysis model works correctly")
    except Exception as e:
        print(f"❌ FAIL | FileAnalysis validation error: {e}")
        return False

    return True

def check_lm_studio_connection():
    """Check if LM Studio endpoint is reachable"""
    print("\n" + "="*70)
    print("CHECKING LM STUDIO CONNECTION")
    print("="*70)

    import requests

    with open('config.json', 'r') as f:
        config = json.load(f)

    endpoint = config['llm']['endpoint']

    try:
        # Try to reach the base endpoint
        response = requests.get(endpoint.replace('/v1', '/v1/models'), timeout=5)
        if response.status_code == 200:
            print(f"✅ PASS | LM Studio is reachable at {endpoint}")
            return True
        else:
            print(f"⚠️  WARN | LM Studio responded with status {response.status_code}")
            return False
    except requests.exceptions.RequestException as e:
        print(f"❌ FAIL | Cannot reach LM Studio at {endpoint}")
        print(f"         Error: {e}")
        return False

def main():
    print("\n" + "="*70)
    print("OPTIMIZATION VERIFICATION SCRIPT")
    print("="*70)
    print("\nThis script verifies all code-side optimizations are in place.")
    print("Run this BEFORE making manual LM Studio changes.\n")

    results = []

    # Run all verifications
    results.append(("Config.json settings", verify_config()))
    results.append(("VFPChunker optimization", verify_chunker()))
    results.append(("Pydantic models", verify_pydantic_models()))
    results.append(("LM Studio connection", check_lm_studio_connection()))

    # Summary
    print("\n" + "="*70)
    print("VERIFICATION SUMMARY")
    print("="*70)

    all_passed = all(passed for _, passed in results)

    for name, passed in results:
        status = "✅ PASS" if passed else "❌ FAIL"
        print(f"{status} | {name}")

    print("="*70)

    if all_passed:
        print("\n✅ ALL VERIFICATIONS PASSED!")
        print("\n📋 NEXT STEPS:")
        print("1. Open LM Studio")
        print("2. Go to model settings (OpenAI's gpt-oss 20B)")
        print("3. Context tab → Set GPU Offload to 18 (from 12)")
        print("4. Inference tab → Set Temperature to 0.05 (from 0.1)")
        print("5. Save settings and restart model if loaded")
        print("6. Run: python.exe test_two_phase.py")
        print("\n📖 For detailed instructions, see OPTIMIZATION_GUIDE.md")
        return 0
    else:
        print("\n❌ SOME VERIFICATIONS FAILED!")
        print("Please check the errors above and fix before proceeding.")
        return 1

if __name__ == "__main__":
    sys.exit(main())
