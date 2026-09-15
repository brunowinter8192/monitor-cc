# INFRASTRUCTURE
import glob
import json
import os
import re
import sys
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "src", "hooks"))
from block_non_canonical_edit import _decide

_REPO_ROOT = Path(__file__).resolve().parents[2]
_CORPUS_GLOB = str(_REPO_ROOT / "dev" / "cache" / "jsonl" / "bash_file_mods_*.jsonl")
_REPORT_PATH = Path(__file__).parent / "md" / "block_non_canonical_edit_corpus_report.md"

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


def _write_report(results: list) -> None:
    _REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    counts = {"allow": 0, "block": 0, "error": 0}
    for r in results:
        counts[r["verdict"]] = counts.get(r["verdict"], 0) + 1
    lines = []
    lines.append("# block_non_canonical_edit corpus verification")
    lines.append("")
    lines.append(f"Total records evaluated: {len(results)}")
    lines.append(f"allow: {counts.get('allow', 0)}")
    lines.append(f"block: {counts.get('block', 0)}")
    lines.append(f"error: {counts.get('error', 0)}")
    lines.append("")
    lines.append("`cwd_guess` is a leading `cd <path>` extracted from the command text itself for this ")
    lines.append("offline verification only -- the real hook uses the `cwd` field Claude Code sends on ")
    lines.append("its own stdin payload, which this corpus does not carry. A record with no leading `cd` ")
    lines.append("shows `cwd_guess: null` and any relative path in it could not be resolved against the ")
    lines.append("session's real working directory.")
    lines.append("")
    lines.append("## BLOCK verdicts (full list)")
    lines.append("")
    for r in results:
        if r["verdict"] != "block":
            continue
        lines.append(f"- session={r['session']} tool_use_id={r['tool_use_id']} matched_forms={r['matched_forms']} cwd_guess={r['cwd_guess']!r}")
        lines.append(f"  command: {r['command'][:200]!r}")
        lines.append(f"  reason (first line): {r['reason'].splitlines()[0]}")
        lines.append("")
    lines.append("## ERROR verdicts (full list)")
    lines.append("")
    for r in results:
        if r["verdict"] != "error":
            continue
        lines.append(f"- session={r['session']} tool_use_id={r['tool_use_id']} matched_forms={r['matched_forms']}")
        lines.append(f"  command: {r['command'][:200]!r}")
        lines.append(f"  error: {r['reason']}")
        lines.append("")
    lines.append("## ALLOW verdicts (first 40, for spot-checking)")
    lines.append("")
    allow_shown = 0
    for r in results:
        if r["verdict"] != "allow":
            continue
        if allow_shown >= 40:
            break
        allow_shown += 1
        lines.append(f"- session={r['session']} tool_use_id={r['tool_use_id']} matched_forms={r['matched_forms']} cwd_guess={r['cwd_guess']!r}")
        lines.append(f"  command: {r['command'][:200]!r}")
        lines.append("")
    _REPORT_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")


if __name__ == "__main__":
    verify_workflow()
