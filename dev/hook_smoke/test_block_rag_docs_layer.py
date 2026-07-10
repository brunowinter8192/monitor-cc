# INFRASTRUCTURE
import json
import subprocess
import sys

HOOK = "src/hooks/block_rag_docs_layer.py"

CASES = [
    # (description, command, expected_exit_code)
    # --- must block: *-docs search_hybrid with no layer filter ---
    ("docs collection no filter BLOCK",
     'rag-cli search_hybrid "q" monitor-cc-docs', 2),
    ("docs collection after cd BLOCK",
     'cd /x && rag-cli search_hybrid "q" foo-docs', 2),
    ("docs collection with unrelated code subpath filter BLOCK",
     "rag-cli search_hybrid \"q\" monitor-cc-docs --document 'src/search/%'", 2),
    # --- must allow: *-docs search_hybrid with process-docs filter ---
    ("docs collection --document process-docs ALLOW",
     "rag-cli search_hybrid \"q\" monitor-cc-docs --document 'process-docs/%'", 0),
    ("docs collection --exclude process-docs ALLOW",
     "rag-cli search_hybrid \"q\" monitor-cc-docs --exclude 'process-docs/%'", 0),
    ("docs collection --document= equals form ALLOW",
     "rag-cli search_hybrid \"q\" monitor-cc-docs --document='process-docs/%'", 0),
    ("docs collection --document specific area ALLOW",
     "rag-cli search_hybrid \"q\" monitor-cc-docs --document 'process-docs/retrieval/%'", 0),
    # --- must allow: non-docs collection unaffected ---
    ("reference collection ALLOW",
     'rag-cli search_hybrid "q" monitor-cc-reference', 0),
    # --- must allow: non search_hybrid subcommand unaffected ---
    ("list_documents ALLOW",
     "rag-cli list_documents monitor-cc-docs", 0),
    # --- must allow: no rag-cli at all ---
    ("no rag-cli ALLOW",
     "echo hello world", 0),
    # --- shell-strip: rag-cli inside single-quoted string must be blanked ---
    ("rag-cli inside single-quotes ALLOW",
     "echo 'rag-cli search_hybrid \"q\" monitor-cc-docs'", 0),
]


# ORCHESTRATOR

def test_block_rag_docs_layer_workflow() -> None:
    failures = []
    for desc, cmd, expected in CASES:
        got = _run_hook(cmd)
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
    print(f"All {len(CASES)} tests passed.")


# FUNCTIONS

# Run hook with given command string; return exit code
def _run_hook(command: str) -> int:
    payload = json.dumps({
        "tool_name": "Bash",
        "tool_input": {"command": command},
    })
    result = subprocess.run(
        ["python3", HOOK],
        input=payload.encode(),
        capture_output=True,
    )
    return result.returncode


if __name__ == "__main__":
    test_block_rag_docs_layer_workflow()
