# CLAUDE.MD - Master Engineering Reference

## CRITICAL STANDARDS

- NO comments inside function bodies (only function header comments + section markers)
- NO src/debug/ or src/logs/ folders in version control (MUST be in .gitignore)
- NO emojis in production code, READMEs, DOCS.md, logs
- NO verbose console output (use logging instead)

**Type hints:** REQUIRED for orchestrators (clear contracts), RECOMMENDED for functions

**Fail-Fast:** Let exceptions fly. No try-catch that silently swallows errors affecting business logic. Script must fail if it cannot fulfill its purpose.

**Keyboard-First:** UI-Steuerung immer per Tastatur, nicht per Maus. Mausinteraktionen nur für Textauswahl/Kopieren. Grund: Terminals haben inkonsistentes Mouse-Handling (SGR mode conflicts, scroll issues).

---

## ARCHITECTURE - 3 LEVELS

### Level 1: PROJECT
```
project/
├── workflow.py          # Project-level orchestrator (root entry point)
├── README.md            # Quick start, installation, basic usage
├── CLAUDE.md            # Engineering standards (this file)
├── LOGS_MAP.md          # Logging architecture and workflow phases
├── src/                 # CRITICAL: All source modules
│   ├── __init__.py      # Package marker
│   ├── module_step1.py  # Self-contained workflow step
│   ├── module_step2.py  # Self-contained workflow step
│   ├── DOCS.md          # Complete module documentation
│   └── logs/            # CRITICAL: Workflow-oriented log files
│       ├── 01_startup.log
│       ├──...
├── bug_fixes/           # CRITICAL: Successful bug-fix documentation (timestamped)
│   └── issue_name_YYYYMMDD_HHMMSS.md
└── not_working/         # CRITICAL: Failed fix attempts documentation (timestamped)
    └── issue_name_YYYYMMDD_HHMMSS_failed.md
```

**Workflow-oriented approach:**
- workflow.py stays at root as entry point, imports from src/ package
- All modules reside in src/ folder with relative imports
- New additions: Extend existing module OR create new module if step is substantial (see thresholds below)
- Utilities and helpers: Part of the module where they're used

**Module Complexity Thresholds ("substantial"):**

A new module is warranted when ANY of these thresholds are exceeded:

1. **Lines of Code:** > 400 LOC with distinct functional groups
2. **Function Count:** > 15 functions (likely multiple responsibilities)
3. **Single Responsibility:** Module handles multiple unrelated concerns

**Example Decision:**
- Module is 320 LOC but has two distinct concerns (scraping + formatting) → Split into 2 modules
- Module is 450 LOC but single cohesive concern → Keep together, extract helper functions instead

**Additional Indicators:**
- Function > 50 LOC → Extract helper functions (not new module)
- > 5 cross-module imports → Review dependencies, may indicate over-coupling

### Level 2: MODULE
Self-contained step: Fixed Input → Processing → Fixed Output.
Not strict pipelines (loops/branches/spirals OK) but clear contracts.

**Clear contracts:** Orchestrator with type hints (input/output) + DOCS.md documentation.

**Each module has its own orchestrator** that calls internal functions in sequence.

### Level 3: FUNCTIONS
Business logic orchestrated by module's internal orchestrator.

---

## 2-LEVEL ORCHESTRATION MODEL

**CRITICAL:** Two distinct orchestration levels

### Project Level (workflow.py)
Orchestrates modules. Calls module orchestrators in sequence.

### Module Level (module_name.py)
Each module has an orchestrator that calls internal functions.

### Inter-Module Dependencies
When module A needs functionality from module B:
- Module A imports specific functions from module B using relative imports
- Module A's orchestrator calls imported functions
- This is reflected in module A's orchestrator

**Example (within src/ package):**
```python
# In src/module_processor.py
# INFRASTRUCTURE
from .module_loader import load_validated_data  # From other module (relative import)

# ORCHESTRATOR
def process_workflow(source):
    raw = load_validated_data(source)  # Cross-module call
    cleaned = clean_data(raw)          # Internal function
    return transform_data(cleaned)     # Internal function
```

**Example (workflow.py importing from src/):**
```python
# In workflow.py (root level)
# INFRASTRUCTURE
from src.module_processor import process_workflow  # Absolute import from src package

# ORCHESTRATOR
def main():
    process_workflow("./data/source.csv")
```

---

## DOCUMENTATION STRUCTURE

### Terminology

| Term | Definition | Example |
|------|------------|---------|
| **Workflow** | README.md level directory containing a complete INDEPENDENT pipeline | `Monitor_CC/` |
| **Directory** | Subdirectory within a workflow (a phase) | `src/` |
| **Module** | Python script (`.py` file) | `monitor.py` |
| **Function** | Python function within a module | `run_monitor()` |

### Hierarchy

```
Workflow/          -> README.md (tree to directories)
├── Directory_A/   -> DOCS.md (tree to modules)
└── Directory_B/   -> DOCS.md
```

**Principle:** No redundancy - README stops where DOCS begins.

---

### README.md (Workflow-Level)

**Purpose:** High-level overview linking to DOCS.md for details

**Placement:**
- **Location:** Workflow root (same directory as workflow.py)
- **Relationship:** One README per workflow
- **Scope:** Tree to directories, links to DOCS.md

**Required Sections:**

#### 1. Title + Description

Workflow name as H1, followed by 1-2 sentence description.

#### 2. Directory Structure

Tree showing root-level files AND directories with `[See DOCS.md]` links:

```
Monitor_CC/
    workflow.py
    README.md
    CLAUDE.md
    LOGS_MAP.md
    src/                                 [See DOCS.md](src/DOCS.md)
```

**Rule:** Only root-level files. Scripts inside directories belong in their DOCS.md.

#### 3. Workflow

Per phase: Purpose, Input, Output, Details link:

```markdown
## Workflow

### Phase 1: Session Discovery

**Purpose:** Find active Claude Code sessions

**Input:** ~/.claude/projects directory

**Output:** List of JSONL file paths

**Details:** [src/DOCS.md](src/DOCS.md)
```

---

### DOCS.md (Directory-Level)

**Purpose:** Detailed documentation of all modules within one directory

**Placement:**
- **Location:** Directory root (e.g., `src/`)
- **Relationship:** Multiple DOCS can exist under one README
- **Scope:** Tree to modules, module-level documentation

**Required Sections:**

#### 1. Working Directory (CRITICAL)

All commands assume CWD = this directory.

```markdown
## Working Directory

**CRITICAL:** All commands assume CWD = `src/`

cd /path/to/Monitor_CC/src
```

#### 2. Directory Structure

Tree showing modules (no functions in tree):

```
src/
├── DOCS.md
├── monitor.py
├── session_finder.py
├── jsonl_parser.py
└── formatter.py
```

#### 3. Module Documentation

Per module with Purpose, Inputs, Outputs, Usage, Variables (NO function-level headers):

```markdown
## monitor.py

**Purpose:** Core polling orchestrator. Continuously monitors session files and displays new tool calls.

**Inputs:**
- `project_filter`: Optional project path to filter sessions
- `mode`: Filter for main/subagent/all files
- `ui_mode`: Enable collapsible UI (boolean)

**Outputs:**
- Formatted tool calls to console
- Collapsible UI list (if ui_mode enabled)

**Usage:**
Called by workflow.py: run_monitor(project_filter, mode, ui_mode)

**Variables:**
- `POLL_INTERVAL`: Seconds between polls (default: 0.5)
```

**Inputs vs Variables:**

| Type | Without it | Example |
|------|------------|---------|
| Input | workflow FAILS | `project_filter`, `mode` |
| Variable | workflow uses defaults | `POLL_INTERVAL` |

---

**Key principle:**
- README.md = "How to RUN this workflow" (paired with workflow.py at root)
- src/DOCS.md = "How modules WORK" (paired with module files in src/)

---

## CODE ORGANIZATION

**CRITICAL:** Every script follows this structure:

**INFRASTRUCTURE → ORCHESTRATOR → FUNCTIONS**

```python
# INFRASTRUCTURE
import pandas as pd
BATCH_SIZE = 100

# ORCHESTRATOR
def process_workflow(input_file: str, output_dir: str) -> None:
    raw = load_data(input_file)
    cleaned = clean_data(raw)
    export_results(analyze_data(cleaned), output_dir)

# FUNCTIONS

# Load raw data from CSV
def load_data(file: str) -> pd.DataFrame:
    return pd.read_csv(file)

# Remove invalid rows
def clean_data(df: pd.DataFrame) -> pd.DataFrame:
    return df.dropna()

# Calculate statistics
def analyze_data(df: pd.DataFrame) -> pd.DataFrame:
    return df.groupby('category').mean()

# Save results to CSV
def export_results(results: pd.DataFrame, output_dir: str) -> None:
    results.to_csv(f'{output_dir}/results.csv')
```

**Section definitions:**

**INFRASTRUCTURE:**
- Imports and constants
- NO functions
- NO logic

**ORCHESTRATOR:**
- ONE function
- Calls only (function composition)
- ZERO functional logic (no calculations, transformations, business rules)
- Meta-logic allowed: conditional workflow execution, parameter routing

**Orchestrator Naming:**
- Name is freely chosen, semantically matching module purpose
- Examples: main(), run_monitor(), find_active_sessions(), format_tool_call()
- Role is defined by placement in ORCHESTRATOR section, not by naming pattern

**Example of allowed meta-logic:**
```python
# ORCHESTRATOR
def process_workflow(input_file: str, output_dir: str, mode: str) -> None:
    raw = load_data(input_file)
    if mode == 'full':
        cleaned = deep_clean(raw)
    else:
        cleaned = quick_clean(raw)
    export_results(analyze_data(cleaned), output_dir)
```

**FUNCTIONS:**
- Ordered by call sequence
- One responsibility each
- Can call other functions internally

**CRITICAL:** All functions must be called by the module's orchestrator (directly or indirectly).
If a function is only used by another module, it belongs in THAT module, not here.

---

## COMMENT RULES

**CRITICAL:** Three types of allowed comments only

### 1. Section Markers
```python
# INFRASTRUCTURE
# ORCHESTRATOR
# FUNCTIONS
```

### 2. Function Header Comments
```python
# Load validated customer data from CSV
def load_customer_data(file_path: str) -> pd.DataFrame:
    return pd.read_csv(file_path)
```

**Rules:**
- One line describing WHAT the function does
- Never HOW it does it
- Placed directly above function definition

### 3. Cross-Module Import Comments
```python
# INFRASTRUCTURE
import pandas as pd

# From data_loader.py: Load and validate CSV
from .data_loader import load_validated_data

# From transformers.py: Apply normalization
from .transformers import normalize_pipeline
```

**Format:** `# From <module>.py: <what it does>`

**For workflow.py (root level):**
```python
# INFRASTRUCTURE
# From src/monitor.py: Run continuous monitoring loop
from src.monitor import run_monitor
```

**Format:** `# From src/<module>.py: <what it does>`

### PROHIBITED: Inline Comments
```python
# INCORRECT - inline comment inside function body
def process_data(df):
    df = df.dropna()  # Remove missing values  <- PROHIBITED
    return df

# CORRECT - no inline comments
def process_data(df):
    df = df.dropna()
    return df
```

---

## LOGGING STANDARDS

**CRITICAL:** This project requires COMPREHENSIVE logging for debugging.

### Fundamental Rules

1. **NO console prints** during normal execution (use logging instead)
2. **src/logs/ folder** - one or more log files per module
3. **Workflow-oriented log files** - Follow LOGS_MAP.md structure (workflow phases 01-09)
4. **Every non-trivial function MUST log** 
5. **Avoid redundant logging of static states or loops.**
6. **Log only actionable events: Status changes, branches, errors, and operation results.**

### LOGS_MAP.md Integration

**CRITICAL:** This project uses structured workflow-oriented logging documented in LOGS_MAP.md.

**When adding new logging:**
1. **Check LOGS_MAP.md** to identify which workflow phase your module belongs to
2. **Use existing log file** if module fits into existing workflow phase (01-09)
3. **If new workflow phase needed:**
   - Add new numbered log file (e.g., 10_new_phase.log)
   - Document in LOGS_MAP.md with: Events, Module, Function, Tag, Color
   - Follow existing event mapping structure
4. **Log with tags** matching LOGS_MAP.md conventions for consistency

**Why this matters:** Structured logging enables systematic debugging and monitoring across the entire workflow.

### What MUST Be Logged

**CRITICAL:**
- Orchestrator entry/exit with parameters and result counts
- State changes (cache ops, data transforms, mode switches)
- Control flow decisions (which branch taken, filter matches)
- Error paths (expected + unexpected with full context)
- Data processing statistics (success/failure counts, ratios)

**IMPORTANT:**
- Function entry/exit for non-trivial operations
- Loop summaries (periodic heartbeats, NOT every iteration)
- Tool call categorization breakdowns
- JSONL parsing results (valid, malformed, orphaned)
- Session discovery (filter applied, matches/misses)

### Setup Patterns

**Single logger (most modules):**
```python
# INFRASTRUCTURE
import logging

logging.basicConfig(
    filename='src/logs/module_name.log',
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
```

**Multiple loggers (distinct concerns):**
```python
# INFRASTRUCTURE
import logging

log_format = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')

logger_concern1 = logging.getLogger('module.concern1')
handler = logging.FileHandler('src/logs/module_concern1.log')
handler.setFormatter(log_format)
logger_concern1.addHandler(handler)
logger_concern1.setLevel(logging.INFO)
```

**See README.md for detailed logging patterns, examples, and debugging guide.**

---

## ERROR HANDLING

**IMPORTANT:** Fail-fast philosophy

### When to use try-catch
**ALLOWED:**
- Retry logic with exponential backoff
- Graceful degradation with explicit logging
- Resource cleanup (files, connections)
- Converting exceptions to domain errors

**PROHIBITED:**
- Silently swallowing errors
- Generic `except Exception: pass`
- Hiding failures that affect business logic

**Example - CORRECT:**
```python
# Retry with logging
def fetch_data(url):
    for attempt in range(3):
        try:
            return requests.get(url)
        except requests.RequestException as e:
            logging.error(f"Attempt {attempt} failed: {e}")
            if attempt == 2:
                raise
```

**Example - INCORRECT:**
```python
# Silent failure - PROHIBITED
def fetch_data(url):
    try:
        return requests.get(url)
    except:
        return None  # Business logic affected, error hidden
```

**Principle:** If the script cannot fulfill its purpose, it must fail visibly.

---

## MAIN WORKFLOW (workflow.py)

**Purpose:** Project-level orchestrator at root level

```python
# INFRASTRUCTURE
# From src/data_loader.py: Load raw data
from src.data_loader import load_raw_data

# From src/processor.py: Clean and transform
from src.processor import process_data_workflow

# From src/exporter.py: Export results
from src.exporter import export_results

# ORCHESTRATOR
def main_workflow(source: str, dest: str) -> None:
    raw = load_raw_data(source)
    processed = process_data_workflow(raw)
    export_results(processed, dest)

if __name__ == "__main__":
    main_workflow("./data/source.csv", "./output/results.csv")
```

**CRITICAL:**
- Filename MUST be `workflow.py` at project root
- Imports from src/ package using absolute imports
- Only INFRASTRUCTURE + ORCHESTRATOR sections
- No FUNCTIONS section needed (if __name__ entrypoint doesn't require it)
- Same 3-section structure principles apply

---

## AUTOMATION SUITE

### Skills (Session-wide)

| Skill | Purpose |
|-------|---------|
| `iterative-dev` | PLAN→IMPLEMENT→RECAP→IMPROVE→CLOSING cycle with beads tracking |
| `agent-dispatch` | Guidelines for effective agent usage (when, how to prompt, verification) |

### Agents (Task-scoped)

| Agent | Model | Purpose |
|-------|-------|---------|
| `code-investigate-specialist` | Haiku | Codebase exploration, file search, pattern finding |
| `compliance-reviewer-global` | Sonnet | CLAUDE.md compliance audits across directories |

### Slash Commands (Single invocation)

| Command | Purpose |
|---------|---------|
| `/debug [observation]` | Systematic debugging: Context→Root Cause→Fix→Documentation |
| `/refactor-ask [path]` | Analyze module complexity, create refactoring plan |

---
