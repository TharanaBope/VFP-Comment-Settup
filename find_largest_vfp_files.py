import os

# Path to your main VFP folder
base_path = r"D:\Medical Wizard\VFP Entire Codebase\VFP Comment Settup\VFP_Files_Copy"

# File extensions to check
extensions = (".prg", ".spr")

largest_files = []

# Walk through all subdirectories
for root, _, files in os.walk(base_path):
    for file in files:
        if file.lower().endswith(extensions):
            full_path = os.path.join(root, file)
            try:
                with open(full_path, "r", encoding="utf-8", errors="ignore") as f:
                    lines = sum(1 for _ in f)
                largest_files.append((lines, full_path))
            except Exception as e:
                print(f"Error reading {full_path}: {e}")

# Sort by line count descending
largest_files.sort(reverse=True, key=lambda x: x[0])

# Display top 10 biggest files
print("\nTop 10 Largest VFP Files:\n")
for lines, path in largest_files[:10]:
    print(f"{lines:6} lines  -  {path}")
