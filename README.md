# VFP Legacy Code Commenting Tool

🛡️ **CRITICAL SAFETY FIRST**: This tool NEVER modifies original VFP code - it only adds comments while preserving code 100%.

## Overview

Automatically adds comprehensive comments to Visual FoxPro (.prg and .spr) legacy code files using a local LLM (GPTOSS20B via LM Studio) while maintaining **STRICT CODE PRESERVATION**.

**Found**: 2,190 VFP files (64.3 MB) ready for processing across your codebase.

## Key Features

- 🔒 **Code Preservation Guarantee**: Multiple validation layers ensure original code is never modified
- 📝 **Comprehensive Comments**: Adds file headers, section comments, and inline explanations
- 📂 **Recursive Processing**: Handles entire directory structures with progress tracking
- 🔄 **Resume Capability**: Can resume interrupted processing sessions
- 📊 **Progress Tracking**: Real-time progress with folder-level statistics
- ⚡ **Local LLM**: Uses LM Studio for privacy and control

## Quick Start

### 1. Prerequisites

- Python 3.8+ installed
- LM Studio running locally with GPTOSS20B model
- LM Studio API endpoint: `http://127.0.0.1:1234/v1/chat/completions`

### 2. Installation

```bash
# Install dependencies
pip install -r requirements.txt

# Verify installation
python main.py --version
```

### 3. Test Setup

```bash
# Test file scanner (safe - read-only)
python file_scanner.py

# Test LLM connection
python main.py test-llm

# Analyze files (safe - no processing)
python main.py analyze --root "VFP_Files_Copy"
```

### 4. Process Files

```bash
# Dry run (see what would be processed)
python main.py process --root "VFP_Files_Copy" --dry-run

# Process all files
python main.py process --root "VFP_Files_Copy"

# Process with limits (for testing)
python main.py process --root "VFP_Files_Copy" --max-files 5
```

## Safety Features

### 🛡️ Code Preservation Validation

The tool implements **5 validation layers**:

1. **Hash Comparison**: SHA-256 hash of original code vs commented code
2. **Line Count Validation**: Ensures no code lines are added/removed
3. **Line-by-Line Comparison**: Verifies each code line is identical
4. **Missing Line Detection**: Checks for any missing original code
5. **Extra Code Detection**: Prevents addition of new code (only comments allowed)

### 🚨 Automatic Safety Features

- **Backup Creation**: Original files are backed up before processing
- **Atomic Operations**: Files are written atomically to prevent corruption
- **Validation Failures**: Processing halts immediately if any validation fails
- **Retry Logic**: Failed validations trigger retry with stronger prompts
- **Comprehensive Logging**: All validation steps are logged for audit

## File Structure

```
VFP Comment Setup/
├── main.py              # CLI entry point
├── file_scanner.py      # VFP file discovery
├── llm_client.py        # LLM communication
├── vfp_processor.py     # File processing with validation
├── utils.py             # Code preservation validation
├── config.py            # Configuration management
├── progress_tracker.py  # Progress tracking and reporting
├── config.json          # Configuration settings
├── requirements.txt     # Python dependencies
└── README.md           # This file
```

## Processing Results

**Input**: `filename.prg` → **Output**: `filename_commented.prg` (same directory)

The tool processes:
- `.prg` and `.PRG` files (Visual FoxPro programs)
- `.spr` and `.SPR` files (Visual FoxPro screen files)
- Maintains exact directory structure
- Skips files already containing "_commented" in the name

## Configuration

The `config.json` file contains safety-first defaults:

```json
{
  "safety": {
    "require_code_hash_match": true,      // CRITICAL
    "require_line_count_match": true,     // CRITICAL  
    "backup_before_processing": true,     // CRITICAL
    "halt_on_validation_failure": true,   // CRITICAL
    "validate_vfp_syntax": true
  }
}
```

**⚠️ WARNING**: Do not disable safety settings without understanding the risks.

## Commands

### `process` - Main Processing Command
```bash
python main.py process --root "VFP_Files_Copy"           # Process all files
python main.py process --root "VFP_Files_Copy" --dry-run # Preview only
python main.py process --root "VFP_Files_Copy" --resume  # Resume session
```

### `analyze` - File Analysis (Safe)
```bash
python main.py analyze --root "VFP_Files_Copy"           # Analyze structure
```

### `test-llm` - Test LLM Connection
```bash
python main.py test-llm                                  # Test with sample code
```

### `show-config` - View Configuration
```bash
python main.py show-config                               # Display settings
```

## Progress Tracking

The tool provides comprehensive progress tracking:

```
File 45/2190 [████████████░░░░░░░] 19.1% | ✓1832 ✗12 ⊘346 | Time: 05:23 | ETA: 22:15

Current Folder: Prgs16
✓ Classes (1 files)
✓ Custom Prgs (2 files)  
✓ Forms (33 files)
⟳ Prgs16 (processing...)
  PrgsREF (pending)
```

## Validation Example

**Original Code**:
```foxpro
LOCAL lcName, lnAge
lcName = "John Doe"
lnAge = 30
IF lnAge > 18
    ? "Adult"
ENDIF
RETURN lcName
```

**Valid Commented Output**:
```foxpro
* ===== FILE HEADER =====
* Program: sample.prg
* Purpose: Sample VFP program demonstrating age validation
* ========================

* Declare local variables for person information
LOCAL lcName, lnAge
lcName = "John Doe"  && Set person's name
lnAge = 30           && Set person's age

* Check if person is an adult (18 or older)
IF lnAge > 18
    ? "Adult"        && Display adult status
ENDIF

* Return the person's name
RETURN lcName
```

**Hash Validation**: ✅ PASSED (original code preserved exactly)

## Error Handling

The tool handles various error conditions:

- **LLM Connection Failures**: Automatic retry with exponential backoff
- **Validation Failures**: Immediate halt with detailed error reporting
- **File Access Errors**: Skip inaccessible files with logging
- **Interrupted Processing**: Resume capability with session persistence
- **Memory Issues**: Process one file at a time to minimize memory usage

## Performance

**Current Scan Results**:
- **Total Files**: 2,190 VFP files
- **Total Size**: 64.3 MB
- **Estimated Time**: ~18 hours (30 seconds per file average)
- **Extensions**: .PRG (464), .prg (1,592), .SPR (22), .spr (112)

## Troubleshooting

### LLM Connection Issues
```bash
# Verify LM Studio is running
curl http://127.0.0.1:1234/v1/chat/completions

# Test connection
python main.py test-llm
```

### Validation Failures
- Check `vfp_commenting.log` for detailed error messages
- Ensure LLM is not modifying original code
- Review system and user prompts in `config.json`

### Performance Issues
- Reduce `batch_size` in config.json
- Use `--max-files` for testing
- Monitor memory usage with large files

## Security Notes

- All processing is done locally (no cloud APIs)
- Original files are never modified
- Backups are created before processing
- All operations are logged for audit
- Configuration emphasizes safety over speed

## Support

For issues or questions:
1. Check the logs in `vfp_commenting.log`
2. Review the configuration in `config.json`
3. Test with a small subset using `--max-files 5`
4. Examine the detailed error messages

---

**Remember**: This tool prioritizes safety over everything else. Original code preservation is guaranteed through multiple validation layers.