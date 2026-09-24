# INFRASTRUCTURE
import shlex
import time

from .launch_config import LAUNCH_DESKTOPS, LAUNCH_PROJECTS
from .menubar_log import log_menubar
from .paths import MONITOR_CC_ROOT
from .space_switch import active_desktop_number, switch_to_desktop_workflow
from .system import _launch_monitor_ghostty_native

_SETTLE_SECONDS = 1.0
_START_SCRIPT = './src/claude_proxy_start.sh'

# ORCHESTRATOR

def launch_workflow(desktop: int, project: str) -> None:
    outcome = _attempt_launch(desktop, project)
    _log_outcome(desktop, project, outcome)

# FUNCTIONS

def _attempt_launch(desktop: int, project: str) -> dict:
    stage = 'validate'
    try:
        _validate_request(desktop, project)
        command = _build_start_command(MONITOR_CC_ROOT, project)
        stage = 'switch'
        switch_ms = switch_to_desktop_workflow(desktop)
        time.sleep(_SETTLE_SECONDS)
        stage = 'open_window'
        result = _launch_monitor_ghostty_native(command)
        if result.returncode != 0:
            return {'ok': False, 'stage': stage, 'detail': f'rc={result.returncode} stderr={result.stderr.strip()}'}
        return {'ok': True, 'stage': stage, 'detail': f'switch_ms={switch_ms:.0f} active_desktop_after={active_desktop_number()}'}
    except Exception as exc:
        return {'ok': False, 'stage': stage, 'detail': repr(exc)}

def _validate_request(desktop: int, project: str) -> None:
    if desktop not in LAUNCH_DESKTOPS:
        raise ValueError(f'desktop {desktop} not in {LAUNCH_DESKTOPS}')
    if project not in LAUNCH_PROJECTS:
        raise ValueError(f'project {project} not in launch list')

def _build_start_command(root, project: str) -> str:
    return (f'cd {shlex.quote(str(root))} && '
            f'PATH="$HOME/.local/bin:$PATH" {_START_SCRIPT} --project {shlex.quote(project)}')

def _log_outcome(desktop: int, project: str, outcome: dict) -> None:
    status = 'OK' if outcome['ok'] else 'FAILED'
    log_menubar('launch', f'{status} desktop={desktop} project={project} '
                          f'stage={outcome["stage"]} {outcome["detail"]}')
