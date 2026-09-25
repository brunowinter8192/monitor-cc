# INFRASTRUCTURE
import json
from pathlib import Path

from composition_probe_ops import _strip_cache_control, _block_text, compose_block, check_invariants
from composition_probe_passes import run_passes_and_collect_ops

_AREA_ROOT = next(p for p in Path(__file__).resolve().parents if p.name == 'proxy_dual_log')
_PROJECT_ROOT = _AREA_ROOT.parent.parent


_PROJECT_PARTS = _PROJECT_ROOT.parts
_MAIN_CHECKOUT_ROOT = Path(*_PROJECT_PARTS[:-3]) if len(_PROJECT_PARTS) >= 3 and _PROJECT_PARTS[-3] == '.claude' and _PROJECT_PARTS[-2] == 'worktrees' else _PROJECT_ROOT

_log_from_main = (_PROJECT_ROOT / "src" / "logs" / "dual_log").resolve()
_log_from_wt   = (_MAIN_CHECKOUT_ROOT / "src" / "logs" / "dual_log").resolve()
LOG_DIR        = _log_from_main if _log_from_main.exists() else _log_from_wt

LOG_STEMS = [
    "api_requests_opus_monitor_cc_1780933074",
    "api_requests_opus_wise2627_1780929790",
    "api_requests_opus_trading_1780939398",
    "api_requests_worker_25c51a2e_composition-probe_1780947130",
    "api_requests_worker_25c51a2e_proxy-req-pane_1780939927",
]

# FUNCTIONS

def _check_block(stem: str, entry: dict, msg_idx, c0_content, cfwd_content, blk_idx,
                 block_op_list: list, pass_stats: dict, failed_cases: list) -> tuple:
    c0_text   = _block_text(c0_content,   blk_idx)
    cfwd_text = _block_text(cfwd_content, blk_idx)
    spans     = compose_block(c0_text, block_op_list)
    ok, detail = check_invariants(spans, c0_text, cfwd_text)

    pass_names = [op[0] for op in block_op_list]
    for pn in pass_names:
        ps = pass_stats.setdefault(pn, [0, 0])
        ps[0 if ok else 1] += 1

    if not ok:
        failed_cases.append({
            "stem":       stem,
            "flow_id":    entry.get("flow_id", "?")[:16],
            "msg_idx":    msg_idx,
            "blk_idx":    blk_idx,
            "pass_chain": pass_names,
            "c0_len":     len(c0_text),
            "cfwd_len":   len(cfwd_text),
            "detail":     detail,
            "ops":        [(pn, off, repr(rem[:40]), repr(inj[:40]))
                           for pn, off, rem, inj in block_op_list],
        })

    is_multi = len(block_op_list) > 1
    is_double_inject = sum(1 for _, _, _, inj in block_op_list if inj) >= 2
    return ok, is_multi, is_double_inject


def _scan_entry(stem: str, entry: dict, stats: dict) -> None:
    payload  = _strip_cache_control(entry.get("payload", {}))
    messages = payload.get("messages", [])
    if not messages:
        return

    final_msgs, ops = run_passes_and_collect_ops(list(messages))
    if not ops:
        return
    stats["entries_modified"] += 1

    for msg_idx, blk_map in ops.items():
        c0_content   = messages[msg_idx].get("content", "")   if msg_idx < len(messages)   else ""
        cfwd_content = final_msgs[msg_idx].get("content", "") if msg_idx < len(final_msgs) else ""

        for blk_idx, block_op_list in blk_map.items():
            stats["blocks_checked"] += 1
            ok, is_multi, is_double = _check_block(
                stem, entry, msg_idx, c0_content, cfwd_content, blk_idx, block_op_list,
                stats["pass_stats"], stats["failed_cases"],
            )
            if ok:
                stats["blocks_passed"] += 1
            if is_multi:
                stats["multi_pass_blocks"] += 1
            if is_double:
                stats["double_inject_blocks"] += 1


def run_corpus() -> dict:
    stats = {
        "total_entries":        0,
        "entries_modified":     0,
        "blocks_checked":       0,
        "blocks_passed":        0,
        "failed_cases":         [],
        "pass_stats":           {},
        "multi_pass_blocks":    0,
        "double_inject_blocks": 0,
    }

    for stem in LOG_STEMS:
        orig_path = LOG_DIR / f"{stem}_original.jsonl"
        if not orig_path.exists():
            continue
        with open(orig_path) as f:
            entries = [json.loads(line) for line in f]

        for entry in entries:
            stats["total_entries"] += 1
            _scan_entry(stem, entry, stats)

    return {
        "total_entries":        stats["total_entries"],
        "entries_modified":     stats["entries_modified"],
        "blocks_checked":       stats["blocks_checked"],
        "blocks_passed":        stats["blocks_passed"],
        "blocks_failed":        len(stats["failed_cases"]),
        "failed_cases":         stats["failed_cases"],
        "pass_stats":           stats["pass_stats"],
        "multi_pass_blocks":    stats["multi_pass_blocks"],
        "double_inject_blocks": stats["double_inject_blocks"],
    }


def get_money_shot_case():
    stem       = "api_requests_opus_monitor_cc_1780933074"
    target_fid = "58620c90-9e81-497d-98d6-1cf8a63e3491"
    orig_path  = LOG_DIR / f"{stem}_original.jsonl"
    with open(orig_path) as f:
        for line in f:
            e = json.loads(line)
            if e.get("flow_id") == target_fid:
                payload   = _strip_cache_control(e["payload"])
                messages  = payload["messages"]
                final_msgs, ops = run_passes_and_collect_ops(list(messages))
                blk_ops   = ops.get(100, {}).get(0, [])
                c0_text   = _block_text(messages[100].get("content",   ""), 0)
                cfwd_text = _block_text(final_msgs[100].get("content", ""), 0)
                spans     = compose_block(c0_text, blk_ops)
                return c0_text, cfwd_text, blk_ops, spans
    return None, None, [], []
