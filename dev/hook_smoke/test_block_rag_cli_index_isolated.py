# INFRASTRUCTURE
import json
import sys
from hook_runner import run_hook

HOOK = "src/hooks/block_rag_cli_index_isolated.py"

CASES = [
    ("observed tail+echo+cd+index BLOCK",
     'tail -20 /tmp/linkedin-reference_batch2_index.log\n'
     'echo "--- is rag-cli still holding lock? ---"\n'
     'cd ~/Documents/ai/Meta/ClaudeCode/cli/rag-cli && '
     'rag-cli index --collection linkedin-reference > /tmp/lock_check4.log 2>&1', 2),
    ("tail before index && BLOCK",
     "tail -20 /tmp/x.log && rag-cli index --collection x", 2),
    ("index then echo && BLOCK",
     "rag-cli index --collection x && echo done", 2),
    ("index then tail ; BLOCK",
     "rag-cli index --collection x ; tail /tmp/x.log", 2),
    ("second rag-cli command alongside index BLOCK",
     "rag-cli delete --collection x && rag-cli index --collection x", 2),
    ("index piped to tee BLOCK",
     "rag-cli index --collection x | tee /tmp/log", 2),
    ("tail before env-prefixed index BLOCK",
     "tail -20 /tmp/x.log && PYTHONUNBUFFERED=1 rag-cli index --collection x", 2),
    ("env-prefixed index then echo BLOCK",
     "PYTHONUNBUFFERED=1 rag-cli index --collection x && echo done", 2),
    ("multi-env-prefixed index piped to tee BLOCK",
     "FOO=1 BAR=2 rag-cli index --collection x | tee /tmp/log", 2),
    ("assignment line + tail + cd + env-prefixed index BLOCK",
     'RAG_ROOT=/x\ntail /tmp/y.log\ncd "$RAG_ROOT" && PYTHONUNBUFFERED=1 rag-cli index --collection x', 2),
    ("cmd subst in assignment value BLOCK",
     "X=$(tail /tmp/a.log) rag-cli index --collection x", 2),
    ("backtick subst in assignment value BLOCK",
     "X=`tail /tmp/a.log` rag-cli index --collection x", 2),
    ("cmd subst in --collection argument BLOCK",
     "rag-cli index --collection $(cat /tmp/name.txt)", 2),
    ("process substitution on redirect target BLOCK",
     "rag-cli index --collection x > >(tail -5)", 2),
    ("process substitution as input BLOCK",
     "rag-cli index --collection x < <(cat /tmp/y)", 2),
    ("arithmetic expansion in assignment value BLOCK",
     "X=$((1+1)) rag-cli index --collection x", 2),
    ("cmd subst inside double-quoted cd target BLOCK",
     'cd "$(pwd)" && rag-cli index --collection x', 2),
    ("backtick inside redirect filename BLOCK",
     "rag-cli index --collection x > `pwd`/out.log", 2),
    ("bare & no trailing space smuggling BLOCK",
     "rag-cli index --collection x &tail /tmp/y", 2),
    ("bare & no spaces at all smuggling BLOCK",
     "rag-cli index --collection x&tail /tmp/y", 2),
    ("bare index ALLOW",
     "rag-cli index --collection linkedin-reference", 0),
    ("index redirected to log ALLOW",
     "rag-cli index --collection x > /tmp/out.log 2>&1", 0),
    ("cd before index ALLOW",
     "cd /some/path && rag-cli index --collection x", 0),
    ("cd before index with redirect ALLOW",
     "cd /path && rag-cli index --collection x > /tmp/out.log 2>&1", 0),
    ("env-prefixed bare index ALLOW",
     "PYTHONUNBUFFERED=1 rag-cli index --collection x", 0),
    ("assignment line + cd + env-prefixed index + line-continued redirect ALLOW",
     'RAG_ROOT=~/Documents/ai/Meta/ClaudeCode/cli/rag-cli\n'
     'cd "$RAG_ROOT" && PYTHONUNBUFFERED=1 rag-cli index --collection linkedin-reference \\\n'
     '    > /tmp/linkedin-reference_batch3_index.log 2>&1', 0),
    ("assignment line + cd + bare index + redirect ALLOW",
     'RAG_ROOT=/x\ncd "$RAG_ROOT" && rag-cli index --collection x > /tmp/o.log 2>&1', 0),
    ("bare index with backslash line-continued redirect ALLOW",
     "rag-cli index --collection x \\\n    > /tmp/x.log 2>&1", 0),
    ("quoted semicolon in assignment value ALLOW",
     'X="a;b" rag-cli index --collection x', 0),
    ("plain $VAR expansion in cd target is not command substitution ALLOW",
     'RAG_ROOT=/x\ncd "$RAG_ROOT" && rag-cli index --collection x', 0),
    ("&> redirect not mistaken for background-& separator ALLOW",
     "rag-cli index --collection x &> /tmp/out.log", 0),
    ("rag-cli search out of scope ALLOW",
     'rag-cli search_hybrid "q" coll', 0),
    ("rag-cli list_documents out of scope ALLOW",
     "rag-cli list_documents coll | head", 0),
    ("rag-cli delete out of scope ALLOW",
     "rag-cli delete --collection x", 0),
    ("no rag-cli ALLOW",
     "echo hello world", 0),
    ("rag-cli index inside single-quotes ALLOW",
     "echo 'tail /tmp/x.log && rag-cli index --collection x'", 0),
    ("rag-cli index inside heredoc body ALLOW",
     "cat <<'EOF'\ntail /tmp/x.log && rag-cli index --collection x\nEOF", 0),
]


# ORCHESTRATOR

def test_block_rag_cli_index_isolated_workflow() -> None:
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

def _run_hook(command: str) -> int:
    payload = json.dumps({
        "tool_name": "Bash",
        "tool_input": {"command": command},
    })
    result = run_hook(HOOK, payload.encode())
    return result.returncode


if __name__ == "__main__":
    test_block_rag_cli_index_isolated_workflow()
