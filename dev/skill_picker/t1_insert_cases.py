# INFRASTRUCTURE
import shutil
import subprocess
import tempfile
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from dev.skill_picker.t1_fixtures import _REAL_SHAPED_FULL, _imp

# FUNCTIONS

def _case_insert_text() -> str:
    si = _imp('skill_insert')
    names = _REAL_SHAPED_FULL + ['penny', 'wise2627-tracker']
    for name in names:
        assert si._build_insert_text(name) == f'Aktiviere den Skill {name}.', name
    assert si._build_insert_text('iterative-dev:iterative-dev-doccheck') == 'Aktiviere den Skill iterative-dev:iterative-dev-doccheck.'
    return f'{len(names)} inserted texts exact, e.g. {si._build_insert_text(names[0])!r}'

def _case_applescript() -> str:
    si = _imp('skill_insert')
    text = si._build_insert_text('websearch:websearch-pdf')
    script = si._build_script('TERM-1', text)
    assert script == ('tell application "Ghostty"\n'
                      '  set t to first terminal whose id is "TERM-1"\n'
                      '  input text "Aktiviere den Skill websearch:websearch-pdf." to t\n'
                      'end tell'), script
    for forbidden in ('send key', 'activate', 'focus', 'System Events', 'keystroke'):
        assert forbidden not in script, f'{forbidden} in script'
    tricky = si._build_script('T"1', 'a "quoted" \\ back')
    assert 'whose id is "T\\"1"' in tricky and 'input text "a \\"quoted\\" \\\\ back" to t' in tricky, tricky
    tmp = Path(tempfile.mkdtemp(prefix='skillpicker_'))
    r = subprocess.run(['osacompile', '-o', str(tmp / 'x.scpt'), '-e', script], capture_output=True, text=True, timeout=30)
    assert r.returncode == 0, f'osacompile rc={r.returncode} {r.stderr}'
    shutil.rmtree(tmp)
    return 'script exact, no send key/activate/focus/System Events, quoting escaped, osacompile (compile only, nothing executed) rc=0'

def _run_insert(terminal_id, run_effect=None):
    si = _imp('skill_insert')
    logs = []
    calls = []
    def fake_run(cmd, **kw):
        calls.append((cmd, kw))
        if isinstance(run_effect, Exception):
            raise run_effect
        return run_effect or SimpleNamespace(returncode=0, stdout='', stderr='')
    with patch.object(si, 'get_ghostty_terminal_id', lambda cwd: terminal_id), \
         patch.object(si.subprocess, 'run', fake_run), \
         patch.object(si, 'log_menubar', lambda c, m: logs.append((c, m))):
        si.insert_skill_workflow('/p/x', 'gh-cli:gh-cli-search')
    return calls, logs

def _case_insert_paths() -> str:
    out = []
    calls, logs = _run_insert(None)
    assert calls == [], 'osascript called without terminal id'
    assert len(logs) == 1 and logs[0][0] == 'skill' and logs[0][1].startswith('FAILED cwd=/p/x skill=gh-cli:gh-cli-search stage=terminal_id no_terminal_id'), logs
    out.append(f'no terminal id: {logs[0][1]}')
    calls, logs = _run_insert('T9', SimpleNamespace(returncode=1, stdout='', stderr='not allowed'))
    assert len(calls) == 1 and logs[0][1].startswith('FAILED') and 'stage=osascript' in logs[0][1] and 'not allowed' in logs[0][1], logs
    out.append(f'rc=1: {logs[0][1]}')
    calls, logs = _run_insert('T9', subprocess.TimeoutExpired('osascript', 5))
    assert len(calls) == 1 and logs[0][1].startswith('FAILED') and 'stage=osascript' in logs[0][1] and 'TimeoutExpired' in logs[0][1], logs
    out.append(f'timeout: {logs[0][1][:120]}')
    calls, logs = _run_insert('T9')
    assert len(calls) == 1 and calls[0][0][:2] == ['osascript', '-e'], calls
    assert 'Aktiviere den Skill gh-cli:gh-cli-search.' in calls[0][0][2] and 'send key' not in calls[0][0][2]
    assert calls[0][1]['timeout'] == 5
    assert logs[0][1].startswith('OK cwd=/p/x skill=gh-cli:gh-cli-search stage=osascript terminal=T9'), logs
    out.append(f'success: one osascript call, {logs[0][1][:90]}')
    return ' | '.join(out)
