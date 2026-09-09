"""
P2 — verifies the launch-ack-triggered tmux-Escape mechanism (src/proxy/bg_escape.py).

Covers: dedup-by-task-id across repeated acks (real 142/169 shape), two-distinct-ids → two
sends, both CC ack wordings, main-context never fires, tmux session name derivation (incl.
hyphenated worker names), a real tmux round trip, and failure isolation (dead session, missing
tmux binary — both at the unit level and through the real ProxyAddon.request() path).

Run from project root or worktree root:
    ./venv/bin/python dev/bg_wakeup_id_line/p2_bg_escape_probe.py
"""

# INFRASTRUCTURE
import json
import os
import subprocess
import sys
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path
from unittest import mock

WORKTREE_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(WORKTREE_ROOT / 'src'))

from proxy import bg_escape
from proxy.bg_escape import (
    _trigger_bg_escape, _extract_task_id, _derive_tmux_session_name, _send_escape_key,
)
from proxy.addon import ProxyAddon, _derive_worker_context

_PASS = "\033[32mPASS\033[0m"
_FAIL = "\033[31mFAIL\033[0m"

_RESULTS = []


def check(label, condition):
    _RESULTS.append((label, bool(condition)))
    print(f"  {_PASS if condition else _FAIL}  {label}")
    return condition


_WORDING_1 = (
    "Command running in background with ID: bg_task_alpha. "
    "Output is being written to: /tmp/output_alpha.txt. "
    "You will be notified when it completes. "
    "To check interim output, use Read on that file path."
)
_WORDING_2 = (
    "Command was manually backgrounded by user with ID: bg_task_beta. "
    "Output is being written to: /tmp/output_beta.txt"
)


# FUNCTIONS

# Test 1 — dedup across repeated acks: the SAME ack (same task id) fed across 169 simulated
# requests (142 carrying the ack, real 142/169 shape) fires the Escape exactly once.
def test_dedup_repeated_acks():
    print("\n[Test 1] Dedup across repeated acks (142/169 real shape)")
    bg_escape._escaped_task_ids.clear()
    sent_calls = []
    with mock.patch.object(bg_escape, "_send_escape_key", lambda s: sent_calls.append(s) or True):
        carrying = [True] * 142 + [False] * 27
        for has_ack in carrying:
            removed = {0: [_WORDING_1]} if has_ack else {0: ["unrelated tool_result content"]}
            _trigger_bg_escape(removed, "worker:esc-live", str(WORKTREE_ROOT))
    check("169 simulated requests, 142 carrying the ack → exactly 1 Escape sent", len(sent_calls) == 1)
    check("task id recorded in dedup store after firing", "bg_task_alpha" in bg_escape._escaped_task_ids)


# Test 2 — two distinct task ids → two Escapes.
def test_two_distinct_ids():
    print("\n[Test 2] Two distinct task ids")
    bg_escape._escaped_task_ids.clear()
    sent_calls = []
    with mock.patch.object(bg_escape, "_send_escape_key", lambda s: sent_calls.append(s) or True):
        ack_gamma = _WORDING_1.replace("bg_task_alpha", "bg_task_gamma")
        ack_delta = _WORDING_1.replace("bg_task_alpha", "bg_task_delta")
        for ack in [ack_gamma, ack_gamma, ack_delta, ack_gamma, ack_delta]:
            _trigger_bg_escape({0: [ack]}, "worker:esc-live", str(WORKTREE_ROOT))
    check("2 distinct task ids across 5 repeated calls → exactly 2 Escapes", len(sent_calls) == 2)


# Test 3 — both CC wordings trigger.
def test_both_wordings_trigger():
    print("\n[Test 3] Both CC wordings trigger")
    bg_escape._escaped_task_ids.clear()
    sent_calls = []
    with mock.patch.object(bg_escape, "_send_escape_key", lambda s: sent_calls.append(s) or True):
        _trigger_bg_escape({0: [_WORDING_1]}, "worker:esc-live", str(WORKTREE_ROOT))
        _trigger_bg_escape({0: [_WORDING_2]}, "worker:esc-live", str(WORKTREE_ROOT))
    check("wording 1 ('running in background with ID') triggers", "bg_task_alpha" in bg_escape._escaped_task_ids)
    check("wording 2 ('manually backgrounded by user with ID') triggers", "bg_task_beta" in bg_escape._escaped_task_ids)
    check("both wordings together fired 2 sends", len(sent_calls) == 2)


# Test 4 — main context never triggers.
def test_main_context_never_triggers():
    print("\n[Test 4] main context never triggers")
    bg_escape._escaped_task_ids.clear()
    sent_calls = []
    with mock.patch.object(bg_escape, "_send_escape_key", lambda s: sent_calls.append(s) or True):
        _trigger_bg_escape({0: [_WORDING_1]}, "main", str(WORKTREE_ROOT))
        _trigger_bg_escape({0: [_WORDING_2]}, "main", str(WORKTREE_ROOT))
    check("main context + genuine ack (both wordings) → 0 Escapes sent", len(sent_calls) == 0)
    check("_derive_tmux_session_name('main', ...) returns empty", _derive_tmux_session_name("main", str(WORKTREE_ROOT)) == "")


# Test 5 — tmux session name derivation from PROXY_LOG_ID + PROXY_PROJECT_PATH, including a
# hyphenated worker name.
def test_tmux_session_name_derivation():
    print("\n[Test 5] tmux session name derivation")
    cases = [
        ("worker_25c51a2e_esc-live_1785424292", "/Users/brunowinter2000/Documents/ai/monitor-cc",
         "worker-monitor-cc-esc-live"),
        ("worker_25c51a2e_bg-ack-shapes_1785359201", "/Users/brunowinter2000/Documents/ai/monitor-cc",
         "worker-monitor-cc-bg-ack-shapes"),
    ]
    for log_id, project_path, expected in cases:
        with mock.patch.dict(os.environ, {"PROXY_LOG_ID": log_id, "PROXY_PROJECT_PATH": project_path}, clear=False):
            worker_context = _derive_worker_context()
            derived = _derive_tmux_session_name(worker_context, project_path)
        check(f"{log_id} -> worker_context={worker_context!r}", worker_context == f"worker:{log_id.split('_', 2)[2].rsplit('_', 1)[0]}")
        check(f"{log_id} + {os.path.basename(project_path)} -> tmux session {expected!r}", derived == expected)
    with mock.patch.dict(os.environ, {"PROXY_LOG_ID": "opus_monitor_cc_1785336796", "PROXY_PROJECT_PATH": "/x/monitor-cc"}, clear=False):
        main_ctx = _derive_worker_context()
    check("non-worker PROXY_LOG_ID -> worker_context='main'", main_ctx == "main")
    check("'main' context -> no tmux session derivable", _derive_tmux_session_name(main_ctx, "/x/monitor-cc") == "")


# Test 5b — a fire writes one JSONL trace line to bg_escape_events.jsonl (MONITOR_CC_ROOT-scoped),
# carrying task id, derived tmux session, and the send result — the trace the rolled-back menubar
# mechanism had and this one lacked until now.
def test_fire_writes_log_line():
    print("\n[Test 5b] Fire writes a log line (task id, tmux session, send result)")
    bg_escape._escaped_task_ids.clear()
    with tempfile.TemporaryDirectory() as tmp_root:
        log_path = Path(tmp_root) / "src" / "logs" / "bg_escape_events.jsonl"
        ack = _WORDING_1.replace("bg_task_alpha", "bg_task_epsilon")
        with mock.patch.dict(os.environ, {"MONITOR_CC_ROOT": tmp_root}, clear=False):
            with mock.patch.object(bg_escape, "_send_escape_key", lambda s: True):
                _trigger_bg_escape({0: [ack]}, "worker:esc-live", str(WORKTREE_ROOT))
        check("bg_escape_events.jsonl created under MONITOR_CC_ROOT/src/logs/", log_path.exists())
        lines = log_path.read_text().strip().splitlines() if log_path.exists() else []
        check("exactly one log line written for the fire", len(lines) == 1)
        entry = json.loads(lines[0]) if lines else {}
        check("logged event == 'fired'", entry.get("event") == "fired")
        check("logged task_id == 'bg_task_epsilon'", entry.get("task_id") == "bg_task_epsilon")
        check("logged tmux_session == expected worker session", entry.get("tmux_session") == f"worker-{WORKTREE_ROOT.name}-esc-live")
        check("logged send_result == True", entry.get("send_result") is True)

    # Same request-shape, main context this time — this IS a matter-of skip case, so it must ALSO
    # log (not silently no-op), reason == 'main_context'.
    with tempfile.TemporaryDirectory() as tmp_root:
        log_path = Path(tmp_root) / "src" / "logs" / "bg_escape_events.jsonl"
        ack = _WORDING_1.replace("bg_task_alpha", "bg_task_zeta")
        with mock.patch.dict(os.environ, {"MONITOR_CC_ROOT": tmp_root}, clear=False):
            _trigger_bg_escape({0: [ack]}, "main", str(WORKTREE_ROOT))
        entry = json.loads(log_path.read_text().strip().splitlines()[0]) if log_path.exists() else {}
        check("main-context skip logs event='skipped' reason='main_context'",
              entry.get("event") == "skipped" and entry.get("reason") == "main_context")

    # A request with no bg-launch-ack chunk at all must never touch the log sink.
    with tempfile.TemporaryDirectory() as tmp_root:
        log_path = Path(tmp_root) / "src" / "logs" / "bg_escape_events.jsonl"
        with mock.patch.dict(os.environ, {"MONITOR_CC_ROOT": tmp_root}, clear=False):
            _trigger_bg_escape({0: ["ordinary tool_result content, no ack here"]}, "worker:esc-live", str(WORKTREE_ROOT))
        check("no ack present -> log sink never touched (no file created)", not log_path.exists())


# Test 6 — real tmux round trip: spawn a throwaway session running a raw-mode 1-byte reader,
# call the PRODUCTION _send_escape_key against it, confirm the Escape byte (0x1b) arrived via
# capture-pane.
def test_real_tmux_roundtrip():
    print("\n[Test 6] Real tmux round trip")
    session = f"__bg_escape_probe_{int(time.time())}"
    reader_script = tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False)
    reader_script.write(
        "import sys, tty, termios\n"
        "fd = sys.stdin.fileno()\n"
        "old = termios.tcgetattr(fd)\n"
        "tty.setcbreak(fd)\n"
        "b = sys.stdin.read(1)\n"
        "termios.tcsetattr(fd, termios.TCSADRAIN, old)\n"
        "print('GOT_BYTE:' + repr(b))\n"
        "sys.stdout.flush()\n"
    )
    reader_script.close()
    try:
        subprocess.run(["tmux", "kill-session", "-t", session], capture_output=True)
        create = subprocess.run(
            ["tmux", "new-session", "-d", "-s", session, f"python3 {reader_script.name}; sleep 5"],
            capture_output=True, timeout=5,
        )
        check("tmux new-session for the reader pane succeeded", create.returncode == 0)
        time.sleep(0.5)
        exists_before = subprocess.run(["tmux", "has-session", "-t", session], capture_output=True).returncode == 0
        check("session exists before the send", exists_before)

        sent = _send_escape_key(session)  # the PRODUCTION function, not a re-implementation
        check("_send_escape_key() reports success", sent is True)
        time.sleep(0.5)

        pane = subprocess.run(["tmux", "capture-pane", "-p", "-t", session], capture_output=True, text=True)
        arrived = "GOT_BYTE:" in pane.stdout and repr(chr(0x1b)) in pane.stdout
        check("capture-pane shows the reader received the Escape byte (0x1b)", arrived)
    finally:
        subprocess.run(["tmux", "kill-session", "-t", session], capture_output=True)
        os.unlink(reader_script.name)


# Test 7 — failure isolation: dead/missing tmux session and a missing tmux binary must not raise,
# and the real ProxyAddon.request() path must still complete (forward the request) when the
# tmux binary itself is absent.
def test_failure_isolation():
    print("\n[Test 7] Failure isolation")
    dead_session = "__bg_escape_probe_definitely_does_not_exist__"
    subprocess.run(["tmux", "kill-session", "-t", dead_session], capture_output=True)
    try:
        result = _send_escape_key(dead_session)
        check("dead/missing tmux session -> _send_escape_key returns False, no raise", result is False)
    except Exception as e:
        check(f"dead/missing tmux session -> _send_escape_key returns False, no raise (raised {e!r})", False)

    with mock.patch.object(bg_escape.subprocess, "run", side_effect=FileNotFoundError("no such file: tmux")):
        try:
            result = _send_escape_key("any-session")
            check("missing tmux binary -> _send_escape_key returns False, no raise", result is False)
        except Exception as e:
            check(f"missing tmux binary -> _send_escape_key returns False, no raise (raised {e!r})", False)

    # Entry-point level: real ProxyAddon.request() with a payload carrying a genuine ack, tmux
    # binary simulated absent — the request must still forward (flow.request.content gets set).
    flow = _build_fake_flow_with_ack()
    addon = ProxyAddon()
    with mock.patch.dict(os.environ, {"PROXY_LOG_ID": "worker_deadbeef_isolation-check_1785000000",
                                       "PROXY_PROJECT_PATH": str(WORKTREE_ROOT)}, clear=False):
        addon.identity.worker_context = _derive_worker_context()
        with mock.patch.object(bg_escape.subprocess, "run", side_effect=FileNotFoundError("no such file: tmux")):
            addon.request(flow)
    check("real ProxyAddon.request() still forwards (flow.request.content set) with tmux binary absent",
          flow.request.content is not None and len(flow.request.content) > 0)


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


# Minimal real-shaped payload whose user turn carries a genuine bg-launch ack tool_result block —
# exercises the real apply_modification_rules -> _trigger_bg_escape wiring end to end.
def _build_fake_flow_with_ack():
    payload = {
        "model": "claude-opus-4-6",
        "max_tokens": 8000,
        "system": [
            {"type": "text", "text": "sys0"},
            {"type": "text", "text": "You are Claude Code, Anthropic's official CLI for Claude."},
            {"type": "text", "text": "sys2"},
        ],
        "messages": [
            {"role": "user", "content": [
                {"type": "tool_result", "tool_use_id": "toolu_01", "content": _WORDING_1},
            ]},
        ],
        "tools": [],
    }
    return _FakeFlow(payload)


# ORCHESTRATOR

def run_probe_workflow():
    print("=" * 70)
    print("bg_escape probe — tmux-Escape-on-launch-ack mechanism")
    print("=" * 70)
    test_dedup_repeated_acks()
    test_two_distinct_ids()
    test_both_wordings_trigger()
    test_main_context_never_triggers()
    test_tmux_session_name_derivation()
    test_fire_writes_log_line()
    test_real_tmux_roundtrip()
    test_failure_isolation()

    total = len(_RESULTS)
    passed = sum(1 for _, ok in _RESULTS if ok)
    print("\n" + "=" * 70)
    print(f"{passed}/{total} checks passed")
    print("=" * 70)

    _write_report(passed, total)
    return passed == total


def _write_report(passed, total):
    md_dir = WORKTREE_ROOT / "dev" / "bg_wakeup_id_line" / "md"
    md_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    out_path = md_dir / f"p2_bg_escape_probe_{stamp}.md"
    lines = [
        f"# P2 — bg_escape probe run ({datetime.now(timezone.utc).isoformat()})",
        "",
        f"**Result: {passed}/{total} checks passed**",
        "",
        "| Check | Result |",
        "|---|---|",
    ]
    for label, ok in _RESULTS:
        lines.append(f"| {label} | {'PASS' if ok else 'FAIL'} |")
    out_path.write_text("\n".join(lines) + "\n")
    print(f"\nReport written to: {out_path}")


if __name__ == "__main__":
    ok = run_probe_workflow()
    sys.exit(0 if ok else 1)
