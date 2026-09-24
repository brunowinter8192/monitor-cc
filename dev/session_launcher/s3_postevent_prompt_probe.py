# INFRASTRUCTURE
import shutil
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

from dev.session_launcher.space_lib import write_report

_SOURCE = Path(__file__).resolve().parent / 's3_postevent_stub.m'
_STUB_ROOT = Path('/tmp/s3_postevent_stubs')
_MODES = ('main', 'bg')
_BUNDLE_ID_PREFIX = 'com.brunowinter.spaceprobe.postevent.'
_RUN_SECONDS = 55

# ORCHESTRATOR

def main() -> None:
    build_only = '--build-only' in sys.argv
    if _STUB_ROOT.exists():
        shutil.rmtree(_STUB_ROOT)
    apps = {mode: _build_stub(mode) for mode in _MODES}
    if build_only:
        print(f'built: {apps}')
        return
    sections = [_run_stub(mode, apps[mode]) for mode in _MODES]
    cleanup_notes = [_cleanup(mode) for mode in _MODES]
    path = write_report(__file__, _build_report(sections, cleanup_notes))
    print(f'report: {path}')

# FUNCTIONS

def _run(cmd: list, timeout: int = 60) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, capture_output=True, text=True, encoding='utf-8', errors='replace', timeout=timeout)

def _build_stub(mode: str) -> Path:
    app = _STUB_ROOT / f'{mode}.app'
    exe_dir = app / 'Contents' / 'MacOS'
    exe_dir.mkdir(parents=True)
    exe = exe_dir / 'stub'
    r = _run(['clang', '-fobjc-arc', '-framework', 'AppKit', '-framework', 'ApplicationServices',
              str(_SOURCE), '-o', str(exe)])
    if r.returncode != 0:
        raise RuntimeError(f'clang failed: {r.stderr}')
    (app / 'Contents' / 'Info.plist').write_text(_info_plist(mode), encoding='utf-8')
    r = _run(['codesign', '-s', '-', '--force', '--deep', str(app)])
    if r.returncode != 0:
        raise RuntimeError(f'codesign failed: {r.stderr}')
    return app

def _info_plist(mode: str) -> str:
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>CFBundleIdentifier</key><string>{_BUNDLE_ID_PREFIX}{mode}</string>
  <key>CFBundleName</key><string>spaceprobe-postevent-{mode}</string>
  <key>CFBundleExecutable</key><string>stub</string>
  <key>CFBundlePackageType</key><string>APPL</string>
  <key>CFBundleVersion</key><string>1</string>
  <key>LSUIElement</key><true/>
</dict>
</plist>
"""

def _run_stub(mode: str, app: Path) -> str:
    log = Path(f'/tmp/s3_postevent_{mode}.log')
    if log.exists():
        log.unlink()
    _run(['open', '-n', str(app), '--args', mode])
    time.sleep(_RUN_SECONDS)
    text = log.read_text(encoding='utf-8') if log.exists() else '(no log written)'
    return f'### mode {mode}\n\n```\n{text}```\n'

def _cleanup(mode: str) -> str:
    bundle_id = f'{_BUNDLE_ID_PREFIX}{mode}'
    lines = []
    for service in ('PostEvent', 'Accessibility'):
        r = _run(['tccutil', 'reset', service, bundle_id])
        lines.append(f'- tccutil reset {service} {bundle_id}: rc={r.returncode} {r.stdout.strip()} {r.stderr.strip()}')
    return '\n'.join(lines)

def _build_report(sections: list, cleanup_notes: list) -> str:
    lines = ['# s3_postevent_prompt_probe report', '', f'- time: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}',
             '- each stub is an ad-hoc signed accessory-policy NSApplication bundle with its own bundle id, started via `open -n`',
             '- mode main: CGRequestPostEventAccess called from the main thread 1 s after launch; mode bg: from a global dispatch queue',
             '- whether a system prompt appeared is observed by the user, not by this script', '']
    lines.extend(sections)
    lines.append('## Cleanup')
    lines.append('')
    lines.extend(cleanup_notes)
    lines.append('')
    return '\n'.join(lines)

if __name__ == '__main__':
    main()
