# VFP Legacy Code Documentation Automation Project

## Project Overview
Build a Python-based automation tool to add comprehensive comments to Visual FoxPro (VFP) legacy code files (.prg and .spr extensions) using a local LLM (GPTOSS20B) running on LM Studio. The tool will recursively process all files in nested folder structures, maintaining the original directory hierarchy.

## Context
- **Legacy System**: Visual FoxPro application codebase
- **Root Directory**: `VFP_Files_Copy` containing multiple folders and subfolders
- **Goal**: Make the codebase understandable for modern developers by adding detailed comments
- **LLM**: GPTOSS20B running locally via LM Studio
- **Endpoint**: `http://127.0.0.1:1234/v1/chat/completions` (OpenAI-compatible API)
- **File Placement**: Commented files are placed in the same directory as originals

## Directory Structure Example
```
VFP_Files_Copy/
├── Classes/
│   ├── stdResizer.PRG
│   ├── stdResizer_commented.PRG  (generated)
│   └── otherClass.PRG
├── Custom Prgs/
│   ├── utility.prg
│   ├── utility_commented.prg  (generated)
│   └── SubFolder/
│       ├── helper.spr
│       └── helper_commented.spr  (generated)
├── Forms/
│   └── mainForm.prg
└── Prgs16/
    └── legacy.prg
```

## Example Transformation
The tool should transform files similar to how `chk_snd_get_eprescription.prg` was converted to `chk_snd_get_eprescription_pretty.prg`:

### Key Transformation Features:
1. **File Header Comment**: Brief explanation of what the entire file/program does
2. **Line-by-Line Comments**: Explanatory comments for complex logic
3. **Block Comments**: For logical sections of code
4. **Preserve Original Code**: Only add comments, don't modify the actual VFP code
5. **Naming Convention**: Original files get "_commented" suffix (not "_pretty")
6. **In-Place Generation**: Commented files are saved in the same directory as originals

## Technical Requirements

### Core Functionality
1. **Recursive Processing**: Process all .prg and .spr files in all subdirectories
2. **In-Place File Generation**: Save commented files in the same directory as originals
3. **LLM Integration**: Use local LLM via LM Studio's OpenAI-compatible API
4. **Progress Tracking**: Show progress with folder path and file count
5. **Error Handling**: Gracefully handle API failures and retry logic
6. **Skip Logic**: Skip already processed files (files with "_commented" in name)
7. **Logging**: Comprehensive logging with folder context

### File Processing Rules
1. Input: `filename.prg` → Output: `filename_commented.prg` (same directory)
2. Input: `filename.spr` → Output: `filename_commented.spr` (same directory)
3. Input: `FILENAME.PRG` → Output: `FILENAME_commented.PRG` (preserve case)
4. Skip files already containing "_commented" in the name
5. Maintain original file structure and formatting
6. Add comments in VFP comment syntax (`*` for full line, `&&` for inline)
7. Process files regardless of case (.prg, .PRG, .spr, .SPR)

### Comment Style Guidelines
```foxpro
* ===== FILE HEADER =====
* Program: [filename]
* Purpose: [Brief description of what this program/file does]
* Location: [Relative path from VFP_Files_Copy]
* Dependencies: [List any called programs or required files]
* Database Tables: [List tables accessed]
* Key Functions: [List main functions/procedures]
* ========================

* [Section description for logical blocks]
LOCAL variable1, variable2  && Declare local variables for [purpose]

* [Explain complex logic before the code block]
IF condition
    * [What this branch does]
    SOME_COMMAND  && [Inline explanation if needed]
ENDIF
```

## Implementation Structure

### Required Python Files:
1. **`main.py`**: Entry point with CLI interface
2. **`llm_client.py`**: LLM communication handler
3. **`vfp_processor.py`**: VFP file parsing and comment injection
4. **`file_scanner.py`**: Recursive directory scanning and file discovery
5. **`config.py`**: Configuration management
6. **`utils.py`**: Helper functions
7. **`progress_tracker.py`**: Progress tracking and reporting
8. **`requirements.txt`**: Python dependencies

### Configuration File (`config.json`):
```json
{
  "llm": {
    "endpoint": "http://127.0.0.1:1234/v1/chat/completions",
    "model": "local-model",
    "temperature": 0.3,
    "max_tokens": 4000,
    "timeout": 60
  },
  "processing": {
    "root_directory": "D:/Medical Wizard/VFP Entire Codebase/VFP Comment Settup/VFP_Files_Copy",
    "file_extensions": [".prg", ".PRG", ".spr", ".SPR"],
    "output_suffix": "_commented",
    "batch_size": 5,
    "retry_attempts": 3,
    "preserve_structure": true,
    "skip_patterns": ["_commented", "_pretty", "_backup"],
    "parallel_workers": 1
  },
  "prompts": {
    "system_prompt": "You are an expert in Visual FoxPro programming. CRITICAL: DO NOT CHANGE ANY ORIGINAL CODE - ONLY ADD COMMENTS.",
    "comment_style": "comprehensive",
    "code_preservation": "strict"
  },
  "logging": {
    "log_level": "INFO",
    "log_file": "vfp_commenting.log",
    "progress_file": "processing_progress.json"
  }
}
```

## File Scanner Implementation

### Directory Walker Function:
```python
def scan_vfp_files(root_directory):
    """
    Recursively scan for .prg and .spr files
    Returns: List of tuples (full_path, relative_path, filename)
    """
    vfp_files = []
    extensions = {'.prg', '.PRG', '.spr', '.SPR'}
    
    for root, dirs, files in os.walk(root_directory):
        for file in files:
            if any(file.endswith(ext) for ext in extensions):
                # Skip already commented files
                if '_commented' not in file and '_pretty' not in file:
                    full_path = os.path.join(root, file)
                    relative_path = os.path.relpath(full_path, root_directory)
                    vfp_files.append({
                        'full_path': full_path,
                        'relative_path': relative_path,
                        'directory': root,
                        'filename': file,
                        'output_path': os.path.join(
                            root, 
                            file.rsplit('.', 1)[0] + '_commented.' + file.rsplit('.', 1)[1]
                        )
                    })
    
    return vfp_files
```

## LLM Prompt Engineering

### System Prompt Template:
```
You are an expert Visual FoxPro (VFP) programmer tasked with adding comprehensive comments to legacy VFP code. Your goal is to make the code understandable for developers who may not be familiar with VFP.

Rules:
1. Add a comprehensive header comment explaining the file's purpose
2. Include the file's location path in the header
3. Add comments before complex logic blocks
4. Use inline comments (&&) for single-line clarifications
5. Use full-line comments (*) for multi-line explanations
6. Identify and document:
   - Input parameters and their types
   - Return values
   - Database operations
   - External file operations
   - Key business logic
   - Error handling patterns
7. Preserve the original code exactly - only add comments
8. Use clear, concise language avoiding VFP jargon where possible
```

### User Prompt Template:
```
Please add comprehensive comments to this VFP code file. Include:
1. A header comment block with file purpose, parameters, dependencies
2. Section comments for logical code blocks
3. Line-by-line comments for complex operations
4. Inline comments for clarification where needed

File: [FILENAME]
Location: [RELATIVE_PATH]

Original VFP Code:
[CODE_CONTENT]

Return the same code with added comments in VFP comment syntax.
```

## Features to Implement

### Phase 1 - Core Functionality
- [ ] Recursive directory scanning for VFP files
- [ ] Basic LLM connection to LM Studio
- [ ] Single file processing with in-place output
- [ ] Comment injection without breaking code
- [ ] Basic error handling

### Phase 2 - Batch Processing
- [ ] Process all discovered files with progress tracking
- [ ] Skip already processed files
- [ ] Resume capability for interrupted batches
- [ ] Folder-by-folder progress reporting
- [ ] Save progress state for recovery

### Phase 3 - Advanced Features
- [ ] Parallel processing for multiple files (optional)
- [ ] Smart chunking for large files
- [ ] Comment quality validation
- [ ] Processing statistics per folder
- [ ] Generate summary report with folder tree

### Phase 4 - Optimization
- [ ] Memory-efficient processing for large codebases
- [ ] Incremental processing (only new/modified files)
- [ ] Custom prompts for specific folders
- [ ] Backup original files before processing (optional)

## Progress Tracking

### Progress Display Format:
```
Processing VFP Files
====================
Root: D:\Medical Wizard\VFP Entire Codebase\VFP Comment Settup\VFP_Files_Copy
Total Files Found: 247
Files to Process: 235 (12 already commented)

Current Folder: Classes
[████████████░░░░░░░] 45/235 (19.1%) - stdResizer.PRG
Time Elapsed: 00:05:23 | Est. Remaining: 00:22:15

Completed Folders:
✓ Classes (23 files)
✓ Custom Prgs (45 files)
⟳ Forms (processing...)
  Forms16 (pending)
  FormsREF (pending)
```

## Error Handling Strategy
1. **API Timeouts**: Implement exponential backoff with folder context
2. **Token Limits**: Smart file chunking with size detection
3. **Malformed Responses**: Validation and retry logic
4. **File I/O Errors**: Proper exception handling with path info
5. **LLM Hallucinations**: Post-processing validation
6. **Permission Errors**: Skip and log files that can't be accessed

## Testing Strategy
1. Start with a single subfolder (e.g., test on `Classes` folder first)
2. Validate that original code remains unchanged
3. Check comment syntax is valid VFP
4. Verify commented files are in correct locations
5. Test with complex nested structures
6. Ensure case sensitivity is handled correctly

## Success Metrics
- All accessible .prg and .spr files have commented versions
- Commented files are in the same directories as originals
- Comments are accurate and helpful
- Original code functionality preserved
- Processing time is reasonable (< 30 seconds per file)
- Error rate < 5%
- Complete folder structure processed

## CLI Usage Examples
```bash
# Process entire VFP_Files_Copy directory structure
python main.py --root "D:/Medical Wizard/VFP Entire Codebase/VFP Comment Settup/VFP_Files_Copy"

# Process specific subfolder only
python main.py --root "D:/Medical Wizard/VFP Entire Codebase/VFP Comment Settup/VFP_Files_Copy/Classes"

# Dry run to see what would be processed
python main.py --root "./VFP_Files_Copy" --dry-run

# Resume interrupted processing
python main.py --root "./VFP_Files_Copy" --resume

# Generate report of all commented files
python main.py --root "./VFP_Files_Copy" --report

# Process with custom config
python main.py --config custom_config.json

# Show folder tree with file counts
python main.py --root "./VFP_Files_Copy" --analyze
```

## Sample Progress State File (`processing_progress.json`)
```json
{
  "session_id": "2024-01-15_143022",
  "root_directory": "D:/Medical Wizard/VFP Entire Codebase/VFP Comment Settup/VFP_Files_Copy",
  "total_files": 247,
  "processed_files": 45,
  "failed_files": 2,
  "skipped_files": 12,
  "current_file": "Forms/mainForm.prg",
  "folders_status": {
    "Classes": "completed",
    "Custom Prgs": "completed",
    "Forms": "in_progress",
    "Forms16": "pending",
    "FormsREF": "pending"
  },
  "processed_list": [
    "Classes/stdResizer.PRG",
    "Classes/baseClass.prg",
    "Custom Prgs/utility.prg"
  ],
  "failed_list": [
    {
      "file": "Classes/corrupted.prg",
      "error": "File encoding error"
    }
  ]
}
```

## Development Steps
1. Set up Python environment with required packages
2. Test LM Studio connection with simple prompt
3. Build recursive file scanner for VFP_Files_Copy
4. Implement in-place file generation logic
5. Create progress tracking with folder context
6. Add comprehensive logging with paths
7. Test on single folder first
8. Implement batch processing for entire structure
9. Add resume capability
10. Process entire codebase
11. Generate final report with folder tree

## Notes for Implementation
- **IMPORTANT**: Always save commented files in the same directory as originals
- Use os.path.join() for cross-platform path handling
- Handle both uppercase and lowercase extensions (.prg, .PRG, .spr, .SPR)
- Implement atomic file writes to prevent corruption
- Create detailed logs with full paths for debugging
- Consider file locking for concurrent access scenarios
- Make sure to handle special characters in folder names
- Test with deep nested folder structures

## Dependencies
- Python 3.8+
- requests (for API calls)
- tqdm (progress bars with nested folder support)
- colorama (colored output)
- tenacity (retry logic)
- click (CLI interface)
- pathlib (modern path handling)
- json (progress state management)
- asyncio (optional - for parallel processing)