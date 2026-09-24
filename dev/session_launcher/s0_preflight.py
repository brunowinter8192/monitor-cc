# INFRASTRUCTURE
import os
import plistlib
import shutil
import subprocess
import sys
from datetime import datetime
from typing import List

from dev.session_launcher.space_lib import (
    active_space,
    display_count,
    ghostty_window_ids,
    permission_state,
    process_ancestry,
    spaces_for_window,
    spaces_with_types,
    write_report,
)

_HOTKEY_IDS = ('118', '119', '120', '121', '122')

# ORCHESTRATOR

def main() -> None:
    sections = [
        _section_header(),
        _section_ancestry(),
        _section_permissions(),
        _section_spaces(),
        _section_settings(),
        _section_hotkeys(),
        _section_ghostty(),
        _section_tools(),
    ]
    text = '\n'.join(sections)
    path = write_report(__file__, text)
    print(text)
    print(f'report: {path}')

# FUNCTIONS

def _run(cmd: List[str]) -> str:
    r = subprocess.run(cmd, capture_output=True, text=True, encoding='utf-8', errors='replace', timeout=15)
    return (r.stdout + r.stderr).strip()

def _section_header() -> str:
    return '\n'.join([
        '# s0_preflight report',
        '',
        f'- time: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}',
        f'- sw_vers: {_run(["sw_vers", "-productVersion"])} / {_run(["sw_vers", "-buildVersion"])}',
        f'- python: {sys.executable} ({sys.version.split()[0]})',
        f'- pid: {os.getpid()}',
        '',
    ])

def _section_ancestry() -> str:
    chain = process_ancestry(os.getpid())
    lines = ['## Process ancestry (child first)', ''] + [f'- {c}' for c in chain] + ['']
    return '\n'.join(lines)

def _section_permissions() -> str:
    lines = ['## Permission state of this process (preflight calls)', '']
    for name, state in permission_state().items():
        lines.append(f'- {name}: {state}')
    lines.append('')
    return '\n'.join(lines)

def _section_spaces() -> str:
    spaces = spaces_with_types()
    active = active_space()
    lines = ['## Spaces', '', f'- displays: {display_count()}', f'- spaces on active display: {len(spaces)}', f'- active space id: {active}', '']
    for i, (sid, stype) in enumerate(spaces, start=1):
        marker = ' <- active' if sid == active else ''
        lines.append(f'- index {i}: space id {sid}, type {stype}{marker}')
    lines.append('')
    return '\n'.join(lines)

def _section_settings() -> str:
    lines = ['## Mission Control settings', '']
    lines.append(f'- spans-displays: {_run(["defaults", "read", "com.apple.spaces", "spans-displays"])}')
    lines.append(f'- AppleSpacesSwitchOnActivate: {_run(["defaults", "read", "NSGlobalDomain", "AppleSpacesSwitchOnActivate"])}')
    lines.append(f'- workspaces-auto-swoosh: {_run(["defaults", "read", "com.apple.dock", "workspaces-auto-swoosh"])}')
    lines.append('')
    return '\n'.join(lines)

def _section_hotkeys() -> str:
    raw = subprocess.run(['defaults', 'export', 'com.apple.symbolichotkeys', '-'], capture_output=True, timeout=15).stdout
    hotkeys = plistlib.loads(raw).get('AppleSymbolicHotKeys', {})
    lines = ['## Symbolic hotkeys 118-122', '']
    for hid in _HOTKEY_IDS:
        entry = hotkeys.get(hid, {})
        params = entry.get('value', {}).get('parameters')
        lines.append(f'- {hid}: enabled={entry.get("enabled")} parameters={params}')
    lines.append('')
    return '\n'.join(lines)

def _section_ghostty() -> str:
    running = _run(['pgrep', '-f', 'Ghostty.app/Contents/MacOS'])
    lines = ['## Ghostty', '', f'- pgrep: {running.replace(chr(10), ",") or "not running"}']
    for wid in ghostty_window_ids():
        lines.append(f'- window {wid}: spaces {spaces_for_window(wid)}')
    lines.append('')
    return '\n'.join(lines)

def _section_tools() -> str:
    lines = ['## Tools', '', f'- clang: {shutil.which("clang")}', f'- osascript: {shutil.which("osascript")}', '']
    return '\n'.join(lines)

if __name__ == '__main__':
    main()
