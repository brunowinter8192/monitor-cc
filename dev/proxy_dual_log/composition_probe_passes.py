# INFRASTRUCTURE
from composition_probe_ops import extract_ops_from_pair, get_block_pairs

# FUNCTIONS

def _record_ops(ops: dict, msg_idx, blk_idx, pass_name: str, op_list: list) -> None:
    for off, rem, inj in op_list:
        ops.setdefault(msg_idx, {}).setdefault(blk_idx, []).append((pass_name, off, rem, inj))


def _collect_real_ops(pass_name: str, result: tuple, ops: dict) -> None:
    # Use directly-recorded ops from the pass's 6th return value
    pass_ops = result[5]
    for msg_idx, blk_map in pass_ops.items():
        for blk_idx, op_list in blk_map.items():
            _record_ops(ops, msg_idx, blk_idx, pass_name, op_list)


def _collect_standin_ops(pass_name: str, before: list, after_msgs: list, changed_idxs: list, ops: dict) -> None:
    # Stand-in for passes not yet migrated to op recording
    for msg_idx in changed_idxs:
        bc = before[msg_idx].get("content", "")     if msg_idx < len(before)     else ""
        ac = after_msgs[msg_idx].get("content", "") if msg_idx < len(after_msgs) else ""
        for blk_idx, bt, at in get_block_pairs(bc, ac):
            _record_ops(ops, msg_idx, blk_idx, pass_name, extract_ops_from_pair(bt, at))


# Run all passes sequentially, collecting per-block ops in Ck coordinates.
# Lazy-imports src/ pass functions to avoid top-level hook block.
# Returns (final_messages, ops_by_msg_blk) where
#   ops_by_msg_blk[msg_idx][blk_idx] = [(pass_name, offset, removed, injected), ...]
def run_passes_and_collect_ops(messages: list) -> tuple:
    from src.proxy.rules import (
        _apply_first_pass, _apply_cumulative_sr_strips, _apply_final_sr_pass,
        _apply_po_preview_strip, _apply_bg_exit_strip, _apply_hook_prefix_strip,
        _apply_git_lock_strip, _apply_bd_noise_strip, _dedup_wakeup_blocks,
    )
    # Passes with real op recording (result[5]) — 1A: po_preview, hook_prefix, git_lock, bd_noise; 1B: bg_exit; 1C: cumulative_sr, final_sr; 1D: first_pass — ALL passes now real, no stand-in
    real_ops_passes = frozenset({"po_preview", "hook_prefix", "git_lock", "bd_noise", "bg_exit", "cumulative_sr", "final_sr", "first_pass"})
    pass_sequence = [
        ("first_pass",    _apply_first_pass),
        ("cumulative_sr", _apply_cumulative_sr_strips),
        ("final_sr",      _apply_final_sr_pass),
        ("po_preview",    _apply_po_preview_strip),
        ("bg_exit",       _apply_bg_exit_strip),
        ("hook_prefix",   _apply_hook_prefix_strip),
        ("git_lock",      _apply_git_lock_strip),
        ("bd_noise",      _apply_bd_noise_strip),
    ]
    ops     = {}
    current = messages

    for pass_name, pass_fn in pass_sequence:
        before = current
        result = pass_fn(before)
        after_msgs = result[0]
        if pass_name in real_ops_passes:
            _collect_real_ops(pass_name, result, ops)
        else:
            _collect_standin_ops(pass_name, before, after_msgs, result[3], ops)
        current = after_msgs

    # Dedup wakeup — Layer-1 payload modification, uses real ops from _dedup_wakeup_blocks (1B)
    after_dedup, dedup_ops = _dedup_wakeup_blocks(current)
    for msg_idx, blk_map in dedup_ops.items():
        for blk_idx, op_list in blk_map.items():
            _record_ops(ops, msg_idx, blk_idx, "dedup_wakeup", op_list)

    return after_dedup, ops
