# CLAUDE.MD - Master Engineering Reference

## CRITICAL STANDARDS

- NO comments inside function bodies (only function header comments + section markers)
- NO src/debug/ or src/logs/ folders in version control (MUST be in .gitignore)
- NO emojis in production code, READMEs, DOCS.md, logs
- NO verbose console output (use logging instead)

**Type hints:** REQUIRED for orchestrators (clear contracts), RECOMMENDED for functions

**Fail-Fast:** Let exceptions fly. No try-catch that silently swallows errors affecting business logic. Script must fail if it cannot fulfill its purpose.

**Keyboard-First:** UI-Steuerung immer per Tastatur, nicht per Maus. Mausinteraktionen nur fuer Textauswahl/Kopieren. Grund: Terminals haben inkonsistentes Mouse-Handling (SGR mode conflicts, scroll issues).

---

## CODE ORGANIZATION

**CRITICAL:** Every script follows this structure:

**INFRASTRUCTURE -> ORCHESTRATOR -> FUNCTIONS**

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

### Section Definitions

**INFRASTRUCTURE:**
- Imports and constants
- NO functions
- NO logic

**ORCHESTRATOR:**
- ONE function
- Calls only (function composition)
- ZERO functional logic (no calculations, transformations, business rules)
- Meta-logic allowed: conditional workflow execution, parameter routing

**FUNCTIONS:**
- Ordered by call sequence
- One responsibility each
- Can call other functions internally

**CRITICAL:** All functions must be called by the module's orchestrator (directly or indirectly).
If a function is only used by another module, it belongs in THAT module, not here.

### Orchestrator Naming

- Name is freely chosen, semantically matching module purpose
- Examples: main(), run_monitor(), find_active_sessions(), format_tool_call()
- Role is defined by placement in ORCHESTRATOR section, not by naming pattern

### workflow.py (Project Entry Point)

```python
# INFRASTRUCTURE
# From src/monitor.py: Run continuous monitoring loop
from src.monitor import run_monitor

# From src/session_finder.py: Find active sessions
from src.session_finder import find_active_sessions

# ORCHESTRATOR
def main(project_filter: str, mode: str) -> None:
    sessions = find_active_sessions(project_filter)
    run_monitor(sessions, mode)

if __name__ == "__main__":
    main(args.project, args.mode)
```

**Rules:**
- Filename MUST be `workflow.py` at project root
- Imports from src/ package using absolute imports
- Only INFRASTRUCTURE + ORCHESTRATOR sections
- No FUNCTIONS section needed

### Inter-Module Dependencies

When module A needs functionality from module B:
- Module A imports specific functions from module B using relative imports
- Module A's orchestrator calls imported functions

**Example (within src/ package):**
```python
# In src/monitor.py
# INFRASTRUCTURE
from .formatter import format_tool_call  # From other module

# ORCHESTRATOR
def run_monitor(sessions, mode):
    for call in parse_sessions(sessions):
        output = format_tool_call(call)  # Cross-module call
        display(output)
```

### Module Complexity Thresholds

A new module is warranted when ANY of these thresholds are exceeded:

1. **Lines of Code:** > 400 LOC with distinct functional groups
2. **Function Count:** > 15 functions (likely multiple responsibilities)
3. **Single Responsibility:** Module handles multiple unrelated concerns

**Additional Indicators:**
- Function > 50 LOC -> Extract helper functions (not new module)
- > 5 cross-module imports -> Review dependencies, may indicate over-coupling

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
```

**Format:** `# From <module>.py: <what it does>`

**For workflow.py (root level):**
```python
# From src/monitor.py: Run continuous monitoring loop
from src.monitor import run_monitor
```

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

### What MUST Be Logged

**CRITICAL:**
- Orchestrator entry/exit with parameters and result counts
- State changes (cache ops, data transforms, mode switches)
- Control flow decisions (which branch taken, filter matches)
- Error paths (expected + unexpected with full context)
- Data processing statistics (success/failure counts, ratios)

### Setup Pattern

```python
# INFRASTRUCTURE
import logging

logging.basicConfig(
    filename='src/logs/module_name.log',
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
```

### LOGS_MAP.md Integration

**When adding new logging:**
1. **Check LOGS_MAP.md** to identify which workflow phase your module belongs to
2. **Use existing log file** if module fits into existing workflow phase (01-09)
3. **If new workflow phase needed:** Add new numbered log file and document in LOGS_MAP.md

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
def fetch_data(url):
    for attempt in range(3):
        try:
            return requests.get(url)
        except requests.RequestException as e:
            logging.error(f"Attempt {attempt} failed: {e}")
            if attempt == 2:
                raise
```

**Principle:** If the script cannot fulfill its purpose, it must fail visibly.

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

### README.md (Workflow-Level)

**Purpose:** High-level overview linking to DOCS.md for details

**Required Sections:**
1. Title + Description
2. Directory Structure (tree with `[See DOCS.md]` links)
3. Workflow (per phase: Purpose, Input, Output, Details link)

### DOCS.md (Directory-Level)

**Purpose:** Detailed documentation of all modules within one directory

**Required Sections:**
1. Working Directory (CRITICAL - all commands assume CWD = this directory)
2. Directory Structure (tree showing modules)
3. Module Documentation (Purpose, Inputs, Outputs, Usage, Variables)

**Inputs vs Variables:**

| Type | Without it | Example |
|------|------------|---------|
| Input | workflow FAILS | `project_filter`, `mode` |
| Variable | workflow uses defaults | `POLL_INTERVAL` |

---

## AUTOMATION SUITE

### Skills (Session-wide)

| Skill | Purpose |
|-------|---------|
| `iterative-dev` | PLAN->IMPLEMENT->RECAP->IMPROVE->CLOSING cycle with beads tracking |
| `agent-dispatch` | Guidelines for effective agent usage (when, how to prompt, verification) |

### Agents (Task-scoped)

| Agent | Model | Purpose |
|-------|-------|---------|
| `code-investigate-specialist` | Haiku | Codebase exploration, file search, pattern finding |
| `compliance-reviewer-global` | Sonnet | CLAUDE.md compliance audits across directories |

### Slash Commands (Single invocation)

| Command | Purpose |
|---------|---------|
| `/debug [observation]` | Systematic debugging: Context->Root Cause->Fix->Documentation |
| `/refactor-ask [path]` | Analyze module complexity, create refactoring plan |
