# INFRASTRUCTURE
import importlib
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

WORKTREE_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(WORKTREE_ROOT))
os.environ.setdefault('MONITOR_CC_ROOT', str(WORKTREE_ROOT))

_ROOT_PKG = 'src'
mod_warnings = importlib.import_module(f'{_ROOT_PKG}.panes.warnings_pane')
mod_warnings_render = importlib.import_module(f'{_ROOT_PKG}.panes.warnings_render')
mod_proxy = importlib.import_module(f'{_ROOT_PKG}.proxy_display.pane')
mod_proxy_format = importlib.import_module(f'{_ROOT_PKG}.proxy_display.format')

_PASS = "\033[32mPASS\033[0m"
_FAIL = "\033[31mFAIL\033[0m"
_RESULTS = []


def check(label, condition):
    _RESULTS.append((label, bool(condition)))
    print(f"  {_PASS if condition else _FAIL}  {label}")
    return condition


# FUNCTIONS

def _make_proxy_entry(idx, model='claude-sonnet', msg_count=3, bp=2):
    return {
        'model': model, 'message_count': msg_count, 'cache_breakpoints': [{}] * bp,
        'system_total_chars': 10000 if bp > 0 else 0, 'tools_total_chars': 5000 if bp > 0 else 0,
        'messages_total_chars': 3000, 'tools_count': 10 if bp > 0 else 0, 'tools_hash': f'hash{idx}',
        'tools_names': [f'tool_{j}' for j in range(10)] if bp > 0 else [], 'tools_defs': [],
        'system_blocks': [{'idx': 0, 'chars': 10000, 'preview': 'sys content'}] if bp > 0 else [],
        'messages': [{'role': 'user', 'type': 'text', 'chars': 500, 'blocks': []} for _ in range(msg_count)],
        'schema_warnings': [], 'stripped_msg_indices': [], 'modifications': [], '_stripped_spans': {'system': {}, 'tools': {}, 'messages': {}, 'fields': {}}, '_injected_spans': {'system': {}, 'tools': {}, 'messages': {}, 'fields': {}},
        'timestamp': f'2026-04-21T10:0{idx}:00Z',
    }


def test_warnings_refresh_button():
    mod_warnings.tool_errors.clear()
    mod_warnings.error_expand_states.clear()
    mod_warnings.error_hover_row = None
    mod_warnings.error_scroll_offset = 0
    mod_warnings._force_refresh = False
    mod_warnings._last_refresh_ts = 1234567890.0

    output, header = mod_warnings._build_warnings_output()
    regions = dict(mod_warnings._warnings_header_regions)
    check("warnings: [refresh] button region registered", regions.get((sorted(regions)[0])) == 'refresh' if regions else False)
    check("warnings: exactly one header region, on row 2 (shifted past the new search bar)",
          len(regions) == 1 and next(iter(regions))[2] == 1 + mod_warnings._WARNINGS_SEARCH_BAR_LINES)
    check("warnings: button text visible in header", '[refresh]' in header)

    (sc, ec, er), _ = next(iter(regions.items()))
    click_col = (sc + ec) // 2

    mod_warnings._force_refresh = False
    key_changed = mod_warnings._handle_warnings_key('r')
    key_refresh = mod_warnings._force_refresh

    mod_warnings._force_refresh = False
    click_changed = mod_warnings._handle_warnings_mouse(0, click_col, er)
    click_refresh = mod_warnings._force_refresh

    check("warnings: 'r' key sets _force_refresh", key_changed and key_refresh)
    check("warnings: click on [refresh] sets _force_refresh (same as key)", click_changed and click_refresh)

    narrow_regions = {}
    narrow_header = mod_warnings_render._format_warnings_header(1234567890.0, 10, narrow_regions)
    check("warnings: width guard -- no region and no button text when pane_width=10",
          len(narrow_regions) == 0 and '[refresh]' not in narrow_header)


def test_proxy_pane_permanent_search_bar_header():
    output = _reset_and_render_proxy_pane()
    key_row2 = _check_proxy_header_shift_contract(output)
    _check_proxy_focus_and_expand_clicks(key_row2)
    _check_proxy_copy_click()
    _check_proxy_undo_and_scroll(key_row2)
    _check_proxy_auto_scroll_after_expand()


def _reset_and_render_proxy_pane():
    mod_proxy.proxy_entries.clear()
    mod_proxy._proxy_session_start_ts = '2000-01-01T00:00:00Z'
    mod_proxy.proxy_expand_states.clear()
    mod_proxy.proxy_line_map.clear()
    mod_proxy.proxy_hover_row = None
    mod_proxy.proxy_scroll_offset = 0
    mod_proxy._proxy_undo_stack.clear()
    mod_proxy._copy_feedback_until.clear()
    mod_proxy._proxy_search.query = ''
    mod_proxy._proxy_search.focused = False
    mod_proxy._proxy_search.matches = []
    mod_proxy._proxy_search.match_set = set()
    mod_proxy.proxy_entries.extend(_make_proxy_entry(i) for i in range(3))
    return mod_proxy._build_proxy_output()


def _check_proxy_header_shift_contract(output):
    check("proxy: _build_proxy_output returns a plain string (header+'\\n'+body baked in)",
          isinstance(output, str))
    check("proxy: search bar text visible on the first line", output.splitlines()[0].find('search:') != -1)
    check("proxy: no leftover _proxy_header_regions module attribute (that was the reverted-button's)",
          not hasattr(mod_proxy, '_proxy_header_regions'))
    check("proxy: no leftover _format_proxy_header function in format.py (that was the reverted-button's)",
          not hasattr(mod_proxy_format, '_format_proxy_header'))

    check("proxy: row 1 is NOT a body key (it's the search bar)", mod_proxy.proxy_line_map.get(1) is None)
    key_row2 = mod_proxy.proxy_line_map.get(2)
    check("proxy: row 2 resolves to a body row (REQ key)",
          key_row2 is not None and ((isinstance(key_row2, tuple) and key_row2[0] == 'req') or isinstance(key_row2, int)))
    return key_row2


def _check_proxy_focus_and_expand_clicks(key_row2):
    mod_proxy._proxy_search.focused = False
    focus_click_changed = mod_proxy._handle_proxy_mouse(0, 5, 1)
    check("proxy: click on row 1 focuses the search bar",
          focus_click_changed and mod_proxy._proxy_search.focused is True)
    mod_proxy._proxy_search.focused = False

    pre_expand = mod_proxy.proxy_expand_states.get(key_row2, False)
    row_click_changed = mod_proxy._handle_proxy_mouse(0, 5, 2)
    check("proxy: click on row 2 toggles expand/collapse at the shifted row",
          row_click_changed and mod_proxy.proxy_expand_states.get(key_row2) != pre_expand)
    mod_proxy._build_proxy_output()


def _check_proxy_copy_click():
    orig_copy = mod_proxy.copy_to_clipboard
    captured = []
    mod_proxy.copy_to_clipboard = lambda text: captured.append(text)
    try:
        check("proxy: at least one copy row registered", bool(mod_proxy._proxy_copy_rows))
        if mod_proxy._proxy_copy_rows:
            copy_row = next(iter(mod_proxy._proxy_copy_rows))
            check("proxy: copy row is >= 2 (never lands on the header row)", copy_row >= 2)
            copy_click_changed = mod_proxy._handle_proxy_mouse(0, mod_proxy._proxy_pane_width - 1, copy_row)
            check("proxy: copy-symbol click still fires at its own shifted row",
                  copy_click_changed and len(captured) == 1)
    finally:
        mod_proxy.copy_to_clipboard = orig_copy


def _check_proxy_undo_and_scroll(key_row2):
    mod_proxy.proxy_expand_states.clear()
    mod_proxy._proxy_undo_stack.clear()
    mod_proxy.proxy_expand_states[key_row2] = True
    mod_proxy._proxy_undo_stack.append((key_row2, False))
    key_changed = mod_proxy._undo_proxy_expand()
    check("proxy: 'u' key (_undo_proxy_expand) still undoes the last toggle, unchanged",
          key_changed and mod_proxy.proxy_expand_states.get(key_row2) is False and not mod_proxy._proxy_undo_stack)

    mod_proxy.proxy_scroll_offset = 0
    scroll_changed = mod_proxy._handle_proxy_mouse(64, 5, 2)
    check("proxy: scroll wheel (button 64) still works",
          scroll_changed and mod_proxy.proxy_scroll_offset == 3)


def _check_proxy_auto_scroll_after_expand():
    mod_proxy.proxy_scroll_offset = 0
    mod_proxy.proxy_expand_states.clear()
    mod_proxy._build_proxy_output()
    target_row = next(iter(mod_proxy.proxy_line_map))
    target_key = mod_proxy.proxy_line_map[target_row]
    check("proxy: first body row after header shift is >= 2", target_row >= 2)
    mod_proxy._handle_proxy_mouse(0, 5, target_row)
    check("proxy: _proxy_just_expanded set by the click", mod_proxy._proxy_just_expanded == target_key)
    mod_proxy._build_proxy_output()
    check("proxy: just-expanded entry stays visible in the next render (auto-scroll intact)",
          target_key in mod_proxy.proxy_line_map.values())


# ORCHESTRATOR

def run_probe_workflow():
    print("=" * 70)
    print("pane-chrome button click probe -- proxy undo, warnings refresh")
    print("=" * 70)
    test_warnings_refresh_button()
    test_proxy_pane_permanent_search_bar_header()

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
    out_path = md_dir / f"p3_button_click_probe_{stamp}.md"
    lines = [
        f"# P3 -- pane-chrome button click probe run ({datetime.now(timezone.utc).isoformat()})",
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
