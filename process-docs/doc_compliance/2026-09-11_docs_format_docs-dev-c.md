# DOCS.md format cut — docs-dev-c

This file is the process-docs record for the DOCS.md format compliance task covering
`dev/dual_log_cli/`, `dev/proxy_forensics/`, `dev/grid_probe/`, `dev/proxy_analysis/`,
`dev/bead_tracker/`, `dev/menubar_per_project/`, and `dev/coteditor/` — seven `dev/` areas that had
no DOCS.md before this task. All seven files were new, so no salvage of prior prose applied; this
file holds the recap only.

## 2026-09-11 — recap

Created all seven DOCS.md files from a full read of every `.py` file in scope (20 modules, 4,467
LOC total) plus the relevant `src/dual_log_cli/`, `src/menubar/system.py`, and `src/tmux_launcher.py`
modules for caller verification, and sibling `dev/*/DOCS.md` files (`dev/click_ui/DOCS.md`,
`dev/jsonl/DOCS.md`, `dev/hook_error_correlation/DOCS.md`, `dev/hook_smoke/DOCS.md`) for style
precedent.

**Two DEAD CODE / staleness findings surfaced during the read, both confirmed by grep across the
whole tree, not by commit history:**

- `dev/bead_tracker/smoke.py` hardcodes a hook path under `src/menubar/` that does not exist
  anywhere in the tree (`find . -iname "*bead_tracker*"` returns only `dev/bead_tracker/` and its
  own `process-docs/` area — no `src/` file of that name). Documented as DEAD CODE in
  `dev/bead_tracker/DOCS.md`.
- `dev/proxy_analysis/01_session_summary.py` reads a flat `api_requests_<id>.jsonl` schema
  (top-level `total_input_chars`, `diff_from_prev`, `message_count`, `cache_breakpoints` keys) that
  no current `src/` writer produces — `src/proxy/addon_dual_log.py` writes the six-stream split
  under `src/logs/dual_log/` instead. The script imports no `src` module, so it does not meet the
  letter of the DEAD-CODE-by-import-smoke test; kept `Called by: none — run manually` and recorded
  the schema mismatch as a Gotcha instead, per Main's confirmed verdict.

**Process note:** on the first pass I wrote a salvage section into this file before Main sent "Go",
misreading the generic salvage-method instruction against the task's explicit override ("There is
nothing to salvage, so your process-docs file holds only your recap section (create it at recap
time, not before)"). Caught it before implementing and deleted the file; no process-docs file
existed until this recap.

**Post-review fix:** review flagged that `dev/bead_tracker/DOCS.md` named the missing hook path in
backticked form (`` `src/menubar/bead_tracker_hook.py` `` ), which `docs-drift-check` flags as a
broken path reference even though the whole point of that line is that the path is gone. Reworded
to plain words ("the bead_tracker_hook script under src/menubar") so the finding disappears from
`docs-drift-check` while the DEAD CODE claim itself is unchanged. Verified: `docs-drift-check`'s
Path-Drift count dropped from 21 to 20 findings repo-wide, with the `bead_tracker` line gone from
its output; the remaining 20 findings are all pre-existing `src/logs`/`src/logs/dual_log`
references (gitignored runtime directory, absent in a fresh worktree checkout) matching the same
accepted pattern already present in `dev/DOCS.md`, `src/DOCS.md`, and `src/dual_log_cli/DOCS.md` —
none of them in this task's scope to fix, and Main confirmed the `src/logs` mentions are fine (the
directory exists in the main checkout).

LOC-Drift and Symbol-Drift: 0 findings, both before and after the fix.
