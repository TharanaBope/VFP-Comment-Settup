# VFP Legacy Code Commenting Tool - Production System

🚀 **PRODUCTION READY**: Two-phase commenting system with Pydantic/Instructor validation

## Overview

Automatically adds comprehensive comments to Visual FoxPro (.prg and .spr) legacy code files using a local LLM (GPT OSS 20B via LM Studio) with **strict code preservation** through structured output validation.

**System Architecture**: Two-phase Pydantic/Instructor system with adaptive chunking optimized for 24GB VRAM.

## Key Features

- 🔒 **Guaranteed Code Preservation**: Pydantic validators ensure 100% original code preservation
- 📝 **Intelligent Comments**: Two-phase system (context extraction + chunk commenting)
- 🎯 **Adaptive Chunking**: Automatically adjusts chunk size (100-200 lines) based on file size
- 📊 **Multi-Layer Validation**: 3 validators (Quality, Insertion, Metrics)
- 📂 **Flexible Processing**: Single file, folder, or entire directory
- 🔄 **Progress Tracking**: Real-time progress with comprehensive statistics
- ⚡ **Local LLM**: Privacy-focused with LM Studio

## Hardware Requirements

- **GPU**: AMD Radeon RX 7900 XTX 24GB VRAM (or equivalent)
- **RAM**: 128GB recommended
- **Model**: GPT OSS 20B (selected after testing vs Qwen3Coder 30B)

## Quick Start

### 1. Prerequisites

- Python 3.8+ installed
- LM Studio running locally with GPT OSS 20B model
- LM Studio endpoint configured in `config.json`

### 2. Installation

```bash
# Create virtual environment (if not exists)
python -m venv venv

# Activate virtual environment
# Windows:
venv\Scripts\activate
# Linux/Mac:
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

### 3. Configuration

Edit `config.json` to set your LM Studio endpoint:

```json
{
  "llm": {
    "endpoint": "http://YOUR_IP:1234/v1",
    "model": "openai/gpt-oss-20b"
  }
}
```

### 4. Test Single File

```bash
# Test on a single file first
python batch_process_vfp.py --path "VFP_Files_Copy/Classes/stdResizer.PRG"
```

### 5. Production Batch Processing

```bash
# Dry run to preview
python batch_process_vfp.py --path "VFP_Files_Copy" --dry-run

# Process entire directory
python batch_process_vfp.py --path "VFP_Files_Copy"

# Process specific folder only
python batch_process_vfp.py --path "VFP_Files_Copy/Forms"

# Skip already-commented files
python batch_process_vfp.py --path "VFP_Files_Copy" --skip-existing
```

## Command-Line Interface

### Main Production Tool: `batch_process_vfp.py`

| Option | Description | Example |
|--------|-------------|---------|
| `--path`, `-p` | Path to process (file/folder/directory) | `--path "VFP_Files_Copy"` |
| `--config`, `-c` | Configuration file | `--config "config.json"` |
| `--skip-existing` | Skip files with `_commented` versions | `--skip-existing` |
| `--dry-run` | Preview without processing | `--dry-run` |
| `--resume` | Resume from previous session | `--resume` |

### Examples

```bash
# Process entire directory
python batch_process_vfp.py --path "VFP_Files_Copy"

# Process single folder
python batch_process_vfp.py --path "VFP_Files_Copy/Forms"

# Process single file
python batch_process_vfp.py --path "VFP_Files_Copy/Custom Prgs/getdailycomments.prg"

# Dry run preview
python batch_process_vfp.py --path "VFP_Files_Copy/Classes" --dry-run

# Resume after interruption
python batch_process_vfp.py --path "VFP_Files_Copy" --resume --skip-existing
```

## Two-Phase Processing Architecture

### Phase 1: Context Extraction
- Analyzes file structure (PROCEDURE/FUNCTION signatures)
- Extracts high-level understanding (file overview, dependencies)
- Returns validated `FileAnalysis` Pydantic model
- Fast operation (~1-2 seconds)

### Phase 2: Chunk-Based Commenting
- Splits file into VFP-aware chunks (respects PROCEDURE boundaries)
- Adaptive sizing: 100-200 lines based on file size
- Each chunk processed with Phase 1 context
- Returns validated `ChunkComments` with exact insertion points
- Validates and inserts comments into original code

## Multi-Layer Validation System

### 1. Comment Quality Validator
- ✅ VFP syntax check (all comments start with `*`)
- ✅ Relevance check (10% keyword coverage minimum)
- ✅ Completeness check (file header + inline comments)
- ✅ Business logic coverage (50% dependency mentions)

### 2. Comment Insertion Validator
- ✅ Pre-insertion: Line numbers valid, no duplicates
- ✅ Post-insertion: Code preservation verified
- ✅ Comment count matches expected

### 3. Comment Metrics
- Comment ratio (comments per 100 lines of code)
- Keyword coverage percentage
- Procedure coverage percentage
- Average comment length

## File Processing Results

**Input**: `filename.prg`
**Output**: `filename_commented.prg` (same directory)

The tool processes:
- `.prg` and `.PRG` files (Visual FoxPro programs)
- `.spr` and `.SPR` files (Visual FoxPro screen files)
- Maintains exact directory structure
- Skips files already containing `_commented` in the name

## Performance (GPT OSS 20B on 24GB VRAM)

| File Size | Chunks | Processing Time | Performance |
|-----------|--------|-----------------|-------------|
| ~100 lines | 1 | ~30 seconds | Small files |
| ~500 lines | 3 | ~1 minute | Medium files |
| ~1,200 lines | 8 | ~2 minutes | Large files |
| ~8,000 lines | 41 | ~8 minutes | Very large files |

**Optimization**: Adaptive chunking provides ~70% faster processing vs fixed 30-line chunks.

## Project Structure

```
VFP Comment Settup/
├── batch_process_vfp.py       # Main production CLI tool
├── instructor_client.py       # LLM client with Instructor integration
├── structured_output.py       # Pydantic models + 3 validators
├── two_phase_processor.py     # Two-phase orchestrator
├── vfp_chunker.py            # Adaptive VFP-aware chunking
├── file_scanner.py           # Recursive VFP file scanner
├── progress_tracker.py       # Progress tracking & persistence
├── config.py                 # Configuration manager
├── utils.py                  # Helper functions & validators
│
├── config.json               # Production configuration (24GB VRAM optimized)
├── requirements.txt          # Python dependencies
├── README.md                 # This file
│
├── test_large_file.py        # Single-file testing tool
│
├── .claude/                  # Claude Code project settings
│   └── CLAUDE.md            # Detailed system documentation
│
├── used-methods/            # Archive of development utilities
├── compare/                 # Test outputs and comparisons
├── venv/                   # Python virtual environment
└── VFP_Files_Copy/         # Source VFP files
```

## Configuration Highlights

### 24GB VRAM Optimizations (config.json)

```json
{
  "llm": {
    "max_tokens": 16000,           // 4x increase for complex code
    "context_window": 32000,       // Full 24GB VRAM capacity
    "timeout": 1200                // 20 min for large files
  },
  "processing": {
    "max_chunk_lines": 150,        // 5x increase vs basic
    "adaptive_chunk_small_file": 100,
    "adaptive_chunk_medium_file": 150,
    "adaptive_chunk_large_file": 200,
    "context_extraction_max_lines": 1000,  // 2x increase
    "enable_adaptive_chunking": true,
    "chunk_validation_strict": true
  }
}
```

## Testing Workflow

### Step 1: Test Single Small File
```bash
python batch_process_vfp.py --path "VFP_Files_Copy/Classes/stdResizer.PRG"
# Expected: ~30 seconds, produces stdResizer_commented.PRG
```

### Step 2: Test Small Folder
```bash
python batch_process_vfp.py --path "VFP_Files_Copy/Classes"
# Processes all files in Classes folder
```

### Step 3: Production Run
```bash
python batch_process_vfp.py --path "VFP_Files_Copy" --skip-existing
# Overnight run for all files
```

## Progress Tracking Output

```
VFP Batch Processor - Two-Phase Commenting System
================================================================================

Scanning for VFP files...
Total VFP Files Found: 247
Files ready for processing: 247

Ready to process 247 VFP files.

Initializing two-phase processor...
Processor initialized.

File 45/247 [████████████░░░░░░░] 18.2% | ✓42 ✗1 ⊘2 | Time: 12:34 | ETA: 54:20

FINAL PROCESSING REPORT
================================================================================
Files Processed: 247/247
Results:
  ✅ Successful: 244 (98.8%)
  ❌ Failed: 1
  ⊘ Skipped: 2
Performance:
  Average Processing Time: 45.23 seconds per file
  Processing Rate: 1.3 files per minute
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
* ====================================================================
* FILE: sample.prg
* LOCATION: Custom Prgs/sample.prg
* ====================================================================
*
* OVERVIEW: Sample VFP program demonstrating age validation logic
*
* DEPENDENCIES:
*   - None
*
* TOTAL LINES: 7
* ====================================================================

* Declare local variables for person information
LOCAL lcName, lnAge
lcName = "John Doe"
lnAge = 30

* Check if person is an adult (18 or older)
IF lnAge > 18
    ? "Adult"
ENDIF

* Return the person's name
RETURN lcName
```

**Validation**: ✅ PASSED (original code 100% preserved)

## Error Handling

The tool gracefully handles:
- **LLM Connection Failures**: Automatic retry with exponential backoff
- **Validation Failures**: Logs error and continues to next file
- **File Access Errors**: Skips inaccessible files with logging
- **Interrupted Processing**: Resume capability with `--resume` flag
- **Large Files**: Adaptive chunking prevents memory issues

## Logging

- `batch_processing.log` - Detailed processing log with timestamps
- `processing_progress.json` - Progress state for resume capability
- Console output - Real-time progress and statistics

## Troubleshooting

### LLM Connection Issues
```bash
# Verify LM Studio is running
curl http://YOUR_IP:1234/v1/models

# Test with single file
python batch_process_vfp.py --path "VFP_Files_Copy/Classes/stdResizer.PRG"
```

### Incorrect Location Headers
- Ensure `config.json` has correct `root_directory` path
- Location is calculated relative to `root_directory` setting

### Performance Issues
- Check GPU memory usage in LM Studio
- Reduce `max_chunk_lines` if timeouts occur
- Use `--skip-existing` to resume failed runs

## Model Selection

**Chosen Model**: GPT OSS 20B
**Runner-up**: Qwen3Coder 30B

**Selection Criteria**:
- ✅ Better comments for developers unfamiliar with VFP
- ✅ More detailed explanations of business logic
- ✅ Clearer file headers and dependencies
- ✅ Validated on 7,915 line files successfully

## Security & Privacy

- ✅ All processing done locally (no cloud APIs)
- ✅ Original files never modified (output saved separately)
- ✅ No data leaves your network
- ✅ All operations logged for audit

## Support & Documentation

- **Usage Guide**: `used-methods/BATCH_PROCESSOR_USAGE.md`
- **System Architecture**: `.claude/CLAUDE.md`
- **Logs**: `batch_processing.log`
- **Configuration**: `config.json`

## Development vs Production

| Tool | Purpose | Use Case |
|------|---------|----------|
| `batch_process_vfp.py` | **Production** | Batch processing entire codebase |
| `test_large_file.py` | **Testing** | Single-file testing and validation |

---

**Status**: ✅ PRODUCTION READY
**Last Updated**: 2025-10-27
**System Version**: Two-Phase Pydantic/Instructor v1.0
