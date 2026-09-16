# INFRASTRUCTURE
import glob
import json
import os
import re
import sys
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "src", "hooks"))
from block_non_canonical_edit import _decide

from verify_block_non_canonical_edit_report import _write_report

_REPO_ROOT = Path(__file__).resolve().parents[2]
_CORPUS_GLOB = str(_REPO_ROOT / "dev" / "cache" / "jsonl" / "bash_file_mods_*.jsonl")

_LEADING_CD_RE = re.compile(r"^\s*cd\s+([^\s;&|]+)")


# ORCHESTRATOR

def verify_workflow() -> None:
    records = _load_corpus_records()
    results = [_evaluate(r) for r in records]
    _write_report(results)


# FUNCTIONS

def _load_corpus_records() -> list:
    records = []
    for path in sorted(glob.glob(_CORPUS_GLOB)):
        with open(path, encoding="utf-8") as f:
            for line in f:
                records.append(json.loads(line))
    return records


def _testing_cwd(command: str):
    m = _LEADING_CD_RE.match(command)
    if not m:
        return None
    return m.group(1).strip("'\"")


def _evaluate(record: dict) -> dict:
    cwd = _testing_cwd(record["command"])
    try:
        verdict, reason = _decide(record["command"], cwd)
    except Exception as e:
        verdict, reason = "error", f"{type(e).__name__}: {e}"
    return {
        "session": record["session"],
        "tool_use_id": record["tool_use_id"],
        "matched_forms": record["matched_forms"],
        "command": record["command"],
        "cwd_guess": cwd,
        "verdict": verdict,
        "reason": reason,
    }


if __name__ == "__main__":
    verify_workflow()
