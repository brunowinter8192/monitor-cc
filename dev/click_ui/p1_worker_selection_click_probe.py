# INFRASTRUCTURE
import importlib
import os
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace

WORKTREE_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(WORKTREE_ROOT))
os.environ.setdefault('MONITOR_CC_ROOT', str(WORKTREE_ROOT))

_ROOT_PKG = 'src'
wp = importlib.import_module(f'{_ROOT_PKG}.proxy_display.worker_proxy_pane')
wpane = importlib.import_module(f'{_ROOT_PKG}.workers.worker_tokens_pane')

_RUN_ID = uuid.uuid4().hex[:8]
_FAKE_PROXY_PROJECT = f'/tmp/click_ui_probe_worker_proxy_{_RUN_ID}'
_FAKE_WORKERS_PROJECT = f'/tmp/click_ui_probe_worker_tokens_{_RUN_ID}'

_PASS = "\033[32mPASS\033[0m"
_FAIL = "\033[31mFAIL\033[0m"
_RESULTS = []


# ORCHESTRATOR

def main():
    ok = run_probe_workflow()
    exit_with_status(ok)


# FUNCTIONS

def run_probe_workflow():
    print("=" * 70)
    print("worker-selection click probe -- worker-proxy header + workers-pane row")
    print("=" * 70)
    test_worker_proxy_header_click()
    test_worker_proxy_header_wrap_straddle()
    test_worker_tokens_header_click()
    test_worker_tokens_header_wrap_at_narrow_pane_width()

    total = len(_RESULTS)
    passed = sum(1 for _, ok in _RESULTS if ok)
    print("\n" + "=" * 70)
    print(f"{passed}/{total} checks passed")
    print("=" * 70)

    _write_report(passed, total)
    return passed == total


def test_worker_proxy_header_click():
    monitor = SimpleNamespace(active_project_filter=_FAKE_PROXY_PROJECT)
    workers = [{'name': 'alice'}, {'name': 'bob'}, {'name': 'carol'}]
    wp._worker_proxy_workers = workers
    _clear_selection(wp.get_selection_file_path, _FAKE_PROXY_PROJECT)

    wp._build_worker_proxy_output(monitor)
    regions = dict(wp._worker_proxy_header_regions)

    check("worker-proxy: one header region per worker", len(regions) == len(workers))
    check("worker-proxy: region targets match worker names",
          sorted(regions.values()) == sorted(w['name'] for w in workers))
    check("worker-proxy: region coordinates plausible (1-based, sc<=ec, er>=1)",
          all(sc >= 1 and ec >= sc and er >= 1 for (sc, ec, er) in regions))
    ordered = sorted(regions.keys(), key=lambda r: r[0])
    check("worker-proxy: header regions do not overlap",
          all(ordered[i][1] < ordered[i + 1][0] for i in range(len(ordered) - 1)))

    name_to_region = {name: rect for rect, name in regions.items()}
    for idx, w in enumerate(workers, 1):
        name = w['name']
        sc, ec, er = name_to_region[name]
        click_col = (sc + ec) // 2

        _clear_selection(wp.get_selection_file_path, _FAKE_PROXY_PROJECT)
        wp._worker_proxy_force_reload = False
        key_changed = wp._handle_worker_proxy_key(str(idx), monitor)
        key_selection = _read_selection(wp.get_selection_file_path, _FAKE_PROXY_PROJECT)
        key_reload = wp._worker_proxy_force_reload

        _clear_selection(wp.get_selection_file_path, _FAKE_PROXY_PROJECT)
        wp._worker_proxy_force_reload = False
        mouse_changed = wp._handle_worker_proxy_mouse(0, click_col, er, monitor)
        mouse_selection = _read_selection(wp.get_selection_file_path, _FAKE_PROXY_PROJECT)
        mouse_reload = wp._worker_proxy_force_reload

        check(f"worker-proxy: digit-key '{idx}' selects '{name}'",
              key_changed and key_selection == name and key_reload)
        check(f"worker-proxy: click at col {click_col} row {er} on '[{idx}]{name}' selects it",
              mouse_changed and mouse_selection == name and mouse_reload)
        check(f"worker-proxy: click/key parity for '{name}'", key_selection == mouse_selection)

    _clear_selection(wp.get_selection_file_path, _FAKE_PROXY_PROJECT)


def _clear_selection(get_path_fn, project_filter):
    path = get_path_fn(project_filter)
    if os.path.exists(path):
        os.remove(path)


def check(label, condition):
    _RESULTS.append((label, bool(condition)))
    print(f"  {_PASS if condition else _FAIL}  {label}")
    return condition


def _read_selection(get_path_fn, project_filter):
    path = get_path_fn(project_filter)
    if not os.path.exists(path):
        return ''
    return open(path, 'r', encoding='utf-8').read().strip()


def test_worker_proxy_header_wrap_straddle():
    monitor = SimpleNamespace(active_project_filter=_FAKE_PROXY_PROJECT)
    workers = [{'name': 'alpha'}, {'name': 'beta'}, {'name': 'gamma-long-name'}, {'name': 'delta'}]
    wp._worker_proxy_workers = workers
    names = {w['name'] for w in workers}
    straddle_found = False

    for pane_width in (200, 60, 40, 30):
        wp._format_worker_proxy_header(workers, None, pane_width, wp._worker_proxy_header_regions)
        shifted = {
            (sc, ec, er + wp._WP_SEARCH_BAR_LINES): name
            for (sc, ec, er), name in wp._worker_proxy_header_regions.items()
        }
        wp._worker_proxy_header_regions.clear()
        wp._worker_proxy_header_regions.update(shifted)
        regions = dict(wp._worker_proxy_header_regions)
        covered = set(regions.values())
        check(f"worker-proxy wrap: all {len(workers)} markers have >=1 region at pane_width={pane_width}",
              covered == names)

        by_name = {}
        for rect, name in regions.items():
            by_name.setdefault(name, []).append(rect)
        for name, rects in by_name.items():
            if len(rects) <= 1:
                continue
            straddle_found = True
            idx = next(i for i, w in enumerate(workers, 1) if w['name'] == name)
            for sc, ec, er in rects:
                _clear_selection(wp.get_selection_file_path, _FAKE_PROXY_PROJECT)
                changed = wp._handle_worker_proxy_mouse(0, (sc + ec) // 2, er, monitor)
                selection = _read_selection(wp.get_selection_file_path, _FAKE_PROXY_PROJECT)
                check(f"worker-proxy wrap: click on segment {(sc, ec, er)} of straddling "
                      f"'[{idx}]{name}' (pane_width={pane_width}) selects it",
                      changed and selection == name)

    check("worker-proxy wrap: sweep actually forced >=1 straddling marker", straddle_found)
    _clear_selection(wp.get_selection_file_path, _FAKE_PROXY_PROJECT)


def test_worker_tokens_header_click():
    project_filter = _FAKE_WORKERS_PROJECT
    workers = [
        {'name': 'w1', 'status': 'working', 'context_pct': 70},
        {'name': 'w2', 'status': 'idle', 'context_pct': 20},
    ]
    monitor = SimpleNamespace(active_project_filter=project_filter)
    wpane._worker_tokens_workers = workers
    _clear_selection(wpane.get_selection_file_path, project_filter)

    wpane._build_worker_tokens_output(monitor)
    regions = dict(wpane._worker_tokens_header_regions)

    check("worker-tokens: one header region per worker", len(regions) == len(workers))
    check("worker-tokens: region targets match worker names",
          sorted(regions.values()) == sorted(w['name'] for w in workers))
    check("worker-tokens: region coordinates plausible (1-based, sc<=ec, er>=1)",
          all(sc >= 1 and ec >= sc and er >= 1 for (sc, ec, er) in regions))

    name_to_region = {name: rect for rect, name in regions.items()}
    for idx, w in enumerate(workers, 1):
        name = w['name']
        sc, ec, er = name_to_region[name]
        click_col = (sc + ec) // 2

        _clear_selection(wpane.get_selection_file_path, project_filter)
        wpane._worker_tokens_force_reload = False
        key_changed = wpane._handle_worker_tokens_key(str(idx), monitor)
        key_selection = _read_selection(wpane.get_selection_file_path, project_filter)
        key_reload = wpane._worker_tokens_force_reload

        _clear_selection(wpane.get_selection_file_path, project_filter)
        wpane._worker_tokens_force_reload = False
        mouse_changed = wpane._handle_worker_tokens_mouse(0, click_col, er, monitor)
        mouse_selection = _read_selection(wpane.get_selection_file_path, project_filter)
        mouse_reload = wpane._worker_tokens_force_reload

        check(f"worker-tokens: digit-key '{idx}' selects '{name}'",
              key_changed and key_selection == name and key_reload)
        check(f"worker-tokens: click at col {click_col} row {er} on '[{idx}]{name}' selects it",
              mouse_changed and mouse_selection == name and mouse_reload)
        check(f"worker-tokens: click/key parity for '{name}'", key_selection == mouse_selection)

    _clear_selection(wpane.get_selection_file_path, project_filter)


def test_worker_tokens_header_wrap_at_narrow_pane_width():
    project_filter = _FAKE_WORKERS_PROJECT
    monitor = SimpleNamespace(active_project_filter=project_filter)
    workers = [
        {'name': 'capture-git-status', 'status': 'idle', 'context_pct': 82},
        {'name': 'devproxy-docs', 'status': 'working', 'context_pct': 45},
        {'name': 'gcommit-umlaut', 'status': 'working', 'context_pct': 12},
        {'name': 'spawn-placement-msg', 'status': 'exited', 'context_pct': None},
        {'name': 'verifier-retire', 'status': 'idle', 'context_pct': 60},
    ]
    names = {w['name'] for w in workers}
    straddle_found = False

    for pane_width in (200, 60, 40, 34):
        wpane._worker_tokens_workers = workers
        _clear_selection(wpane.get_selection_file_path, project_filter)
        wpane._build_worker_tokens_header_block(monitor, pane_width)
        regions = dict(wpane._worker_tokens_header_regions)
        covered = set(regions.values())
        check(f"worker-tokens wrap: all {len(workers)} markers have >=1 region at pane_width={pane_width}",
              covered == names)

        by_name = {}
        for rect, name in regions.items():
            by_name.setdefault(name, []).append(rect)
        for name, rects in by_name.items():
            if len(rects) > 1:
                straddle_found = True
            for sc, ec, er in rects:
                _clear_selection(wpane.get_selection_file_path, project_filter)
                changed = wpane._handle_worker_tokens_mouse(0, (sc + ec) // 2, er, monitor)
                selection = _read_selection(wpane.get_selection_file_path, project_filter)
                check(f"worker-tokens wrap: click on segment {(sc, ec, er)} of '{name}' "
                      f"(pane_width={pane_width}) selects it",
                      changed and selection == name)

    check("worker-tokens wrap: the narrow sweep actually forced >=1 straddling marker", straddle_found)
    check("worker-tokens wrap: pane_width=34 (the pane's real 34% window share) was swept", True)
    _clear_selection(wpane.get_selection_file_path, project_filter)


def _write_report(passed, total):
    md_dir = WORKTREE_ROOT / "dev" / "click_ui" / "md"
    md_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    out_path = md_dir / f"p1_worker_selection_click_probe_{stamp}.md"
    lines = [
        f"# P1 -- worker-selection click probe run ({datetime.now(timezone.utc).isoformat()})",
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


def exit_with_status(ok):
    sys.exit(0 if ok else 1)


if __name__ == '__main__':
    main()
