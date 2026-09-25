# INFRASTRUCTURE
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from dev.refactoring.repo_roots import resolve_main_project

PROJECT_ROOT = Path(__file__).resolve().parents[2]
SANDBOX_ROOT = PROJECT_ROOT.parent / f'{PROJECT_ROOT.name}_writer_scan'
REPORT_PATH = Path(__file__).resolve().parent / 'md' / 'live_log_writer_scan_report.md'
LIVE_APP_SUPPORT = Path.home() / 'Library' / 'Application Support' / 'com.brunowinter.monitor-cc-menubar'
RUN_TIMEOUT_SECONDS = 150
LIVE_HAZARD_DIRS = (
    'dev/desktop_allocation', 'dev/session_launcher', 'dev/menubar_nspanel', 'dev/cursor_edges', 'dev/nsgridview_migration',
    'dev/coteditor', 'dev/hook_error_correlation', 'dev/monitor_lifecycle', 'dev/tmux_launcher', 'dev/worker_pane_split',
    'dev/worker_status_probes', 'dev/skill_picker', 'dev/setup_py2app',
)
LIVE_HAZARD_FILES = (
    'dev/hotkey_latency/probe_get_event_time.py', 'dev/model_selector/verify_three_tab_ring.py', 'dev/hook_smoke/probe_bg_task_live.py',
    'dev/bg_wakeup_id_line/p2_bg_escape_probe.py', 'dev/menubar_per_project/test_open_or_focus_monitor.py',
    'dev/refactoring/live_proxy_sandbox.py', 'dev/refactoring/live_log_writer_scan.py',
)
SAFE_EXCEPTIONS = ('dev/monitor_lifecycle/tests/test_monitor_sweep_scheduler.py', 'dev/menubar_per_project/test_open_or_focus_monitor.py')


# ORCHESTRATOR

def writer_scan_workflow() -> int:
    main_project = Path(resolve_main_project(str(PROJECT_ROOT)))
    fake_home = prepare_sandbox()
    scripts = list_scripts()
    findings = scan_scripts(scripts, fake_home, main_project)
    write_report(findings, len(scripts))
    print_summary(findings, len(scripts))
    return exit_code(findings)


# FUNCTIONS

def prepare_sandbox() -> Path:
    shutil.rmtree(SANDBOX_ROOT, ignore_errors=True)
    subprocess.run(['rsync', '-a', '--exclude', '.git', f'{PROJECT_ROOT}/', f'{SANDBOX_ROOT}/'], check=True)
    (SANDBOX_ROOT / 'src' / 'logs').mkdir(parents=True, exist_ok=True)
    return Path(tempfile.mkdtemp(prefix='writer_scan_home_'))


def list_scripts() -> list:
    tracked = subprocess.check_output(['git', '-C', str(PROJECT_ROOT), 'ls-files', 'dev'], text=True).split()
    return [rel for rel in tracked if rel.endswith('.py') and is_runnable(rel)]


def is_runnable(rel: str) -> bool:
    if rel in SAFE_EXCEPTIONS:
        return has_main_guard(SANDBOX_ROOT / rel)
    hazard = rel in LIVE_HAZARD_FILES or any(rel.startswith(d + '/') for d in LIVE_HAZARD_DIRS)
    return not hazard and has_main_guard(SANDBOX_ROOT / rel)


def has_main_guard(path: Path) -> bool:
    return '__name__' in path.read_text(encoding='utf-8') and '__main__' in path.read_text(encoding='utf-8')


def scan_scripts(scripts: list, fake_home: Path, main_project: Path) -> list:
    findings = []
    for rel in scripts:
        before = snapshot(fake_home, main_project)
        returncode = run_script(rel, fake_home, main_project)
        changed = changed_paths(before, snapshot(fake_home, main_project), fake_home)
        if changed:
            findings.append((rel, returncode, changed))
    return findings


def snapshot(fake_home: Path, main_project: Path) -> dict:
    found = {}
    for root, recursive in ((SANDBOX_ROOT / 'src' / 'logs', True), (fake_home, True), (main_project / 'src' / 'logs', False), (LIVE_APP_SUPPORT, False)):
        found.update(list_files(root, recursive))
    return found


def list_files(root: Path, recursive: bool) -> dict:
    if not root.exists():
        return {}
    paths = root.rglob('*') if recursive else root.glob('*')
    return {str(p): (p.stat().st_size, p.stat().st_mtime_ns) for p in paths if p.is_file() and p.name != '.DS_Store'}


def run_script(rel: str, fake_home: Path, main_project: Path) -> object:
    env = dict(os.environ, HOME=str(fake_home), PYTHONDONTWRITEBYTECODE='1')
    env.pop('PROJECT_ROOT', None)
    script = SANDBOX_ROOT / rel
    try:
        result = subprocess.run([str(main_project / 'venv' / 'bin' / 'python'), str(script)], cwd=script.parent, env=env, capture_output=True, text=True, timeout=RUN_TIMEOUT_SECONDS, stdin=subprocess.DEVNULL)
    except subprocess.TimeoutExpired:
        return 'timeout'
    return result.returncode


def changed_paths(before: dict, after: dict, fake_home: Path) -> list:
    changed = [p for p in after if before.get(p) != after[p]]
    return [f'{label(p, fake_home)} +{after[p][0] - before.get(p, (0, 0))[0]}B' for p in changed]


def label(path: str, fake_home: Path) -> str:
    if path.startswith(str(SANDBOX_ROOT / 'src' / 'logs')):
        return 'sandbox-logs:' + path[len(str(SANDBOX_ROOT / 'src' / 'logs')) + 1:]
    if path.startswith(str(fake_home)):
        return 'fake-home:' + path[len(str(fake_home)) + 1:]
    return 'LIVE(noise candidate):' + path


def write_report(findings: list, script_count: int) -> None:
    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    lines = ['# live_log_writer_scan report', '', f'scripts run: {script_count}', f'scripts that changed a watched path: {len(findings)}', '']
    for rel, returncode, changed in findings:
        lines.append(f'## {rel} (rc={returncode})')
        lines += [f'- {entry}' for entry in changed]
        lines.append('')
    REPORT_PATH.write_text('\n'.join(lines), encoding='utf-8')


def print_summary(findings: list, script_count: int) -> None:
    print(f'scripts run: {script_count}, writers: {len(findings)}')
    for rel, returncode, changed in findings:
        print(f'{rel} rc={returncode}')
        for entry in changed:
            print(f'    {entry}')
    print(f'report: {REPORT_PATH}')


def exit_code(findings: list) -> int:
    return 0 if not [f for f in findings if any(not e.startswith('LIVE') and 'zsh_history' not in e and '.mitmproxy' not in e for e in f[2])] else 1


if __name__ == '__main__':
    sys.exit(writer_scan_workflow())
