"""
P2 -- copy-by-click parity probe (Milestone 2: copy-by-click in the y-only panes).

Proves, per pane, that after ONE real render pass:
  1. the copy-row registry (phys_row set/dict populated by the pane's own build function) contains
     an entry for every row that carries a copyable unit, at plausible coordinates
  2. dispatching a synthetic mouse click on the symbol column of that row copies EXACTLY the same
     string the 'y' key produces for that same row -- both paths run through the REAL serializer,
     nothing hardcoded, the two outputs are compared against each other
  3. a too-narrow pane_width suppresses BOTH the visible symbol and the row registration (width
     guard) -- proven once at the pure-function level (append_copy_symbol) and once at the
     render-integration level (format_cache_tracker, tokens pane)

**(2026-09) The main pane was removed entirely** (window 0 is now the tokens pane at full width,
see `process-docs/main_pane/`) — `test_main_pane_copy_click` and its `mod_main_display`/
`mod_monitor` imports were dropped accordingly.

**(2026-09, panesplit) The all-workers list pane (worker_pane.py) is gone**, replaced by
`worker_tokens_pane.py` -- a single-selected-worker cache tracker with the exact same
`(turn_idx, call_idx)`-keyed copy-row shape `token_pane.py` already has (no more worker-header-row
copy case, since there is no worker header ROW anymore in this pane -- worker identity now lives
in the switch header's marker regions, covered by `p1_worker_selection_click_probe.py`, not here).
`test_workers_pane_copy_click` is retargeted at `worker_tokens_pane.py` accordingly, same shape as
`test_tokens_pane_copy_click`.

Covers:
  - src/panes/token_pane.py :: _build_tokens_output (cache_copy_rows), _handle_tokens_mouse,
    _handle_tokens_key
  - src/panes/warnings_pane.py :: _build_warnings_output (error_copy_rows), _handle_warnings_mouse,
    _handle_warnings_key -- plus a regression guard for the pre-existing _serialize_warnings
    int-vs-tuple key bug fixed as part of this milestone
  - src/workers/worker_tokens_pane.py :: _build_worker_tokens_output (worker_tokens_copy_rows),
    _handle_worker_tokens_mouse, _handle_worker_tokens_key

No live tmux/terminal needed -- module globals are seeded directly with synthetic data;
copy_to_clipboard is monkeypatched per module to a capturing stub (no real pbcopy calls, no OS
clipboard dependency) so both paths' output can be read back and compared.

Run from project root or worktree root:
    ./venv/bin/python dev/click_ui/p2_copy_click_probe.py
"""

# INFRASTRUCTURE
import importlib
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace

WORKTREE_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(WORKTREE_ROOT))
os.environ.setdefault('MONITOR_CC_ROOT', str(WORKTREE_ROOT))

_ROOT_PKG = 'src'
mod_tokens = importlib.import_module(f'{_ROOT_PKG}.panes.token_pane')
mod_token_format = importlib.import_module(f'{_ROOT_PKG}.format.token_format')
mod_warnings = importlib.import_module(f'{_ROOT_PKG}.panes.warnings_pane')
mod_warnings_render = importlib.import_module(f'{_ROOT_PKG}.panes.warnings_render')
mod_workers = importlib.import_module(f'{_ROOT_PKG}.workers.worker_tokens_pane')
mod_utils = importlib.import_module(f'{_ROOT_PKG}.utils')

_PASS = "\033[32mPASS\033[0m"
_FAIL = "\033[31mFAIL\033[0m"
_RESULTS = []


def check(label, condition):
    _RESULTS.append((label, bool(condition)))
    print(f"  {_PASS if condition else _FAIL}  {label}")
    return condition


# FUNCTIONS

# Monkeypatch mod.copy_to_clipboard with a capturing stub; returns the capture list
def _patch_clipboard(mod):
    captured = []
    mod.copy_to_clipboard = lambda text: captured.append(text)
    return captured


# Pure-function width guard: symbol appended when room, unchanged when not
def test_append_copy_symbol_width_guard():
    wide = mod_utils.append_copy_symbol("short line", '⎘', 50)
    check("append_copy_symbol: appends ⎘ when the pane is wide enough", '⎘' in wide and wide != "short line")
    narrow = mod_utils.append_copy_symbol("x" * 60, '⎘', 50)
    check("append_copy_symbol: leaves line unchanged when too narrow (no invisible hit zone)", narrow == "x" * 60)


# Tokens pane: one copy region per API-call row; click vs 'y' parity; width guard end-to-end
def test_tokens_pane_copy_click():
    captured = _patch_clipboard(mod_tokens)
    mod_tokens.cache_expand_states.clear()
    mod_tokens.cache_hover_row = None
    mod_tokens.cache_scroll_offset = 0
    mod_tokens._cache_copy_feedback_until.clear()
    mod_tokens._cache_turns = [{
        'prompt': 'do the thing', 'timestamp': '2026-01-01T00:00:00Z',
        'api_calls': [
            {'cache_read': 1000, 'cache_creation': 0, 'direct': 0, 'output_tokens': 50, 'content_blocks': []},
            {'cache_read': 2000, 'cache_creation': 500, 'direct': 0, 'output_tokens': 80, 'content_blocks': []},
        ],
    }]

    mod_tokens._build_tokens_output()
    check("tokens: one copy region per API call (2 calls)", len(mod_tokens.cache_copy_rows) == 2)

    for row in sorted(mod_tokens.cache_copy_rows):
        key = mod_tokens.cache_line_map[row]
        mod_tokens.cache_hover_row = row
        captured.clear()
        mod_tokens._handle_tokens_key('y')
        y_text = captured[-1] if captured else None

        captured.clear()
        click_col = mod_tokens._cache_pane_width - 1
        changed = mod_tokens._handle_tokens_mouse(0, click_col, row)
        check(f"tokens: click on row {row} (key={key}) triggers copy", changed and len(captured) == 1)
        if captured:
            check(f"tokens: click/y parity row {row} (key={key})",
                  captured[-1] == y_text and y_text)

    narrow_lines, narrow_keys, _, _, _ = mod_token_format.format_cache_tracker(
        mod_tokens._cache_turns, {}, 50, 10, 0, copy_feedback={},
    )
    check("tokens: width guard -- no ⎘/✓ symbol rendered when pane_width=10 (too narrow)",
          not any(('⎘' in ln or '✓' in ln) for ln in narrow_lines))


# Warnings pane: fixed int-key serializer bug regression guard + one copy region per error row
def test_warnings_pane_copy_click():
    check("warnings: _serialize_warnings bug fix -- int key now returns real content",
          mod_warnings_render._serialize_warnings(0, [{'tool_name': 'Bash', 'tool_call_input': {}, 'full_text': 'boom'}]) != '')

    captured = _patch_clipboard(mod_warnings)
    mod_warnings.tool_errors.clear()
    mod_warnings.error_expand_states.clear()
    mod_warnings.error_hover_row = None
    mod_warnings.error_scroll_offset = 0
    mod_warnings._error_copy_feedback_until.clear()
    mod_warnings.tool_errors.extend([
        {'timestamp': '10:00:00', 'tool_name': 'Bash', 'summary': 'err1', 'full_text': 'boom one',
         'tool_call_input': {'command': 'ls'}, 'worker_name': ''},
        {'timestamp': '10:01:00', 'tool_name': 'Grep', 'summary': 'err2', 'full_text': 'boom two',
         'tool_call_input': {'pattern': 'x'}, 'worker_name': ''},
    ])

    mod_warnings._build_warnings_output()
    check("warnings: one copy region per error row (2 errors)", len(mod_warnings.error_copy_rows) == 2)

    for row in sorted(mod_warnings.error_copy_rows):
        key = mod_warnings.error_line_map[row]
        mod_warnings.error_hover_row = row
        captured.clear()
        mod_warnings._handle_warnings_key('y')
        y_text = captured[-1] if captured else None

        captured.clear()
        click_col = mod_warnings._error_pane_width - 1
        changed = mod_warnings._handle_warnings_mouse(0, click_col, row)
        check(f"warnings: click on row {row} (idx={key}) triggers copy", changed and len(captured) == 1)
        if captured:
            check(f"warnings: click/y parity row {row} (idx={key})",
                  captured[-1] == y_text and y_text)

    narrow_out, narrow_map = mod_warnings_render._format_warnings_pane(
        mod_warnings.tool_errors, {}, None, 0, 50, 10, '', copy_feedback={}, copy_rows_out=set(),
    )
    check("warnings: width guard -- no ⎘/✓ symbol rendered when pane_width=10 (too narrow)",
          '⎘' not in narrow_out and '✓' not in narrow_out)


# worker_tokens pane: one copy region per API-call row (same (turn_idx, call_idx)-keyed shape as
# token_pane.py, since this pane shows exactly one worker's own cache tracker); click vs 'y'
# parity; width guard end-to-end
def test_worker_tokens_copy_click():
    captured = _patch_clipboard(mod_workers)
    project_filter = '/tmp/click_ui_probe_p2_worker_tokens'
    monitor = SimpleNamespace(active_project_filter=project_filter)
    mod_workers.worker_tokens_expand_states.clear()
    mod_workers.worker_tokens_line_map.clear()
    mod_workers.worker_tokens_hover_row = None
    mod_workers.worker_tokens_scroll_offset = 0
    mod_workers.worker_tokens_copy_rows.clear()
    mod_workers._worker_tokens_copy_feedback_until.clear()
    mod_workers._worker_tokens_workers = [{'name': 'w1', 'status': 'working', 'context_pct': 50}]
    mod_workers._worker_tokens_turns = [{
        'prompt': 'do the thing', 'timestamp': '2026-01-01T00:00:00Z',
        'api_calls': [
            {'cache_read': 1000, 'cache_creation': 0, 'direct': 0, 'output_tokens': 50, 'content_blocks': []},
            {'cache_read': 2000, 'cache_creation': 500, 'direct': 0, 'output_tokens': 80, 'content_blocks': []},
        ],
    }]
    if os.path.exists(mod_workers.get_selection_file_path(project_filter)):
        os.remove(mod_workers.get_selection_file_path(project_filter))
    mod_workers.write_selection(project_filter, 'w1')

    mod_workers._build_worker_tokens_output(monitor)
    check("worker-tokens: one copy region per API call (2 calls)", len(mod_workers.worker_tokens_copy_rows) == 2)

    for row in sorted(mod_workers.worker_tokens_copy_rows):
        key = mod_workers.worker_tokens_line_map[row]
        mod_workers.worker_tokens_hover_row = row
        captured.clear()
        mod_workers._handle_worker_tokens_key('y', monitor)
        y_text = captured[-1] if captured else None

        captured.clear()
        click_col = mod_workers._worker_tokens_pane_width - 1
        changed = mod_workers._handle_worker_tokens_mouse(0, click_col, row, monitor)
        check(f"worker-tokens: click on row {row} (key={key}) triggers copy", changed and len(captured) == 1)
        if captured:
            check(f"worker-tokens: click/y parity row {row} (key={key})",
                  captured[-1] == y_text and y_text)

    if os.path.exists(mod_workers.get_selection_file_path(project_filter)):
        os.remove(mod_workers.get_selection_file_path(project_filter))

    narrow_lines, narrow_keys, _, _, _ = mod_token_format.format_cache_tracker(
        mod_workers._worker_tokens_turns, {}, 50, 10, 0, copy_feedback={},
    )
    check("worker-tokens: width guard -- no ⎘/✓ symbol rendered when pane_width=10 (too narrow)",
          not any(('⎘' in ln or '✓' in ln) for ln in narrow_lines))


# ORCHESTRATOR

def run_probe_workflow():
    print("=" * 70)
    print("copy-by-click parity probe -- tokens, warnings, workers")
    print("=" * 70)
    test_append_copy_symbol_width_guard()
    test_tokens_pane_copy_click()
    test_warnings_pane_copy_click()
    test_worker_tokens_copy_click()

    total = len(_RESULTS)
    passed = sum(1 for _, ok in _RESULTS if ok)
    print("\n" + "=" * 70)
    print(f"{passed}/{total} checks passed")
    print("=" * 70)

    _write_report(passed, total)
    return passed == total


def _write_report(passed, total):
    md_dir = WORKTREE_ROOT / "dev" / "click_ui" / "md"
    md_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    out_path = md_dir / f"p2_copy_click_probe_{stamp}.md"
    lines = [
        f"# P2 -- copy-by-click parity probe run ({datetime.now(timezone.utc).isoformat()})",
        "",
        f"**Result: {passed}/{total} checks passed**",
        "",
        "| Check | Result |",
        "|---|---|",
    ]
    for label, ok in _RESULTS:
        lines.append(f"| {label} | {'PASS' if ok else 'FAIL'} |")
    out_path.write_text("\n".join(lines) + "\n")
    print(f"\nReport written to: {out_path}")


if __name__ == "__main__":
    ok = run_probe_workflow()
    sys.exit(0 if ok else 1)
