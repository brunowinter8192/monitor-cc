# INFRASTRUCTURE
import os
from pathlib import Path

_LABEL           = 'com.brunowinter.monitor-cc-menubar'
_PLIST_TMPL      = Path(__file__).resolve().parent / f'{_LABEL}.plist'
_LAUNCH_AGENTS   = Path.home() / 'Library' / 'LaunchAgents'
_DEST            = _LAUNCH_AGENTS / f'{_LABEL}.plist'
_PROJECT_ROOT    = Path(os.environ['PROJECT_ROOT']) if os.environ.get('PROJECT_ROOT') \
                   else Path(__file__).resolve().parent.parent.parent
_BUNDLE          = Path.home() / 'Applications' / 'monitor-cc-menubar.app'
_BUNDLE_LAUNCHER = _BUNDLE / 'Contents' / 'MacOS' / 'menubar'
_BUNDLE_EXE      = _BUNDLE / 'Contents' / 'MacOS' / 'monitor-cc-menubar'

# FUNCTIONS

def write_plist() -> None:
    content = _PLIST_TMPL.read_text(encoding='utf-8')
    content = content.replace('<PROJECT_ROOT>', str(_PROJECT_ROOT))
    content = content.replace('<BUNDLE_LAUNCHER>', str(_BUNDLE_LAUNCHER))
    _LAUNCH_AGENTS.mkdir(parents=True, exist_ok=True)
    _DEST.write_text(content, encoding='utf-8')
    print(f'  wrote {_DEST}')

def write_plist_py2app() -> None:
    content = _PLIST_TMPL.read_text(encoding='utf-8')
    content = content.replace('<PROJECT_ROOT>', str(_PROJECT_ROOT))
    content = content.replace('<BUNDLE_LAUNCHER>', str(_BUNDLE_EXE))
    _LAUNCH_AGENTS.mkdir(parents=True, exist_ok=True)
    _DEST.write_text(content, encoding='utf-8')
