# VFP Comment Tool Enhancement Plan
## Transform from Batch Processor to Interactive Developer Assistant

### Current Architecture Analysis

#### Existing Commands:
1. `process` - Batch process entire directory
2. `scan` - Analyze files without processing
3. `test-llm` - Test LLM connection
4. `show-config` - Display configuration
5. `process-file` - Process single file (basic)

#### Current Modules:
- **main.py**: CLI interface with Click framework
- **llm_client.py**: LLM communication via API
- **vfp_processor.py**: File processing and validation
- **file_scanner.py**: Directory scanning and file discovery
- **config.py**: Configuration management
- **progress_tracker.py**: Progress tracking and session management
- **utils.py**: Validation and utility functions

### Enhancement Goals

#### 1. Interactive Developer Workflow
Transform the tool to provide immediate feedback and control:

```bash
# New enhanced workflow
python main.py interactive --file myfile.prg --custom-prompt "Add database table documentation"
```

**Workflow Steps:**
1. Developer specifies file and optional custom prompt
2. Tool processes file with LLM
3. Shows preview of commented code
4. Asks developer: "Are you satisfied with the output? (s)ave/(d)elete/(r)etry: "
5. If retry: allows custom prompt modification
6. If save: writes commented file
7. If delete: discards output

#### 2. Custom Prompt System
Allow developers to augment the base commenting with specific requests:

**Examples:**
- "Add detailed database schema documentation"
- "Focus on explaining business logic for accounting rules"
- "Add performance optimization notes"
- "Include error handling explanations"

#### 3. Preview and Comparison System
- Show side-by-side original vs commented code
- Highlight added comment sections
- Display statistics (lines added, coverage %)

### Implementation Plan

#### Phase 1: Core Interactive Features

##### 1.1 Enhanced CLI Interface
**File:** `main.py`
- Add `interactive` command
- Add `--custom-prompt` parameter
- Add `--preview-only` flag
- Add confirmation system

**New Command Structure:**
```python
@cli.command()
@click.option('--file', '-f', required=True, type=click.Path(exists=True))
@click.option('--custom-prompt', '-p', help='Additional instructions for LLM')
@click.option('--preview-only', is_flag=True, help='Show preview without saving')
@click.option('--template', '-t', help='Use predefined prompt template')
@click.option('--diff', is_flag=True, help='Show side-by-side comparison')
def interactive(file, custom_prompt, preview_only, template, diff):
    """Interactive file processing with preview and confirmation."""
```

##### 1.2 Custom Prompt Integration
**File:** `llm_client.py`
- Modify `process_file()` to accept custom prompts
- Merge base system prompt with custom instructions
- Maintain prompt history for retry scenarios

**Enhancement:**
```python
def process_file(self, code_content: str, filename: str, relative_path: str,
                file_size: int, custom_prompt: Optional[str] = None) -> Optional[str]:
    """Enhanced process_file with custom prompt support."""

    # Build enhanced user prompt
    user_prompt = self._build_user_prompt(code_content, filename, relative_path, file_size)

    if custom_prompt:
        user_prompt += f"\n\nADDITIONAL REQUIREMENTS:\n{custom_prompt}"

    # Process with enhanced prompt
    return self._make_llm_request(messages)
```

##### 1.3 Preview System
**New File:** `preview_manager.py`
- Display formatted code preview
- Show diff between original and commented
- Statistics display (lines added, coverage)

**Features:**
```python
class PreviewManager:
    def show_preview(self, original: str, commented: str, filename: str):
        """Display formatted preview with statistics."""

    def show_diff(self, original: str, commented: str):
        """Side-by-side comparison view."""

    def get_statistics(self, original: str, commented: str) -> Dict:
        """Calculate commenting statistics."""
```

##### 1.4 Confirmation System
**New File:** `interaction_manager.py`
- Handle user confirmations
- Manage retry workflows
- File save/delete operations

**Features:**
```python
class InteractionManager:
    def get_user_decision(self) -> str:
        """Get save/delete/retry decision from user."""

    def handle_retry(self, original_prompt: str) -> str:
        """Allow user to modify prompt for retry."""

    def save_or_delete(self, decision: str, content: str, output_path: str):
        """Execute user's save/delete decision."""
```

#### Phase 2: Advanced Features

##### 2.1 Prompt Template System
**New File:** `prompt_templates.py`
- Pre-defined templates for common scenarios
- Template management and customization
- Template library expansion

**Templates:**
```python
TEMPLATES = {
    'database': 'Focus on database operations, table schemas, and SQL queries',
    'business_logic': 'Explain business rules, calculations, and decision logic',
    'error_handling': 'Document error conditions, validations, and exception handling',
    'performance': 'Add performance considerations and optimization notes',
    'integration': 'Document external system integrations and API calls'
}
```

##### 2.2 Enhanced Diff Viewer
- Colored output for terminal
- Line-by-line comparison
- Comment highlighting
- Export diff to HTML

##### 2.3 Session Management
- Track processing history
- Save successful prompts for reuse
- Maintain user preferences

#### Phase 3: Developer Experience

##### 3.1 Configuration Profiles
- Project-specific settings
- Team prompt standards
- IDE integration support

##### 3.2 Batch Interactive Mode
- Process multiple files with individual review
- Consistent prompt application
- Bulk approval/rejection

##### 3.3 Quality Metrics
- Comment coverage analysis
- Consistency scoring
- Style compliance checking

### File Structure Changes

#### New Files to Create:
```
VFP Comment Settup/
├── preview_manager.py       # Preview and diff display
├── interaction_manager.py   # User interaction handling
├── prompt_templates.py      # Template management
├── quality_analyzer.py      # Comment quality metrics
└── developer_workflow.py    # High-level workflow orchestration
```

#### Modified Files:
```
├── main.py                  # Add interactive command
├── llm_client.py           # Custom prompt support
├── config.py               # Template and profile management
└── vfp_processor.py        # Enhanced processing pipeline
```

### Example Usage Scenarios

#### Scenario 1: Basic Interactive Processing
```bash
python main.py interactive --file accounting.prg
# Shows preview, asks for confirmation
```

#### Scenario 2: Custom Requirements
```bash
python main.py interactive --file report_gen.prg \
  --custom-prompt "Add detailed SQL query explanations and performance notes"
```

#### Scenario 3: Template Usage
```bash
python main.py interactive --file db_helper.prg --template database --diff
```

#### Scenario 4: Preview Only
```bash
python main.py interactive --file complex_calc.prg --preview-only
```

### Benefits of Enhanced Tool

#### For Developers:
- **Full Control**: See output before committing
- **Customization**: Tailor comments to specific needs
- **Quality Assurance**: Review and iterate on results
- **Learning**: Understand code through interactive exploration

#### For Teams:
- **Consistency**: Shared templates and standards
- **Quality**: Review process ensures useful comments
- **Efficiency**: Interactive workflow faster than manual commenting
- **Preservation**: Safe code analysis with rollback capability

### Implementation Timeline

#### Week 1: Core Interactive Features
- Enhanced CLI with interactive command
- Basic preview system
- Save/delete confirmation workflow

#### Week 2: Custom Prompt Integration
- LLM client enhancements
- Prompt merging and management
- Retry functionality with prompt modification

#### Week 3: Preview and Diff System
- Advanced preview manager
- Side-by-side diff viewer
- Statistics and metrics display

#### Week 4: Template System
- Prompt template library
- Template management interface
- Configuration integration

#### Week 5: Polish and Testing
- Error handling improvements
- User experience refinements
- Comprehensive testing

### Success Metrics

#### Technical:
- [ ] Interactive workflow completes without errors
- [ ] Custom prompts properly integrated with base prompts
- [ ] Preview system accurately displays changes
- [ ] Save/delete operations work reliably

#### User Experience:
- [ ] Developers can easily preview results
- [ ] Custom prompts produce expected output variations
- [ ] Confirmation system prevents unwanted saves
- [ ] Template system speeds up common tasks

#### Quality:
- [ ] Comments remain consistent with base standards
- [ ] Custom requirements properly addressed
- [ ] No code modification during enhancement process
- [ ] Tool remains backward compatible

This plan transforms the VFP commenting tool from a batch processor into an interactive developer assistant, providing full control over the commenting process while maintaining the existing safety and quality features.