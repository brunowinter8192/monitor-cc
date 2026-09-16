# INFRASTRUCTURE
from datetime import datetime, timezone
from pathlib import Path

from main_log_elimination_reconstruct import _DELTA_COVERED

_AREA_ROOT = Path(__file__).resolve().parent
while _AREA_ROOT.name != 'proxy_dual_log':
    _AREA_ROOT = _AREA_ROOT.parent

# FUNCTIONS

def _report_header(session: str, paths: dict, a: dict, now, date_str: str) -> list:
    lines = [f"# Main Log Elimination Probe — {date_str}"]
    lines.append(f"\n**Session:** `{session}`")
    lines.append(f"**Dataset:** `{paths['main'].name}` ({a['main_count']} request entries, {a['fwd_count']} forwarded entries)")
    lines.append(f"**Run:** {now.strftime('%Y-%m-%dT%H:%M:%SZ')}")
    return lines


def _report_question_a_summary(a: dict) -> tuple:
    lines = ["\n---"]
    lines.append("\n## Question A — Forwarded Reconstruction vs Main Log raw_payload")
    lines.append("\n### Method")
    lines.append(
        "Accumulated `_forwarded` delta log per-model-family into full `{system, tools, messages}` "
        "payloads. Matched to main-log `raw_payload` by position (request_ids absent in quartet; "
        "proxy writes both logs serially in same request() hook). "
        "Cache_control stripped from both sides before content comparison. "
        "Messages additionally normalized via `_normalize_msg_shape_for_hash` (user single-text-block → string)."
    )

    lines.append("\n### Content Match Summary")
    n = a["n"]
    lines.append(f"\n| Section | Matches | Total | Verdict |")
    lines.append(f"|---|---|---|---|")
    lines.append(f"| system | {a['total_sys_match']} | {n} | {'✅ LOSSLESS' if a['total_sys_match'] == n else '❌ DIVERGENCE'} |")
    lines.append(f"| tools | {a['total_tools_match']} | {n} | {'✅ LOSSLESS' if a['total_tools_match'] == n else '❌ DIVERGENCE'} |")
    lines.append(f"| messages | {a['total_msgs_match']} | {n} | {'✅ LOSSLESS' if a['total_msgs_match'] == n else '❌ DIVERGENCE'} |")

    all_content_lossless = (
        a["total_sys_match"] == n and
        a["total_tools_match"] == n and
        a["total_msgs_match"] == n
    )
    lines.append(
        f"\n**Content verdict (after cache_control normalize): "
        f"{'LOSSLESS — system/tools/messages reconstruct exactly' if all_content_lossless else 'DIVERGENCE — see per-request table'}**"
    )

    lines.append("\n### Cache_control (BP) Count Divergence")
    lines.append("\nExpected: main log raw_payload carries pre-cache-ops CC markers (CC's original); "
                 "_forwarded carries post-cache-ops proxy BP markers. Count WILL differ — this is known.")
    lines.append("\n| Req# | model | BP main (pre-ops) | BP reconstructed (post-ops) | Δ |")
    lines.append("|---|---|---|---|---|")
    for r in a["per_request"]:
        delta = r["bp_fwd"] - r["bp_main"]
        lines.append(
            f"| {r['idx']} | {r['model'][:30]} | {r['bp_main']} | {r['bp_fwd']} | {delta:+d} |"
        )

    return lines, all_content_lossless


def _report_question_a_divergences(a: dict) -> list:
    lines = []
    divergent = [r for r in a["per_request"] if not (r["sys_match"] and r["tools_match"] and r["msgs_match"])]
    if divergent:
        lines.append("\n### Content Divergences (per request)")
        for r in divergent:
            lines.append(f"\n**Req {r['idx']}** model={r['model']} family={r['family']}")
            if not r["sys_match"]:
                lines.append(f"  - system: {'; '.join(r['sys_div'])}")
            if not r["tools_match"]:
                lines.append(f"  - tools: {'; '.join(r['tools_div'])}")
            if not r["msgs_match"]:
                lines.append(f"  - messages (raw_count={r['raw_msg_count']} fwd_count={r['fwd_msg_count']}): {'; '.join(r['msgs_div'])}")
    else:
        lines.append("\n_No content divergences after normalization._")
    return lines


def _report_question_a_fields(a: dict) -> tuple:
    lines = ["\n### Top-level Field Classification"]
    lines.append("\nFields in `raw_payload` not in `{system, tools, messages, model}`:")
    lines.append("\n| Field | Status | Notes |")
    lines.append("|---|---|---|")
    for field, status, note in a["field_classification"]:
        if field in _DELTA_COVERED:
            continue
        lines.append(f"| `{field}` | {status} | {note} |")

    lines.append("\n#### Must-Add fields for _forwarded write-side")
    must_add = [(f, n) for f, s, n in a["field_classification"] if s == "MUST-ADD"]
    if must_add:
        for field, note in must_add:
            lines.append(f"- **`{field}`**: {note}")
    else:
        lines.append("_None identified._")

    lines.append("\n#### Metadata-pane-only fields (irrelevant after deletion)")
    meta_only = [(f, n) for f, s, n in a["field_classification"] if s == "metadata-pane-only"]
    for field, note in meta_only:
        lines.append(f"- `{field}`: {note}")

    return lines, must_add, meta_only


def _report_question_b(b: dict) -> list:
    lines = ["\n---"]
    lines.append("\n## Question B — Tool Error Extraction from _original")
    lines.append("\n### Method")
    lines.append(
        "Scanned all `_original` payload messages for `type=tool_result` blocks with `is_error=True`. "
        "Deduplicated by `tool_use_id` (same error reappears in every subsequent request's cumulative history). "
        "Compared extracted set against `tool_errors.jsonl` entries whose `proxy_file` matches this session."
    )

    lines.append(f"\n**Unique errors extracted from _original (by tool_use_id):** {b['extracted_count']}")
    lines.append(f"**Entries in tool_errors.jsonl for this session:** {b['persisted_count']}")

    if b["exact_match"]:
        lines.append("\n**Verdict: ✅ EXACT MATCH — quartet produces identical error set as main-log scan**")
    else:
        lines.append("\n**Verdict: ❌ MISMATCH**")
        if b["only_in_extracted"]:
            lines.append(f"\nOnly in _original extraction (not in tool_errors.jsonl): {b['only_in_extracted']}")
        if b["only_in_persisted"]:
            lines.append(f"\nOnly in tool_errors.jsonl (not extracted from _original): {b['only_in_persisted']}")

    lines.append("\n### Extracted Errors")
    if b["unique_errors"]:
        lines.append("\n| tool_use_id | first_entry | first_msg | content_preview |")
        lines.append("|---|---|---|---|")
        for e in b["unique_errors"]:
            preview = e["content_preview"].replace("|", "\\|").replace("\n", " ")[:120]
            lines.append(
                f"| `{e['tool_use_id']}` | {e['first_seen_entry']} | {e['first_seen_msg']} | {preview} |"
            )
    else:
        lines.append("\n_No is_error=True tool_result blocks found._")

    if b["tool_errors_records"]:
        lines.append("\n### tool_errors.jsonl Records for This Session")
        lines.append("\n| tool_use_id | worker | tool_name | request_id |")
        lines.append("|---|---|---|---|")
        for r in b["tool_errors_records"]:
            lines.append(
                f"| `{r.get('tool_use_id','')}` | {r.get('worker','')} | {r.get('tool_name','')} | `{r.get('request_id','')}` |"
            )

    return lines


def _report_migration_verdict(b: dict, all_content_lossless: bool, must_add: list, meta_only: list) -> list:
    lines = ["\n---"]
    lines.append("\n## Migration Verdict")

    lines.append("\n### A — Content (system/tools/messages)")
    if all_content_lossless:
        lines.append(
            "**LOSSLESS** after cache_control normalization. "
            "The `_forwarded` delta log reconstructs system/tools/messages exactly. "
            "The known BP-count divergence is structural (pre-ops vs post-ops cache markers) "
            "and not a data loss — cache_control is stripped before any content comparison."
        )
    else:
        lines.append("**NOT lossless** — see divergences above.")

    lines.append("\n### A — Missing Top-level Fields (migration action required)")
    lines.append(
        f"\n`_forwarded` only carries `{{system, tools, messages, model}}`. "
        f"The following fields must be added to `_build_forwarded_delta` write-side "
        f"to allow the read-side to eliminate the main log:"
    )
    for field, note in must_add:
        lines.append(f"\n- **`{field}`** — {note}")
    if not must_add:
        lines.append("\n_No must-add fields identified._")

    lines.append(
        f"\n{len(meta_only)} metadata-pane-only fields (`"
        + "`, `".join(f for f, _ in meta_only)
        + "`) are irrelevant after the metadata pane deletion — no migration action needed."
    )

    lines.append("\n### B — Error Set")
    if b["exact_match"]:
        lines.append(
            "**EXACT MATCH.** The proxy can derive the tool-error set write-side from the `_original` "
            "quartet log using `tool_use_id`-based dedup. The current `tool_errors.jsonl` write path "
            "(which reads the main log) can be migrated to read from `_original` without information loss."
        )
    else:
        lines.append("**MISMATCH** — error set is not fully derivable from _original. Investigation required.")

    return lines


def _write_report(session: str, paths: dict, a: dict, b: dict) -> Path:
    now = datetime.now(timezone.utc)
    date_str = now.strftime("%Y%m%d")
    report_dir = _AREA_ROOT / "main_log_elimination_probe_reports"
    report_dir.mkdir(exist_ok=True)
    report_path = report_dir / f"{date_str}.md"

    lines = _report_header(session, paths, a, now, date_str)
    a_summary_lines, all_content_lossless = _report_question_a_summary(a)
    lines += a_summary_lines
    lines += _report_question_a_divergences(a)
    a_fields_lines, must_add, meta_only = _report_question_a_fields(a)
    lines += a_fields_lines
    lines += _report_question_b(b)
    lines += _report_migration_verdict(b, all_content_lossless, must_add, meta_only)

    report_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return report_path
