"""
main_log_elimination_probe.py — Feasibility probe for eliminating the main log.

Answers two questions on a real session:

  Question A (Forwarded reconstruction):
    Accumulate _forwarded delta log into a full forwarded payload per request.
    Diff against main log raw_payload (pre-cache-ops) after normalising cache_control.
    Report content match, BP-count divergence, and missing top-level fields.

  Question B (Error extraction):
    Extract is_error==True tool_result blocks from _original payloads.
    Dedup by tool_use_id. Compare against tool_errors.jsonl for this session.

Session data:
  Main log:     src/logs/api_requests_<session>.jsonl
  Quartet:      src/logs/dual_log/api_requests_<session>_{original,forwarded,...}.jsonl
  Tool errors:  src/logs/tool_errors.jsonl

Matching strategy: positional — entry N in _forwarded == request entry N in main log.
Both are written by the same serial proxy request() hook in identical order.
Request IDs are empty in quartet (CC sends no x-request-id header); main log uses UUID4.

Usage (from project root):
    ./venv/bin/python dev/proxy_dual_log/main_log_elimination_probe.py <session_suffix>

    <session_suffix> is the log_id portion, e.g. opus_monitor_cc_1780602018

    Paths are resolved relative to the project root (MONITOR_CC_ROOT or auto-detected).
"""

# INFRASTRUCTURE
import argparse
import hashlib
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

# ORCHESTRATOR

def main_log_elimination_probe_workflow(session: str) -> None:
    root = _resolve_root()
    paths = _resolve_paths(root, session)
    _check_paths(paths)

    main_entries = _load_main_log(paths["main"])
    fwd_entries = _load_jsonl(paths["fwd"])
    orig_entries = _load_jsonl(paths["orig"])
    tool_errors = _load_tool_errors(paths["tool_errors"], session)

    a_results = _run_question_a(main_entries, fwd_entries)
    b_results = _run_question_b(orig_entries, tool_errors)

    report_path = _write_report(session, paths, a_results, b_results)
    print(report_path)

# FUNCTIONS

# Recursively strip cache_control keys — verbatim copy of src/proxy/logging.py:_strip_cache_control
def _strip_cache_control(obj):
    if isinstance(obj, dict):
        return {k: _strip_cache_control(v) for k, v in obj.items() if k != "cache_control"}
    if isinstance(obj, list):
        return [_strip_cache_control(item) for item in obj]
    return obj


# Mirror of cache._normalize_user_content_shape — verbatim copy of src/proxy/logging.py:_normalize_msg_shape_for_hash
def _normalize_msg_shape_for_hash(msg: dict) -> dict:
    if msg.get("role") != "user":
        return msg
    content = msg.get("content")
    if not isinstance(content, list) or len(content) != 1:
        return msg
    block = content[0]
    if not isinstance(block, dict):
        return msg
    if set(block.keys()) == {"type", "text"} and block["type"] == "text":
        return {**msg, "content": block["text"]}
    return msg


# Infer model family from model string — mirrors src/proxy_display/parser.py:_infer_model_family
def _infer_family(model: str) -> str:
    m = model.lower()
    if "haiku" in m:
        return "haiku"
    if "sonnet" in m:
        return "sonnet"
    return "opus"


# Resolve project root from env or __file__
def _resolve_root() -> Path:
    env = os.environ.get("MONITOR_CC_ROOT")
    if env:
        return Path(env)
    return Path(__file__).parent.parent.parent


# Build all log file paths for the session
def _resolve_paths(root: Path, session: str) -> dict:
    logs = root / "src" / "logs"
    dual = logs / "dual_log"
    return {
        "main": logs / f"api_requests_{session}.jsonl",
        "orig": dual / f"api_requests_{session}_original.jsonl",
        "fwd": dual / f"api_requests_{session}_forwarded.jsonl",
        "stripped": dual / f"api_requests_{session}_stripped.jsonl",
        "injected": dual / f"api_requests_{session}_injected.jsonl",
        "tool_errors": logs / "tool_errors.jsonl",
    }


# Fail-fast if any required log file is missing
def _check_paths(paths: dict) -> None:
    for key in ("main", "orig", "fwd"):
        p = paths[key]
        if not p.exists():
            print(f"ERROR: {key} log not found: {p}", file=sys.stderr)
            sys.exit(1)


# Load JSONL, skip blank lines and bad JSON
def _load_jsonl(path: Path) -> list:
    entries = []
    with open(path, encoding="utf-8") as f:
        for lineno, line in enumerate(f, 1):
            line = line.strip()
            if not line:
                continue
            try:
                entries.append(json.loads(line))
            except json.JSONDecodeError as e:
                print(f"  [warn] {path.name}:{lineno} — {e}", file=sys.stderr)
    return entries


# Load main log — return only request entries (no type field), preserving order
def _load_main_log(path: Path) -> list:
    all_entries = _load_jsonl(path)
    return [e for e in all_entries if "type" not in e]


# Load tool_errors.jsonl — filter by proxy_file containing session suffix
def _load_tool_errors(path: Path, session: str) -> list:
    if not path.exists():
        return []
    all_records = _load_jsonl(path)
    return [r for r in all_records if session in r.get("proxy_file", "")]


# Count cache_control markers recursively in a payload element
def _count_cache_control(obj) -> int:
    if isinstance(obj, dict):
        count = 1 if "cache_control" in obj else 0
        return count + sum(_count_cache_control(v) for v in obj.values())
    if isinstance(obj, list):
        return sum(_count_cache_control(item) for item in obj)
    return 0


# Reconstruct full forwarded payloads from the delta stream, per-model-family.
# Returns list of dicts matching order of forwarded entries:
#   {model, system, tools, messages, is_first, counts}
def _reconstruct_forwarded(fwd_entries: list) -> list:
    chain: dict = {}  # family → {system: [], tools: [], messages: []}
    results = []
    for entry in fwd_entries:
        if entry.get("type") != "forwarded_delta":
            continue
        model = entry.get("model", "")
        family = _infer_family(model)
        is_first = entry.get("is_first", False)
        counts = entry.get("counts", {})

        if is_first:
            curr = {
                "system": _dict_to_list(entry.get("system_delta", {}), counts.get("system", 0)),
                "tools": _dict_to_list(entry.get("tools_delta", {}), counts.get("tools", 0)),
                "messages": _dict_to_list(entry.get("messages_delta", {}), counts.get("messages", 0)),
            }
        else:
            prev = chain.get(family, {"system": [], "tools": [], "messages": []})
            curr = {}
            for cat in ("system", "tools", "messages"):
                lst = list(prev[cat])
                for idx_str, elem in entry.get(f"{cat}_delta", {}).items():
                    i = int(idx_str)
                    while len(lst) <= i:
                        lst.append(None)
                    lst[i] = elem
                curr[cat] = lst[:counts.get(cat, len(lst))]

        chain[family] = curr
        results.append({
            "model": model,
            "family": family,
            "is_first": is_first,
            "counts": counts,
            "system": curr["system"],
            "tools": curr["tools"],
            "messages": curr["messages"],
        })
    return results


# Expand {idx_str: elem} dict into list of length n, filling gaps with None
def _dict_to_list(d: dict, n: int) -> list:
    lst = [None] * n
    for idx_str, elem in d.items():
        i = int(idx_str)
        if i < n:
            lst[i] = elem
    return lst


# Normalize a reconstructed element for comparison: strip cache_control + normalize msg shape
def _normalize_elem(elem, is_message: bool = False) -> str:
    stripped = _strip_cache_control(elem)
    if is_message and isinstance(stripped, dict):
        stripped = _normalize_msg_shape_for_hash(stripped)
    return json.dumps(stripped, sort_keys=True)


# Fields classification: which raw_payload top-level fields are needed by proxy pane vs metadata-only
_PROXY_PANE_FIELDS = {
    "model": "already in _forwarded entry.model",
    "max_tokens": "MUST-ADD — proxy pane header: think:Nk via _fmt_thinking_budget(max_tokens)",
    "output_config": "MUST-ADD — proxy pane header: eff:X via output_config.effort → effort_value",
}
_METADATA_PANE_FIELDS = {
    "temperature": "metadata-pane-only → irrelevant after deletion",
    "top_p": "metadata-pane-only → irrelevant after deletion",
    "top_k": "metadata-pane-only → irrelevant after deletion",
    "tool_choice": "metadata-pane-only → irrelevant after deletion",
    "thinking": "metadata-pane-only (thinking_config/budget_tokens); proxy pane uses max_tokens directly",
    "context_management": "metadata-pane-only → irrelevant after deletion",
    "metadata": "metadata-pane-only (request metadata) → irrelevant after deletion",
    "diagnostics": "metadata-pane-only → irrelevant after deletion",
    "stream": "metadata-pane-only → irrelevant after deletion",
}
# system / tools / messages are reconstructed from the delta; model is in the delta entry header
_DELTA_COVERED = {"system", "tools", "messages", "model"}


# Run Question A: compare reconstructed forwarded payloads against main log raw_payloads
def _run_question_a(main_entries: list, fwd_entries: list) -> dict:
    reconstructed = _reconstruct_forwarded(fwd_entries)

    if len(main_entries) != len(reconstructed):
        print(
            f"  [warn] main log has {len(main_entries)} request entries but forwarded has {len(reconstructed)} — "
            "positional match may be off. Results may be unreliable.",
            file=sys.stderr,
        )

    n = min(len(main_entries), len(reconstructed))
    per_request = []
    total_sys_match = total_tools_match = total_msgs_match = 0
    total_sys = total_tools = total_msgs = 0

    # Collect all top-level field keys seen across ALL raw_payloads (to build the complete classification)
    all_raw_keys: set = set()

    for i in range(n):
        main_e = main_entries[i]
        fwd_r = reconstructed[i]

        raw_payload = main_e.get("raw_payload", {})
        all_raw_keys.update(raw_payload.keys())

        # BP count: count cache_control markers in each side
        bp_main = _count_cache_control(raw_payload)
        bp_fwd = _count_cache_control({
            "system": fwd_r["system"],
            "tools": fwd_r["tools"],
            "messages": fwd_r["messages"],
        })

        # Normalize both sides: strip cache_control + normalize message shape
        raw_sys = [_normalize_elem(b) for b in (raw_payload.get("system") or [])]
        raw_tools = [_normalize_elem(t) for t in (raw_payload.get("tools") or [])]
        raw_msgs = [_normalize_elem(m, is_message=True) for m in (raw_payload.get("messages") or [])]

        fwd_sys = [_normalize_elem(b) for b in (fwd_r["system"] or [])]
        fwd_tools = [_normalize_elem(t) for t in (fwd_r["tools"] or [])]
        fwd_msgs = [_normalize_elem(m, is_message=True) for m in (fwd_r["messages"] or [])]

        sys_match = raw_sys == fwd_sys
        tools_match = raw_tools == fwd_tools
        msgs_match = raw_msgs == fwd_msgs

        # Count element-level divergences for non-matching sections
        sys_div = _element_divergences(raw_sys, fwd_sys) if not sys_match else []
        tools_div = _element_divergences(raw_tools, fwd_tools) if not tools_match else []
        msgs_div = _element_divergences(raw_msgs, fwd_msgs) if not msgs_match else []

        # Missing top-level fields (in raw_payload but not reconstructable from _forwarded)
        missing_fields = [k for k in raw_payload.keys() if k not in _DELTA_COVERED]

        total_sys += 1
        total_tools += 1
        total_msgs += 1
        if sys_match:
            total_sys_match += 1
        if tools_match:
            total_tools_match += 1
        if msgs_match:
            total_msgs_match += 1

        per_request.append({
            "idx": i,
            "request_id": main_e.get("request_id", ""),
            "model": main_e.get("model", ""),
            "family": fwd_r["family"],
            "is_first": fwd_r["is_first"],
            "bp_main": bp_main,
            "bp_fwd": bp_fwd,
            "sys_match": sys_match,
            "tools_match": tools_match,
            "msgs_match": msgs_match,
            "sys_div": sys_div,
            "tools_div": tools_div,
            "msgs_div": msgs_div,
            "raw_msg_count": len(raw_msgs),
            "fwd_msg_count": len(fwd_msgs),
            "missing_fields": missing_fields,
        })

    # Classify all raw payload keys seen
    field_classification = _classify_fields(all_raw_keys)

    return {
        "n": n,
        "per_request": per_request,
        "total_sys_match": total_sys_match,
        "total_tools_match": total_tools_match,
        "total_msgs_match": total_msgs_match,
        "all_raw_keys": sorted(all_raw_keys),
        "field_classification": field_classification,
        "main_count": len(main_entries),
        "fwd_count": len(reconstructed),
    }


# Return list of (idx, note) for element-level divergences between two normalized lists
def _element_divergences(a: list, b: list) -> list:
    divs = []
    if len(a) != len(b):
        divs.append(f"count: {len(a)} vs {len(b)}")
    for i in range(min(len(a), len(b))):
        if a[i] != b[i]:
            divs.append(f"elem[{i}] differs")
    return divs


# Classify raw_payload keys into delta-covered, proxy-pane-needed, metadata-only, other
def _classify_fields(keys: set) -> list:
    rows = []
    for k in sorted(keys):
        if k in _DELTA_COVERED:
            rows.append((k, "delta-covered", "reconstructed from _forwarded delta"))
        elif k in _PROXY_PANE_FIELDS:
            rows.append((k, "MUST-ADD", _PROXY_PANE_FIELDS[k]))
        elif k in _METADATA_PANE_FIELDS:
            rows.append((k, "metadata-pane-only", _METADATA_PANE_FIELDS[k]))
        else:
            rows.append((k, "UNCLASSIFIED", "not in classification table — needs manual review"))
    return rows


# Run Question B: extract is_error tool_result blocks from _original, dedup by tool_use_id
def _run_question_b(orig_entries: list, tool_errors: list) -> dict:
    seen_ids: set = set()
    unique_errors = []

    for entry_idx, entry in enumerate(orig_entries):
        payload = entry.get("payload", {})
        messages = payload.get("messages", [])
        for msg_idx, msg in enumerate(messages):
            content = msg.get("content", [])
            if not isinstance(content, list):
                continue
            for blk in content:
                if blk.get("type") != "tool_result":
                    continue
                if blk.get("is_error") is not True:
                    continue
                tid = blk.get("tool_use_id", "")
                if tid in seen_ids:
                    continue
                seen_ids.add(tid)
                raw_content = blk.get("content", "")
                if isinstance(raw_content, list):
                    preview = " ".join(
                        b.get("text", "")[:80] for b in raw_content
                        if isinstance(b, dict)
                    )[:200]
                else:
                    preview = str(raw_content)[:200]
                unique_errors.append({
                    "tool_use_id": tid,
                    "first_seen_entry": entry_idx,
                    "first_seen_msg": msg_idx,
                    "content_preview": preview,
                })

    # Tool errors from tool_errors.jsonl for this session
    persisted_ids = {r.get("tool_use_id", "") for r in tool_errors}
    extracted_ids = {e["tool_use_id"] for e in unique_errors}

    only_in_extracted = extracted_ids - persisted_ids
    only_in_persisted = persisted_ids - extracted_ids
    both = extracted_ids & persisted_ids

    return {
        "unique_errors": unique_errors,
        "extracted_count": len(unique_errors),
        "persisted_count": len(tool_errors),
        "both": sorted(both),
        "only_in_extracted": sorted(only_in_extracted),
        "only_in_persisted": sorted(only_in_persisted),
        "tool_errors_records": tool_errors,
        "exact_match": not only_in_extracted and not only_in_persisted,
    }


# Write the markdown report and return its path
def _write_report(session: str, paths: dict, a: dict, b: dict) -> Path:
    now = datetime.now(timezone.utc)
    date_str = now.strftime("%Y%m%d")
    report_dir = Path(__file__).parent / "main_log_elimination_probe_reports"
    report_dir.mkdir(exist_ok=True)
    report_path = report_dir / f"{date_str}.md"

    lines = []
    lines.append(f"# Main Log Elimination Probe — {date_str}")
    lines.append(f"\n**Session:** `{session}`")
    lines.append(f"**Dataset:** `{paths['main'].name}` ({a['main_count']} request entries, {a['fwd_count']} forwarded entries)")
    lines.append(f"**Run:** {now.strftime('%Y-%m-%dT%H:%M:%SZ')}")

    lines.append("\n---")
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

    # Per-request content divergences (only if any)
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

    lines.append("\n### Top-level Field Classification")
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

    lines.append("\n---")
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

    lines.append("\n---")
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

    report_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return report_path


# Resolve log file path from session suffix
def _cli() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Probe: can _forwarded quartet replace the main log?"
    )
    parser.add_argument(
        "session",
        nargs="?",
        default="opus_monitor_cc_1780602018",
        help="Log session suffix, e.g. opus_monitor_cc_1780602018",
    )
    return parser.parse_args()


if __name__ == "__main__":
    args = _cli()
    main_log_elimination_probe_workflow(args.session)
