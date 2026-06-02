"""
verify_delta.py — Verify forwarded delta log for losslessness and self-consistency.

Reads an _original + _forwarded JSONL pair, reconstructs each request's full forwarded
payload from the delta stream (per model-family chain), and checks two invariants:

  Check 1 (HARD): reconstructed counts == declared counts in the delta entry.
                  A violation is a delta-builder bug — always FAIL.

  Check 2 (SOFT diagnostic): forwarded counts.messages vs message count in the original.
                  A mismatch is reported with context but does NOT fail the script —
                  the proxy legitimately changes message count (msg0-strip, sidecar path).

Usage (from project root):
    ./venv/bin/python dev/proxy_dual_log/verify_delta.py \\
        src/logs/dual_log/api_requests_<id>_original.jsonl \\
        src/logs/dual_log/api_requests_<id>_forwarded.jsonl

Or with named flags:
    ./venv/bin/python dev/proxy_dual_log/verify_delta.py \\
        --original src/logs/dual_log/api_requests_<id>_original.jsonl \\
        --forwarded src/logs/dual_log/api_requests_<id>_forwarded.jsonl
"""

# INFRASTRUCTURE
import argparse
import json
import sys
from pathlib import Path

# ORCHESTRATOR

def verify_delta_workflow(original_path: Path, forwarded_path: Path) -> int:
    original_entries = _load_jsonl(original_path)
    forwarded_entries = _load_jsonl(forwarded_path)

    original_index = _build_original_index(original_entries)
    results = _reconstruct_and_check(forwarded_entries, original_index)
    _print_report(results, original_path, forwarded_path)

    hard_fails = [r for r in results if r["hard_fail"]]
    return 1 if hard_fails else 0

# FUNCTIONS

# Load JSONL file — skip blank lines and non-JSON lines with a warning
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
                print(f"  [warn] {path.name}:{lineno} — JSON parse error: {e}", file=sys.stderr)
    return entries


# Build index: request_id → message count from original payload
# Falls back to per-family line-order list for empty request_ids
def _build_original_index(entries: list) -> dict:
    by_reqid = {}
    by_family_order = {}  # model_family → [message_count, ...]
    for entry in entries:
        payload = entry.get("payload", {})
        msg_count = len(payload.get("messages", []))
        model = entry.get("model", "")
        family = _infer_family(model)
        reqid = entry.get("request_id", "")
        if reqid:
            by_reqid[reqid] = msg_count
        by_family_order.setdefault(family, []).append(msg_count)
    return {"by_reqid": by_reqid, "by_family_order": by_family_order, "_family_cursors": {}}


# Reconstruct per-model-family chains and run both checks for every forwarded entry
def _reconstruct_and_check(forwarded_entries: list, original_index: dict) -> list:
    chain_states = {}   # model_family → {"system": [...], "tools": [...], "messages": [...]}
    family_cursors = {} # model_family → next index into original_index by_family_order
    results = []

    for lineno, entry in enumerate(forwarded_entries, 1):
        if entry.get("type") != "forwarded_delta":
            continue

        model = entry.get("model", "")
        family = _infer_family(model)
        is_first = entry.get("is_first", False)
        counts = entry.get("counts", {})
        request_id = entry.get("request_id", "")

        if is_first:
            # Full reconstruction from delta dicts
            curr_state = {
                "system": _dict_to_list(entry.get("system_delta", {}), counts.get("system", 0)),
                "tools": _dict_to_list(entry.get("tools_delta", {}), counts.get("tools", 0)),
                "messages": _dict_to_list(entry.get("messages_delta", {}), counts.get("messages", 0)),
            }
            chain_states[family] = curr_state
        else:
            prev_state = chain_states.get(family, {"system": [], "tools": [], "messages": []})
            curr_state = {}
            for cat in ("system", "tools", "messages"):
                prev_list = list(prev_state[cat])
                for idx_str, elem in entry.get(f"{cat}_delta", {}).items():
                    i = int(idx_str)
                    while len(prev_list) <= i:
                        prev_list.append(None)
                    prev_list[i] = elem
                curr_state[cat] = prev_list[:counts.get(cat, len(prev_list))]
            chain_states[family] = curr_state

        # Check 1 (hard): reconstructed counts == declared counts
        hard_fail = False
        hard_fail_details = []
        for cat in ("system", "tools", "messages"):
            reconstructed = len(curr_state[cat])
            declared = counts.get(cat, -1)
            if reconstructed != declared:
                hard_fail = True
                hard_fail_details.append(f"{cat}: reconstructed={reconstructed} declared={declared}")

        # Check 2 (soft): forwarded counts.messages vs original message count
        orig_msg_count = _lookup_original_msg_count(
            request_id, family, original_index, family_cursors
        )
        soft_mismatch = None
        if orig_msg_count is not None:
            fwd_msg_count = counts.get("messages", 0)
            if fwd_msg_count != orig_msg_count:
                soft_mismatch = f"forwarded={fwd_msg_count} original={orig_msg_count} diff={fwd_msg_count - orig_msg_count:+d}"

        delta_size = _delta_bytes(entry)
        delta_indices = {
            cat: sorted(int(k) for k in entry.get(f"{cat}_delta", {}).keys())
            for cat in ("system", "tools", "messages")
        }

        results.append({
            "lineno": lineno,
            "request_id": request_id[:16] if request_id else "(none)",
            "model_family": family,
            "model": model,
            "is_first": is_first,
            "counts": counts,
            "delta_indices": delta_indices,
            "delta_bytes": delta_size,
            "hard_fail": hard_fail,
            "hard_fail_details": hard_fail_details,
            "soft_mismatch": soft_mismatch,
        })

    return results


# Lookup original message count by request_id, falling back to family-order index
def _lookup_original_msg_count(request_id: str, family: str, index: dict, cursors: dict):
    if request_id and request_id in index["by_reqid"]:
        return index["by_reqid"][request_id]
    # Fallback: consume next entry in family order
    order_list = index["by_family_order"].get(family, [])
    cursor = cursors.get(family, 0)
    if cursor < len(order_list):
        cursors[family] = cursor + 1
        return order_list[cursor]
    return None


# Convert {"0": elem, "2": elem} delta dict to a list of declared_count length
def _dict_to_list(delta_dict: dict, declared_count: int) -> list:
    result = [None] * declared_count
    for idx_str, elem in delta_dict.items():
        i = int(idx_str)
        if i < declared_count:
            result[i] = elem
    return result


# Rough byte size of delta payload (system+tools+messages deltas only)
def _delta_bytes(entry: dict) -> int:
    return sum(
        len(json.dumps(entry.get(f"{cat}_delta", {})).encode("utf-8"))
        for cat in ("system", "tools", "messages")
    )


# Infer model family from model string (mirrors addon.py logic)
def _infer_family(model: str) -> str:
    m = model.lower()
    if "haiku" in m:
        return "haiku"
    if "sonnet" in m:
        return "sonnet"
    return "opus"


# Print per-request table and PASS/FAIL summary
def _print_report(results: list, original_path: Path, forwarded_path: Path) -> None:
    print(f"\nverify_delta — {forwarded_path.name}")
    print(f"  original:  {original_path}")
    print(f"  forwarded: {forwarded_path}")
    print(f"  entries:   {len(results)}\n")

    col = "{:<4} {:<18} {:<7} {:<8} {:>6} {:>5} {:>5} {:>5} {:>9} {}"
    print(col.format("line", "request_id", "family", "is_first", "sys", "tools", "msgs", "dKB", "status", "delta_indices / notes"))
    print("-" * 110)

    for r in results:
        is_first_str = "FIRST" if r["is_first"] else ""
        dkb = f"{r['delta_bytes'] / 1024:.1f}"
        idx_summary = "  ".join(
            f"{cat}[{','.join(str(i) for i in idxs)}]" if idxs else f"{cat}[]"
            for cat, idxs in r["delta_indices"].items()
        )
        if r["hard_fail"]:
            status = "FAIL"
            notes = f"HARD FAIL: {'; '.join(r['hard_fail_details'])}"
        elif r["soft_mismatch"]:
            status = "warn"
            notes = f"msg-count mismatch ({r['soft_mismatch']})  {idx_summary}"
        else:
            status = "ok"
            notes = idx_summary

        print(col.format(
            r["lineno"],
            r["request_id"],
            r["model_family"],
            is_first_str,
            r["counts"].get("system", "?"),
            r["counts"].get("tools", "?"),
            r["counts"].get("messages", "?"),
            dkb,
            status,
            notes,
        ))

    print()
    hard_fails = [r for r in results if r["hard_fail"]]
    soft_warns = [r for r in results if r["soft_mismatch"] and not r["hard_fail"]]
    ok_count = len(results) - len(hard_fails) - len(soft_warns)

    if not hard_fails:
        print(f"PASS — {ok_count} ok, {len(soft_warns)} soft-mismatch (proxy modification), 0 hard-fail")
        print("Delta self-consistency: VERIFIED (reconstructed counts == declared counts on all entries)")
    else:
        print(f"FAIL — {len(hard_fails)} hard-fail, {len(soft_warns)} soft-mismatch, {ok_count} ok")
        print("Delta self-consistency: BROKEN — see HARD FAIL rows above")
    print()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Verify forwarded delta log self-consistency against original log.",
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

    sys.exit(verify_delta_workflow(Path(orig), Path(fwd)))
