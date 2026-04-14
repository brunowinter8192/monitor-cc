# src/ Refactoring Plan

Scan date: 2026-04-15. Generated from LOC analysis + cohesion grouping.

---

## LOC Inventory

All `src/*.py` files + subpackage files, sorted by LOC descending.
Reference subpackages (`proxy/`, `proxy_display/`) included for completeness — marked OUT OF SCOPE.

| File | LOC | Current location | Over 200? |
|---|---|---|---|
| src/proxy/addon.py | 446 | proxy/ subpackage | ✅ (out of scope) |
| src/proxy/rules.py | 356 | proxy/ subpackage | ✅ (out of scope) |
| src/proxy_display/pane.py | 241 | proxy_display/ subpackage | ✅ (out of scope) |
| **src/warnings_pane.py** | **243** | **flat** | **✅ REFACTOR TARGET** |
| src/proxy_display/render_entry.py | 233 | proxy_display/ subpackage | ✅ (out of scope) |
| src/metadata_format.py | 199 | flat | — |
| src/token_format.py | 198 | flat | — |
| src/monitor.py | 196 | flat | — |
| src/jsonl_parser.py | 196 | flat | — |
| src/jsonl_extractors.py | 194 | flat | — |
| src/proxy_display/format.py | 196 | proxy_display/ subpackage | — |
| src/monitor_session.py | 180 | flat | — |
| src/tmux_launcher.py | 174 | flat | — |
| src/formatter.py | 174 | flat | — |
| src/proxy_display/render_messages.py | 175 | proxy_display/ subpackage | — |
| src/rules_pane.py | 169 | flat | — |
| src/hooks_format.py | 169 | flat | — |
| src/proxy/tool_injection.py | 167 | proxy/ subpackage | — |
| src/constants.py | 161 | flat | — |
| src/proxy_display/parser.py | 161 | proxy_display/ subpackage | — |
| src/hooks_pane.py | 158 | flat | — |
| src/worker_format.py | 157 | flat | — |
| src/proxy/message_summary.py | 157 | proxy/ subpackage | — |
| src/worker_pane.py | 156 | flat | — |
| src/proxy_display/render_sections.py | 156 | proxy_display/ subpackage | — |
| src/token_pane.py | 155 | flat | — |
| src/subagent_pane.py | 155 | flat | — |
| src/proxy/cache.py | 142 | proxy/ subpackage | — |
| src/proxy/logging.py | 136 | proxy/ subpackage | — |
| src/proxy/content_strip.py | 136 | proxy/ subpackage | — |
| src/proxy_display/render_turn.py | 133 | proxy_display/ subpackage | — |
| src/subagent_ui.py | 127 | flat | — |
| src/click_handler.py | 127 | flat | — |
| src/jsonl_cache_turns.py | 125 | flat | — |
| src/monitor_display.py | 114 | flat | — |
| src/ui_mode.py | 104 | flat | — |
| src/metadata_pane.py | 100 | flat | — |
| src/subagent_ui_format.py | 95 | flat | — |
| src/worker_tmux.py | 94 | flat | — |
| src/session_finder.py | 85 | flat | — |
| src/hooks_persist.py | 79 | flat | — |
| src/subagent_render.py | 77 | flat | — |
| src/formatter_events.py | 72 | flat | — |
| src/hook_parser.py | 62 | flat | — |
| src/startup.py | 48 | flat | — |
| src/proxy_addon.py | 31 | flat | — |
| src/proxy/tools.py | 23 | proxy/ subpackage | — |
| src/utils.py | 17 | flat | — |

**Summary:** 1 flat file over 200 LOC (warnings_pane.py). All subpackage overages are out of scope.

---

## Proposed Subpackages

### src/hooks/

**Rationale:** hook_parser.py, hooks_pane.py, hooks_format.py, and hooks_persist.py form a complete
hook data pipeline: parse the hook log → filter noise → build display items → enrich with persisted
additionalContext files → render in a dedicated pane. Zero unrelated responsibilities. Already mirrors
the proxy/ pattern (parser → format → pane).

**Files to move:**
- `src/hook_parser.py` → `src/hooks/hook_parser.py`
- `src/hooks_pane.py` → `src/hooks/hooks_pane.py`
- `src/hooks_format.py` → `src/hooks/hooks_format.py`
- `src/hooks_persist.py` → `src/hooks/hooks_persist.py`

**`__init__.py` exports:**
```python
from .hooks_pane import run_hooks_loop
from .hook_parser import parse_new_hook_entries, filter_by_project, filter_by_timestamp, get_current_position
```

**New `src/hooks/DOCS.md`** with sections:
- Purpose (hook log pipeline: parse → filter → display)
- Module tree (4 modules with one-liner each)
- Data flow: hook_outputs.jsonl → hook_parser → filter/ts-scope → hooks_format/hooks_persist → hooks_pane TUI

**Cross-module impact:** 2 files outside the group need import updates:
- `monitor.py`: `from .hook_parser import get_current_position` → `from .hooks import get_current_position`
- `rules_pane.py`: `from .hook_parser import parse_new_hook_entries, filter_by_project, filter_by_timestamp` → `from .hooks import parse_new_hook_entries, filter_by_project, filter_by_timestamp`
- `monitor.py` (lazy): `from .hooks_pane import run_hooks_loop` → `from .hooks import run_hooks_loop`

Total: **3 import lines** in 2 external files.

---

### src/workers/

**Rationale:** worker_pane.py (event loop + state), worker_format.py (data extraction + rendering),
and worker_tmux.py (tmux session detection) are exclusively about the workers pane. No external file
imports from any of these three. Clean boundary. Mirrors the proxy/ pattern.

**Files to move:**
- `src/worker_pane.py` → `src/workers/worker_pane.py`
- `src/worker_format.py` → `src/workers/worker_format.py`
- `src/worker_tmux.py` → `src/workers/worker_tmux.py`

**Internal import change** (inside the moved files):
- `worker_format.py`: `from .token_format import _format_k, format_cache_tracker` → `from ..token_format import ...`
  (token_format stays flat — it's a shared utility used by 3 subpackages)
- `worker_tmux.py`: `from .session_finder import encode_project_path` → `from ..session_finder import ...`

**`__init__.py` exports:**
```python
from .worker_pane import run_workers_loop
```

**New `src/workers/DOCS.md`** with sections:
- Purpose (workers pane: tmux session detection, token extraction, TUI display)
- Module tree (3 modules)
- Data flow: tmux sessions → worker_tmux → worker_format → worker_pane TUI loop

**Cross-module impact:** 1 file outside the group:
- `monitor.py` (lazy): `from .worker_pane import run_workers_loop` → `from .workers import run_workers_loop`

Total: **1 import line** in 1 external file.

---

### src/subagents/

**Rationale:** subagent_pane.py (event loop), subagent_render.py (cache-turn rendering),
subagent_ui.py (state + list building), and subagent_ui_format.py (entry formatting helpers) are
exclusively about the subagents pane. The split between 4 files already reflects internal cohesion;
they just need grouping into a subpackage.

**Files to move:**
- `src/subagent_pane.py` → `src/subagents/subagent_pane.py`
- `src/subagent_render.py` → `src/subagents/subagent_render.py`
- `src/subagent_ui.py` → `src/subagents/subagent_ui.py`
- `src/subagent_ui_format.py` → `src/subagents/subagent_ui_format.py`

**Note on ui_mode.py:** `ui_mode.py` stays flat. It has two responsibilities —
`track_subagent_metadata()` (subagent-specific) and `format_rules_block()` (rules-specific). Moving it
into `src/subagents/` would force `rules_pane.py` to import from a pane-sibling package, which is
conceptually wrong. Accepted trade-off.

**Internal import change** (inside the moved files):
- `subagent_render.py`: `from .token_format import ...` → `from ..token_format import ...`
- All cross-module imports to constants, utils, session_finder, jsonl_parser get `..` prefix

**`__init__.py` exports:**
```python
from .subagent_pane import run_subagents_loop
```

**New `src/subagents/DOCS.md`** with sections:
- Purpose (subagents pane: per-agent state, cache tracker, TUI display)
- Module tree (4 modules)
- Data flow: monitor.py state → subagent_ui/subagent_ui_format → subagent_render (cache turns) → subagent_pane TUI

**Cross-module impact:** 2 files outside the group:
- `monitor.py` (lazy): `from .subagent_pane import run_subagents_loop` → `from .subagents import run_subagents_loop`
- `ui_mode.py`: `from .subagent_ui import subagent_states` and `from .subagent_ui_format import ...` → `from .subagents.subagent_ui import ...` / `from .subagents.subagent_ui_format import ...`

Total: **3 import lines** in 2 external files.

---

### src/metadata/

**Rationale:** metadata_pane.py (event loop, 2 modes: main + worker) and metadata_format.py
(rendering with prev-value state tracking) are the complete metadata pane implementation. No other
file imports from either. Clean 2-file subpackage.

**Files to move:**
- `src/metadata_pane.py` → `src/metadata/metadata_pane.py`
- `src/metadata_format.py` → `src/metadata/metadata_format.py`

**Internal import change:**
- `metadata_format.py`: `from .token_format import _format_k` → `from ..token_format import _format_k`

**`__init__.py` exports:**
```python
from .metadata_pane import run_metadata_loop, run_worker_metadata_loop
```

**New `src/metadata/DOCS.md`** with sections:
- Purpose (metadata pane: API config state — model, tokens, thinking, cache markers, per-request diff)
- Module tree (2 modules)
- Data flow: proxy log → metadata_pane reads entries → metadata_format renders diffs

**Cross-module impact:** 1 file outside the group:
- `monitor.py` (lazy): 2 lines `from .metadata_pane import run_metadata_loop` / `run_worker_metadata_loop` → `from .metadata import run_metadata_loop, run_worker_metadata_loop`

Total: **2 import lines** in 1 external file.

---

### src/jsonl/

**Rationale:** jsonl_parser.py (read + parse + extract tool calls), jsonl_extractors.py (extract
user prompts / media / thinking / usage / system messages), and jsonl_cache_turns.py (cache turn
grouping for token/worker/subagent panes) are a self-contained JSONL data pipeline. They have no
display logic and are exclusively data-transformation functions.

**Files to move:**
- `src/jsonl_parser.py` → `src/jsonl/jsonl_parser.py`
- `src/jsonl_extractors.py` → `src/jsonl/jsonl_extractors.py`
- `src/jsonl_cache_turns.py` → `src/jsonl/jsonl_cache_turns.py`

**`__init__.py` exports** (re-export the most-used symbols to minimize importer churn):
```python
from .jsonl_parser import (
    parse_new_tool_calls, parse_jsonl_lines, read_new_lines,
    get_current_position, get_message_content, is_tool_use,
)
from .jsonl_extractors import extract_usage_data
from .jsonl_cache_turns import extract_cache_turns
```

**New `src/jsonl/DOCS.md`** with sections:
- Purpose (JSONL data pipeline: file I/O, line parsing, message extraction, cache turn grouping)
- Module tree (3 modules)
- Data flow: session .jsonl file → read_new_lines → parse_jsonl_lines → extract_* → callers

**Cross-module impact:** highest in the codebase. Files needing import updates:
- `monitor.py`: parse_jsonl_lines, read_new_lines
- `monitor_session.py`: parse_new_tool_calls
- `token_pane.py`: read_new_lines, parse_jsonl_lines, extract_cache_turns
- `subagent_pane.py` (or `subagents/`): read_new_lines, parse_jsonl_lines, extract_cache_turns
- `worker_pane.py` (or `workers/`): read_new_lines, parse_jsonl_lines, extract_cache_turns
- `worker_format.py` (or `workers/`): read_new_lines, parse_jsonl_lines, get_message_content, is_tool_use
- `hooks_persist.py` (or `hooks/`): uses session_finder only, no jsonl imports — unaffected
- `warnings_pane.py` (scan): no jsonl imports — unaffected

Total: **~12 import lines** in 6-7 files (depends on which subpackages have been merged first).

**Risk:** If steps 1-4 are done before this step, the import paths for workers/ and subagents/
already use `..` prefixes — adding jsonl/ is one more level. No circular import risk since
jsonl/ has zero pane/monitor dependencies.

---

## Files Over 200 LOC — Split Proposal

### src/warnings_pane.py (current: 243 LOC)

**Current responsibilities:**
- Module-level state: unknown type counts, tool error list, scroll/hover/expand state, proxy log position
- `track_unknown_type()` — JSONL unknown-type accumulation (called from monitor_session.py)
- `format_warnings_block()` — legacy string formatter (still called? check before removing)
- `load_historical_warnings()` — session init
- `_is_tool_error()` + `_extract_tool_name()` + `_scan_proxy_entries_for_errors()` — proxy error scanning
- `_format_warnings_pane()` — full scroll/hover/expand renderer
- `run_warnings_loop()` — event loop (mouse + keyboard + data refresh)

**Proposed split (stays flat — no subpackage, only 1 logical pane):**
- `warnings_scan.py` — `_is_tool_error`, `_extract_tool_name`, `_scan_proxy_entries_for_errors` — est. **65 LOC**
- `warnings_format.py` — `format_warnings_block`, `format_unknown_type_warning`, `_format_warnings_pane` — est. **85 LOC**
- `warnings_pane.py` — state, `track_unknown_type`, `load_historical_warnings`, `run_warnings_loop` — est. **95 LOC**

**Risk:** Low. All three files stay flat in src/. warnings_pane.py imports from warnings_scan and
warnings_format within the same package. monitor_session.py's import of `track_unknown_type` is
unchanged (still `from .warnings_pane import track_unknown_type`).

**Honest note:** At 243 LOC this is only modestly over the threshold. The structure is clear but
the file is not painfully large. A single worker can do this split in ~1 hour.

---

## Migration Order

Ordered lowest-risk first. Each step is scoped for a single worker session (1-3 hours).

**Step 1 — `src/workers/`**
Scope: Move worker_pane.py, worker_format.py, worker_tmux.py. Update `from ..` prefixes inside moved
files. Update monitor.py (1 lazy import line). Create workers/__init__.py and workers/DOCS.md.
Risk: Minimal — no other file imports from these 3. monitor.py import is lazy.
Unblocks: Nothing. Independent.

**Step 2 — `src/subagents/`**
Scope: Move subagent_pane.py, subagent_render.py, subagent_ui.py, subagent_ui_format.py. Update
`from ..` prefixes inside moved files. Update monitor.py (1 lazy import) + ui_mode.py (2 imports).
Create subagents/__init__.py and subagents/DOCS.md.
Risk: Low — ui_mode.py update is surgical (2 lines). subagent_render imports token_format (flat, clean).
Unblocks: Step 6 (fewer files to update when jsonl/ moves).

**Step 3 — `src/hooks/`**
Scope: Move hook_parser.py, hooks_pane.py, hooks_format.py, hooks_persist.py. Update monitor.py (3
import lines) + rules_pane.py (1 import line). Create hooks/__init__.py and hooks/DOCS.md.
Risk: Low — rules_pane.py dependency on hook_parser is a single import line. hooks_persist.py
imports from hooks_format (internal after move, no change needed outside).
Unblocks: Step 6 (fewer files to update when jsonl/ moves).

**Step 4 — `src/metadata/`**
Scope: Move metadata_pane.py, metadata_format.py. Update monitor.py (2 lazy import lines). Update
metadata_format.py `from ..token_format` prefix. Create metadata/__init__.py and metadata/DOCS.md.
Risk: Minimal — only 2 files, 1 external importer (monitor.py lazy imports).
Unblocks: Nothing. Independent.

**Step 5 — `warnings_pane.py` split**
Scope: Extract warnings_scan.py and warnings_format.py from warnings_pane.py. No new subpackage.
warnings_pane.py drops from 243 → ~95 LOC. All 3 files stay flat in src/.
Risk: Low — no external import changes. monitor_session.py's `track_unknown_type` stays in
warnings_pane.py.
Unblocks: Nothing. Can be done in parallel with Steps 1-4.

**Step 6 — `src/jsonl/`**
Scope: Move jsonl_parser.py, jsonl_extractors.py, jsonl_cache_turns.py. Update imports in monitor.py,
monitor_session.py, token_pane.py, and whichever subpackages have been merged (workers/, subagents/,
hooks/). Create jsonl/__init__.py and jsonl/DOCS.md.
Risk: Medium — most widely imported group (~12 import lines across 6-7 files). No circular import risk.
Prerequisite: Steps 1-3 should be done first so worker, subagent, hooks imports update to `..jsonl`
paths in one pass rather than being updated twice.
Unblocks: None (this is the final structural step).

---

## Out of Scope

- `src/proxy/` — reference subpackage, do not touch.
- `src/proxy_display/` — reference subpackage, do not touch.
- `src/proxy/addon.py` (446 LOC) and `src/proxy/rules.py` (356 LOC) — both significantly over 200 LOC.
  The proxy package has its own architectural constraints (mitmproxy live-copy pattern, hot-reload
  sensitivity). Splitting addon.py or rules.py would require proxy-package-level design decisions
  and is not in scope for this structural refactoring pass.
- `src/monitor.py`, `src/monitor_session.py`, `src/monitor_display.py` — the core orchestration trio.
  All three are under 200 LOC and tightly coupled to every other module via `from . import monitor as
  _monitor` back-references. Grouping into a `core/` subpackage is theoretically possible but would
  create deep circular import risks. Benefit does not justify risk.
- `src/formatter.py`, `src/formatter_events.py`, `src/monitor_display.py` — these 3 form a "main pane
  formatter" cluster. All under 200 LOC. formatter.py is imported by worker_format.py (outside the
  cluster), which makes the boundary fuzzy. Not recommended as a subpackage.
- `src/token_pane.py` + `src/token_format.py` — token_format.py is imported by 3 other modules
  (worker_format, subagent_render, metadata_format). Moving it into a tokens/ subpackage would force
  cross-package imports in all 3. Keeping it flat as a shared formatter is the right call.
  token_pane.py alone does not make a 2-file subpackage.
- `src/rules_pane.py`, `src/ui_mode.py`, `src/click_handler.py`, `src/constants.py`, `src/utils.py`,
  `src/startup.py`, `src/session_finder.py`, `src/tmux_launcher.py` — all single-purpose infrastructure
  or shared utilities. Under 200 LOC. No grouping needed.
