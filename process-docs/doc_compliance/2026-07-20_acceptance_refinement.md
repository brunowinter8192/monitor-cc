# Doc-Compliance Sweep — decisions/ Acceptance Refinement (2026-07-20)

An iterative-dev-doccheck pass brought the monitor-cc doc surface into compliance with the Documentation Hierarchy standard (the structural `decisions/` → `process-docs/` rename with 65 thematic areas was already committed earlier; this pass finished the content + reference cleanup).

## The refined acceptance
The original goal was a literal `git grep -n 'decisions/'` returning zero repo-wide. As of 2026-07-20 this was refined: **zero on ACTIVE surfaces, deliberate retention on captured records / data.**

- **Active surfaces → 0** (fixed this pass): all `process-docs/**`, every `DOCS.md`, `src/` code comments, and `scripts/docs_drift_whitelist.txt`. These are maintained artifacts; a stale `decisions/` path there is a real defect.
- **Retained (12 occurrences, intentionally NOT edited):** editing them would falsify forensic records or break regression baselines — the same write-once principle that protects process-docs.
  - 9 dev-report `.md` under `dev/tool_use_analysis/md/` + `dev/sleep_pattern_analysis/md/`: `decisions/` appears there as captured content — a logged `bd comments add` command, a captured tool-call JSON payload, a git error message. These are forensic snapshots of past runs.
  - 2 regression baselines `dev/display/json/baseline_*.json` + `dev/jsonl/json/baseline_*.json`: `decisions/` sits inside captured rendered-pane snapshots (the baseline literally quotes a user turn "alle decisions/-Edits über Worker…"). Editing breaks the baseline comparison AND falsifies what the pane rendered.
  - 1 synthetic test fixture `dev/proxy_dual_log/proxy_176_bg_launch_ack_tests.py`: the string `decisions/strip_bg_launch_ack.md` is a fake RAG-result fixture; the referenced file never existed.

## Consequence for future audits
A future `git grep 'decisions/'` returning ~12 hits is EXPECTED, not incomplete work — all remaining hits are captured records / baseline data / a synthetic fixture. Verify newness against this set before "fixing"; do not edit captured forensic records or regression baselines to chase a literal zero.

## Reference-resolution notes from the same pass
- Moved `dev/menubar_debug.py` → `dev/menubar_nspanel/menubar_debug.py`; `src/menubar/DOCS.md` refs updated accordingly.
- `dev/watchdog_scope/` Phase-A proposals migrated into `process-docs/watchdog_idle_detection/` (they are the design-proposal stage of the same watchdog idle-detection feature whose settled design lives in that area).
- `dev/tool_use_analysis/CONVENTION.md` folded into that area's `DOCS.md`; `dev/ToolsSystemPrompts/` given a `DOCS.md` (it is a captured tool-definition reference corpus, kept intact rather than split).
