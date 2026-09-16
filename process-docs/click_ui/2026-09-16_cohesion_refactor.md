# 2026-09-16 — Cohesion refactor of dev/click_ui/

## Task

`dev/click_ui/` had one file-size and three function-length violations against the project code
standard. Measured before this session:

```
539 p5_proxy_message_copy_click_probe.py [_run_block_click_suite 62, _run_pane_click_suite 52, _run_thinking_click_suite 50]
266 p3_button_click_probe.py             [test_proxy_pane_permanent_search_bar_header 88]
```

`p1_worker_selection_click_probe.py`, `p2_copy_click_probe.py`, `p4_gpu_news_button_probe.py`
were read in full (they may import the split targets — none of them do; each `pN_` script in
this directory is fully independent) and needed no changes.

Goal: every module under 400 LOC, every function under 50 lines, behavior unchanged, no
comments/docstrings added beyond what already existed.

## Hazard classification (read carefully before touching this area again)

Every script in `dev/click_ui/` calls pane logic (`_handle_*_mouse`, `_build_*_output`,
`_render_pane`) as **plain in-process Python function calls** with synthetic row/column
integers — none of them send a real OS-level mouse or key event (no Quartz `CGEvent`, no
`pyautogui`, no AppleScript `tell application "System Events"`, no tmux `send-keys`). All five
scripts are **read-only with respect to the real macOS desktop**:

- `p1_worker_selection_click_probe.py` — writes only to throwaway `/tmp/monitor_cc_selected_worker_<hash>.txt` IPC files, removed after each check.
- `p2_copy_click_probe.py` — `copy_to_clipboard` monkeypatched to a capturing stub; no real `pbcopy`.
- `p3_button_click_probe.py` — same clipboard monkeypatch; no real refresh/subprocess call (the warnings `[refresh]` button only flips an in-memory flag).
- `p4_gpu_news_button_probe.py` — `subprocess.Popen` monkeypatched to a capturing stub; no real `rag-cli`/news-pipeline process launched, confirmed by reading the monkeypatch before running anything.
- `p5_proxy_message_copy_click_probe.py` — same clipboard monkeypatch pattern; calls `format_proxy_block`/`_handle_*_mouse` directly, `os.get_terminal_size` never reached on this path (confirmed by reading `src/proxy_display/pane.py`/`proxy_pane_shared.py` before running — see the terminal-size gotcha below, which is about a DIFFERENT, unrelated function in `p3`, not about p5's mutation risk).

I ran all four scripts I verified against (`p3`, `p5`, plus the read comprehension of `p1`/`p2`/`p4`) with this classification confirmed first, per the milestone's hazard instruction.

## What changed

- **`p3_button_click_probe.py`** (266 -> 286 LOC, single file, no split needed):
  `test_proxy_pane_permanent_search_bar_header` (88 lines) split along the boundaries the
  function's own inline comments already marked (`# Click on row 1 focuses...`, `# Expand/collapse
  click still works...`, `# Copy-symbol click still fires...`, `# 'u' key...`, `# Scroll wheel...`,
  `# Auto-scroll-to-just-expanded...`): `_reset_and_render_proxy_pane`,
  `_check_proxy_header_shift_contract`, `_check_proxy_focus_and_expand_clicks`,
  `_check_proxy_copy_click`, `_check_proxy_undo_and_scroll`, `_check_proxy_auto_scroll_after_expand`,
  called in sequence from the now-6-line original function.
- **`p5_proxy_message_copy_click_probe.py`** (539 -> 158 LOC entry + 4 new sibling modules): split
  by the three copy-granularity milestones the module's own docstring already numbers (P5.1-5.5
  message rows, P5.6-5.10 thinking rows, P5.11-5.15 generic block rows) plus one shared-fixture
  module:
  - `proxy_copy_probe_shared.py` (60 LOC, no orchestrator) — `mod_proxy`/`mod_worker_proxy`/
    `mod_format`/`mod_shared` handles, `check()`/`_RESULTS`, `_patch_clipboard`, `_make_entry`,
    `_render_expanded`.
  - `proxy_copy_message_probe.py` (118 LOC) — P5.1-5.5. `_run_pane_click_suite` (was 52 lines)
    split into `_setup_pane_click_fixture` (fixture wiring: which module attrs, which handler
    lambda, resetting all of them) + `_run_pane_click_suite` (just the click assertions).
  - `proxy_copy_thinking_probe.py` (131 LOC) — P5.6-5.10, same shape:
    `_setup_thinking_click_fixture` + `_run_thinking_click_suite` (was 50 lines).
  - `proxy_copy_block_probe.py` (132 LOC) — P5.11-5.15, same shape: `_setup_block_click_fixture` +
    `_run_block_click_suite` (was 62 lines).
  - `p5_proxy_message_copy_click_probe.py` (158 LOC) — kept its exact filename and its full
    milestone docstring (the docstring IS the spec for all three sibling modules — did not
    duplicate it into them); now just imports the 15 test functions from the three sibling
    modules plus `_RESULTS` from the shared module, and orchestrates + writes the report exactly
    as before.

  The three `_setup_*_click_fixture` helpers are near-identical (same ~19-line block: resolve
  `entries_attr`/`line_map_attr`/`copy_rows_attr`/`feedback_attr`/`expand_states_attr`/
  `pane_width_attr_name`/`handler` by `pane_name`, then reset all of them). I deliberately did
  NOT collapse these three into one shared helper in `proxy_copy_probe_shared.py`, even though
  the milestone's own instructions allow real concern extraction — the negative-scope clause says
  "do not deduplicate across scripts," and after the split these three call sites live in three
  separate files; collapsing them would be exactly that kind of cross-file dedup, done under
  cover of a split. Keeping one private copy per file costs ~19 duplicate lines per file and
  buys unambiguous compliance with the negative scope. If a future milestone asks for the
  dedup explicitly, it's a 3-line import change in each of the three probe modules.

## Verification method (per file)

- **`p3_button_click_probe.py`**: full-script before/after diffing hit a real (pre-existing, not
  introduced by me) environment wall — `test_warnings_refresh_button` (a function I did NOT
  touch, and which runs BEFORE my changed function in `run_probe_workflow`'s call order) calls
  `os.get_terminal_size()`, which raises `OSError: [Errno 25] Inappropriate ioctl for device` in
  this sandboxed shell (no real tty). That's not fixable by `COLUMNS`/`LINES` env vars —
  `os.get_terminal_size()` (unlike `shutil.get_terminal_size()`) does the ioctl unconditionally
  and ignores those env vars. Wrapping the run in `script -q <logfile> <cmd>` (BSD `script`,
  available on macOS, allocates a real pty) gets past that OSError but the allocated pty reports
  `0x0`, so a later, different assertion (`next(iter(regions.items()))`) fails with
  `StopIteration` instead — still before ever reaching my changed function, since it's earlier in
  call order. Given the full-script path was structurally blocked by an unrelated, pre-existing
  test running first, I fell back to the milestone's explicitly-sanctioned alternate method:
  loaded the pre-split backup via `importlib.util.spec_from_file_location`, called
  `test_proxy_pane_permanent_search_bar_header()` directly on both the pre-split and post-split
  module (bypassing `test_warnings_refresh_button` entirely — this function has no dependency on
  it), and compared the resulting `_RESULTS` lists element-for-element. `MATCH: True`, 14/14
  checks identical on both sides (including one pre-existing FAIL — `at least one copy row
  registered` — caused by the same 0x0-pty width starving `_proxy_copy_rows`; present and
  identical on both sides, so it's an environment limitation, not a regression).
- **`p5_proxy_message_copy_click_probe.py`**: no terminal dependency at all on this file's path
  (confirmed by reading `src/proxy_display/pane.py`/`format.py` before running — `format_proxy_block`
  is called directly, matching the module's own docstring claim "os.get_terminal_size is never
  invoked on that path"). Ran the pre-split backup (copied into the real `dev/click_ui/`
  directory under a throwaway name — copying straight to `/tmp` breaks
  `WORKTREE_ROOT = Path(__file__).resolve().parents[2]`, the same gotcha hit and documented in
  the two prior cohesion-refactor sessions, see `process-docs/timer-loop/` and
  `process-docs/model_selector/`) and the post-split entry script back to back. Diffed stdout and
  the generated `md/*.md` report with the `# P5 ... (<timestamp>)` header line stripped from the
  md diff (stdout has no timestamp so it was diffed unstripped) — both byte-identical, both exit
  0, both 91/91 checks passed (visually confirmed the count before diffing).

## Gotchas / things I'd tell my replacement

- `os.get_terminal_size()` fails in this sandboxed Bash tool (no real tty) — this blocks
  full-script execution for ANY `dev/` script that calls it on its main path (`p3`'s
  `test_warnings_refresh_button` via `mod_warnings._build_warnings_output`; `p5` is fine, it
  never calls it). `script -q <logfile> <cmd>` gets a pty allocated but its reported size is
  `0x0`, which just moves the failure to whatever assertion depends on nonzero pane width next —
  it does NOT give you a working "real terminal" substitute. If you need genuinely working
  terminal-size-dependent output from this sandbox, you don't have a way to get it; fall back to
  the per-function importlib-backed comparison method instead of insisting on a full-script run.
- Same `REPO_ROOT`/`WORKTREE_ROOT` depth gotcha as the last two cohesion-refactor sessions
  (`dev/timer-loop/`, `dev/model_selector/`): a pre-split backup copied to `/tmp` breaks
  `Path(__file__).resolve().parents[2]`. Copy it into the real directory under a throwaway name
  instead, delete it before committing.
- All the `pN_click_probe.py` scripts in this directory follow the exact same shape: a
  `_PASS`/`_FAIL`/`_RESULTS`/`check()` harness, a `run_probe_workflow()` orchestrator, a
  `_write_report()` that stamps a timestamped `.md` file under `md/`. If you split another one of
  these later, the concern boundaries are almost always already spelled out in the module's own
  docstring (numbered milestones/parts) or in the test function's own inline `# --comment--`
  markers before each assertion block — I did not have to invent boundaries in either file this
  session, I just followed what the code already said about itself.
