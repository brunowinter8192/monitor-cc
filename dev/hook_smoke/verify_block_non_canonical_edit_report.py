# INFRASTRUCTURE
from pathlib import Path

_REPORT_PATH = Path(__file__).parent / "md" / "block_non_canonical_edit_corpus_report.md"


# FUNCTIONS

def _count_verdicts(results):
    counts = {"allow": 0, "block": 0, "error": 0}
    for r in results:
        counts[r["verdict"]] = counts.get(r["verdict"], 0) + 1
    return counts


def _render_header(results, counts):
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
    return lines


def _render_block_section(results):
    lines = []
    lines.append("## BLOCK verdicts (full list)")
    lines.append("")
    for r in results:
        if r["verdict"] != "block":
            continue
        lines.append(f"- session={r['session']} tool_use_id={r['tool_use_id']} matched_forms={r['matched_forms']} cwd_guess={r['cwd_guess']!r}")
        lines.append(f"  command: {r['command'][:200]!r}")
        lines.append(f"  reason (first line): {r['reason'].splitlines()[0]}")
        lines.append("")
    return lines


def _render_error_section(results):
    lines = []
    lines.append("## ERROR verdicts (full list)")
    lines.append("")
    for r in results:
        if r["verdict"] != "error":
            continue
        lines.append(f"- session={r['session']} tool_use_id={r['tool_use_id']} matched_forms={r['matched_forms']}")
        lines.append(f"  command: {r['command'][:200]!r}")
        lines.append(f"  error: {r['reason']}")
        lines.append("")
    return lines


def _render_allow_section(results):
    lines = []
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
    return lines


def _write_report(results: list) -> None:
    _REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    counts = _count_verdicts(results)
    lines = []
    lines += _render_header(results, counts)
    lines += _render_block_section(results)
    lines += _render_error_section(results)
    lines += _render_allow_section(results)
    _REPORT_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")
