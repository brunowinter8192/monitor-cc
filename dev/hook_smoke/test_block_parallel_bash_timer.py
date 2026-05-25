# INFRASTRUCTURE
import json
import os
import subprocess
import sys
import tempfile

HOOK = "src/hooks/block_parallel_bash_timer.py"


# ORCHESTRATOR

def test_block_parallel_bash_timer_workflow() -> None:
    cases = _build_cases()
    failures = []
    for desc, blocks, current_cmd, expected in cases:
        tp = _make_transcript(blocks)
        try:
            got = _run_hook(tp, current_cmd)
        finally:
            os.unlink(tp)
        status = "OK  " if got == expected else "FAIL"
        print(f"  [{status}] {desc}: exit={got} (expected {expected})")
        if got != expected:
            failures.append(desc)
    print()
    if failures:
        print(f"FAILED: {len(failures)} case(s):")
        for f in failures:
            print(f"  - {f}")
        sys.exit(1)
    print(f"All {len(cases)} tests passed.")


# FUNCTIONS

# Build (description, content_blocks, current_cmd, expected_exit) tuples
def _build_cases() -> list:
    return [
        # --- true positives: must block ---
        ("strict canonical timer + foreground Bash BLOCK",
         [_bash("worker-cli send X hi"), _bash("sleep 600 && echo done")],
         "worker-cli send X hi", 2),
        ("loose timer (echo with quoted string) + foreground Bash BLOCK",
         [_bash("worker-cli list"), _bash('sleep 480 && echo "8min check"')],
         "worker-cli list", 2),
        ("three Bashes one is timer BLOCK",
         [_bash("ls"), _bash("sleep 300 && echo X"), _bash("pwd")],
         "ls", 2),
        ("thinking + tool_use mix with timer BLOCK",
         [{"type": "thinking", "thinking": "..."},
          _bash("ls"), _bash("sleep 600 && echo done")],
         "ls", 2),
        ("float-second timer (sleep 1.5) BLOCK",
         [_bash("worker-cli status X"), _bash("sleep 1.5 && echo done")],
         "worker-cli status X", 2),

        # --- false positive fixes: must pass ---
        ("single Bash (no timer) PASS",
         [_bash("ls -la")], "ls -la", 0),
        ("single Bash IS timer (no parallel) PASS",
         [_bash("sleep 600 && echo done")], "sleep 600 && echo done", 0),
        ("two non-timer Bashes PASS",
         [_bash("worker-cli list"), _bash("git status")], "worker-cli list", 0),
        ("timer-text quoted inside other command (not standalone) PASS",
         [_bash("echo 'sleep 60 && echo done'"), _bash("ls")],
         "echo 'sleep 60 && echo done'", 0),
        ("chained sleep in middle of larger command (not standalone) PASS",
         [_bash("worker-cli send X done && sleep 5 && worker-cli status X"),
          _bash("ls")],
         "worker-cli send X done && sleep 5 && worker-cli status X", 0),
        ("no transcript_path (fail-open) PASS",
         None, "sleep 600 && echo done", 0),
    ]


# Build a Bash tool_use content block dict with the given command
def _bash(command: str) -> dict:
    return {"type": "tool_use", "name": "Bash", "input": {"command": command}}


# Write a temp JSONL transcript with a single assistant message containing the given content blocks; return path
# blocks=None → write only a user-line (no assistant message — triggers fail-open at "no transcript_path" path)
def _make_transcript(blocks) -> str:
    fd, path = tempfile.mkstemp(suffix=".jsonl")
    with os.fdopen(fd, "w") as f:
        f.write(json.dumps({"type": "user", "message": {"role": "user", "content": "test"}}) + "\n")
        if blocks is not None:
            f.write(json.dumps({
                "type": "assistant",
                "message": {"role": "assistant", "content": blocks},
            }) + "\n")
    return path


# Run hook with constructed payload; return exit code
def _run_hook(transcript_path, command: str) -> int:
    payload_dict = {
        "tool_name": "Bash",
        "tool_input": {"command": command},
    }
    if transcript_path is not None:
        payload_dict["transcript_path"] = transcript_path
    payload = json.dumps(payload_dict)
    # Isolate hook_firing.jsonl writes from real log
    env = dict(os.environ)
    env["MONITOR_CC_HOOK_FIRING_LOG"] = "/tmp/test_block_parallel_bash_timer_fire.jsonl"
    result = subprocess.run(
        ["python3", HOOK],
        input=payload.encode(),
        capture_output=True,
        env=env,
    )
    return result.returncode


if __name__ == "__main__":
    test_block_parallel_bash_timer_workflow()
