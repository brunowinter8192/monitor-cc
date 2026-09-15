# 2026-09-16 — Cohesion refactor of dev/desktop_detection/

## Task

Split the 6 numbered probe scripts in `dev/desktop_detection/` so every module is under 400 LOC
and every function is under 50 lines, without changing behavior. Full context and constraints are
in the milestone prompt; this entry records what a successor needs that isn't visible from the
code alone.

## Result

All 6 entry scripts (`01_probe.py` .. `06_move_sweep_probe.py`) kept their exact filenames and
CLI. Each was split into unprefixed `probeNN_*.py` sibling modules living in the same directory
(no leading digit — not a valid module name), imported by bare name (this directory already
relies on the script directory being on `sys.path[0]`, not on `src.`-style absolute imports — a
project hook blocks `from src.` under `dev/`). 26 new sibling files + the 6 rewritten entry files
= 32 `.py` files total, none at or over 400 LOC, longest function 42 lines
(`probe05_trial.py::_measure_signals`). No cross-script deduplication was done — 01/04/05/06 each
have their own near-identical `probeNN_bridge.py` even though the ctypes/objc plumbing is
line-for-line similar across scripts, per explicit negative-scope instruction.

## Safety classification (self-verified, not taken on faith)

Confirmed by reading every call site, not by trusting the prior classification handed to me:
- `02`, `03` — read-only (only `CGWindowListCopyWindowInfo`, `CGSCopySpacesForWindows`, read-only
  AppleScript property/bounds/position queries, TCC.db read, `codesign`, `ps`).
- `01` — mutates: `_osc2_inject_match` writes an OSC-2 escape sequence to a live CC session's
  `/dev/tty*`, changing that window's title (then restores it).
- `04` — mutates: `_bridged_move` calls `SLSBridgedMoveWindowsToManagedSpaceOperation` for real.
- `05` — mutates: opens/closes tmux sessions, Ghostty windows, CotEditor docs.
- `06` — mutates: opens/closes a CotEditor doc and attempts 4 real Space-move primitives.

## Verification approach that actually worked

The mandated method was: byte-identical backup of each original loaded via
`importlib.util.spec_from_file_location`, then call pre-split vs. post-split functions with
identical inputs and assert equal outputs. In practice this environment has no `pyobjc` installed
(`from Foundation import NSBundle` fails), but `02`/`03` only need it for one field inside
`_collect_context_diagnostics` (`NSBundle.mainBundle().bundleIdentifier()`) — everything else is
raw `ctypes` calls into `libobjc.A.dylib`, which work with no pyobjc at all. Stubbing
`sys.modules["Foundation"]` with a `SimpleNamespace` before importing let both the backup and the
split modules import cleanly and be compared directly; the stub is identical on both sides of the
comparison so it cannot mask a real difference (Main confirmed this reasoning before green-lighting
the approach).

Executing full scripts for real was only done for `02` and `03` (read-only). `01`, `04`, `05`, `06`
were never executed as whole scripts — but most of their *internal* functions are pure queries
(`_build_space_map`, `_spaces_for_wid`, `_on_screen_wids`, `_method_a`/`_method_b`, `_wid_info`,
`_wid_exists`, `_owner_pids`, `_owner_wids_layer0`, `_check_permissions`, `_find_nonempty_nonactive_space`,
even `_take_screenshot` — a screenshot mutates nothing) and were called live against the real
desktop, comparing backup vs. split output directly. This caught real bugs before commit, e.g. an
import that pulled `_make_uint_array` from the wrong sibling module in `probe06_workflow.py`.

Only the genuinely mutating leaf functions (`_bridged_move`, `_open_window`, `_close_window_for_type`,
`_open_coteditor_doc`, `_close_coteditor_doc`, `_detect_coteditor_doc`, `_ensure_coteditor_running`,
`_run_primitive_trial`, `_take_screenshot`'s caller) were never called; they were verified by
`ast.get_source_segment` diff against the backup (proving the function body moved byte-for-byte
unchanged) plus literal-string-set and call-occurrence-count comparisons between the original
`probe_workflow` body and the new split (proving nothing was dropped, duplicated, or reordered).

**Concrete gotcha hit during this**: for `04_space_move_probe.py`, the dev machine actually
satisfies the probe's move preconditions right now (5 Mission Control spaces, 13 off-screen named
Ghostty windows) — calling the *real* `probe_workflow` or even a naive `_check_preconditions`
replica would have proceeded into `_bridged_move` and moved a real window. The fix: factor the
precondition check into its own function (`_check_preconditions`) that only ever queries and
returns `None`/a state dict — never calls the move — and verify *that* function alone against a
hand-written replica of the original's inline precondition logic. Same pattern was reused for
`06`'s `_validate_preconditions`. Anyone touching `04` or `06` again should keep this boundary:
the precondition-check function must stay side-effect-free so it stays safely callable for
verification.

## Design decisions for a successor

- **`_REPORTS_DIR` is redefined per-module, not passed as a parameter or imported across files.**
  Each module that writes to `NN_reports/` defines its own `_REPORTS_DIR = Path(__file__).parent /
  "NN_reports"`, matching the original because all these files live in the same directory — this
  avoided changing any function signature and kept diff-equivalence trivial to prove.
- **Shared per-script constants (e.g. `05`'s `_WIN_TMUX`/`_OWNER`/`_REQUIRE_NAME`/`_TOKEN_PREFIX`)
  went into the first/foundational sibling module** (`probe05_detection.py`) rather than a new
  file, since a numbered entry script can't be imported by its siblings (leading digit) and a
  dedicated constants-only file felt like cosmetic fragmentation for 3 dict literals.
- **`02` and `03` each got their own `probeNN_diagnostics.py`** with identical-looking
  `_collect_context_diagnostics`/`_collect_tcc_state` bodies — this looks like exactly the
  cross-script duplication the milestone forbids deduplicating, and that's correct: the milestone
  explicitly says do not deduplicate across scripts, only within one script's split.
- **`06_move_sweep_probe.py`'s `_setup`/`_try_sym` were deliberately placed in
  `probe06_primitives.py`, not `probe06_bridge.py`**, even though they look like "bridge setup" —
  they operate on symbols resolved dynamically at runtime for the 4 move primitives, which is a
  distinct concern from the static CDLL/argtypes setup that every other script's bridge module
  holds. `probe06_bridge.py` holds only the CG/OBJ/SkyLight/ApplicationServices CDLL loads and
  their static `argtypes`/`restype`, matching the pattern in `01`/`02`/`03`/`04`/`05`.

## What I did not touch

Left `02_bundle_stub.app/`, `03_bundle_stub.app/`, `json/`, `png/`, `txt/` untouched — out of
scope. Left the pre-existing DOCS.md/code mismatch alone (DOCS.md said `02`/`03` write to
`json/<tag>_<timestamp>.json`; the code actually writes to `02_reports/`/`03_reports/` — this
mismatch predates this refactor and fixing it was not part of the milestone, so the new DOCS.md
still describes the actual `NN_reports/` behavior without commentary on the old text it replaced).
