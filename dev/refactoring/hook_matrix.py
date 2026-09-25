# INFRASTRUCTURE
import json
import os
import subprocess
import sys
import tempfile
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

_MAX_LOG_COMMANDS = 400
_EXCLUDED_HOOKS = ('hook_setup.py', 'block_rag_cli_document_repeat.py')
_SYNTHETIC_COMMANDS = [
    'git commit --amend -m x', 'git push --force origin main', 'git config user.name x', 'git config --list',
    'find / -name "*.py"', 'grep -r foo /', 'sleep 5 && echo done', 'sleep 3; ls', 'while true; do ls; done',
    'kill -9 1234', 'pkill -f python', 'cd /tmp && ls', 'rag-cli index docs /tmp/x', 'rag-cli search q col-docs',
    'worker-cli send w1 "hi"', 'worker-cli wait w1', 'cat /tmp/a.py | scraper', 'gh api repos/x/y', 'ls',
    'python3 -c "print(1)"', 'venv/bin/python x.py', './venv/bin/python x.py > /tmp/o.txt 2>&1',
    'git add node_modules', 'git add -A', 'echo hi &', 'nohup sleep 100 &', 'rm -rf /tmp/x', 'cat process-docs/a.md',
    'poread /tmp/x', 'search-reddit --limit 500', 'git worktree remove x', 'tmux kill-session -t x',
]
_SYNTHETIC_FILE_PAYLOADS = [
    {'tool_name': 'Read', 'tool_input': {'file_path': '/tmp'}},
    {'tool_name': 'Read', 'tool_input': {'file_path': '/etc/hosts'}},
    {'tool_name': 'Edit', 'tool_input': {'file_path': '/tmp/a.py', 'old_string': 'x', 'new_string': 'x'}},
    {'tool_name': 'Edit', 'tool_input': {'file_path': '/tmp/a.py', 'old_string': 'x', 'new_string': 'y'}},
    {'tool_name': 'Write', 'tool_input': {'file_path': '/tmp/dev/a.py', 'content': 'from src.x import y\n'}},
    {'tool_name': 'Write', 'tool_input': {'file_path': '/tmp/a.py', 'content': 'try:\n    x()\nexcept Exception:\n    pass\n'}},
    {'tool_name': 'Grep', 'tool_input': {'pattern': 'foo', 'path': '/'}},
    {'tool_name': 'mcp__x__y', 'tool_input': {}},
]


# ORCHESTRATOR

def hook_matrix_workflow() -> None:
    root, snapshot_log, out_path = _parse_args()
    payloads = _build_payloads(snapshot_log)
    hooks = _list_hooks(root)
    lines = _run_matrix(hooks, payloads)
    _write_report(lines, out_path)
    _print_counts(hooks, payloads, lines)


# FUNCTIONS

def _parse_args() -> tuple:
    return Path(sys.argv[1]).resolve(), Path(sys.argv[2]), Path(sys.argv[3])


def _build_payloads(snapshot_log: Path) -> list:
    commands = sorted({json.loads(line)['command'] for line in snapshot_log.read_text().splitlines() if line.strip()})
    commands = commands[:_MAX_LOG_COMMANDS] + _SYNTHETIC_COMMANDS
    payloads = [{'tool_name': 'Bash', 'tool_input': {'command': c}, 'session_id': 'matrix', 'cwd': '/tmp'} for c in commands]
    return payloads + [{**p, 'session_id': 'matrix', 'cwd': '/tmp'} for p in _SYNTHETIC_FILE_PAYLOADS]


def _list_hooks(root: Path) -> list:
    return sorted(p for p in (root / 'src' / 'hooks').glob('*.py') if p.name not in _EXCLUDED_HOOKS and not p.name.startswith('_'))


def _run_matrix(hooks: list, payloads: list) -> list:
    jobs = [(hook, index, payload) for hook in hooks for index, payload in enumerate(payloads)]
    with ThreadPoolExecutor(max_workers=24) as pool:
        return list(pool.map(_run_job, jobs))


def _run_job(job: tuple) -> str:
    hook, index, payload = job
    with tempfile.TemporaryDirectory() as tmp:
        log_path = Path(tmp) / 'fire.jsonl'
        _write_decoy_src(Path(tmp))
        env = {**os.environ, 'MONITOR_CC_HOOK_FIRING_LOG': str(log_path)}
        proc = subprocess.run([_interpreter(), str(hook)], input=json.dumps(payload), capture_output=True, text=True, cwd=tmp, env=env, timeout=60)
        fired = _normalized_log(log_path)
    record = {'rc': proc.returncode, 'out': proc.stdout, 'err': proc.stderr, 'log': fired}
    return f'{hook.name}\t{index}\t{json.dumps(record, sort_keys=True)}'


def _write_decoy_src(cwd: Path) -> None:
    (cwd / 'src' / 'hooks').mkdir(parents=True)
    (cwd / 'src' / '__init__.py').write_text('')
    (cwd / 'src' / 'hooks' / '_fire_log.py').write_text('raise RuntimeError("decoy src imported from cwd")\n')


def _interpreter() -> str:
    return os.environ.get('MATRIX_PYTHON', sys.executable)


def _normalized_log(log_path: Path) -> list:
    if not log_path.exists():
        return []
    records = [json.loads(line) for line in log_path.read_text().splitlines() if line.strip()]
    for record in records:
        record.pop('ts', None)
        record['reason'] = record.get('reason', '').replace('/private', '')
    return records


def _write_report(lines: list, out_path: Path) -> None:
    out_path.write_text('\n'.join(sorted(lines)) + '\n')


def _print_counts(hooks: list, payloads: list, lines: list) -> None:
    print(f'hooks={len(hooks)} payloads={len(payloads)} runs={len(lines)}')


if __name__ == '__main__':
    hook_matrix_workflow()
