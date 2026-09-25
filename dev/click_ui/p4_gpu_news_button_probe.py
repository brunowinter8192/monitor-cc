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
mod_gpu = importlib.import_module(f'{_ROOT_PKG}.gpu_pane.pane')
mod_news = importlib.import_module(f'{_ROOT_PKG}.news_pane.pane')

_PASS = "\033[32mPASS\033[0m"
_FAIL = "\033[31mFAIL\033[0m"
_RESULTS = []


# ORCHESTRATOR

def run_probe_workflow():
    print("=" * 70)
    print("gpu + news pane button probe")
    print("=" * 70)
    test_gpu_digit_key_covered_by_existing_button()
    test_gpu_refresh_button()
    test_gpu_refresh_button_width_sweep()
    test_news_refresh_button()
    test_news_refresh_button_width_sweep()

    total = len(_RESULTS)
    passed = sum(1 for _, ok in _RESULTS if ok)
    print("\n" + "=" * 70)
    print(f"{passed}/{total} checks passed")
    print("=" * 70)

    _write_report(passed, total)
    return passed == total


# FUNCTIONS

def test_gpu_digit_key_covered_by_existing_button():
    orig_names = mod_gpu.PRESET_NAMES
    mod_gpu.PRESET_NAMES = ['preset-a', 'preset-b']
    try:
        presets = [
            _make_preset('preset-a', running=False, healthy=False),
            _make_preset('preset-b', running=True, healthy=True, port=8001, pid=999),
        ]
        mod_gpu._toggle_state.clear()
        output = mod_gpu._render_pane(150, 30, presets, [], [], [], {}, [])
        regions = dict(mod_gpu._button_regions)

        preset_regions = {name: rect for rect, (action, name) in regions.items()
                           if name in ('preset-a', 'preset-b')}
        check("gpu: both preset rows have a button region", len(preset_regions) == 2)
        refresh_regions = {rect: v for rect, v in regions.items() if v == ('refresh', 'refresh')}
        check("gpu: preset button rows are disjoint from the [refresh] header row",
              all(rect[2] != next(iter(refresh_regions))[2] for rect in preset_regions.values()) if refresh_regions else False)

        for idx, (name, expect_action) in enumerate([('preset-a', 'start'), ('preset-b', 'stop')]):
            rect, (btn_action, btn_target) = next((r, v) for r, v in regions.items() if v[1] == name)
            check(f"gpu: registered button action for '{name}' is '{expect_action}'",
                  btn_action == expect_action)

            mod_gpu._toggle_state.clear()
            key_captured = _patch_popen(mod_gpu)
            mod_gpu._toggle_server(idx, presets)
            key_popen_calls = list(key_captured)
            key_toggle_state = dict(mod_gpu._toggle_state)

            mod_gpu._toggle_state.clear()
            click_captured = _patch_popen(mod_gpu)
            sc, ec, er = rect
            result = _dispatch_gpu_click((sc + ec) // 2, er)
            click_popen_calls = list(click_captured)
            click_toggle_state = dict(mod_gpu._toggle_state)

            check(f"gpu: click on '{name}' button dispatched (matched region, fired)",
                  result == (btn_action, name))
            check(f"gpu: click/digit-key parity for '{name}' -- same subprocess.Popen args",
                  key_popen_calls == click_popen_calls and len(key_popen_calls) == 1)
            check(f"gpu: click/digit-key parity for '{name}' -- same _toggle_state action label "
                  "(timestamps differ by real elapsed time between the two calls, not compared)",
                  name in key_toggle_state and name in click_toggle_state
                  and key_toggle_state[name][0] == click_toggle_state[name][0])
    finally:
        mod_gpu.PRESET_NAMES = orig_names
        mod_gpu._toggle_state.clear()


def _make_preset(name, running, healthy, port=None, pid=None):
    return {
        'name': name, 'kind': 'preset', 'running': running, 'healthy': healthy,
        'port': port, 'pid': pid, 'rss_mb': None, 'idle_seconds': None,
        'idle_state_missing': False, 'model_name': None,
    }


def check(label, condition):
    _RESULTS.append((label, bool(condition)))
    print(f"  {_PASS if condition else _FAIL}  {label}")
    return condition


def _patch_popen(mod):
    captured = []

    class _FakePopen:
        def __init__(self, *args, **kwargs):
            captured.append((args, kwargs))

    mod.subprocess.Popen = _FakePopen
    return captured


def _dispatch_gpu_click(col, row):
    for (sc, ec, er), (action, target) in list(mod_gpu._button_regions.items()):
        if row == er and sc <= col <= ec:
            if action == 'refresh':
                return 'refresh'
            if target not in mod_gpu._toggle_state:
                mod_gpu._fire_button(action, target)
                return (action, target)
            return None
    return None


def test_gpu_refresh_button():
    orig_names = mod_gpu.PRESET_NAMES
    mod_gpu.PRESET_NAMES = ['preset-a']
    try:
        presets = [_make_preset('preset-a', running=False, healthy=False)]
        output = mod_gpu._render_pane(150, 30, presets, [], [], [], {}, [])
        regions = dict(mod_gpu._button_regions)
        refresh_entries = [(r, v) for r, v in regions.items() if v == ('refresh', 'refresh')]
        check("gpu: [refresh] button region registered", len(refresh_entries) == 1)
        check("gpu: [refresh] button on row 1", refresh_entries[0][0][2] == 1)
        check("gpu: [refresh] button text visible in header line",
              '[refresh]' in output.split('\n')[0])

        (sc, ec, er), _ = refresh_entries[0]
        result = _dispatch_gpu_click((sc + ec) // 2, er)
        check("gpu: click on [refresh] is recognized as the refresh action (same as 'r' key branch)",
              result == 'refresh')

        narrow_output = mod_gpu._render_pane(20, 30, presets, [], [], [], {}, [])
        narrow_regions = dict(mod_gpu._button_regions)
        check("gpu: width guard -- no [refresh] region when pane_width=20 (too narrow)",
              ('refresh', 'refresh') not in narrow_regions.values())
        check("gpu: width guard -- no [refresh] text in header when too narrow",
              '[refresh]' not in narrow_output.split('\n')[0])
    finally:
        mod_gpu.PRESET_NAMES = orig_names


def test_gpu_refresh_button_width_sweep():
    orig_names = mod_gpu.PRESET_NAMES
    mod_gpu.PRESET_NAMES = []
    try:
        no_button_widths = [5, 20, 26]
        button_widths = [27, 30, 50, 90, 130, 215]
        for w in no_button_widths:
            output = mod_gpu._render_pane(w, 30, [], [], [], [], {}, [])
            first_line = output.split('\n')[0]
            check(f"gpu width={w}: no [refresh] region (too narrow even at the rule minimum)",
                  ('refresh', 'refresh') not in mod_gpu._button_regions.values())
            check(f"gpu width={w}: title text 'GPU Servers' still fully visible",
                  'GPU Servers' in first_line)
        for w in button_widths:
            output = mod_gpu._render_pane(w, 30, [], [], [], [], {}, [])
            first_line = output.split('\n')[0]
            rule_chars = first_line.count('═')
            check(f"gpu width={w}: [refresh] region registered (decoration yielded, not the button)",
                  ('refresh', 'refresh') in mod_gpu._button_regions.values())
            if w < 90:
                check(f"gpu width={w}: rule shrank below its 64-char cap to make room",
                      0 < rule_chars < 64)
    finally:
        mod_gpu.PRESET_NAMES = orig_names


def test_news_refresh_button():
    status = {'doc_count': 5, 'chunk_count': 50, 'last_run_ts': '2026-01-01 00:00:00'}
    output = mod_news._render_pane(120, 30, status, running=False)
    regions = dict(mod_news._button_regions)
    refresh_entries = [(r, v) for r, v in regions.items() if v == ('refresh', 'refresh')]
    run_entries = [(r, v) for r, v in regions.items() if v == ('run', 'pipeline')]
    check("news: [refresh] button region registered", len(refresh_entries) == 1)
    check("news: [run pipeline] button region still registered (unchanged)", len(run_entries) == 1)
    check("news: [refresh] and [run pipeline] rows are disjoint (no collision)",
          refresh_entries[0][0][2] != run_entries[0][0][2])
    check("news: [refresh] button text visible in header line", '[refresh]' in output.split('\n')[0])

    (sc, ec, er), _ = refresh_entries[0]
    result = _dispatch_news_click((sc + ec) // 2, er)
    check("news: click on [refresh] is recognized as the refresh action (same as 'r' key branch)",
          result == 'refresh')

    captured = _patch_popen(mod_news)
    mod_news._pipeline_proc = None
    (rsc, rec, rer), _ = run_entries[0]
    run_result = _dispatch_news_click((rsc + rec) // 2, rer)
    check("news: [run pipeline] click still fires the pipeline (regression)",
          run_result == 'run_pipeline' and len(captured) == 1)

    narrow_output = mod_news._render_pane(15, 30, status, running=False)
    narrow_regions = dict(mod_news._button_regions)
    check("news: width guard -- no [refresh] region when pane_width=15 (too narrow)",
          ('refresh', 'refresh') not in narrow_regions.values())
    check("news: width guard -- no [refresh] text in header when too narrow",
          '[refresh]' not in narrow_output.split('\n')[0])


def _dispatch_news_click(col, row):
    for (sc, ec, er), (action, target) in list(mod_news._button_regions.items()):
        if row == er and sc <= col <= ec:
            if action == 'refresh':
                return 'refresh'
            if not mod_news._is_running():
                mod_news._fire_pipeline()
                return 'run_pipeline'
            return None
    return None


def test_news_refresh_button_width_sweep():
    status = {'doc_count': 5, 'chunk_count': 50, 'last_run_ts': '2026-01-01 00:00:00'}
    no_button_widths = [5, 20, 37]
    button_widths = [38, 40, 60, 86, 107]
    for w in no_button_widths:
        output = mod_news._render_pane(w, 30, status, running=False)
        first_line = output.split('\n')[0]
        check(f"news width={w}: no [refresh] region (too narrow even at the rule minimum)",
              ('refresh', 'refresh') not in mod_news._button_regions.values())
        check(f"news width={w}: title text 'CoinDesk News Pipeline' still fully visible",
              'CoinDesk News Pipeline' in first_line)
    for w in button_widths:
        output = mod_news._render_pane(w, 30, status, running=False)
        first_line = output.split('\n')[0]
        rule_chars = first_line.count('═')
        check(f"news width={w}: [refresh] region registered (decoration yielded, not the button)",
              ('refresh', 'refresh') in mod_news._button_regions.values())
        if w < 86:
            check(f"news width={w}: rule shrank below its 52-char cap to make room",
                  0 < rule_chars < 52)


def _write_report(passed, total):
    md_dir = WORKTREE_ROOT / "dev" / "click_ui" / "md"
    md_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    out_path = md_dir / f"p4_gpu_news_button_probe_{stamp}.md"
    lines = [
        f"# P4 -- gpu + news pane button probe run ({datetime.now(timezone.utc).isoformat()})",
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
