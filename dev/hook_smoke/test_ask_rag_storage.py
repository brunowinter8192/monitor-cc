# INFRASTRUCTURE
import json
import os
import sys
import tempfile
from pathlib import Path

from case_strands import case_runners, fail_open_runner, function_runners, report_case, run_case_strands
from hook_runner import FIRING_LOG_ENV, run_hook

HOOK = "src/hooks/ask_rag_storage.py"
ROOTS_ENV = "MONITOR_CC_RAG_STORAGE_ROOTS"
PINNED_HOME = "/Users/brunowinter2000"
PROD = PINNED_HOME + "/Documents/ai/Meta/ClaudeCode/cli/rag-cli"
BERICHTE = PINNED_HOME + "/Documents/wise2627/BOM1/Berichte"
SEARCH_UNSET = "unset PYTHONHOME PYTHONPATH RESOURCEPATH EXECUTABLEPATH ARGVZERO; "
LOOP = (
    'for f in *.pdf; do t=$(readlink "$f"); mv "$t" "$P/bom1/$f"; ln -s "$P/bom1/$f" "$f"; done'
)

ASK = True
PASS = False
TMP = "tmp"
PROD_ROOTS = "prod"

CASES = [
    ("observed: pdftotext through a Berichte symlink",
     "Bash", {"command": "pdftotext -f 22 -l 22 -layout {T}/proj/Berichte/ADS_RemunerationReport_2024.pdf -"}, None, ASK, TMP),
    ("observed: cd Berichte then mv loop with P built from a variable (production paths)",
     "Bash", {"command": f"P={PROD}/data/pdf; cd {BERICHTE}; {LOOP}"}, None, ASK, PROD_ROOTS),
    ("observed: same loop with relative glob only, no storage path in the text",
     "Bash", {"command": f'cd {{T}}/proj/Berichte; for f in *.pdf; do mv "$f" ../plain/; done'}, None, ASK, TMP),
    ("observed: cp between documents folders through R variable (production paths)",
     "Bash", {"command": f"R={PROD}; cp $R/data/documents/wise2627-reference/BOM1_* $R/data/documents/bom1-reference/"}, None, ASK, PROD_ROOTS),
    ("observed: env -u ... rag-cli index",
     "Bash", {"command": "env -u PYTHONHOME -u PYTHONPATH -u RESOURCEPATH rag-cli index --collection bom1-reference"}, None, ASK, PROD_ROOTS),
    ("observed: unset prefix plus rag-cli search PASS",
     "Bash", {"command": SEARCH_UNSET + "rag-cli search \"Performance Bonus target achievement\" bom1-reports --document 'ADS_RemunerationReport%'"}, None, PASS, PROD_ROOTS),
    ("observed: ls on a Berichte directory full of symlinks",
     "Bash", {"command": "ls {T}/proj/Berichte"}, None, ASK, TMP),
    ("observed: ls on Berichte with a glob",
     "Bash", {"command": "ls {T}/proj/Berichte/ADS_*"}, None, ASK, TMP),
    ("directory with symlinks listed with trailing slash",
     "Bash", {"command": "ls -la {T}/proj/Berichte/"}, None, ASK, TMP),
    ("ls with no argument inside the symlink directory (working directory rule)",
     "Bash", {"command": "ls"}, "{T}/proj/Berichte", ASK, TMP),
    ("cd into the symlink directory then ls",
     "Bash", {"command": "cd {T}/proj/Berichte && ls"}, None, ASK, TMP),
    ("ls on a real directory without symlinks PASS",
     "Bash", {"command": "ls {T}/proj/Notizen"}, None, PASS, TMP),
    ("ls on the project directory whose entries are real directories PASS",
     "Bash", {"command": "ls {T}/proj"}, None, PASS, TMP),
    ("verification case: ls on pdf/bom1",
     "Bash", {"command": "ls {T}/rag-cli/data/pdf/bom1"}, None, ASK, TMP),
    ("ls on the documents tree",
     "Bash", {"command": "ls {T}/rag-cli/data/documents/bom1-reference"}, None, ASK, TMP),
    ("tilde path to the pdf tree (production roots)",
     "Bash", {"command": "ls ~/Documents/ai/Meta/ClaudeCode/cli/rag-cli/data/pdf/bom1"}, None, ASK, PROD_ROOTS),
    ("sibling folder pdf-old is not storage PASS",
     "Bash", {"command": "ls {T}/rag-cli/data/pdf-old"}, None, PASS, TMP),
    ("relative path from the rag-cli directory",
     "Bash", {"command": "ls data/pdf/bom1"}, "{T}/rag-cli", ASK, TMP),
    ("relative path with dot-dot out of the project",
     "Bash", {"command": "ls ../rag-cli/data/documents"}, "{T}/proj", ASK, TMP),
    ("cd into storage then relative ls",
     "Bash", {"command": "cd {T}/rag-cli/data/pdf/bom1 && ls"}, None, ASK, TMP),
    ("quoted path inside bash -c",
     "Bash", {"command": "bash -c \"cat {T}/rag-cli/data/documents/bom1-reference/x.md\""}, None, ASK, TMP),
    ("unbalanced quote forces the fallback tokenizer, path still found",
     "Bash", {"command": "echo it's fine; ls {T}/rag-cli/data/pdf"}, None, ASK, TMP),
    ("rag-cli delete",
     "Bash", {"command": "rag-cli delete --collection bom1-reference --document x.md"}, None, ASK, PROD_ROOTS),
    ("rag-cli search chained with a storage copy",
     "Bash", {"command": "rag-cli search q c; cp {T}/rag-cli/data/pdf/bom1/a.pdf /tmp/x.pdf"}, None, ASK, TMP),
    ("redirect target inside storage",
     "Bash", {"command": "echo hi > {T}/rag-cli/data/documents/bom1-reference/new.md"}, None, ASK, TMP),
    ("rag-cli expand_chunks and list commands chained PASS",
     "Bash", {"command": "rag-cli list_collections; rag-cli list_documents bom1-reports; rag-cli expand_chunks c d.md 3 --before 2 --after 2"}, None, PASS, PROD_ROOTS),
    ("storage path only assigned to a variable, search runs PASS",
     "Bash", {"command": "P={T}/rag-cli/data/pdf; rag-cli search \"q\" c"}, None, PASS, TMP),
    ("cat on a plain note PASS",
     "Bash", {"command": "cat {T}/proj/Notizen/n.md"}, None, PASS, TMP),
    ("rag-cli search with working directory in the symlink directory PASS",
     "Bash", {"command": "rag-cli search q c --document 'ADS_%'"}, "{T}/proj/Berichte", PASS, TMP),
    ("Read through a symlink",
     "Read", {"file_path": "{T}/proj/Berichte/ADS_RemunerationReport_2024.pdf"}, None, ASK, TMP),
    ("Read of a plain note PASS",
     "Read", {"file_path": "{T}/proj/Notizen/n.md"}, None, PASS, TMP),
    ("Write of a new file into documents",
     "Write", {"file_path": "{T}/rag-cli/data/documents/bom1-reference/new.md", "content": "x"}, None, ASK, TMP),
    ("Write of a new file into pdf (production paths)",
     "Write", {"file_path": PROD + "/data/pdf/bom1/new.pdf", "content": "x"}, None, ASK, PROD_ROOTS),
    ("Edit of a document",
     "Edit", {"file_path": "{T}/rag-cli/data/documents/wise2627-reference/BOM1_x.md", "old_string": "a", "new_string": "b"}, None, ASK, TMP),
    ("Glob in the symlink directory",
     "Glob", {"path": "{T}/proj/Berichte", "pattern": "*.pdf"}, None, ASK, TMP),
    ("Glob with absolute pattern into pdf",
     "Glob", {"pattern": "{T}/rag-cli/data/pdf/**/*.pdf"}, None, ASK, TMP),
    ("Glob in a plain directory PASS",
     "Glob", {"path": "{T}/proj/Notizen", "pattern": "*.md"}, None, PASS, TMP),
    ("Grep on the documents tree",
     "Grep", {"pattern": "x", "path": "{T}/rag-cli/data/documents"}, None, ASK, TMP),
    ("Grep without path from the symlink directory",
     "Grep", {"pattern": "x"}, "{T}/proj/Berichte", ASK, TMP),
    ("Grep on a plain directory PASS",
     "Grep", {"pattern": "x", "path": "{T}/proj/Notizen"}, None, PASS, TMP),
    ("unrelated tool Task PASS",
     "Task", {"prompt": "{T}/rag-cli/data/pdf"}, None, PASS, TMP),
]


# ORCHESTRATOR

def test_ask_rag_storage_workflow() -> None:
    sys.exit(run_case_strands(globals(), __file__, _all_runners()))


# FUNCTIONS

def _all_runners() -> dict:
    runners = case_runners(CASES, _check_case)
    runners.update(fail_open_runner("malformed stdin payload fails open", _run_raw, b"not valid json at all"))
    runners.update(function_runners([_check_ask_output_shape, _check_fire_log_record]))
    return runners


def _check_case(case: tuple) -> None:
    desc, tool, tool_input, cwd, expect_ask, root_mode = case
    with tempfile.TemporaryDirectory(prefix="ask_rag_storage_") as tmp:
        _build_tree(tmp)
        result = _run(tool, tool_input, cwd, root_mode, tmp)
    asked = _decision(result.stdout) == "ask"
    ok = asked == expect_ask and result.returncode == 0
    report_case(desc, ok, f": exit={result.returncode} asked={asked} (expected {expect_ask})")


def _build_tree(base: str) -> None:
    root = Path(base)
    bom1 = root / "rag-cli" / "data" / "pdf" / "bom1"
    documents = root / "rag-cli" / "data" / "documents" / "bom1-reference"
    berichte = root / "proj" / "Berichte"
    for directory in (bom1, documents, berichte, root / "proj" / "Notizen", root / "proj" / "plain",
                      root / "rag-cli" / "data" / "pdf-old", root / "rag-cli" / "data" / "documents" / "wise2627-reference"):
        directory.mkdir(parents=True, exist_ok=True)
    for name in ("ADS_RemunerationReport_2024.pdf", "DAI_AnnualReport_2024.pdf"):
        (bom1 / name).write_bytes(b"%PDF")
        os.symlink(bom1 / name, berichte / name)
    (documents / "x.md").write_text("x")
    (root / "proj" / "Notizen" / "n.md").write_text("n")


def _run(tool: str, tool_input: dict, cwd, root_mode: str, base: str, log_path: str = None, session_id: str = None):
    payload = {"tool_name": tool, "tool_input": json.loads(json.dumps(tool_input).replace("{T}", base))}
    if cwd:
        payload["cwd"] = cwd.replace("{T}", base)
    if session_id:
        payload["session_id"] = session_id
    extra_env = {"HOME": PINNED_HOME, ROOTS_ENV: None}
    if root_mode == TMP:
        extra_env[ROOTS_ENV] = os.pathsep.join([f"{base}/rag-cli/data/pdf", f"{base}/rag-cli/data/documents"])
    if log_path:
        extra_env[FIRING_LOG_ENV] = log_path
    return run_hook(HOOK, json.dumps(payload).encode(), extra_env=extra_env)


def _run_raw(stdin_bytes: bytes) -> int:
    return run_hook(HOOK, stdin_bytes).returncode


def _decision(stdout: bytes):
    if not stdout.strip():
        return None
    return json.loads(stdout)["hookSpecificOutput"]["permissionDecision"]


def _check_ask_output_shape() -> None:
    with tempfile.TemporaryDirectory(prefix="ask_rag_storage_") as tmp:
        _build_tree(tmp)
        result = _run("Bash", {"command": "ls {T}/rag-cli/data/pdf/bom1"}, None, TMP, tmp)
    output = json.loads(result.stdout)["hookSpecificOutput"]
    ok = (output["hookEventName"] == "PreToolUse" and output["permissionDecision"] == "ask"
          and "RAG storage" in output["permissionDecisionReason"] and "updatedInput" not in output
          and result.returncode == 0 and not result.stderr)
    report_case("ask output: PreToolUse ask with reason, exit 0, no stderr, no updatedInput", ok)


def _check_fire_log_record() -> None:
    with tempfile.TemporaryDirectory(prefix="ask_rag_storage_") as tmp:
        _build_tree(tmp)
        log_path = str(Path(tmp) / "fire.jsonl")
        _run("Bash", {"command": "ls {T}/proj/Berichte"}, None, TMP, tmp, log_path=log_path, session_id="s-ask")
        records = [json.loads(line) for line in Path(log_path).read_text().splitlines() if line.strip()]
    record = records[-1] if records else {}
    ok = (record.get("decision") == "ask" and record.get("hook") == "ask_rag_storage"
          and record.get("session") == "s-ask" and bool(record.get("reason")) and "rewritten" not in record)
    report_case("fire log: decision=ask with reason and session, no rewritten field", ok)


if __name__ == "__main__":
    test_ask_rag_storage_workflow()
