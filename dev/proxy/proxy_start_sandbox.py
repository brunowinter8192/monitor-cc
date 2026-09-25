# INFRASTRUCTURE
import difflib
import json
import hashlib
import os
import re
import shutil
import subprocess
import tempfile
import time
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
BASE_REF = '0c837c41'
TOOLS = ['sed', 'tr', 'head', 'tail', 'basename', 'dirname', 'cat', 'find', 'sort', 'ls', 'grep', 'rm', 'mkdir',
         'cp', 'ps', 'stat', 'date', 'pgrep', 'nohup', 'md5', 'python3', 'sleep', 'touch', 'wc']
NEW_SCRIPTS = ['claude_proxy_start.sh', 'proxy_start_janitor.sh', 'proxy_start_markers.sh']
RUN_TIMEOUT_SECONDS = 60
EPOCH_PATTERN = re.compile(r'(?<![0-9])1[0-9]{9}(?![0-9])')
PLUGINS_JSON = '{"plugins": ["iterative-dev"]}'

STUB_MITMDUMP = '''#!/bin/bash
{ echo "ARGS: $*"; echo "ENV: $PROXY_SESSION_ID $PROXY_LOG_ID $PROXY_PROJECT_PATH $MONITOR_CC_ROOT"; } >> "$STUB_OUT/mitm.txt"
[ -n "$STUB_MITM_EXIT" ] && exit "$STUB_MITM_EXIT"
exec sleep 30
'''
STUB_CLAUDE = '''#!/bin/bash
{
  echo "ARGC: $#"
  for a in "$@"; do echo "ARG: $a"; done
  echo "ENV: $HTTPS_PROXY|$NODE_EXTRA_CA_CERTS|$SSL_CERT_FILE|$REQUESTS_CA_BUNDLE"
  echo "PWD: $(pwd -P)"
  echo "PPID: $PPID"
  for f in "$STUB_LOG_DIR"/.proxy_session_*; do [ -f "$f" ] && { echo "MARKER $(basename "$f")"; cat "$f"; }; done
  [ -f "$STUB_TMP_MARKER" ] && { echo "TMPMARKER"; cat "$STUB_TMP_MARKER"; }
  echo "LIVE: $(ls -A "$STUB_LOG_DIR" | grep -c '^\\.proxy_addon_live_')"
} >> "$STUB_OUT/claude.txt"
exit 0
'''
STUB_LSOF = '''#!/bin/bash
for p in $STUB_BUSY; do
  case "$*" in *"TCP:$p "*) exit 0 ;; esac
done
exit 1
'''
STUB_WORKER_CLI = '#!/bin/bash\nexit 0\n'


# FUNCTIONS
def make_case_dir() -> Path:
    return Path(tempfile.mkdtemp(prefix='mc6a_case_')).resolve()


def build_stub_bin(bin_dir: Path, with_jq: bool) -> None:
    bin_dir.mkdir(parents=True)
    names = TOOLS + (['jq'] if with_jq else [])
    for name in names:
        target = shutil.which(name)
        if target is None:
            raise RuntimeError(f'tool missing for sandbox: {name}')
        (bin_dir / name).symlink_to(target)
    for name, body in [('mitmdump', STUB_MITMDUMP), ('claude', STUB_CLAUDE), ('lsof', STUB_LSOF), ('worker-cli', STUB_WORKER_CLI)]:
        (bin_dir / name).write_text(body)
        (bin_dir / name).chmod(0o755)


def build_root(root: Path, variant: str) -> Path:
    src = root / 'src'
    src.mkdir(parents=True)
    shutil.copy(REPO_ROOT / 'src' / 'proxy_addon.py', src / 'proxy_addon.py')
    shutil.copytree(REPO_ROOT / 'src' / 'proxy', src / 'proxy', ignore=shutil.ignore_patterns('__pycache__'))
    if variant == 'old':
        text = subprocess.run(['git', '-C', str(REPO_ROOT), 'show', f'{BASE_REF}:src/claude_proxy_start.sh'],
                              capture_output=True, text=True, check=True).stdout
        (src / 'claude_proxy_start.sh').write_text(text)
    else:
        for name in NEW_SCRIPTS:
            shutil.copy(REPO_ROOT / 'src' / name, src / name)
    return src / 'claude_proxy_start.sh'


def build_home(home: Path, spec: dict) -> None:
    ca_dir = home / '.mitmproxy'
    ca_dir.mkdir(parents=True)
    if spec.get('ca', True):
        (ca_dir / 'mitmproxy-ca-cert.pem').write_text('CA-FIXTURE\n')
    config = spec.get('config')
    if config is not None:
        path = home / '.claude' / 'shared-rules' / 'model_selection.json'
        path.parent.mkdir(parents=True)
        path.write_text(config)
        if spec.get('config_unreadable'):
            path.chmod(0)
    claude_bin = home / '.local' / 'bin' / 'claude-280'
    claude_bin.parent.mkdir(parents=True)
    claude_bin.symlink_to(home.parent / 'bin' / 'claude')


def tmp_marker_path(project: Path) -> Path:
    normalized = os.path.normpath(str(project))
    digest = hashlib.md5(normalized.encode()).hexdigest()[:8]
    return Path(f'/tmp/.monitor_cc_proxy_{digest}')


def session_id(project: Path) -> str:
    return tmp_marker_path(project).name.rsplit('_', 1)[1]


def seed_janitor_fixture(log_dir: Path) -> None:
    dual = log_dir / 'dual_log'
    dual.mkdir(parents=True)
    now = time.time()
    old = now - 5 * 3600
    for i in range(20):
        touch(dual / f'api_requests_opus_stale_{i:02d}_original.jsonl', old - i)
        touch(dual / f'api_requests_opus_stale_{i:02d}_forwarded.jsonl', old - i)
    for i in range(40):
        touch(dual / f'api_requests_opus_fresh_{i:02d}_original.jsonl', now - 100 - i * 2)
        touch(dual / f'api_requests_opus_fresh_{i:02d}_forwarded.jsonl', now - 100 - i * 2)
        touch(dual / f'api_requests_opus_fresh_{i:02d}_errors.jsonl', now - 100 - i * 2)
    for i in range(32):
        touch(dual / f'api_requests_worker_w{i:02d}_original.jsonl', now - 300 - i * 2)
        touch(dual / f'api_requests_worker_w{i:02d}_response.jsonl', now - 300 - i * 2)
    touch(dual / 'api_requests_opus_orphan_9_forwarded.jsonl', now - 50)
    (dual / '.proxy_version').write_text('stale-hash\n')
    for name in ['api_error_payload_1.json', 'proxy_errors_x.log', 'tool_use_errors.jsonl', 'keep_me.txt']:
        touch(log_dir / name, now)
    touch(log_dir / '.proxy_addon_live_abc_1_2.py', now)
    (log_dir / '.proxy_live_abc_1_2').mkdir()
    (log_dir / '.proxy_live_zzz').mkdir()


def touch(path: Path, mtime: float) -> None:
    path.write_text('x\n')
    os.utime(path, (mtime, mtime))


def spawn_live_identity_process() -> subprocess.Popen:
    return subprocess.Popen(['bash', '-c', 'exec -a claude_proxy_start.sh sleep 60'])


def seed_marker(spec: dict, root: Path, project: Path, live_pid: int) -> None:
    log_dir = root / 'src' / 'logs'
    log_dir.mkdir(parents=True, exist_ok=True)
    sid = session_id(project)
    kind = spec.get('marker')
    if kind is None:
        return
    pid = live_pid if kind == 'live' else 999999
    dual = log_dir / 'dual_log'
    dual.mkdir(exist_ok=True)
    touch(dual / 'api_requests_opus_existing_1_forwarded.jsonl', time.time())
    (log_dir / f'.proxy_session_{sid}').write_text(f'9999\nopus_existing_1\n{pid}\n')
    if spec.get('tmp_marker'):
        tmp_marker_path(project).write_text(f'9999\nopus_existing_1\n/elsewhere\n{pid}\n')


def run_variant(variant: str, spec: dict, case_dir: Path, project: Path) -> dict:
    vdir = case_dir / variant
    script = build_root(vdir / 'root', variant)
    (vdir / 'bin').parent.mkdir(exist_ok=True)
    build_stub_bin(vdir / 'bin', spec.get('jq', True))
    home = vdir / 'home'
    build_home(home, spec)
    out = vdir / 'out'
    out.mkdir()
    shutil.rmtree(project / '.claude', ignore_errors=True)
    live = spawn_live_identity_process()
    try:
        if spec.get('janitor'):
            seed_janitor_fixture(vdir / 'root' / 'src' / 'logs')
        seed_marker(spec, vdir / 'root', project, live.pid)
        env = {'HOME': str(home), 'PATH': str(vdir / 'bin'), 'STUB_OUT': str(out),
               'STUB_LOG_DIR': str(vdir / 'root' / 'src' / 'logs'), 'STUB_TMP_MARKER': str(tmp_marker_path(project)),
               'STUB_BUSY': spec.get('busy', ''), 'STUB_MITM_EXIT': spec.get('mitm_exit', ''),
               'CLAUDE_BIN': str(vdir / 'bin' / 'claude')}
        proc = subprocess.Popen(['/bin/bash', str(script), *spec.get('args', [])], cwd=project, env=env,
                                stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        stdout, stderr = proc.communicate(timeout=RUN_TIMEOUT_SECONDS)
        result = snapshot(vdir, project, out, stdout, stderr, proc.returncode, proc.pid, live.pid)
    finally:
        live.kill()
        live.wait()
        tmp_marker_path(project).unlink(missing_ok=True)
    return result


def snapshot(vdir: Path, project: Path, out: Path, stdout: str, stderr: str, returncode: int, script_pid: int, live_pid: int) -> dict:
    log_dir = vdir / 'root' / 'src' / 'logs'
    tree = {}
    for path in sorted(log_dir.rglob('*')):
        rel = str(path.relative_to(log_dir))
        tree[rel] = path.read_text() if path.is_file() and path.stat().st_size < 200 else ''
    plugins = project / '.claude' / 'active_plugins.json'
    combined = vdir / 'home' / '.mitmproxy' / 'combined-ca.pem'
    raw = {
        'returncode': returncode, 'stdout': stdout, 'stderr': stderr,
        'claude': read_or_empty(out / 'claude.txt'), 'mitm': read_or_empty(out / 'mitm.txt'),
        'tree': tree, 'plugins': plugins.read_text().strip() if plugins.exists() else None,
        'combined_ca_exists': combined.exists(),
        'tmp_marker_left': tmp_marker_path(project).exists(),
    }
    return normalize(raw, vdir, project, script_pid, live_pid)


def read_or_empty(path: Path) -> str:
    return path.read_text() if path.exists() else ''


def normalize(value, vdir: Path, project: Path, script_pid: int, live_pid: int):
    if isinstance(value, dict):
        return {normalize(k, vdir, project, script_pid, live_pid): normalize(v, vdir, project, script_pid, live_pid) for k, v in value.items()}
    if isinstance(value, str):
        text = value.replace(str(vdir), '<VARIANT>')
        text = re.sub(rf'(?<![0-9]){script_pid}(?![0-9])', '<PID>', text)
        text = re.sub(rf'(?<![0-9]){live_pid}(?![0-9])', '<LIVEPID>', text)
        return EPOCH_PATTERN.sub('<EPOCH>', text)
    return value


def drop_launcher_log_lines(result: dict) -> dict:
    kept = [l for l in result['stderr'].splitlines() if not l.startswith('claude_proxy_start:')]
    return {**result, 'stderr': '\n'.join(kept)}


def diff_report(old: dict, new: dict) -> str:
    a = json.dumps(old, indent=1, sort_keys=True).splitlines()
    b = json.dumps(new, indent=1, sort_keys=True).splitlines()
    return '\n'.join(difflib.unified_diff(a, b, 'old', 'new', lineterm=''))
