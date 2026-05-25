# INFRASTRUCTURE
import json
import subprocess
import sys

HOOK = "src/hooks/rewrite_rag_cli_search_noise.py"

# (description, command, expected_rewrite_or_None)
# None = no rewrite expected (hook should emit nothing and exit 0)
CASES = [
    # --- positive: noise inside the search_hybrid segment is stripped ---
    (
        "2>&1 alone — strip",
        'rag-cli search_hybrid "x" RAG-docs 2>&1',
        'rag-cli search_hybrid "x" RAG-docs',
    ),
    (
        "| head -120 — strip",
        'rag-cli search_hybrid "x" RAG-docs | head -120',
        'rag-cli search_hybrid "x" RAG-docs',
    ),
    (
        "2>&1 | head -120 — strip both",
        'rag-cli search_hybrid "x" RAG-docs 2>&1 | head -120',
        'rag-cli search_hybrid "x" RAG-docs',
    ),
    (
        "| tail -50 — strip",
        'rag-cli search_hybrid "x" RAG-docs | tail -50',
        'rag-cli search_hybrid "x" RAG-docs',
    ),
    (
        "| grep score — strip (filters the result)",
        'rag-cli search_hybrid "x" RAG-docs | grep score',
        'rag-cli search_hybrid "x" RAG-docs',
    ),
    (
        "> /tmp/file redirect — strip",
        'rag-cli search_hybrid "x" RAG-docs > /tmp/out.txt',
        'rag-cli search_hybrid "x" RAG-docs',
    ),
    (
        "cd /path && rag-cli ... | head — strip only the pipe, keep cd chain",
        'cd /path && rag-cli search_hybrid "x" RAG-docs | head',
        'cd /path && rag-cli search_hybrid "x" RAG-docs',
    ),
    (
        "rag-cli ... | head ; bd list — strip pipe, keep trailing chain",
        'rag-cli search_hybrid "x" RAG-docs | head ; bd list',
        'rag-cli search_hybrid "x" RAG-docs ; bd list',
    ),
    (
        "rag-cli ... | head || echo fail — strip pipe, keep || chain",
        'rag-cli search_hybrid "x" RAG-docs | head || echo fail',
        'rag-cli search_hybrid "x" RAG-docs || echo fail',
    ),
    # --- negative: nothing to strip, hook is no-op ---
    (
        "bare search_hybrid — no-op",
        'rag-cli search_hybrid "x" RAG-docs',
        None,
    ),
    (
        "cd /path && rag-cli ... bare — no-op (chain preserved)",
        'cd /path && rag-cli search_hybrid "x" RAG-docs',
        None,
    ),
    (
        "rag-cli ... ; bd list — no-op (trailing chain, no pipe)",
        'rag-cli search_hybrid "x" RAG-docs ; bd list',
        None,
    ),
    (
        "list_collections | head — out of scope, no-op",
        'rag-cli list_collections | head -40',
        None,
    ),
    (
        "read_document | head — out of scope, no-op",
        'rag-cli read_document RAG-docs foo.md 0 | head',
        None,
    ),
    (
        "search_hybrid inside quoted echo — no-op (token in string, not active)",
        'echo "rag-cli search_hybrid foo bar | head"',
        None,
    ),
]


# ORCHESTRATOR

# Run all cases and print results; exit 1 if any fail
def test_rewrite_rag_cli_search_noise_workflow() -> None:
    failures = []
    for desc, cmd, expected_rewrite in CASES:
        exit_code, rewrite = _run_hook(cmd)
        ok = exit_code == 0 and rewrite == expected_rewrite
        status = "OK  " if ok else "FAIL"
        want = repr(expected_rewrite) if expected_rewrite is not None else "None (no output)"
        got  = repr(rewrite) if rewrite is not None else "None (no output)"
        print(f"  [{status}] {desc}")
        if not ok:
            print(f"           want: {want}")
            print(f"           got:  {got} (exit={exit_code})")
            failures.append(desc)
    print()
    if failures:
        print(f"FAILED: {len(failures)} case(s):")
        for f in failures:
            print(f"  - {f}")
        sys.exit(1)
    print(f"All {len(CASES)} tests passed.")


# FUNCTIONS

# Invoke the hook script as subprocess; feed payload via stdin; return (exit_code, rewritten_command_or_None)
def _run_hook(command: str):
    payload = json.dumps({"tool_name": "Bash", "tool_input": {"command": command}})
    proc = subprocess.run(
        ["python3", HOOK],
        input=payload,
        capture_output=True,
        text=True,
        timeout=5,
    )
    rewrite = None
    if proc.stdout.strip():
        try:
            out = json.loads(proc.stdout)
            rewrite = out.get("hookSpecificOutput", {}).get("updatedInput", {}).get("command")
        except json.JSONDecodeError:
            pass
    return proc.returncode, rewrite


if __name__ == "__main__":
    test_rewrite_rag_cli_search_noise_workflow()
