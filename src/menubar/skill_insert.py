# INFRASTRUCTURE
import subprocess
import time

from src.menubar.ghostty import get_ghostty_terminal_id
from src.menubar.menubar_log import log_menubar
from src.menubar.system import _applescript_quote

_OSASCRIPT_TIMEOUT = 5
_TEXT_TEMPLATE = 'Aktiviere den Skill {name}.'

# ORCHESTRATOR

def insert_skill_workflow(cwd: str, skill_full_name: str) -> None:
    outcome = _attempt_insert(cwd, skill_full_name)
    _log_outcome(cwd, skill_full_name, outcome)

# FUNCTIONS

def _attempt_insert(cwd: str, skill_full_name: str) -> dict:
    stage = 'terminal_id'
    try:
        terminal_id = get_ghostty_terminal_id(cwd)
        if not terminal_id:
            return {'ok': False, 'stage': stage, 'detail': 'no_terminal_id'}
        script = _build_script(terminal_id, _build_insert_text(skill_full_name))
        stage = 'osascript'
        t0 = time.monotonic()
        result = subprocess.run(['osascript', '-e', script], capture_output=True, text=True,
                                encoding='utf-8', errors='replace', timeout=_OSASCRIPT_TIMEOUT)
        ms = (time.monotonic() - t0) * 1000
        if result.returncode != 0:
            return {'ok': False, 'stage': stage, 'detail': f'rc={result.returncode} stderr={result.stderr.strip()}'}
        return {'ok': True, 'stage': stage, 'detail': f'terminal={terminal_id} osascript_ms={ms:.0f}'}
    except Exception as exc:
        return {'ok': False, 'stage': stage, 'detail': repr(exc)}

def _build_insert_text(skill_full_name: str) -> str:
    return _TEXT_TEMPLATE.format(name=skill_full_name)

def _build_script(terminal_id: str, text: str) -> str:
    return (
        'tell application "Ghostty"\n'
        f'  set t to first terminal whose id is {_applescript_quote(terminal_id)}\n'
        f'  input text {_applescript_quote(text)} to t\n'
        'end tell'
    )

def _log_outcome(cwd: str, skill_full_name: str, outcome: dict) -> None:
    status = 'OK' if outcome['ok'] else 'FAILED'
    log_menubar('skill', f'{status} cwd={cwd} skill={skill_full_name} '
                         f'stage={outcome["stage"]} {outcome["detail"]}')
