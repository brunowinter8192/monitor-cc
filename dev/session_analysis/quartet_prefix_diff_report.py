# INFRASTRUCTURE
from datetime import datetime

from quartet_prefix_diff_load import REBUILD_CR_RATIO_THRESHOLD
from quartet_prefix_diff_findings import build_findings_summary

# FUNCTIONS

def _build_report_header_lines(fwd_path, session_path, original_path, mapping_notes):
    return [
        "# Quartet Prefix-Diff Forensic Report",
        "",
        f"**Forwarded log:** `{fwd_path}`",
        f"**Session JSONL:** `{session_path}`",
        f"**Original log:** `{original_path}`" if original_path else "**Original log:** _not provided — no client-vs-proxy attribution_",
        f"**Generated:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        "",
        "## Methodology — REQ Number Mapping",
        "",
        "Ground-truth REQ numbers are built by grouping session-JSONL `type=assistant` lines by their "
        "`(cache_read, cache_creation, input, output)` usage tuple — consecutive identical tuples "
        "(including ones separated by interleaved `type=user` tool_result lines from mid-stream tool "
        "execution within the SAME response) collapse into one request. This differs from naive line "
        "position because a single response streams multiple content blocks (thinking/tool_use) as "
        "separate JSONL lines.",
        "",
        "Forwarded-log opus-family entries are aligned to these ground-truth requests by timestamp: "
        "each `forwarded_delta.timestamp` is the SEND time; a ground-truth request's forwarded state is "
        "the LAST forwarded entry sent at or before the request's response timestamp (monotonic "
        "two-pointer). Forwarded entries with no corresponding ground-truth response (retried/aborted "
        "sends) are silently absorbed — this makes the mapping N:1 in places, not a fixed index offset.",
        "",
        f"| Metric | Value |",
        f"|---|---|",
        f"| Opus forwarded-log entries | {mapping_notes['opus_fwd_entries']} |",
        f"| Opus ground-truth request groups | {mapping_notes['opus_gt_groups']} |",
        f"| Ground-truth requests with no forwarded match | {mapping_notes['unmatched_ground_truth']} |",
        f"| Forwarded entries absorbed (retries, no distinct response) | "
        f"{mapping_notes['opus_fwd_entries'] - mapping_notes['opus_gt_groups'] + mapping_notes['unmatched_ground_truth']} |",
        "",
        "**Cache-control breakpoint markers are NOT reported below** (known prior finding): the forwarded "
        "delta chain hashes each element with `cache_control` STRIPPED before comparing "
        "(`logging._delta_hash` -> `_strip_cache_control`), so a marker-only change (breakpoint moved, no "
        "content change) never enters `messages_delta` and is invisible to this reconstruction. A "
        "replayed message's `cache_control` can be stale — carried over from an earlier request's delta "
        "even when the actually-sent marker position for the CURRENT request differs. The true sent "
        "breakpoint positions are not derivable from the quartet reconstruction; use `04_cache_validation.py` "
        "against the single-log format, or the live proxy pane, for breakpoint placement.",
        "",
        "## Auto-Detected CR-Collapse Points",
        "",
        f"Rule: `CC > CR` and `CR < {REBUILD_CR_RATIO_THRESHOLD} x max(CR seen so far in session)` "
        "(mirrors `03_cache_rebuild_context.py`).",
        "",
    ]

def _build_collapse_points_lines(collapse_points, mapped):
    lines = []
    if collapse_points:
        lines.append("| REQ | CR | CC | D | prior max CR |")
        lines.append("|---|---|---|---|---|")
        prev_max = 0
        for m in mapped:
            if m["req"] in collapse_points:
                lines.append(f"| {m['req']} | {m['cr']:,} | {m['cc']:,} | {m['d']:,} | {prev_max:,} |")
            prev_max = max(prev_max, m["cr"])
    else:
        lines.append("_None detected._")
    lines.append("")
    return lines

def _build_pairs_analyzed_lines(range_pairs, auto_pairs, pair_results):
    pairs_requested = sorted(set(range_pairs) | set(auto_pairs))
    return [
        "## Pairs Analyzed",
        "",
        f"Requested: {pairs_requested}",
        f"Analyzed (both sides had a forwarded match): {[(r['req_prev'], r['req_curr']) for r in pair_results]}",
        "",
    ]

def _build_pair_header_and_system_lines(r):
    gp, gc = r["gt_prev"], r["gt_curr"]
    lines = [
        f"## REQ#{r['req_prev']} -> REQ#{r['req_curr']}",
        "",
        "| | CR | CC | D |",
        "|---|---|---|---|",
        f"| REQ#{r['req_prev']} | {gp['cr']:,} | {gp['cc']:,} | {gp['d']:,} |",
        f"| REQ#{r['req_curr']} | {gc['cr']:,} | {gc['cc']:,} | {gc['d']:,} |",
        "",
        "### System Blocks",
        "",
        "| idx | changed | prev_chars | curr_chars | delta_chars |",
        "|---|---|---|---|---|",
    ]
    for s in r["sys_rows"]:
        lines.append(f"| {s['idx']} | {'YES' if s['changed'] else '-'} | {s['prev_chars']:,} | "
                      f"{s['curr_chars']:,} | {s['delta_chars']:+,} |")
    return lines

def _build_pair_tools_lines(r):
    lines = [
        "",
        "### Tools",
        "",
        f"- Changed: **{'YES' if r['tools_changed'] else 'no'}**",
    ]
    if r["tools_changed"]:
        removed = set(r["tools_names_prev"]) - set(r["tools_names_curr"])
        added = set(r["tools_names_curr"]) - set(r["tools_names_prev"])
        lines.append(f"- Names removed: {sorted(removed) or '-'}")
        lines.append(f"- Names added: {sorted(added) or '-'}")
    return lines

def _build_pair_messages_lines(r):
    lines = [
        "",
        f"### Messages ({r['n_msg_prev']} -> {r['n_msg_curr']})",
        "",
        f"- First diverging message index: **{r['first_msg_diff']}**",
        f"- Modified/added/removed rows: {len(r['msg_rows'])}",
        "",
        "| idx | status | prev_chars | curr_chars | delta_chars | prev_img | curr_img | prev_types | curr_types | note |",
        "|---|---|---|---|---|---|---|---|---|---|",
    ]
    for m in r["msg_rows"]:
        img_flag = " <-IMG" if m["prev_image_count"] != m["curr_image_count"] else ""
        lines.append(
            f"| {m['idx']} | {m['status']}{img_flag} | {m['prev_chars']:,} | {m['curr_chars']:,} | "
            f"{m['delta_chars']:+,} | {m['prev_image_count']} | {m['curr_image_count']} | "
            f"{m['prev_types']} | {m['curr_types']} | {m['note']} |"
        )

    img_involved_rows = [m for m in r["msg_rows"] if m["prev_image_count"] != m["curr_image_count"]]
    total_img_removed = sum(max(0, m["prev_image_count"] - m["curr_image_count"]) for m in r["msg_rows"])
    total_img_added = sum(max(0, m["curr_image_count"] - m["prev_image_count"]) for m in r["msg_rows"])
    lines.extend([
        "",
        f"**Image blocks involved:** {'YES' if img_involved_rows else 'no'} "
        f"({len(img_involved_rows)} message(s), {total_img_removed} image block(s) removed, "
        f"{total_img_added} added)",
        "",
    ])
    return lines

def _build_pair_attribution_lines(r):
    oa = r["original_attribution"]
    if oa is None:
        return []
    lines = [
        "### Original-vs-Forwarded Attribution (client-side vs proxy-side)",
        "",
    ]
    if not oa["available"]:
        lines.append(f"_No original-log entry found for REQ#{r['req_prev']} and/or REQ#{r['req_curr']}'s flow_id._")
    elif not oa["rows"]:
        lines.append("_No `modified`-status message rows to cross-check for this pair._")
    else:
        lines.append("| idx | fwd delta_chars | orig prev_chars | orig curr_chars | verdict |")
        lines.append("|---|---|---|---|---|")
        fwd_by_idx = {m["idx"]: m for m in r["msg_rows"]}
        for row in oa["rows"]:
            fwd_delta = fwd_by_idx[row["idx"]]["delta_chars"]
            lines.append(
                f"| {row['idx']} | {fwd_delta:+,} | {row['orig_prev_chars']:,} | "
                f"{row['orig_curr_chars']:,} | {row['verdict']} |"
            )
    lines.append("")
    return lines

def _build_pair_segment_and_reconciliation_lines(r):
    lines = [
        "### Segment Attribution",
        "",
        f"- First diverging segment (raw, includes per-request system[0] churn): "
        f"`{r['first_diverge_any'][0]}[{r['first_diverge_any'][1]}]`",
        f"- First diverging segment (excluding system[0]): "
        f"`{r['first_diverge_no_sys0'][0]}[{r['first_diverge_no_sys0'][1]}]`",
        "",
        "### CR/CC Reconciliation",
        "",
    ]
    rec = r["reconciliation"]
    lines.extend([
        "| Metric | Value |",
        "|---|---|",
        f"| tiktoken estimate: system[0:3] (BP1 hypothesis) | {rec['bp1_estimate_tokens']:,} |",
        f"| tiktoken estimate: system[0:3] + tools (BP1+BP2) | {rec['bp1_plus_tools_estimate_tokens']:,} |",
        f"| Actual CR of REQ#{r['req_curr']} | {rec['actual_cr_curr']:,} |",
        f"| Recovery identity: CR[curr] == CR[prev] + CC[prev]? | "
        f"**{'HOLDS' if rec['recovery_identity_holds'] else 'does not hold'}** "
        f"({rec['recovery_lhs']:,} vs {rec['recovery_rhs']:,}) |",
        "",
    ])
    return lines

def build_pair_section(r):
    lines = _build_pair_header_and_system_lines(r)
    lines.extend(_build_pair_tools_lines(r))
    lines.extend(_build_pair_messages_lines(r))
    lines.extend(_build_pair_attribution_lines(r))
    lines.extend(_build_pair_segment_and_reconciliation_lines(r))
    return lines

def build_report(fwd_path, session_path, original_path, ground_truth, mapped, mapping_notes,
                  collapse_points, range_pairs, auto_pairs, pair_results):
    lines = _build_report_header_lines(fwd_path, session_path, original_path, mapping_notes)
    lines.extend(_build_collapse_points_lines(collapse_points, mapped))
    lines.extend(_build_pairs_analyzed_lines(range_pairs, auto_pairs, pair_results))

    for r in pair_results:
        lines.extend(build_pair_section(r))

    lines.extend(build_findings_summary(pair_results))
    return "\n".join(lines)
