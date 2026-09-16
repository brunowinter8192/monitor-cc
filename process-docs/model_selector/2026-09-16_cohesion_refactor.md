# 2026-09-16 — Cohesion refactor of dev/model_selector/

## Task

`dev/model_selector/` had function-length violations against the project code standard (no file
was near the 400 LOC threshold here — the largest, `verify_model_cycle_and_io.py`, was 309 LOC).
Measured before this session:

```
309 verify_model_cycle_and_io.py [_verify_proxy_rules_read_modify_write 56]
143 verify_three_tab_ring.py     [verify_three_tab_ring_workflow 52]
 82 verify_hook17_removal.py     [verify_hook17_removal_workflow 59]
```

`verify_hook_writer_split.py` (76 LOC) and `verify_launcher_model_precedence.sh` (bash, 200 LOC,
not in scope — the INFRASTRUCTURE/ORCHESTRATOR/FUNCTIONS split is a Python convention) were read
in full but needed no changes.

Goal: every function under 50 lines, behavior unchanged, no comments/docstrings added beyond
what already existed. No file split was needed anywhere in this directory — every offending
function fit under 50 lines via in-file extraction along boundaries the files already marked
with their own numbered/headed sections (`## 1.` .. `## 9.`, `1.` .. `4.`, `## Forward` / `##
Reverse`). This made concern-boundary selection close to mechanical — the split points were
already documented in the code as comments/report headers before I touched anything.

## Hazard classification (all four scripts, one deliberately never run)

- `verify_hook_writer_split.py` — read-only (untouched, not in hit list).
- `verify_model_cycle_and_io.py` — read-only. Pure logic + tempdir JSON fixtures, never touches
  the real `~/.claude/shared-rules/model_selection.json` or `proxy_rules.json`. Ran it.
- `verify_hook17_removal.py` — read-only. Synthetic in-memory dict; never invokes the guarded
  `hook_setup_workflow()` (which refuses to run from a worktree anyway); never touches the real
  `~/.claude/settings.json`. Ran it.
- `verify_three_tab_ring.py` — **MUTATING, not run, in either version.** It builds real
  `PanelManager`/`RagController`/`ModelController` instances (`src/menubar/panel_manager.py`
  etc.), which construct real `NSPanel` objects via `_make_nspanel()`. Its workflow then calls
  the real `_open_main_panel`/`_open_rag_panel`/`_open_models_panel` from
  `src/menubar/panel_lifecycle.py`, which call `panel.orderFrontRegardless()` — genuine AppKit
  that shows a real window on the live screen. This is true regardless of the split; I traced it
  down to `panel_lifecycle.py` before running anything, on my own initiative, because the
  milestone's hazard note said this area was "very likely" to drive the desktop and I wanted a
  concrete mechanism, not a guess. Confirmed with Main before implementing and did not run it at
  all this session, old or new version.

## What changed

- **`verify_model_cycle_and_io.py`** (309 -> 317 LOC): `_verify_proxy_rules_read_modify_write`
  (56 lines) split into three functions along its own section's already-documented structure —
  the function's comments already said "foreign sections... missing entry... touched entries":
  - `_write_proxy_rules_and_check_full_match(ms, lines, tmp)` — writes the fixture, calls
    `_write_proxy_rules_model_params`, asserts the full-file byte-exact match, returns
    `(path, written)`.
  - `_check_proxy_rules_preserved_sections(written, lines)` — foreign top-level section + the two
    untouched model entries.
  - `_check_proxy_rules_touched_and_created(written, lines)` — the touched main entry + the newly
    created worker entry.
  - The original function is now an 8-line caller of these three plus the leftover-`.tmp`-file
    check (which stayed inline since it needs `path` from the first helper and is 3 lines).
- **`verify_hook17_removal.py`** (82 -> 91 LOC): `verify_hook17_removal_workflow` (59 lines) split
  along its own numbered checks (the numbers `1.`/`2.`/`3.`/`4.` were already print lines in the
  original): `_check_file_deleted`, `_check_no_longer_registered`, `_check_sweep_stale_hooks`
  (the big one, ~24 lines), `_append_registration_trace` (pure prose `lines.append` calls, no
  logic — check 4 was always just documentation of a mechanism it doesn't invoke).
- **`verify_three_tab_ring.py`** (143 -> 149 LOC): `verify_three_tab_ring_workflow` (52 lines)
  split into `_verify_forward_ring(app, panel_lifecycle, lines)` and
  `_verify_reverse_ring(app, panel_lifecycle, lines)`, called in sequence inside the same
  `with patch(...)` block (ring state carries from forward's end — back on main — into reverse's
  start). The `## Forward` / `## Reverse` markdown headers in the report were already the exact
  split points.

## Verification method (per file)

- **`verify_model_cycle_and_io.py`, `verify_hook17_removal.py`** (read-only): copied the
  pre-split backup into the real `dev/model_selector/` directory under a throwaway name (NOT
  `/tmp` directly — `REPO_ROOT = Path(__file__).resolve().parents[2]` depends on the file living
  at the correct relative depth; copying straight to `/tmp` resolves `REPO_ROOT` to garbage and
  the import fails with `ModuleNotFoundError: No module named 'src'` — hit this exact failure
  once this session, on the first attempt, before moving the backup into the real directory).
  Ran the pre-split throwaway copy and the post-split file back to back, diffed both the printed
  stdout and the generated `md/*.md` report with the `# ... — <timestamp>` header line stripped.
  Both byte-identical for both scripts. Deleted the throwaway copies and restored the two
  tracked `md/*.md` report files via `git checkout --` before committing (they're tracked data,
  not verification artifacts — don't `rm` them, `git checkout --` them back to the committed
  version after a verification run overwrites them).
- **`verify_three_tab_ring.py`** (mutating, not run): no execution-based proof was possible or
  attempted. Instead, `diff`ed the pre-split backup against the post-split file directly — the
  diff shows only (a) the two-line `with` block now calling `_verify_forward_ring`/
  `_verify_reverse_ring` instead of inlining their bodies, and (b) the two extracted functions
  appearing later in the file with one less level of indentation and their original bodies
  otherwise byte-for-byte unchanged, in the same order. No statement was added, removed, or
  reordered.

## Gotchas / things I'd tell my replacement

- Same sibling-import style as `dev/timer-loop/`: these scripts use
  `importlib.import_module('src.menubar.model_selection')` /
  `importlib.import_module('src.hooks.hook_setup')` (dynamic, package-relative) rather than a
  literal `from src....` — that's what lets them run despite the `block_dev_imports_src.py`
  hook, and it's required anyway because `model_selection.py` has package-relative imports that
  only resolve inside the real `src.menubar` package.
- If you ever need to backup-and-diff a script in this directory (or `dev/timer-loop/`, same
  pattern), copy the backup into the real directory at the real relative depth, not to `/tmp`.
  Every script here computes `REPO_ROOT = Path(__file__).resolve().parents[2]` from its own file
  location — moving the file breaks that math silently in confusing ways (it resolves to
  whatever unrelated directory happens to sit two levels up from wherever you put it, not an
  immediate crash necessarily — my first hook17 attempt resolved into a stale, unrelated
  `worktrees/model-selector/` checkout that still happened to exist on disk and produced a
  *plausible-looking but wrong* diff before it crashed on the `sys.path.insert` not covering the
  real repo).
- `verify_three_tab_ring.py` is a real hazard, not a theoretical one — read
  `src/menubar/panel_lifecycle.py` yourself before ever running this script for any other reason
  (e.g. actually testing a `panel_lifecycle.py` change). `orderFrontRegardless()` is called
  unconditionally by `_open_main_panel`/`_open_rag_panel`/`_open_models_panel`; there is no
  headless/dry-run flag.

## Result

```
      91 verify_hook17_removal.py
     317 verify_model_cycle_and_io.py
     149 verify_three_tab_ring.py
      76 verify_hook_writer_split.py
```

All under 400 LOC (none were close to begin with). Longest function directory-wide after the
split: `_verify_model_selection_readback` in `verify_model_cycle_and_io.py` at 33 lines (already
under 50 before this session — the cap only bound `_verify_proxy_rules_read_modify_write`,
`verify_hook17_removal_workflow`, and `verify_three_tab_ring_workflow`, all now split).
