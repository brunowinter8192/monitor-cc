# INFRASTRUCTURE
import json
import sys
from hook_runner import run_hook

HOOK = "src/hooks/block_rag_corpus_read.py"

CASES = [
    ("cat over a corpus document BLOCK",
     "cat /Users/x/cli/rag-cli/data/documents/github_issues/123.md", 2),
    ("grep -r over the corpus tree BLOCK",
     "grep -r foo /Users/x/cli/rag-cli/data/documents/", 2),
    ("head over a quoted corpus path BLOCK",
     'head -50 "/Users/x/cli/rag-cli/data/documents/x.md"', 2),
    ("tail over a corpus document BLOCK",
     "tail -n 20 /Users/x/cli/rag-cli/data/documents/y.md", 2),
    ("sed over a corpus document BLOCK",
     "sed -n 1,5p /Users/x/cli/rag-cli/data/documents/z.md", 2),
    ("awk over a corpus document BLOCK",
     'awk "{print}" /Users/x/cli/rag-cli/data/documents/z.md', 2),
    ("rg over the corpus tree BLOCK",
     "rg TODO /Users/x/cli/rag-cli/data/documents/", 2),
    ("less over a corpus document BLOCK",
     "less /Users/x/cli/rag-cli/data/documents/z.md", 2),
    ("more over a corpus document BLOCK",
     "more /Users/x/cli/rag-cli/data/documents/z.md", 2),
    ("cat with the corpus path as a non-first argument BLOCK",
     "cat file1.txt /Users/x/cli/rag-cli/data/documents/z.md", 2),
    ("only a quoted corpus path argument BLOCK",
     'cat "/Users/x/cli/rag-cli/data/documents/only_quoted_arg.md"', 2),
    ("real rag-cli invocation chained with a corpus-read segment BLOCK "
     "(the corpus-read segment blocks regardless of what else is chained)",
     "rag-cli index --collection x && cat /Users/x/cli/rag-cli/data/documents/z.md", 2),
    ("renamed checkout (rag-cli-eval) still blocks BLOCK (glob dodge)",
     "cat /Users/x/cli/rag-cli-eval/data/documents/z.md", 2),
    ("renamed worktree (rag-cli-convert) still blocks BLOCK (glob dodge)",
     "cat /Users/x/cli/rag-cli-convert/data/documents/z.md", 2),
    ("ls over the corpus tree ALLOW (management, not a content read)",
     "ls /Users/x/cli/rag-cli/data/documents/", 0),
    ("rm over a corpus document ALLOW (deletion is sanctioned)",
     "rm -rf /Users/x/cli/rag-cli/data/documents/old", 0),
    ("mv within the corpus tree ALLOW",
     "mv /Users/x/cli/rag-cli/data/documents/a /Users/x/cli/rag-cli/data/documents/b", 0),
    ("mkdir under the corpus tree ALLOW",
     "mkdir -p /Users/x/cli/rag-cli/data/documents/new", 0),
    ("cat on an unrelated file ALLOW",
     "cat /etc/hosts", 0),
    ("grep on an unrelated file ALLOW",
     "grep foo /tmp/log.txt", 0),
    ("rag-cli search standalone ALLOW",
     'rag-cli search "q" coll', 0),
    ("rag-cli read_document standalone ALLOW",
     "rag-cli read_document coll doc1", 0),
    ("quoted mention inside echo ALLOW (not an actual read)",
     'echo "you could cat data/documents/x"', 0),
    ("corpus-path text inside a heredoc body ALLOW (shell-strip blanks it before matching)",
     "cat <<'EOF'\ncat /path/rag-cli/data/documents/foo.md\nEOF", 0),
    ("relative corpus path with no rag-* prefix in the text ALLOW (text-only limitation)",
     "cat data/documents/foo.md", 0),
]


# ORCHESTRATOR

def test_block_rag_corpus_read_workflow() -> None:
    failures = []
    for desc, cmd, expected in CASES:
        got = _run_hook(cmd)
        status = "OK  " if got == expected else "FAIL"
        print(f"  [{status}] {desc}: exit={got} (expected {expected})")
        if got != expected:
            failures.append(desc)

    malformed_got = _run_hook_raw(b"not valid json at all")
    status = "OK  " if malformed_got == 0 else "FAIL"
    print(f"  [{status}] malformed stdin payload fails open: exit={malformed_got} (expected 0)")
    if malformed_got != 0:
        failures.append("malformed stdin payload fails open")

    message_got, message_stderr = _run_hook_with_stderr(
        "cat /Users/x/cli/rag-cli/data/documents/z.md")
    for label, ok in _message_checks(message_stderr):
        status = "OK  " if ok else "FAIL"
        print(f"  [{status}] block message: {label}")
        if not ok:
            failures.append(f"block message: {label}")

    print()
    if failures:
        print(f"FAILED: {len(failures)} case(s):")
        for f in failures:
            print(f"  - {f}")
        sys.exit(1)
    print(f"All {len(CASES) + 1 + len(_message_checks(message_stderr))} tests passed.")


# FUNCTIONS

def _message_checks(stderr: str) -> list:
    return [
        ("names rag-cli search as the allowed form", "rag-cli search" in stderr),
        ("names rag-cli read_document as the allowed form", "rag-cli read_document" in stderr),
        ("states file management stays allowed", "ls, rm, mv, mkdir" in stderr),
    ]


def _run_hook(command: str) -> int:
    return _run_hook_raw(_payload(command))


def _run_hook_with_stderr(command: str) -> tuple:
    result = run_hook(HOOK, _payload(command))
    return result.returncode, result.stderr.decode()


def _payload(command: str) -> bytes:
    return json.dumps({
        "tool_name": "Bash",
        "tool_input": {"command": command},
    }).encode()


def _run_hook_raw(stdin_bytes: bytes) -> int:
    result = run_hook(HOOK, stdin_bytes)
    return result.returncode


if __name__ == "__main__":
    test_block_rag_corpus_read_workflow()
