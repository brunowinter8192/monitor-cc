# INFRASTRUCTURE
import contextlib
import glob
import importlib.util
import io
import json
import os
import subprocess
import sys
import tempfile

from case_strands import error_string_runners, run_case_strands

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
HOOK_DIR = os.path.join(REPO_ROOT, "src", "hooks")


# ORCHESTRATOR

def test_hook_trace_lines_workflow() -> None:
    sys.exit(run_case_strands(globals(), __file__, error_string_runners(_collect_cases())))


# FUNCTIONS

def _collect_cases() -> list:
    return [
        case_parse_error_all_hooks, case_log_dir_created, case_log_write_failure_stderr,
        case_strip_raw_fallback, case_shlex_exempt,
        case_po_read_unknown_size, case_rag_state_corrupt_line, case_rag_state_unreadable,
        case_worker_cli_missing, case_worker_cli_rc, case_worker_cli_timeout,
        case_status_fn_raises, case_getcwd_failed, case_sweep_prints, case_null_byte_read_path,
        case_unpack_entry_gone,
    ]


def case_parse_error_all_hooks():
    hooks = [os.path.basename(f) for f in sorted(glob.glob(os.path.join(HOOK_DIR, "*.py")))
             if not os.path.basename(f).startswith("_") and "hook_setup" not in f]
    for hook in hooks:
        proc, lines, _ = _run_hook(hook, b"not json")
        if proc.returncode != 0:
            return f"{hook} exit {proc.returncode}"
        if not _traces(lines, hook[:-3], "parse error"):
            return f"{hook} no parse-error trace"
    return None


def _run_hook(hook: str, stdin: bytes, extra_env: dict = None, cwd: str = None, shell_prefix: str = None) -> tuple:
    tmp = tempfile.mkdtemp()
    log = os.path.join(tmp, "fire.jsonl")
    env = dict(os.environ, MONITOR_CC_HOOK_FIRING_LOG=log)
    env.update(extra_env or {})
    if env.get("MONITOR_CC_HOOK_FIRING_LOG") == "":
        env.pop("MONITOR_CC_HOOK_FIRING_LOG")
    script = os.path.join(HOOK_DIR, hook)
    if shell_prefix:
        args = ["bash", "-c", f"{shell_prefix}python3 {script}"]
    else:
        args = ["python3", script]
    proc = subprocess.run(args, input=stdin, capture_output=True, env=env, cwd=cwd or tmp, timeout=30)
    lines = []
    if os.path.exists(env.get("MONITOR_CC_HOOK_FIRING_LOG", "")):
        lines = [json.loads(x) for x in open(env["MONITOR_CC_HOOK_FIRING_LOG"]).read().splitlines()]
    return proc, lines, tmp


def _traces(lines: list, hook: str, needle: str) -> list:
    return [x for x in lines if x["decision"] == "trace" and x["hook"] == hook and needle in x["reason"]]


def case_log_dir_created():
    tmp = tempfile.mkdtemp()
    log = os.path.join(tmp, "missing", "deeper", "f.jsonl")
    proc, _, _ = _run_hook("block_noop_edit.py", json.dumps({"tool_input": {"file_path": "x", "old_string": "a", "new_string": "a"}}).encode(),
                           {"MONITOR_CC_HOOK_FIRING_LOG": log})
    return _expect(proc.returncode == 2 and os.path.exists(log), f"exit {proc.returncode} exists {os.path.exists(log)}")


def _expect(cond: bool, message: str):
    return None if cond else message


def case_log_write_failure_stderr():
    tmp = tempfile.mkdtemp()
    blocker = os.path.join(tmp, "file")
    open(blocker, "w").close()
    proc, _, _ = _run_hook("block_noop_edit.py", json.dumps({"tool_input": {"file_path": "x", "old_string": "a", "new_string": "a"}}).encode(),
                           {"MONITOR_CC_HOOK_FIRING_LOG": os.path.join(blocker, "f.jsonl")})
    return _expect(proc.returncode == 2 and b"log_fire failed" in proc.stderr, f"exit {proc.returncode} stderr {proc.stderr[-120:]!r}")


def case_strip_raw_fallback():
    proc, lines, _ = _run_hook("block_dangerous_kill.py", _bash("echo 'unclosed"))
    return _expect(proc.returncode == 0 and _traces(lines, "_shell_strip", "raw-text fallback: unclosed single quote"), f"exit {proc.returncode} lines {lines}")


def _bash(command: str) -> bytes:
    return json.dumps({"tool_name": "Bash", "session_id": "s", "cwd": "/tmp", "tool_input": {"command": command}}).encode()


def case_shlex_exempt():
    proc, lines, _ = _run_hook("block_gh_cli_local_path.py", _bash("gh-cli get_file_content 'a"))
    if not (proc.returncode == 0 and _traces(lines, "block_gh_cli_local_path", "shlex ValueError")):
        return f"gh exit {proc.returncode} lines {lines}"
    proc, lines, _ = _run_hook("block_rag_docs_layer.py", _bash("rag-cli search --collection a-docs 'q"))
    return _expect(proc.returncode == 0 and _traces(lines, "block_rag_docs_layer", "shlex ValueError"), f"docs exit {proc.returncode} lines {lines}")


def case_po_read_unknown_size():
    proc, lines, _ = _run_hook("block_po_read.py", _bash("cat /nonexistent/.claude/y.txt"))
    return _expect(proc.returncode == 2 and _traces(lines, "block_po_read", "size unknown, blocking"), f"exit {proc.returncode} lines {lines}")


def case_rag_state_corrupt_line():
    tmp = tempfile.mkdtemp()
    state = os.path.join(tmp, "state.jsonl")
    open(state, "w").write("garbage line\n")
    proc, lines, _ = _run_hook("block_rag_cli_document_repeat.py", _repeat_payload(), {"MONITOR_CC_RAG_DOC_REPEAT_STATE": state})
    return _expect(proc.returncode == 0 and _traces(lines, "block_rag_cli_document_repeat", "skipped 1 corrupt lines"), f"exit {proc.returncode} lines {lines}")


def _repeat_payload():
    return _bash("rag-cli index --collection c --document d.md")


def case_rag_state_unreadable():
    tmp = tempfile.mkdtemp()
    proc, lines, _ = _run_hook("block_rag_cli_document_repeat.py", _repeat_payload(), {"MONITOR_CC_RAG_DOC_REPEAT_STATE": tmp})
    ok = proc.returncode == 0 and _traces(lines, "block_rag_cli_document_repeat", "state read failed") and _traces(lines, "block_rag_cli_document_repeat", "state write failed")
    return _expect(ok, f"exit {proc.returncode} lines {lines}")


def case_worker_cli_missing():
    return _worker_case(None, "worker-cli not found")


def _worker_case(script_body, needle):
    for hook in ("block_worker_kill_while_working.py", "block_worker_send_while_working.py"):
        verb = "kill" if "kill" in hook else "send"
        proc, lines, _ = _run_hook(hook, _bash(f"worker-cli {verb} w1 hi"), _worker_env(script_body))
        if proc.returncode != 0 or not _traces(lines, hook[:-3], needle):
            return f"{hook} exit {proc.returncode} lines {lines}"
    return None


def _worker_env(script_body):
    home = tempfile.mkdtemp()
    if script_body is None:
        return {"PATH": "/usr/bin:/bin", "HOME": home}
    bin_dir = tempfile.mkdtemp()
    path = os.path.join(bin_dir, "worker-cli")
    open(path, "w").write(script_body)
    os.chmod(path, 0o755)
    return {"PATH": bin_dir + ":/usr/bin:/bin", "HOME": home}


def case_worker_cli_rc():
    return _worker_case("#!/bin/sh\nexit 3\n", "rc=3")


def case_worker_cli_timeout():
    for module in ("block_worker_kill_while_working", "block_worker_send_while_working"):
        snippet = (
            "import subprocess, sys\n"
            "sys.path.insert(0, sys.argv[1])\n"
            f"import {module} as m\n"
            "def fake_run(cmd, **kwargs):\n"
            "    raise subprocess.TimeoutExpired(cmd, kwargs['timeout'])\n"
            "m._resolve_worker_cli = lambda: '/fake/worker-cli'\n"
            "m.subprocess.run = fake_run\n"
            "print(repr(m._live_worker_status('w1')))\n"
        )
        proc, lines = _run_snippet(snippet)
        if proc.returncode != 0 or proc.stdout.strip() != "''" or not _traces(lines, module, "status subprocess failed for w1: TimeoutExpired"):
            return f"{module} exit {proc.returncode} stdout {proc.stdout!r} stderr {proc.stderr[-200:]!r} lines {lines}"
    return None


def _run_snippet(snippet: str) -> tuple:
    tmp = tempfile.mkdtemp()
    log = os.path.join(tmp, "f.jsonl")
    env = dict(os.environ, MONITOR_CC_HOOK_FIRING_LOG=log)
    proc = subprocess.run([sys.executable, "-c", snippet, HOOK_DIR], capture_output=True, text=True, env=env, timeout=30)
    lines = [json.loads(x) for x in open(log).read().splitlines()] if os.path.exists(log) else []
    return proc, lines


def case_status_fn_raises():
    for module in ("block_worker_kill_while_working", "block_worker_send_while_working"):
        verb = "kill" if "kill" in module else "send"
        snippet = (
            "import json, sys\n"
            "sys.path.insert(0, sys.argv[1])\n"
            f"import {module} as m\n"
            "def boom(name):\n"
            "    raise RuntimeError('x')\n"
            f"print(json.dumps(m.decide('worker-cli {verb} w1', boom)))\n"
        )
        proc, lines = _run_snippet(snippet)
        if proc.returncode != 0 or json.loads(proc.stdout) != [False, None] or not _traces(lines, module, "status check failed for w1"):
            return f"{module} exit {proc.returncode} stdout {proc.stdout!r} stderr {proc.stderr[-200:]!r} lines {lines}"
    return None


def case_getcwd_failed():
    payload = json.dumps({"tool_input": {"command": "sleep 5", "run_in_background": True}}).encode()
    tmp = tempfile.mkdtemp()
    log = os.path.join(tmp, "f.jsonl")
    script = os.path.join(HOOK_DIR, "rewrite_background_sleep.py")
    proc = subprocess.run(["bash", "-c", f"mkdir {tmp}/d; cd {tmp}/d; rmdir {tmp}/d; python3 {script}"], input=payload,
                          capture_output=True, env=dict(os.environ, MONITOR_CC_HOOK_FIRING_LOG=log), timeout=30)
    lines = [json.loads(x) for x in open(log).read().splitlines()] if os.path.exists(log) else []
    ok = proc.returncode == 0 and proc.stdout == b"" and _traces(lines, "rewrite_background_sleep", "getcwd failed")
    return _expect(ok, f"exit {proc.returncode} stdout {proc.stdout!r} lines {lines}")


def case_sweep_prints():
    mod = _load("hook_setup")
    live = os.path.join(tempfile.mkdtemp(), "live.py")
    open(live, "w").close()
    dead = "/nonexistent/dead_hook.py"
    settings = {"hooks": {"PreToolUse": [{"matcher": "Bash", "hooks": [
        {"command": f"python3 {dead}"}, {"command": f"python3 {live}"}]}]}}
    buf = io.StringIO()
    with contextlib.redirect_stderr(buf):
        swept = mod._sweep_stale_hooks(settings)
    remaining = settings["hooks"]["PreToolUse"][0]["hooks"]
    ok = swept == 1 and f"Swept stale hook: PreToolUse python3 {dead}" in buf.getvalue() and len(remaining) == 1
    return _expect(ok, f"swept {swept} stderr {buf.getvalue()!r}")


def _load(module: str):
    spec = importlib.util.spec_from_file_location(module, os.path.join(HOOK_DIR, module + ".py"))
    mod = importlib.util.module_from_spec(spec)
    sys.path.insert(0, HOOK_DIR)
    spec.loader.exec_module(mod)
    return mod


def case_null_byte_read_path():
    payload = json.dumps({"tool_name": "Read", "tool_input": {"file_path": "/tmp/a\u0000b"}}).encode()
    proc, _, _ = _run_hook("block_read_directory.py", payload)
    return _expect(proc.returncode == 0, f"exit {proc.returncode} stderr {proc.stderr[-200:]!r}")


def case_unpack_entry_gone():
    mod = _load("hook_setup")
    to_install, skipped = mod.decide_entries([("a.py", "Bash")], lambda s: True, lambda s: True)
    return _expect(to_install == [("a.py", "Bash")] and not skipped and not hasattr(mod, "_unpack_entry"), f"{to_install} {skipped}")


if __name__ == "__main__":
    test_hook_trace_lines_workflow()
