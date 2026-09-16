# 2026-09-16 — dev/hook_smoke/ cohesion split

## Scope note

`dev/hook_smoke/` holds ~29 small scripts (one per hook, mostly `test_block_*.py`
drivers plus a couple of probes). Main's prompt for this milestone explicitly
scoped the work to the single file in the hit list,
`verify_block_non_canonical_edit_corpus.py` (115 LOC, `_write_report` at 50
lines) — confirmed via `grep -rl verify_block_non_canonical_edit_corpus *.py
*.sh` that zero other files in the directory reference it, so nothing else
needed even a full read. The other 28 scripts were left untouched.

## What happened

Split the 115-line file (under the 400-LOC file threshold; only the
50-line-function threshold was hit) into two files along the boundary already
visible in its own layout — corpus loading/hook-decision evaluation vs. report
rendering, the same shape as the two preceding splits in this project:

- `verify_block_non_canonical_edit_corpus.py` (64 LOC) — entry script,
  unchanged filename. Kept the broken `from block_non_canonical_edit import
  _decide` import (line 10) EXACTLY as it was — see Hazard below, this is not
  a bug to fix under this milestone. `_REPORT_PATH` moved out (only used by
  the report renderer now). Kept `_load_corpus_records`, `_testing_cwd`,
  `_evaluate`, and the orchestrator (`verify_workflow`).
- `verify_block_non_canonical_edit_report.py` (87 LOC) — new sibling, full
  shared prefix with the entry script's own name (not a bare noun like
  `report.py` — see the `report.py`-collision lesson from
  `process-docs/hook_error_correlation/`, applied a third time now).
  `_write_report` (50 lines) split into `_count_verdicts`, `_render_header`,
  `_render_block_section`, `_render_error_section`, `_render_allow_section`,
  and a 9-line composing `_write_report`.

## Hazard / why this script cannot be run at all, before or after

`block_non_canonical_edit.py` (the hook this script targets) was retired to
`block_non_canonical_edit.py.disabled` before this milestone. Since
`from block_non_canonical_edit import _decide` needs a `.py`-suffixed,
importable module name, running the entry script — pre-split OR post-split —
fails immediately at that import line:

```
ModuleNotFoundError: No module named 'block_non_canonical_edit'
```

This was already documented in `DOCS.md` before this session (adapting the
import was explicitly judged out of scope for the hook's retirement). The
milestone's own negative scope reinforced this: "keep the broken import
broken." Confirmed the entry script still fails at the exact same line after
the split, by actually running it — same traceback, same line number, same
message.

## Verification — the broken import blocks the obvious approach too

`_write_report` (the only thing actually touched) has zero dependency on
`_decide` — but `importlib.util.spec_from_file_location` on the backup still
executes the WHOLE file's top-level code including the broken import, so
loading the backup at all fails the same way running it does. Worked around
this the same way the milestone anticipated for functions with no clean real
input: injected a stub module into `sys.modules['block_non_canonical_edit']`
(a fake `_decide` that is never called by `_write_report` or any of its
extracted helpers) purely so the backup's unrelated, pre-broken import
resolves during the test harness, then loaded the backup via
`importlib.util.spec_from_file_location` as normal. This does not change
shipped behavior in any way — it only lets the test process get past an
import statement neither the old nor the new `_write_report` ever calls into.

Built one synthetic `results` list (45 `allow` entries — to exercise the
40-entry cap in `_render_allow_section` — one `block` entry with a
multi-line `reason`, one `error` entry, and a mix of string/`None`
`cwd_guess`), called `backup._write_report(results)` vs. the new composed
`_write_report(results)` with `_REPORT_PATH` redirected to two separate
`/tmp` files on each side, and diffed the written files.

Result: **byte-identical, 12543 characters both sides.**

## Pointers

- `report.py`-collision naming lesson now applied three times running
  (`hook_error_correlation` → `analyze_report.py`, `menubar_nspanel` →
  `p1_hotkey.py`, this split → `verify_block_non_canonical_edit_report.py`):
  always share the FULL owning-script prefix with a new dev/ sibling module,
  never a bare noun.
- The `sys.modules` stub-injection trick used here for verification (fake
  out an import the touched function never actually calls) generalizes to any
  future split where the target file's untouched half has a broken or
  environment-dependent top-level import — inject a no-op stub for exactly
  that name before `spec_from_file_location`, and only for names the split
  target genuinely never uses at runtime.
