"""
diff_strip_inject.py — Span-level strip/inject diff of Original vs Forwarded proxy logs.

Shows what the proxy stripped (STRIPPED spans) and injected (INJECTED spans) per request.
Reads _original + _forwarded JSONL pair, reconstructs the full forwarded payload from the
delta chain (per model-family), aligns blocks (system by index, tools by name, messages by
index), and classifies spans as equal / stripped / injected using difflib.

Diff strategy: word-level when SequenceMatcher.ratio() >= 0.1 (partial edits, e.g. wakeup
text injected into a message block); whole-block 2-span replacement when ratio < 0.1 (full
replacements like sys[2]: CC prompt → proxy rules, or tool descriptions stripped to "").

Usage (from project root):
    ./venv/bin/python dev/proxy_dual_log/diff_strip_inject.py \\
        src/logs/dual_log/api_requests_<id>_original.jsonl \\
        src/logs/dual_log/api_requests_<id>_forwarded.jsonl

Or with named flags:
    ./venv/bin/python dev/proxy_dual_log/diff_strip_inject.py \\
        --original src/logs/dual_log/api_requests_<id>_original.jsonl \\
        --forwarded src/logs/dual_log/api_requests_<id>_forwarded.jsonl
"""

# INFRASTRUCTURE
import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[2]))

PREVIEW_CHARS = 120


# ORCHESTRATOR

def diff_strip_inject_workflow(original_path: Path, forwarded_path: Path) -> None:
    orig_entries = _load_jsonl(original_path)
    fwd_entries = _load_jsonl(forwarded_path)
    fwd_states = _reconstruct_chains(fwd_entries)
    matched = _match_requests(orig_entries, fwd_entries, fwd_states)
    _print_report(matched, forwarded_path.name)


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
    if "haiku" in m: return "haiku"
    if "sonnet" in m: return "sonnet"
    return "opus"


# Inline of verify_delta.py reconstruction logic — same algorithm, self-contained
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


def _preview(text: str, n: int = PREVIEW_CHARS) -> str:
    s = text.replace("\n", "\\n")
    return repr(s[:n]) + (f"…({len(s)}c)" if len(s) > n else "")


def _print_report(matched: list, filename: str) -> None:
    from src.proxy.diff_engine import _diff_system, _diff_tools, _diff_messages, _span_counts
    print(f"\ndiff_strip_inject — {filename}")
    print(f"  {len(matched)} matched request pairs\n")

    for req_num, (orig_entry, fwd_entry, fwd_state) in enumerate(matched, 1):
        family = _infer_family(fwd_entry.get("model", ""))
        is_first = fwd_entry.get("is_first", False)
        o_model = orig_entry.get("model", "")
        f_model = fwd_entry.get("model", "")
        print(f"=== REQ#{req_num} [{family}]{'  (is_first)' if is_first else ''} ===")
        if o_model != f_model:
            print(f"  model: {o_model!r} → {f_model!r}  [OVERRIDE]")

        o_payload = orig_entry.get("payload", {})
        o_sys   = [b for b in (o_payload.get("system", []) or []) if isinstance(b, dict)]
        o_tools = o_payload.get("tools", []) or []
        o_msgs  = o_payload.get("messages", []) or []
        f_sys   = [b for b in (fwd_state.get("system", []) or []) if isinstance(b, dict)]
        f_tools = [t for t in (fwd_state.get("tools", []) or []) if isinstance(t, dict)]
        f_msgs  = fwd_state.get("messages", []) or []

        # --- SYSTEM ---
        sys_diffs = _diff_system(o_sys, f_sys)
        sys_s = sys_i = 0
        for d in sys_diffs:
            s, inj = _span_counts(d["spans"]); sys_s += s; sys_i += inj
        changed_sys = [d for d in sys_diffs if any(t != "equal" for t, _ in d["spans"])]
        if changed_sys:
            n_id = len(sys_diffs) - len(changed_sys)
            print(f"  SYSTEM ({len(o_sys)}→{len(f_sys)} blocks, {n_id} identical)")
            for d in changed_sys:
                s, inj = _span_counts(d["spans"])
                tag = "REPLACED" if s and inj else ("STRIPPED" if s else "INJECTED")
                print(f"    sys[{d['idx']}]: {tag}   -{len(d['o_text'])} / +{len(d['f_text'])} chars")
                for t, text in d["spans"]:
                    if t in ("stripped", "injected"):
                        print(f"               {t}: {_preview(text)}")

        # --- TOOLS ---
        td = _diff_tools(o_tools, f_tools)
        desc_stripped = [(n, len(od)) for n, od, fd, _ in td["desc_changes"] if not fd]
        desc_other    = [(n, od, fd, sp) for n, od, fd, sp in td["desc_changes"] if fd]
        t_s = len(td["stripped"]) + len(desc_stripped) + sum(_span_counts(sp)[0] for *_, sp in desc_other)
        t_i = len(td["injected"]) + sum(_span_counts(sp)[1] for *_, sp in desc_other)
        if td["stripped"] or td["injected"] or td["desc_changes"]:
            print(f"  TOOLS  -{len(td['stripped'])} stripped / +{len(td['injected'])} injected / ~{len(td['desc_changes'])} desc-changed")
            if td["stripped"]:
                print(f"    STRIPPED: {',  '.join(td['stripped'])}")
            if td["injected"]:
                print(f"    INJECTED: {',  '.join(td['injected'])}")
            if desc_stripped:
                parts = "  ".join(f"{n}(-{l}c)" for n, l in desc_stripped)
                print(f"    DESC STRIPPED: {parts}")
            for n, od, fd, sp in desc_other:
                s, inj = _span_counts(sp)
                print(f"    desc ~{n}: -{len(od)} / +{len(fd)} chars  ({s} stripped / {inj} injected spans)")

        # --- MESSAGES ---
        msg_diffs = _diff_messages(o_msgs, f_msgs)
        msgs_s = msgs_i = 0
        changed_msgs = []
        for md in msg_diffs:
            all_sp = [sp for bd in md["block_diffs"] for sp in bd["spans"]]
            s, inj = _span_counts(all_sp); msgs_s += s; msgs_i += inj
            if s or inj:
                changed_msgs.append(md)
        if changed_msgs:
            n_id = len(msg_diffs) - len(changed_msgs)
            print(f"  MESSAGES ({len(o_msgs)}→{len(f_msgs)}, {n_id} identical)")
            for md in changed_msgs:
                all_sp = [sp for bd in md["block_diffs"] for sp in bd["spans"]]
                s, inj = _span_counts(all_sp)
                print(f"    msg[{md['idx']}] ({len(md['block_diffs'])} blocks)  -{s} stripped / +{inj} injected")
                for bd in md["block_diffs"]:
                    bs, bi = _span_counts(bd["spans"])
                    if bs == 0 and bi == 0:
                        print(f"      block[{bd['bidx']}]: IDENTICAL   {len(bd['o_text'])} chars")
                    else:
                        tag = "REPLACED" if bs and bi else ("STRIPPED" if bs else "INJECTED")
                        print(f"      block[{bd['bidx']}]: {tag}   -{len(bd['o_text'])} / +{len(bd['f_text'])} chars")
                        for t, text in bd["spans"]:
                            if t in ("stripped", "injected"):
                                print(f"               {t}: {_preview(text)}")

        print(f"  SPANS: sys -{sys_s}/+{sys_i}  tools -{t_s}/+{t_i}  msgs -{msgs_s}/+{msgs_i}")
        print()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Span-level strip/inject diff of proxy Original vs Forwarded logs.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument("original", nargs="?", help="Path to _original.jsonl")
    parser.add_argument("forwarded", nargs="?", help="Path to _forwarded.jsonl")
    parser.add_argument("--original", dest="original_flag", help="Path to _original.jsonl (named)")
    parser.add_argument("--forwarded", dest="forwarded_flag", help="Path to _forwarded.jsonl (named)")
    args = parser.parse_args()
    orig = args.original_flag or args.original
    fwd  = args.forwarded_flag or args.forwarded
    if not orig or not fwd:
        parser.print_help()
        sys.exit(1)
    diff_strip_inject_workflow(Path(orig), Path(fwd))
