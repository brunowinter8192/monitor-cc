# INFRASTRUCTURE
import json
import sys
from case_strands import exit_code_runners, run_case_strands
from hook_runner import run_hook

HOOK = "src/hooks/block_rag_docs_layer.py"

CASES = [
    ("docs collection no filter BLOCK",
     'rag-cli search "q" monitor-cc-docs', 2),
    ("docs collection after cd BLOCK",
     'cd /x && rag-cli search "q" foo-docs', 2),
    ("docs collection with unrelated code subpath filter BLOCK",
     "rag-cli search \"q\" monitor-cc-docs --document 'src/search/%'", 2),
    ("docs collection --document process-docs ALLOW",
     "rag-cli search \"q\" monitor-cc-docs --document 'process-docs/%'", 0),
    ("docs collection --exclude process-docs ALLOW",
     "rag-cli search \"q\" monitor-cc-docs --exclude 'process-docs/%'", 0),
    ("docs collection --document= equals form ALLOW",
     "rag-cli search \"q\" monitor-cc-docs --document='process-docs/%'", 0),
    ("docs collection --document specific area ALLOW",
     "rag-cli search \"q\" monitor-cc-docs --document 'process-docs/retrieval/%'", 0),
    ("reference collection ALLOW",
     'rag-cli search "q" monitor-cc-reference', 0),
    ("list_documents ALLOW",
     "rag-cli list_documents monitor-cc-docs", 0),
    ("no rag-cli ALLOW",
     "echo hello world", 0),
    ("rag-cli inside single-quotes ALLOW",
     "echo 'rag-cli search \"q\" monitor-cc-docs'", 0),
]


# ORCHESTRATOR

def test_block_rag_docs_layer_workflow() -> None:
    sys.exit(run_case_strands(globals(), __file__, exit_code_runners(CASES, _run_hook)))


# FUNCTIONS

def _run_hook(command: str) -> int:
    payload = json.dumps({
        "tool_name": "Bash",
        "tool_input": {"command": command},
    })
    result = run_hook(HOOK, payload.encode())
    return result.returncode


if __name__ == "__main__":
    test_block_rag_docs_layer_workflow()
