# CLAUDE.MD - Master Engineering Reference

## CRITICAL STANDARDS

- NO comments inside function bodies (only function header comments + section markers)
- NO test files in root (ONLY in src/debug/ folder)
- NO src/debug/ or src/logs/ folders in version control (MUST be in .gitignore)
- NO emojis in production code, READMEs, DOCS.md, logs
- Emojis ALLOWED in: chat, debug scripts (src/debug/ folder), subagent reports, bug-fix docs
- NO verbose console output (use logging instead)

**Type hints:** RECOMMENDED but optional

**Fail-Fast:** Let exceptions fly. No try-catch that silently swallows errors affecting business logic. Script must fail if it cannot fulfill its purpose.

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
│   ├── debug/           # CRITICAL: ALL tests and debug scripts
│   │   ├── test_feature1.py
│   │   ├── test_feature2.py
│   │   └── debug_helper.py
│   └── logs/            # CRITICAL: Workflow-oriented log files
│       ├── 01_startup.log
│       ├── 02_initialization.log
│       ├── 03_session_discovery.log
│       ├── 04_file_reading.log
│       ├── 05_jsonl_parsing.log
│       ├── 06_tool_extraction.log
│       ├── 07_display_routing.log
│       ├── 08_ui_rendering.log
│       └── 09_click_handling.log
└── bug_fixes/           # CRITICAL: Bug-fix documentation (timestamped)
    └── issue_name_YYYYMMDD_HHMMSS_.md
```

**Workflow-oriented approach:**
- workflow.py stays at root as entry point, imports from src/ package
- All modules reside in src/ folder with relative imports
- New additions: Extend existing module OR create new module if step is substantial
- Utilities and helpers: Part of the module where they're used

### Level 2: MODULE
Self-contained step: Fixed Input → Processing → Fixed Output.
Not strict pipelines (loops/branches/spirals OK) but clear contracts.

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

### README.md (Workflow Entry Point Documentation)
**Purpose:** Quick orientation for executing a workflow

**Placement Rules:**
- **1:1 relationship:** Exactly one README.md per workflow.py
- **Location:** Always at root level of the workflow (same directory as workflow.py)
- **When to create:** Only when the workflow is designed to run independently without any dependencies from other parts of the project

**Example structures:**

```
# Simple project (one workflow)
project/
├── README.md
├── workflow.py
├── CLAUDE.md
└── src/
    ├── __init__.py
    ├── DOCS.md
    └── modules...
```

**Sections:**
1. Workflow Name + One-liner
2. Basic Usage (how to execute this workflow)
3. Link to src/DOCS.md for module documentation

**Keep it short:** 100-200 lines maximum

---

### DOCS.md (Module Documentation)
**Purpose:** Complete architectural documentation of modules

Documents **ALL project files** except documentation markdown files (README.md, DOCS.md, CLAUDE.md).

**Files to document:**
- Python modules (.py)
- Configuration files (.yml, .json, .toml)
- Docker files (docker-compose.yml, Dockerfile)
- Any other functional files

**NOT documented:**
- README.md (entry point documentation)
- DOCS.md (self)
- CLAUDE.md (engineering standards)
- .gitignore (trivial)

**Placement Rules:**
- **Location:** Always in src/ folder alongside the modules it documents
- **Not tied to README:** README.md stays at root, DOCS.md stays in src/
- **Multiple allowed:** One DOCS.md per src/ folder containing modules

**File naming as headings:**
- Each file gets ## header with exact filename
- Use relative path if in subdirectory: `## config/settings.yml`
- NO generic sections like "Configuration" or "Error Handling"

**Example:**

```
project/
├── README.md           # Workflow entry (root)
├── workflow.py         # Entry point (root)
├── CLAUDE.md           # Standards (root)
└── src/
    ├── __init__.py
    ├── DOCS.md         # Documents module_a.py, module_b.py
    ├── module_a.py
    ├── module_b.py
    └── processors/
        ├── DOCS.md     # Documents processor modules
        ├── clean.py
        └── transform.py
```

**Mirrors 3-level architecture: PROJECT → MODULES → FUNCTIONS**

**Structure:**

```markdown
# Section/Project Name
One-liner description

## Project Structure
<Complete tree with entry points marked>

## module_one.py
**Purpose:** WHY it exists (1-2 sentences)
**Input:** What it receives
**Output:** What it produces

### function_name()
Prose text description of WHAT it does. Explains inputs/outputs,
responsibility, and side effects in flowing text.

### next_function()
Prose text description of WHAT it does.

## module_two.py
...

## docker-compose.yml
**Purpose:** Container configuration for service dependencies.

Defines service with port mappings and volume mounts. Sets environment variables and restart policy.

## config/settings.yml
**Purpose:** Application configuration.

Configures runtime settings. Enables specific features. Sets default values for parameters.
```

**CRITICAL Rules:**
1. Every file gets ## header with exact filename (including path if nested)
2. Python modules: functions get ### headers
3. Config files: prose description of purpose and settings
4. Prose text only (no bullet lists for function/config descriptions)
5. Order by logical grouping (Python first, then configs)
6. Describe WHAT not HOW (purpose, not implementation)
7. No code snippets in architecture sections (only in README.md usage examples)

**Function Description Pattern:**
- Start with verb phrase describing action
- Explain inputs/outputs in prose
- Describe responsibility and side effects
- Example: "Polls the log file continuously in a loop. Initializes file position at EOF and maintains a request cache. Reads new lines, parses each line, formats output, and prints to stdout."

**Function header comments vs DOCS.md:**
- Header comment: 1 line describing WHAT (in code)
- DOCS.md entry: Detailed prose text (in documentation)
- No duplication - different levels of detail

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

**CRITICAL:** This project requires COMPREHENSIVE logging for agent-based debugging.

**Why:** Agents debug EXCLUSIVELY through logs (no monitor/debugger available). Every function that can produce meaningful logs MUST do so.

### Fundamental Rules

1. **NO console prints** during normal execution (use logging instead)
2. **src/logs/ folder** - one or more log files per module
3. **Workflow-oriented log files** - Follow LOGS_MAP.md structure (workflow phases 01-09)
4. **ALL logs on INFO level** (agents need to see everything - no DEBUG)
5. **Every non-trivial function MUST log** entry/exit with parameters and results
6. **Log: state changes, control flow decisions, error paths, cache operations, statistics**

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

## EDGE CASES & FLEXIBILITY

### Utilities and Helpers
Utilities belong to the module where they're used:
```python
# FUNCTIONS

# Main processing function
def process_data(df):
    normalized = _normalize_values(df)
    return _apply_transformations(normalized)

# Normalize column values to 0-1 range
def _normalize_values(df):
    return (df - df.min()) / (df.max() - df.min())

# Apply business transformations
def _apply_transformations(df):
    return df * 100
```

Use underscore prefix for internal helpers (RECOMMENDED).

### When to Create New Module
Create new module when:
- Step is conceptually distinct
- Would benefit from isolated testing
- Has clear input/output contract
- File would exceed ~300-400 lines

Extend existing module when:
- Functionality is tightly coupled
- Shares same conceptual domain
- Would create artificial separation

---

## COMPLIANCE

Use `code-compliance-reviewer` subagent to validate adherence to this standard.

**EXCEPTION:** Scripts in the `src/debug/` folder are exempt from CLAUDE.md compliance requirements. Debug and test scripts serve temporary testing purposes and do not need to follow these standards.

---
