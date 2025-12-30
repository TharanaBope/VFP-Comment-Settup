"""
Quick test to verify VFP preprocessing handles both patterns correctly.
"""
import re

# Test data
threshold = 1000

# Pattern 1: Value="base64..." (for .sc2 forms)
pattern1 = r'(Value\s*=\s*)"([A-Za-z0-9+/=]{' + str(threshold) + r',})"'
replacement1 = r'\1"[OLE_BINARY_DATA_REMOVED_FOR_LLM_PROCESSING]"'

test_sc2 = 'Value="' + 'A' * 2000 + '"'
result1 = re.sub(pattern1, replacement1, test_sc2)
print(f"Pattern 1 (.sc2 forms):")
print(f"  Input length: {len(test_sc2)}")
print(f"  Output: {result1}")
print(f"  PASS" if "[OLE_BINARY_DATA_REMOVED_FOR_LLM_PROCESSING]" in result1 else "  FAIL")
print()

# Pattern 2: <![CDATA[base64...]]> (for .fr2/.lb2 reports)
pattern2 = r'(<!\[CDATA\[)([A-Za-z0-9+/=]{' + str(threshold) + r',})(\]\]>)'
replacement2 = r'\1[BINARY_DATA_REMOVED_FOR_LLM_PROCESSING]\3'

test_fr2 = '<![CDATA[' + 'B' * 3500 + ']]>'
result2 = re.sub(pattern2, replacement2, test_fr2)
print(f"Pattern 2 (.fr2 reports):")
print(f"  Input length: {len(test_fr2)}")
print(f"  Output: {result2}")
print(f"  PASS" if "[BINARY_DATA_REMOVED_FOR_LLM_PROCESSING]" in result2 else "  FAIL")
print()

# Test with actual sample from absreport.fr2
actual_fr2_sample = '<tag2><![CDATA[TWljcm9zb2Z0IFByaW50IHRvIFBERgAAAAAAAAAAAAABBAMGnABQFAMvAQABAAEA' + 'A' * 3000 + ']]>'
result3 = re.sub(pattern2, replacement2, actual_fr2_sample)
print(f"Pattern 2 (actual .fr2 sample):")
print(f"  Input length: {len(actual_fr2_sample)}")
print(f"  Output length: {len(result3)}")
print(f"  Bytes removed: {len(actual_fr2_sample) - len(result3)}")
print(f"  PASS" if "[BINARY_DATA_REMOVED_FOR_LLM_PROCESSING]" in result3 else "  FAIL")
