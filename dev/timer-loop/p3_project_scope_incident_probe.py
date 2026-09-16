# INFRASTRUCTURE
import json
import os
import subprocess
import sys
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest import mock

WORKTREE_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(WORKTREE_ROOT / 'src'))
sys.path.insert(0, str(WORKTREE_ROOT / 'src' / 'hooks'))

HOOK_PATH = str(WORKTREE_ROOT / "src" / "hooks" / "block_timer_pending_bg.py")
REPORT_DIR = Path(__file__).parent / 'md'
REPORT_PATH = REPORT_DIR / 'p3_project_scope_incident_probe_report.md'

_TARGET = "sleep 3300 && echo done"
_RESULTS = []


def check(label, condition):
    _RESULTS.append((label, bool(condition)))
    print(f"  {'PASS' if condition else 'FAIL'}  {label}")
    return condition


def _iso(dt):
    return dt.strftime('%Y-%m-%dT%H:%M:%S.') + f'{dt.microsecond // 1000:03d}Z'


# FUNCTIONS

def _run_hook(command, run_in_background, tmp_root, cwd):
    payload = json.dumps({
        "tool_name": "Bash", "session_id": "incident-probe",
        "tool_input": {"command": command, "run_in_background": run_in_background},
    })
    env = dict(os.environ)
    env["MONITOR_CC_ROOT"] = tmp_root
    result = subprocess.run(
        [sys.executable, HOOK_PATH], input=payload.encode(), capture_output=True, cwd=cwd, env=env,
    )
    return result.returncode, result.stderr.decode()


def _seed_state(tmp_root, state):
    state_path = Path(tmp_root) / "src" / "logs" / "pending_bg_tasks.json"
    state_path.parent.mkdir(parents=True, exist_ok=True)
    state_path.write_text(json.dumps(state), encoding="utf-8")


def test_incident_foreign_project_now_allows():
    print("\n[Test 1] Incident replay — posts-project pending, websearch cwd -> now ALLOWS")
    now = datetime.now(timezone.utc)
    fresh_ts = _iso(now - timedelta(minutes=5))
    with tempfile.TemporaryDirectory() as tmp_root, tempfile.TemporaryDirectory() as outer:
        ws_cwd = Path(outer) / "Websearch"
        ws_cwd.mkdir()
        _seed_state(tmp_root, {"b4z5fzzao": {"status": "pending", "armed_at": fresh_ts, "project": "posts"}})
        code, stderr = _run_hook(_TARGET, True, tmp_root, str(ws_cwd))
        check("posts pending entry + websearch cwd -> exit 0 (allow)", code == 0)
        check("no stderr on allow", stderr == "")


def test_same_project_still_blocks():
    print("\n[Test 2] Same-project pending still blocks")
    now = datetime.now(timezone.utc)
    fresh_ts = _iso(now - timedelta(minutes=5))
    with tempfile.TemporaryDirectory() as tmp_root, tempfile.TemporaryDirectory() as outer:
        ws_cwd = Path(outer) / "Websearch"
        ws_cwd.mkdir()
        _seed_state(tmp_root, {"ws_pending": {"status": "pending", "armed_at": fresh_ts, "project": "websearch"}})
        code, stderr = _run_hook(_TARGET, True, tmp_root, str(ws_cwd))
        check("websearch pending entry + websearch cwd -> exit 2 (block)", code == 2)
        check("block message names the id", "ws_pending" in stderr)


def test_legacy_entry_blocks_everyone():
    print("\n[Test 3] Legacy no-project entry blocks every project")
    now = datetime.now(timezone.utc)
    fresh_ts = _iso(now - timedelta(minutes=5))
    with tempfile.TemporaryDirectory() as tmp_root, tempfile.TemporaryDirectory() as outer:
        ws_cwd = Path(outer) / "Websearch"
        ws_cwd.mkdir()
        _seed_state(tmp_root, {"legacy": {"status": "pending", "armed_at": fresh_ts}})
        code, stderr = _run_hook(_TARGET, True, tmp_root, str(ws_cwd))
        check("legacy entry (pre-migration, no project field) -> exit 2 (block)", code == 2)
    with tempfile.TemporaryDirectory() as tmp_root, tempfile.TemporaryDirectory() as outer:
        posts_cwd = Path(outer) / "Posts"
        posts_cwd.mkdir()
        _seed_state(tmp_root, {"legacy": {"status": "pending", "armed_at": fresh_ts}})
        code, stderr = _run_hook(_TARGET, True, tmp_root, str(posts_cwd))
        check("same legacy entry, different cwd (Posts) -> also exit 2 (blocks every project)", code == 2)


def test_expired_entry_allows_regardless_of_project():
    print("\n[Test 4] Expired entry allows regardless of project match")
    now = datetime.now(timezone.utc)
    stale_ts = _iso(now - timedelta(hours=2))
    with tempfile.TemporaryDirectory() as tmp_root, tempfile.TemporaryDirectory() as outer:
        ws_cwd = Path(outer) / "Websearch"
        ws_cwd.mkdir()
        _seed_state(tmp_root, {"stale_ws": {"status": "pending", "armed_at": stale_ts, "project": "websearch"}})
        code, stderr = _run_hook(_TARGET, True, tmp_root, str(ws_cwd))
        check("expired same-project entry -> exit 0 (allow)", code == 0 and stderr == "")


class _FakeHeaders(dict):
    def get(self, k, default=None):
        return super().get(k.lower(), default) if isinstance(k, str) else default

    def pop(self, k, default=None):
        return dict.pop(self, k.lower(), default)


class _FakeRequest:
    def __init__(self, payload):
        self.method = "POST"
        self.pretty_host = "api.anthropic.com"
        self.path = "/v1/messages"
        self.headers = _FakeHeaders()
        self.content = json.dumps(payload).encode("utf-8")


class _FakeFlow:
    def __init__(self, payload):
        self.request = _FakeRequest(payload)
        self.metadata = {}
        self.id = "fake-flow-id"


def _ack_text(task_id):
    return (
        f"Command running in background with ID: {task_id}. "
        f"Output is being written to: /tmp/output_{task_id}.txt. "
        "You will be notified when it completes. "
        "To check interim output, use Read on that file path."
    )


def _payload_with_user_text(text):
    return {
        "model": "claude-opus-4-6", "max_tokens": 8000,
        "system": [{"type": "text", "text": "sys0"},
                   {"type": "text", "text": "You are Claude Code, Anthropic's official CLI for Claude."},
                   {"type": "text", "text": "sys2"}],
        "messages": [{"role": "user", "content": text}], "tools": [],
    }


def test_writer_stamps_project_e2e():
    print("\n[Test 5] Writer side — real ProxyAddon.request() stamps project")
    from proxy.pending_bg_state import _read_state_file, _resolve_pending_bg_state_file
    from proxy.addon import ProxyAddon, _derive_worker_context

    with tempfile.TemporaryDirectory() as tmp_root:
        with mock.patch.dict(os.environ, {"PROXY_LOG_ID": "opus_websearch_1786100000",
                                           "PROXY_PROJECT_PATH": "/Users/x/Websearch",
                                           "MONITOR_CC_ROOT": tmp_root}, clear=False):
            addon = ProxyAddon()
            addon.identity.worker_context = _derive_worker_context()
            addon.request(_FakeFlow(_payload_with_user_text(_ack_text("incident_e2e"))))
            state = _read_state_file()
        check("armed entry has project == 'websearch' (from PROXY_PROJECT_PATH=/Users/x/Websearch)",
              state.get("incident_e2e", {}).get("project") == "websearch")


# ORCHESTRATOR
def run_probe_workflow() -> bool:
    print("=" * 70)
    print("P3 — cross-project false-block incident replay (2026-08-07 websearch/posts)")
    print("=" * 70)
    test_incident_foreign_project_now_allows()
    test_same_project_still_blocks()
    test_legacy_entry_blocks_everyone()
    test_expired_entry_allows_regardless_of_project()
    test_writer_stamps_project_e2e()

    total = len(_RESULTS)
    passed = sum(1 for _, ok in _RESULTS if ok)
    print("\n" + "=" * 70)
    print(f"{passed}/{total} checks passed")
    print("=" * 70)
    _write_report(passed, total)
    return passed == total


def _write_report(passed, total):
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    lines = [
        '# P3 — project-scoped timer incident probe',
        '',
        'Replays the 2026-08-07 ~01:10 cross-project false-block incident (websearch main session '
        'blocked by a POSTS-project pending entry, task `b4z5fzzao`) through the real '
        '`block_timer_pending_bg.py` hook via subprocess, plus the writer-side '
        '`src/proxy/pending_bg_state.py` stamping via a real `ProxyAddon.request()` call.',
        '',
        f'**Result: {passed}/{total} checks passed**',
        '',
        '| Check | Result |',
        '|---|---|',
    ]
    for label, ok in _RESULTS:
        lines.append(f"| {label} | {'PASS' if ok else 'FAIL'} |")
    REPORT_PATH.write_text('\n'.join(lines) + '\n')
    print(f'\nReport written to: {REPORT_PATH}')


if __name__ == '__main__':
    ok = run_probe_workflow()
    sys.exit(0 if ok else 1)
