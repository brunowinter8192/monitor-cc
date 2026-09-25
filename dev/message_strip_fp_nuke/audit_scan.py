# INFRASTRUCTURE
import json
import sys
import os
import time
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
os.environ.setdefault('MONITOR_CC_ROOT', os.path.join(os.path.dirname(__file__), '..', '..'))

from src.proxy.message_passes import _apply_role_system_strip, _apply_first_pass, _apply_cumulative_sr_strips, _apply_final_sr_pass
from src.proxy.message_passes_simple import (
    _apply_sn_notice_strip, _apply_po_preview_strip, _apply_bg_exit_strip, _apply_bg_launch_ack_strip,
    _apply_hook_prefix_strip, _apply_git_lock_strip, _apply_bd_noise_strip,
)
from src.proxy.strip_sr import _INNER_SR_RE, _match_template, _ALL_TEMPLATES, _ENV_CONTEXT_RE, _IMP_LINE_RE
from src.proxy.content_strip import _REJECTION_MARKER
from src.proxy.rule_ops import _block_inner_text
from src.proxy.strip_git_lock import _GIT_LOCK_MARKER, _GIT_LOCK_ADVICE

LOGS_DIR = Path('/Users/brunowinter2000/Documents/ai/monitor-cc/src/logs/dual_log')

SELF_SESSION_MARKER = 'sr-fp-audit'

PASSES = [
    ('_apply_role_system_strip', _apply_role_system_strip),
    ('_apply_sn_notice_strip', _apply_sn_notice_strip),
    ('_apply_first_pass', _apply_first_pass),
    ('_apply_cumulative_sr_strips', _apply_cumulative_sr_strips),
    ('_apply_final_sr_pass', _apply_final_sr_pass),
    ('_apply_po_preview_strip', _apply_po_preview_strip),
    ('_apply_bg_exit_strip', _apply_bg_exit_strip),
    ('_apply_bg_launch_ack_strip', _apply_bg_launch_ack_strip),
    ('_apply_hook_prefix_strip', _apply_hook_prefix_strip),
    ('_apply_git_lock_strip', _apply_git_lock_strip),
    ('_apply_bd_noise_strip', _apply_bd_noise_strip),
]

_ASSERT_NO_DESCEND = {'_apply_role_system_strip', '_apply_sn_notice_strip', '_apply_bg_exit_strip'}

_FIXED_MOD_MAP = {
    '_apply_po_preview_strip': 'stripped_po_preview',
    '_apply_bg_launch_ack_strip': 'stripped_bg_launch_ack',
    '_apply_hook_prefix_strip': 'stripped_hook_error_prefix',
    '_apply_git_lock_strip': 'stripped_git_lock_advice',
    '_apply_bd_noise_strip': 'stripped_bd_noise',
    '_apply_role_system_strip': 'stripped_role_system_msg',
    '_apply_sn_notice_strip': 'stripped_sn_notice_paragraph',
    '_apply_bg_exit_strip': 'replaced_bg_completed_text',
}


# FUNCTIONS

def _discover_corpus_files():
    files = sorted(LOGS_DIR.glob('*_original.jsonl'))
    included = [f for f in files if SELF_SESSION_MARKER not in f.name]
    excluded = [f for f in files if SELF_SESSION_MARKER in f.name]
    return included, excluded


def _scan_files(included):
    per_file_stats = []
    occurrences = {}
    assertion_hits = []
    for fp in included:
        t0 = time.time()
        occ, hits, total_entries, requests_with_tr_hit = _scan_file(fp)
        for key, rec in occ.items():
            if key in occurrences:
                occurrences[key]['raw_count'] += rec['raw_count']
            else:
                occurrences[key] = rec
        assertion_hits.extend(hits)
        per_file_stats.append({
            'name': fp.name,
            'size_bytes': fp.stat().st_size,
            'entries': total_entries,
            'requests_with_tool_result_hit': requests_with_tr_hit,
            'unique_occurrences': len(occ),
            'seconds': round(time.time() - t0, 1),
        })
        print(f'[{fp.name}] entries={total_entries} unique_occ={len(occ)} '
              f'took={per_file_stats[-1]["seconds"]}s', file=sys.stderr, flush=True)
    return per_file_stats, occurrences, assertion_hits


def _build_tool_id_map(messages):
    m = {}
    for msg in messages:
        if msg.get('role') != 'assistant':
            continue
        content = msg.get('content')
        if not isinstance(content, list):
            continue
        for block in content:
            if isinstance(block, dict) and block.get('type') == 'tool_use':
                m[block.get('id')] = {
                    'name': block.get('name'),
                    'input_preview': json.dumps(block.get('input', {}), ensure_ascii=False)[:200],
                }
    return m


def _classify_removed_text(pass_name, removed_text):
    stripped = removed_text.strip()
    if stripped.startswith('<system-reminder>'):
        inner_m = _INNER_SR_RE.search(stripped)
        if inner_m:
            inner = inner_m.group(1).strip()
            if _ENV_CONTEXT_RE.fullmatch(inner):
                return 'sr:env-context'
            tid, _mode = _match_template(inner, _ALL_TEMPLATES)
            return f'sr:{tid}' if tid else 'sr:unknown-template'
    if _REJECTION_MARKER in removed_text:
        return 'stripped_rejection_message'
    if _IMP_LINE_RE.search(removed_text):
        return 'user-interrupt-important-line'
    return _FIXED_MOD_MAP.get(pass_name, f'unclassified:{pass_name}')


def _odd_fence_count(text_before):
    return text_before.count('```') % 2 == 1


def _context_window(flat_text, offset, removed_len, before=400, after=200):
    start = max(0, offset - before)
    end = min(len(flat_text), offset + removed_len + after)
    return flat_text[start:offset], flat_text[offset + removed_len:end]


def _process_block_ops(fp, line_idx, entry, pass_name, msg_idx, blk_idx, block, tool_id_map, op_list, occurrences, assertion_hits):
    hit_this_request = False
    inner = block.get('content', '')
    shape = 'tool_result_str' if isinstance(inner, str) else 'tool_result_list_joined'
    flat_text = _block_inner_text(block)
    tool_use_id = block.get('tool_use_id')
    tool_info = tool_id_map.get(tool_use_id, {})
    for offset, removed, _injected in op_list:
        if not removed:
            continue
        hit_this_request = True
        if pass_name in _ASSERT_NO_DESCEND:
            assertion_hits.append(
                (fp.name, line_idx, pass_name, msg_idx, blk_idx, removed[:200])
            )
        key = (fp.name, removed)
        if key not in occurrences:
            before_ctx, after_ctx = _context_window(flat_text, offset, len(removed))
            occurrences[key] = {
                'file': fp.name,
                'first_line_idx': line_idx,
                'raw_count': 0,
                'pass_name': pass_name,
                'template': _classify_removed_text(pass_name, removed),
                'tool_name': tool_info.get('name', 'UNKNOWN'),
                'tool_use_id': tool_use_id,
                'tool_input_preview': tool_info.get('input_preview', ''),
                'msg_idx': msg_idx,
                'blk_idx': blk_idx,
                'block_shape': shape,
                'offset': offset,
                'removed_text': removed,
                'context_before': before_ctx,
                'context_after': after_ctx,
                'fence_odd_before': _odd_fence_count(before_ctx),
                'request_id': entry.get('request_id'),
                'flow_id': entry.get('flow_id'),
                'timestamp': entry.get('timestamp'),
            }
        occurrences[key]['raw_count'] += 1
    return hit_this_request


def _process_pass(fp, line_idx, entry, cur_messages, pass_name, pass_fn, tool_id_map, occurrences, assertion_hits):
    new_messages, _mods, _removed, changed_idxs, _inj, ops_by_msg_blk = pass_fn(cur_messages)
    hit_this_request = False
    for msg_idx in changed_idxs:
        old_content = cur_messages[msg_idx].get('content')
        if not isinstance(old_content, list):
            continue
        for blk_idx, op_list in ops_by_msg_blk.get(msg_idx, {}).items():
            if blk_idx >= len(old_content):
                continue
            block = old_content[blk_idx]
            if not (isinstance(block, dict) and block.get('type') == 'tool_result'):
                continue
            if _process_block_ops(fp, line_idx, entry, pass_name, msg_idx, blk_idx, block, tool_id_map, op_list, occurrences, assertion_hits):
                hit_this_request = True
    return new_messages, hit_this_request


def _scan_line(fp, line_idx, entry, occurrences, assertion_hits):
    payload = entry.get('payload') or {}
    messages = payload.get('messages') or []
    if not messages:
        return False
    tool_id_map = _build_tool_id_map(messages)
    cur_messages = messages
    hit_this_request = False
    for pass_name, pass_fn in PASSES:
        cur_messages, hit = _process_pass(fp, line_idx, entry, cur_messages, pass_name, pass_fn, tool_id_map, occurrences, assertion_hits)
        if hit:
            hit_this_request = True
    return hit_this_request


def _scan_file(fp):
    occurrences = {}
    assertion_hits = []
    total_entries = 0
    requests_with_tr_hit = 0
    with open(fp, 'r') as fh:
        for line_idx, line in enumerate(fh):
            line = line.strip()
            if not line:
                continue
            total_entries += 1
            entry = json.loads(line)
            if _scan_line(fp, line_idx, entry, occurrences, assertion_hits):
                requests_with_tr_hit += 1
    return occurrences, assertion_hits, total_entries, requests_with_tr_hit


def _scan_ground_truth_git_lock(files):
    per_file = []
    for fp in files:
        marker_lines = 0
        literal_lines = 0
        with open(fp, 'r') as fh:
            for line in fh:
                if _GIT_LOCK_MARKER not in line:
                    continue
                entry = json.loads(line)
                messages = (entry.get('payload') or {}).get('messages') or []
                has_marker = False
                has_literal = False
                for msg in messages:
                    content = msg.get('content')
                    if not isinstance(content, list):
                        continue
                    for block in content:
                        if not (isinstance(block, dict) and block.get('type') == 'tool_result'):
                            continue
                        flat = _block_inner_text(block)
                        if _GIT_LOCK_MARKER in flat:
                            has_marker = True
                            if _GIT_LOCK_ADVICE in flat:
                                has_literal = True
                if has_marker:
                    marker_lines += 1
                if has_literal:
                    literal_lines += 1
        per_file.append({'file': fp.name, 'marker_lines': marker_lines, 'literal_lines': literal_lines})
    return per_file
