# VFP Batch Processor Usage Guide

## Overview
`batch_process_vfp.py` is a production-ready CLI tool for batch processing Visual FoxPro files using the two-phase commenting system.

## Features
- ✅ Process entire directories recursively
- ✅ Process single folders
- ✅ Process individual files
- ✅ Skip files that already have commented versions
- ✅ Dry-run mode to preview what will be processed
- ✅ Progress tracking with real-time statistics
- ✅ Resume capability (planned)
- ✅ Comprehensive error handling and logging

## Installation
Ensure all dependencies are installed:
```bash
pip install -r requirements.txt
```

## Basic Usage

### 1. Process Entire Directory (Recursive)
Process all VFP files in VFP_Files_Copy and all subdirectories:
```bash
python batch_process_vfp.py --path "VFP_Files_Copy"
```

### 2. Process Single Folder
Process only files in the Forms folder:
```bash
python batch_process_vfp.py --path "VFP_Files_Copy/Forms"
```

### 3. Process Single File
Process one specific file:
```bash
python batch_process_vfp.py --path "VFP_Files_Copy/Custom Prgs/getdailycomments.prg"
```

## Advanced Options

### Skip Already-Commented Files
Skip files that already have `_two_phase_commented` versions:
```bash
python batch_process_vfp.py --path "VFP_Files_Copy" --skip-existing
```

### Dry Run (Preview Mode)
See what would be processed without actually processing files:
```bash
python batch_process_vfp.py --path "VFP_Files_Copy" --dry-run
```

### Custom Configuration File
Use a different configuration file:
```bash
python batch_process_vfp.py --path "VFP_Files_Copy" --config "custom_config.json"
```

### Resume Processing (Future)
Resume from a previous interrupted session:
```bash
python batch_process_vfp.py --path "VFP_Files_Copy" --resume
```

## Command-Line Options

| Option | Short | Description | Default |
|--------|-------|-------------|---------|
| `--path` | `-p` | Path to process (file/folder/directory) | Required |
| `--config` | `-c` | Configuration file path | `config.json` |
| `--skip-existing` | - | Skip files with existing commented versions | `False` |
| `--dry-run` | - | Preview mode - no processing | `False` |
| `--resume` | - | Resume from previous session | `False` |

## Output

### Console Output
The tool displays:
- Real-time progress bar with statistics
- Files processed/successful/failed/skipped counts
- Estimated time remaining
- Processing time per file
- Final comprehensive report

### Files Created
Each processed file creates a new file with `_two_phase_commented` suffix:
- Original: `file.prg`
- Output: `file_two_phase_commented.prg`

Output files are saved in the **same directory** as the original files.

### Log Files
- `batch_processing.log` - Detailed processing log with timestamps
- `processing_progress.json` - Progress state for resume capability

## Examples

### Example 1: First-Time Processing
Process everything for the first time:
```bash
python batch_process_vfp.py --path "VFP_Files_Copy"
```

### Example 2: Re-run After Changes (Skip Completed)
Process only new or unprocessed files:
```bash
python batch_process_vfp.py --path "VFP_Files_Copy" --skip-existing
```

### Example 3: Preview Large Directory
Check what would be processed before running overnight:
```bash
python batch_process_vfp.py --path "VFP_Files_Copy" --dry-run
```

### Example 4: Test on One Folder
Test the system on a small folder first:
```bash
python batch_process_vfp.py --path "VFP_Files_Copy/Classes"
```

### Example 5: Single File Testing
Quick test on a single file:
```bash
python batch_process_vfp.py --path "VFP_Files_Copy/Classes/stdResizer.PRG"
```

## Path Handling

**IMPORTANT**: Use forward slashes in paths to avoid Windows escaping issues:
- ✅ Correct: `"VFP_Files_Copy/Forms/file.prg"`
- ❌ Incorrect: `"VFP_Files_Copy\Forms\file.prg"` (may cause issues)

Alternatively, you can use quotes and backslashes if needed:
```bash
python batch_process_vfp.py --path "VFP_Files_Copy\Forms"
```

## Performance Expectations

Based on testing with GPT OSS 20B on AMD Radeon RX 7900 XTX 24GB:

| File Size | Chunks | Processing Time | Comments |
|-----------|--------|-----------------|----------|
| ~100 lines | 1 | ~30 seconds | Small files |
| ~500 lines | 3 | ~1 minute | Medium files |
| ~1,200 lines | 8 | ~2 minutes | Large files |
| ~8,000 lines | 41 | ~8 minutes | Very large files |

**Estimated Overnight Run**: For ~250 files averaging 500 lines each:
- Total time: ~4-6 hours
- Best approach: Start before bed, review results in morning

## Troubleshooting

### Issue: "Invalid path or not a VFP file"
- Ensure path exists and points to a directory or .prg/.spr file
- Use forward slashes in paths
- Check file extension is .prg or .spr (case-insensitive)

### Issue: "Error loading configuration"
- Verify `config.json` exists in the current directory
- Check JSON syntax is valid
- Ensure LM Studio is running at the configured endpoint

### Issue: Processing is slow
- This is normal for large files (adaptive chunking)
- Check LM Studio GPU utilization
- Consider processing smaller batches first

### Issue: Some files fail
- Check `batch_processing.log` for detailed error messages
- Failed files are tracked in the final report
- You can re-run with `--skip-existing` to only retry failed files

## Comparison with test_large_file.py

| Feature | batch_process_vfp.py | test_large_file.py |
|---------|---------------------|-------------------|
| Purpose | Production batch processing | Single-file testing |
| Input | CLI arguments (flexible) | Hardcoded path (line 42) |
| Multiple files | ✅ Yes | ❌ No |
| Progress tracking | ✅ Yes | ⚠️ Basic |
| Error handling | ✅ Comprehensive | ⚠️ Basic |
| Resume capability | ✅ Planned | ❌ No |
| Dry-run mode | ✅ Yes | ❌ No |
| Skip existing | ✅ Yes | ❌ No |
| **Use case** | **Production overnight runs** | **Development testing** |

## Next Steps

1. **Test on Small Folder First**:
   ```bash
   python batch_process_vfp.py --path "VFP_Files_Copy/Classes" --dry-run
   python batch_process_vfp.py --path "VFP_Files_Copy/Classes"
   ```

2. **Review Results**: Check output files and logs

3. **Run Production Batch**:
   ```bash
   python batch_process_vfp.py --path "VFP_Files_Copy" --skip-existing
   ```

4. **Monitor Progress**: Watch console output and check logs

5. **Review Final Report**: Check statistics and any failed files

## Support

For issues or questions:
- Check `batch_processing.log` for detailed errors
- Review `CLAUDE.md` for system architecture documentation
- Check `config.json` for configuration options
