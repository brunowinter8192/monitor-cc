# Pipeline Evaluation Suite

Dev scripts measuring Monitor_CC pipeline characteristics. Each suite measures one aspect and writes MD reports.

## Working Directory

**CRITICAL:** All commands assume CWD = `Monitor_CC/` (project root)

## Suites

### memory_profile/
**Measures:** tool_use_cache and buffered_subagent_calls growth.
**Usage:** `python3 dev/pipeline/memory_profile/01_cache_growth.py`
**Decision:** process-docs/pipeline/pipe02_data_sources.md, process-docs/pipeline/pipe03_core_loop.md

### io_profile/
**Measures:** Filesystem calls per poll cycle (stat, iterdir, glob).
**Usage:** `python3 dev/pipeline/io_profile/01_poll_cycle_cost.py`
**Decision:** process-docs/pipeline/pipe02_data_sources.md

### parsing_profile/
**Measures:** Time per extract function, multi-pass overhead.
**Usage:** `python3 dev/pipeline/parsing_profile/01_multipass_cost.py`
**Decision:** process-docs/pipeline/pipe02_data_sources.md

### format_stability/
**Measures:** Message type coverage across all JSONL files.
**Usage:** `python3 dev/pipeline/format_stability/01_unknown_types.py`
**Decision:** process-docs/pipeline/pipe02_data_sources.md
