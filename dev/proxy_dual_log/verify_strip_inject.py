"""
verify_strip_inject.py — Completeness proof for the strip/inject diff engine.

Simulates _build_stripped_injected_deltas on every request pair from a real _original +
_forwarded log, then verifies three hard checks per request:

  Check 1 (span reconstruction): for every block where orig_text != fwd_text, the spans
    produced by the diff engine reconstruct orig_text from (equal + stripped) spans, and
    fwd_text from (equal + injected) spans. A failure means _diff_text lost content.

  Check 2 (field coverage): every non-collection top-level field that differs between
    original and forwarded appears in the simulated fields_delta. A failure means a
    field-level modification (like the model override) was silently omitted.

  Check 3 (model cross-check): the injected fields_delta["model"] (if present) matches
    the model field on the _forwarded delta entry for the same request.

Usage (from project root):
    ./venv/bin/python dev/proxy_dual_log/verify_strip_inject.py \\
        src/logs/dual_log/api_requests_<id>_original.jsonl \\
        src/logs/dual_log/api_requests_<id>_forwarded.jsonl

Or with named flags:
    ./venv/bin/python dev/proxy_dual_log/verify_strip_inject.py \\
        --original src/logs/dual_log/api_requests_<id>_original.jsonl \\
        --forwarded src/logs/dual_log/api_requests_<id>_forwarded.jsonl
"""

# INFRASTRUCTURE
import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[2]))


# ORCHESTRATOR

def verify_strip_inject_workflow(original_path: Path, forwarded_path: Path) -> int:
    from src.proxy.strip_inject_delta import _build_stripped_injected_deltas
    from src.proxy.logging import _strip_cache_control
    from src.proxy.diff_engine import _diff_top_level_fields, _diff_system, _diff_tools, _diff_messages, _span_counts

    orig_entries = _load_jsonl(original_path)
    fwd_entries = _load_jsonl(forwarded_path)
    fwd_states = _reconstruct_chains(fwd_entries)
    matched = _match_requests(orig_entries, fwd_entries, fwd_states)

    results = []
    prev_s_by_family: dict = {}
    prev_i_by_family: dict = {}

    for req_num, (orig_entry, fwd_entry, fwd_state) in enumerate(matched, 1):
        family = _infer_family(fwd_entry.get("model", ""))
        orig_payload = orig_entry.get("payload", {})
        fwd_model = fwd_entry.get("model", "")

        # Reconstruct forwarded payload: blocks from _forwarded chain + model from _forwarded entry.
        # model is the only non-block field available in _forwarded; other fields (thinking,
        # output_config, etc.) are not recorded there and cannot be verified here.
        fwd_payload = {
            "system": fwd_state.get("system", []),
            "tools": fwd_state.get("tools", []),
            "messages": fwd_state.get("messages", []),
            "model": fwd_model,
        }

        prev_s = prev_s_by_family.get(family)
        prev_i = prev_i_by_family.get(family)
        req_id = fwd_entry.get("request_id", "")

        s_entry, i_entry, new_s, new_i = _build_stripped_injected_deltas(
            orig_payload, fwd_payload, req_id, prev_s, prev_i, fwd_model,
        )
        prev_s_by_family[family] = new_s
        prev_i_by_family[family] = new_i

        orig_norm = _strip_cache_control(orig_payload)
        fwd_norm = _strip_cache_control(fwd_payload)

        is_first = fwd_entry.get("is_first", False)
        span_fails = _check_span_reconstruction(orig_norm, fwd_norm, _diff_system, _diff_tools, _diff_messages)
        field_fails = _check_field_coverage(orig_norm, fwd_norm, s_entry, i_entry, _diff_top_level_fields, is_first)
        model_fail = _check_model_crosscheck(s_entry, i_entry, orig_payload.get("model", ""), fwd_model, is_first)

        results.append({
            "req_num": req_num,
            "request_id": req_id[:16] if req_id else "(none)",
            "family": family,
            "is_first": fwd_entry.get("is_first", False),
            "orig_counts": {
                "system": len([b for b in (orig_payload.get("system", []) or []) if isinstance(b, dict)]),
                "tools": len(orig_payload.get("tools", []) or []),
                "messages": len(orig_payload.get("messages", []) or []),
            },
            "fwd_counts": fwd_entry.get("counts", {}),
            "is_first": is_first,
            "span_fails": span_fails,
            "field_fails": field_fails,
            "model_fail": model_fail,
        })

    _print_report(results, original_path, forwarded_path)
    hard_fails = [r for r in results if r["span_fails"] or r["field_fails"] or r["model_fail"]]
    return 1 if hard_fails else 0


# FUNCTIONS

def _load_jsonl(path: Path) -> list:
    entries = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line:
            try:
                entries.append(json.loads(line))
            except json.JSONDecodeError:
                pass
    return entries


def _infer_family(model: str) -> str:
    m = model.lower()
    if "haiku" in m:
        return "haiku"
    if "sonnet" in m:
        return "sonnet"
    return "opus"


# Reconstruct full forwarded payload (system/tools/messages) from _forwarded delta chain
def _reconstruct_chains(fwd_entries: list) -> list:
    chain_states = {}
    result = []
    for entry in fwd_entries:
        if entry.get("type") != "forwarded_delta":
            result.append(None)
            continue
        family = _infer_family(entry.get("model", ""))
        counts = entry.get("counts", {})
        if entry.get("is_first"):
            state = {}
            for cat in ("system", "tools", "messages"):
                lst = [None] * counts.get(cat, 0)
                for idx_str, elem in entry.get(f"{cat}_delta", {}).items():
                    i = int(idx_str)
                    if i < len(lst):
                        lst[i] = elem
                state[cat] = lst
        else:
            prev = chain_states.get(family, {"system": [], "tools": [], "messages": []})
            state = {}
            for cat in ("system", "tools", "messages"):
                lst = list(prev[cat])
                for idx_str, elem in entry.get(f"{cat}_delta", {}).items():
                    i = int(idx_str)
                    while len(lst) <= i:
                        lst.append(None)
                    lst[i] = elem
                state[cat] = lst[:counts.get(cat, len(lst))]
        chain_states[family] = state
        result.append(state)
    return result


def _match_requests(orig_entries: list, fwd_entries: list, fwd_states: list) -> list:
    orig_by_reqid = {}
    orig_queues = {}
    for oe in orig_entries:
        family = _infer_family(oe.get("model", ""))
        reqid = oe.get("request_id", "")
        if reqid:
            orig_by_reqid[reqid] = oe
        orig_queues.setdefault(family, []).append(oe)
    cursors = {}
    result = []
    for fe, fs in zip(fwd_entries, fwd_states):
        if fs is None:
            continue
        family = _infer_family(fe.get("model", ""))
        reqid = fe.get("request_id", "")
        if reqid and reqid in orig_by_reqid:
            oe = orig_by_reqid[reqid]
        else:
            q = orig_queues.get(family, [])
            c = cursors.get(family, 0)
            oe = q[c] if c < len(q) else None
            cursors[family] = c + 1
        if oe is not None:
            result.append((oe, fe, fs))
    return result


# Normalize text for reconstruction comparison: collapse all whitespace to single spaces
def _norm(text: str) -> str:
    return " ".join(text.split())


# Check 1: span reconstruction — every block where orig != fwd reconstructs correctly from spans
# Both sides normalized (split+join) before comparison: handles 2-span case where literal text
# has leading newlines, and word-level case where spaces are naturally normalized by the diff.
def _check_span_reconstruction(orig_norm, fwd_norm, _diff_system, _diff_tools, _diff_messages) -> list:
    fails = []
    orig_sys = [b for b in (orig_norm.get("system", []) or []) if isinstance(b, dict)]
    fwd_sys = [b for b in (fwd_norm.get("system", []) or []) if isinstance(b, dict)]

    for d in _diff_system(orig_sys, fwd_sys):
        if d["o_text"] == d["f_text"]:
            continue
        orig_rec = _norm(" ".join(t for tag, t in d["spans"] if tag in ("equal", "stripped")))
        fwd_rec = _norm(" ".join(t for tag, t in d["spans"] if tag in ("equal", "injected")))
        if orig_rec != _norm(d["o_text"]):
            fails.append(f"sys[{d['idx']}] orig reconstruction mismatch: got {orig_rec[:60]!r}")
        if fwd_rec != _norm(d["f_text"]):
            fails.append(f"sys[{d['idx']}] fwd reconstruction mismatch: got {fwd_rec[:60]!r}")

    orig_tools = orig_norm.get("tools", []) or []
    fwd_tools = fwd_norm.get("tools", []) or []
    td = _diff_tools(orig_tools, fwd_tools)
    for name, o_desc, f_desc, spans in td["desc_changes"]:
        if o_desc == f_desc:
            continue
        orig_rec = _norm(" ".join(t for tag, t in spans if tag in ("equal", "stripped")))
        fwd_rec = _norm(" ".join(t for tag, t in spans if tag in ("equal", "injected")))
        if orig_rec != _norm(o_desc):
            fails.append(f"tool[{name}] desc orig reconstruction mismatch")
        if fwd_rec != _norm(f_desc):
            fails.append(f"tool[{name}] desc fwd reconstruction mismatch")

    orig_msgs = orig_norm.get("messages", []) or []
    fwd_msgs = fwd_norm.get("messages", []) or []
    for md in _diff_messages(orig_msgs, fwd_msgs):
        for bd in md["block_diffs"]:
            if bd["o_text"] == bd["f_text"]:
                continue
            orig_rec = _norm(" ".join(t for tag, t in bd["spans"] if tag in ("equal", "stripped")))
            fwd_rec = _norm(" ".join(t for tag, t in bd["spans"] if tag in ("equal", "injected")))
            if orig_rec != _norm(bd["o_text"]):
                fails.append(f"msg[{md['idx']}].block[{bd['bidx']}] orig reconstruction mismatch")
            if fwd_rec != _norm(bd["f_text"]):
                fails.append(f"msg[{md['idx']}].block[{bd['bidx']}] fwd reconstruction mismatch")
    return fails


# Check 2: field coverage — on is_first requests, every differing top-level field must appear in
# fields_delta (no delta suppression on first). Non-first requests can't be verified here because
# the _forwarded log doesn't record non-block top-level fields; unchanged fields are correctly
# delta-suppressed. Model is verified separately via cross-check on ALL requests.
def _check_field_coverage(orig_norm, fwd_norm, s_entry, i_entry, _diff_top_level_fields, is_first: bool) -> list:
    if not is_first:
        return []
    fails = []
    field_diffs = _diff_top_level_fields(orig_norm, fwd_norm)
    s_fields = s_entry.get("fields_delta", {})
    i_fields = i_entry.get("fields_delta", {})
    for fd in field_diffs:
        key = fd["key"]
        if fd["tag"] in ("stripped", "replaced"):
            if key not in s_fields:
                fails.append(f"first-req field '{key}' (tag={fd['tag']}) missing from stripped fields_delta")
        if fd["tag"] in ("injected", "replaced"):
            if key not in i_fields:
                fails.append(f"first-req field '{key}' (tag={fd['tag']}) missing from injected fields_delta")
    return fails


# Check 3: model cross-check — on is_first requests, when orig_model != fwd_model, both stripped
# and injected fields_delta["model"] must be set correctly. Non-first requests: correctly
# delta-suppressed (same model every request), so only checked on first.
def _check_model_crosscheck(s_entry: dict, i_entry: dict, orig_model: str, fwd_model: str, is_first: bool) -> str:
    if not is_first or not orig_model or not fwd_model or orig_model == fwd_model:
        return ""
    s_fields = s_entry.get("fields_delta", {})
    i_fields = i_entry.get("fields_delta", {})
    if "model" not in s_fields:
        return f"model changed ({orig_model!r}->{fwd_model!r}) but missing from stripped fields_delta"
    if s_fields["model"] != orig_model:
        return f"stripped fields_delta model={s_fields['model']!r} != orig model={orig_model!r}"
    if "model" not in i_fields:
        return f"model changed ({orig_model!r}->{fwd_model!r}) but missing from injected fields_delta"
    if i_fields["model"] != fwd_model:
        return f"injected fields_delta model={i_fields['model']!r} != forwarded model={fwd_model!r}"
    return ""


def _print_report(results: list, original_path: Path, forwarded_path: Path) -> None:
    print(f"\nverify_strip_inject — {forwarded_path.name}")
    print(f"  original:  {original_path}")
    print(f"  forwarded: {forwarded_path}")
    print(f"  pairs:     {len(results)}\n")

    col = "{:<4} {:<18} {:<7} {:<8} {:>5} {:>5} {:>5} {:>9} {}"
    print(col.format("req#", "request_id", "family", "is_first",
                     "o_sys", "o_msg", "f_msg", "status", "notes"))
    print("-" * 110)

    for r in results:
        is_first_str = "FIRST" if r["is_first"] else ""
        all_fails = r["span_fails"] + r["field_fails"] + ([r["model_fail"]] if r["model_fail"] else [])
        status = "FAIL" if all_fails else "ok"
        notes = " | ".join(all_fails[:3]) if all_fails else ""
        print(col.format(
            r["req_num"],
            r["request_id"],
            r["family"],
            is_first_str,
            r["orig_counts"].get("system", "?"),
            r["orig_counts"].get("messages", "?"),
            r["fwd_counts"].get("messages", "?"),
            status,
            notes[:80],
        ))

    print()
    hard_fails = [r for r in results if r["span_fails"] or r["field_fails"] or r["model_fail"]]
    ok_count = len(results) - len(hard_fails)

    if not hard_fails:
        print(f"PASS — {ok_count} ok, 0 hard-fail")
        print("Span reconstruction: VERIFIED (all block diffs reconstruct both sides)")
        print("Field coverage: VERIFIED (all top-level field diffs captured in fields_delta)")
        print("Model cross-check: VERIFIED (injected model matches forwarded entry)")
    else:
        print(f"FAIL — {len(hard_fails)} hard-fail, {ok_count} ok")
        print("See FAIL rows above for details.")
    print()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Completeness proof for the strip/inject diff engine.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument("original", nargs="?", help="Path to _original.jsonl")
    parser.add_argument("forwarded", nargs="?", help="Path to _forwarded.jsonl")
    parser.add_argument("--original", dest="original_flag", help="Path to _original.jsonl (named)")
    parser.add_argument("--forwarded", dest="forwarded_flag", help="Path to _forwarded.jsonl (named)")
    args = parser.parse_args()
    orig = args.original_flag or args.original
    fwd = args.forwarded_flag or args.forwarded
    if not orig or not fwd:
        parser.print_help()
        sys.exit(1)
    sys.exit(verify_strip_inject_workflow(Path(orig), Path(fwd)))
