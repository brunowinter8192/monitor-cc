# INFRASTRUCTURE
import json
import sys
from pathlib import Path

WORKTREE_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(WORKTREE_ROOT / 'src'))

# Structural passes (own logic) stayed in message_passes.py; template passes (generic pass
# runner + declarative spec) moved to message_passes_simple.py; the wake-up concern moved to
# message_passes_wakeup.py (2026-09, helper-extraction milestone).
from proxy.message_passes import (
    _apply_role_system_strip,
    _apply_first_pass,
    _apply_cumulative_sr_strips,
    _apply_final_sr_pass,
)
from proxy.message_passes_simple import (
    _apply_sn_notice_strip,
    _apply_po_preview_strip,
    _apply_bg_exit_strip,
    _apply_bg_launch_ack_strip,
    _apply_hook_prefix_strip,
    _apply_git_lock_strip,
    _apply_bd_noise_strip,
)
from proxy.message_passes_wakeup import _dedup_wakeup_blocks
from proxy.rule_ops import _block_inner_text
from proxy.payload_helpers import _top_level_content_contains
from proxy.content_strip import _message_has_rejection

# Real pass order from src/proxy/rules.py::apply_modification_rules — _passes list, then the
# _dedup_wakeup_blocks call that follows the loop. Each pass function is called with ONLY the
# per-request NEW message slice (see _scan_file) — legitimate because every pass here decides
# per-message from that message's own content alone (verified by reading message_passes.py: no
# pass reads any OTHER message's content), so feeding only new messages is equivalent to feeding
# the full growing list and produces identical per-message ops without dual-log's cumulative
# duplicate counting (same dedup principle as D1, blessed for that deliverable).
_PASSES = [
    _apply_role_system_strip,
    _apply_sn_notice_strip,
    _apply_first_pass,
    _apply_cumulative_sr_strips,
    _apply_final_sr_pass,
    _apply_po_preview_strip,
    _apply_bg_exit_strip,
    _apply_bg_launch_ack_strip,
    _apply_hook_prefix_strip,
    _apply_git_lock_strip,
    _apply_bd_noise_strip,
]

# Semantic classification per call site — determined by READING the underlying strip function,
# not by any measured ratio. FULL = new block content is constructed independently of the old
# (a fixed literal, or a freshly-derived string) with no attempt to preserve any of the old text
# outside what a template happens to share. PARTIAL = a known marker/chunk is excised from within
# the text (regex.sub / str.replace / slice) and everything else in the block is kept verbatim.
# STRUCTURAL = neither — an index-shift artifact, not a designed content transform.
PASS_CLASS = {
    '_apply_role_system_strip': (
        'FULL',
        "message_passes.py:66 — result.append({**msg, 'content': '.'}) — content set to the "
        "literal '.' independent of old content"),
    '_apply_sn_notice_strip': (
        'PARTIAL',
        "strip_sn_notice.py:66 — text.replace(needle, '', 1) — paragraph excised, remainder kept"),
    '_apply_cumulative_sr_strips': (
        'PARTIAL',
        "strip_sr.py:138 (via _strip_system_reminder) — _STANDALONE_SR_RE.sub(_replace, text) — "
        "matched SR block(s) excised, remainder kept"),
    '_apply_final_sr_pass': (
        'PARTIAL',
        "strip_sr.py:138 (via _strip_all_system_reminders) — same regex-sub excise mechanism"),
    '_apply_po_preview_strip': (
        'PARTIAL',
        "strip_po.py:72 — _PO_PREVIEW_RE.sub(_replace, text) — only the 'preview' capture group "
        "is dropped, 'open'+'close' groups (and everything outside the match) kept"),
    '_apply_bg_exit_strip': (
        'PARTIAL',
        "strip_bg_completed.py:68 — _BG_EXIT_RE.sub(_replace, text) — matched notification line(s) "
        "excised/replaced in place, remainder kept"),
    '_apply_bg_launch_ack_strip': (
        'FULL',
        "strip_bg_launch_ack.py:44/57/65/76 — block text/content field set wholesale to "
        "_build_launch_ack_replacement(text), independent of old text (anchored block-initial "
        "match only, but ANY trailing content after the ack in that block is also discarded)"),
    '_apply_hook_prefix_strip': (
        'PARTIAL',
        "strip_hook_prefix.py:68 — _HOOK_PREFIX_RE.sub(_replace, text, count=1) — prefix excised, "
        "remainder kept"),
    '_apply_git_lock_strip': (
        'PARTIAL',
        "strip_git_lock.py:70 — text.replace(needle, '', 1) — advice block excised, remainder kept"),
    '_apply_bd_noise_strip': (
        'PARTIAL',
        "strip_bd_noise.py:91 — _BD_NOISE_RE.sub(_collect, text) — matched noise line(s) excised, "
        "remainder kept"),
    '_dedup_wakeup_blocks:str': (
        'PARTIAL',
        "message_passes.py:105 — new_content_str = content[:end] — prefix-preserving truncation, "
        "kept prefix IS the remainder"),
    '_dedup_wakeup_blocks:list': (
        'STRUCTURAL',
        "message_passes.py:88-96 — drops a duplicate BLOCK from the content list; later blocks "
        "shift index, so _ops_from_content_change compares UNRELATED blocks positionally at the "
        "shifted index (index-shift artifact, not a designed content replacement)"),
}

# _apply_first_pass is one function with 5 internal elif-branches, each with a DIFFERENT
# classification — sub-classify per message by re-evaluating the same branch conditions the
# real function uses (reusing the real predicate functions, not reimplementing their logic)
FIRST_PASS_BRANCH_CLASS = {
    'TN': ('PARTIAL',
           "payload_helpers.py:159 — _NOTIF_PAT.sub(_repl, content) or '.' — regex splice, "
           "preserves any surrounding text; falls back to '.' only if nothing remains"),
    'task_tools_nag': ('PARTIAL', "strip_sr.py:138 via _strip_system_reminder"),
    'deferred_tools': ('PARTIAL', "strip_sr.py:138 via _strip_system_reminder"),
    'user_interrupt': ('PARTIAL',
                        "strip_sr.py:134-136 — 'partial' template mode: IMPORTANT line excised, "
                        "user body + outer tags preserved"),
    'rejection': ('FULL',
                  "content_strip.py:31 (str) / :43 (tool_result block) — content set to the "
                  "literal '.' independent of old content"),
}


# FUNCTIONS

# Re-derive which _apply_first_pass elif-branch fires for one message — mirrors the real
# elif-chain in message_passes.py exactly, reusing the real predicate functions
def _first_pass_branch(old_content, role):
    if role in ('user', 'system') and _top_level_content_contains(old_content, '<task-notification>'):
        return 'TN'
    if role == 'user' and _top_level_content_contains(old_content, 'task tools haven'):
        return 'task_tools_nag'
    if role == 'user' and _top_level_content_contains(old_content, 'deferred tools are now available via ToolSearch'):
        return 'deferred_tools'
    if role == 'user' and _top_level_content_contains(old_content, 'user sent a new message while you were working'):
        return 'user_interrupt'
    if role == 'user' and _message_has_rejection(old_content):
        return 'rejection'
    return None


# Block text at blk_idx, mirroring _ops_from_content_change's own extraction exactly
def _block_text(content, blk_idx):
    if isinstance(content, list):
        return _block_inner_text(content[blk_idx]) if blk_idx < len(content) else ''
    if isinstance(content, str):
        return content
    return ''


# Drive one delta message-list through all passes in real order, collecting every op with its
# semantic class + evidence + (bt, at) for corroborating-ratio + render reproduction
def _drive_passes(delta_messages, records):
    new_messages = delta_messages
    for pass_fn in _PASSES:
        messages_before = new_messages
        new_messages, _mods, _removed, c_idxs, _injected, pass_ops = pass_fn(messages_before)
        for msg_idx, blk_map in pass_ops.items():
            role = messages_before[msg_idx].get('role', '?')
            old_content = messages_before[msg_idx].get('content', '')
            new_content = new_messages[msg_idx].get('content', '')
            if pass_fn.__name__ == '_apply_first_pass':
                branch = _first_pass_branch(old_content, role)
                site = f'_apply_first_pass:{branch}'
                cls, evidence = FIRST_PASS_BRANCH_CLASS.get(branch, ('UNKNOWN', 'branch not resolved'))
            else:
                site = pass_fn.__name__
                cls, evidence = PASS_CLASS[site]
            for blk_idx, op_list in blk_map.items():
                bt = _block_text(old_content, blk_idx)
                at = _block_text(new_content, blk_idx)
                for (offset, removed, injected) in op_list:
                    records.append({
                        'site': site, 'class': cls, 'evidence': evidence,
                        'offset': offset, 'removed': removed, 'injected': injected,
                        'bt': bt, 'at': at,
                    })
    # _dedup_wakeup_blocks runs after the pass loop in rules.py, outside _passes
    messages_before = new_messages
    new_messages, pass_ops = _dedup_wakeup_blocks(new_messages)
    for msg_idx, blk_map in pass_ops.items():
        old_content = messages_before[msg_idx].get('content', '')
        new_content = new_messages[msg_idx].get('content', '')
        shape = 'list' if isinstance(old_content, list) else 'str'
        site = f'_dedup_wakeup_blocks:{shape}'
        cls, evidence = PASS_CLASS[site]
        for blk_idx, op_list in blk_map.items():
            bt = _block_text(old_content, blk_idx)
            at = _block_text(new_content, blk_idx)
            for (offset, removed, injected) in op_list:
                records.append({
                    'site': site, 'class': cls, 'evidence': evidence,
                    'offset': offset, 'removed': removed, 'injected': injected,
                    'bt': bt, 'at': at,
                })
    return new_messages


# Scan one corpus file: dedup via prev-message-count delta (same principle as D1) — each pass
# function decides per-message from that message's own content alone (no cross-message
# dependency in any of the 11 passes, verified by reading message_passes.py), so feeding only
# the newly-introduced messages per request reproduces the exact same per-message ops the real
# cumulative pipeline would produce, without reprocessing (and over-counting) duplicated history.
def _scan_file(path, records):
    prev_count = 0
    requests = 0
    with open(path, 'rb') as fh:
        for raw in fh:
            requests += 1
            entry = json.loads(raw)
            messages = entry.get('payload', {}).get('messages', [])
            start = prev_count if prev_count <= len(messages) else 0
            delta = messages[start:]
            if delta:
                _drive_passes(delta, records)
            prev_count = len(messages)
    return requests
