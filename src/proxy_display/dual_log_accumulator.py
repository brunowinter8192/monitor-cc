# INFRASTRUCTURE
import json
from pathlib import Path
from typing import Optional

from .forwarded_parser import _infer_model_family
from .proxy_badge import _is_total_tokens_nuke, _msgs_delta_is_substantial

# FUNCTIONS

# Read new entries from the _original dual-log, keeping the LATEST non-empty tools list per model
# family as a {name: tool_def} map. Unlike _stripped/_injected/_forwarded, _original is NOT
# delta-encoded — every line with tools carries the full list — so no merge logic is needed, just
# overwrite. Tool defs are stable within a session (measured 2026-09-04, process-docs/dual_log_cli/
# 2026-09-04_sys_tool_original_chars_and_whole_strip_lines.md: 0 hash mismatches comparing any
# earlier request's tool-by-name content against the last request's, across 45 sessions), so always
# keeping the newest snapshot is correct without tracking history. acc_by_family: {family ->
# {name -> tool_def}}, mutated IN-PLACE per family dict (same reference-preservation convention as
# accumulate_dual_log) so entries holding a reference see updates automatically. Returns new file
# position; silently ignores missing/unreadable file.
def accumulate_original_tools(path: Optional[Path], last_pos: int, acc_by_family: dict) -> int:
    if path is None or not path.exists():
        return last_pos
    try:
        with open(path, 'r', encoding='utf-8') as f:
            f.seek(last_pos)
            while True:
                raw_line = f.readline()
                if not raw_line:
                    break
                line = raw_line.strip()
                if not line:
                    continue
                try:
                    entry = json.loads(line)
                except json.JSONDecodeError:
                    continue
                tools = (entry.get('payload') or {}).get('tools')
                if not tools:
                    continue
                family = _infer_model_family(entry.get('model', ''))
                fam_map = acc_by_family.setdefault(family, {})
                fam_map.clear()
                for t in tools:
                    if isinstance(t, dict) and t.get('name'):
                        fam_map[t['name']] = t
            return f.tell()
    except OSError:
        return last_pos

# is_first resets the family state — clears every section dict IN PLACE (preserves refs held by
# already-yielded entries) rather than rebinding acc[section] to a new dict.
def _reset_family_acc_if_first(acc: dict, entry: dict) -> None:
    if not entry.get('is_first', False):
        return
    for section in ('system', 'tools', 'messages', 'fields'):
        acc[section].clear()
    acc.setdefault('_has_content_by_flow_id', {}).clear()
    acc.setdefault('_msg_idx_by_flow_id', {}).clear()
    acc.setdefault('_sys_idx_by_flow_id', {}).clear()
    acc.setdefault('_tool_name_by_flow_id', {}).clear()
    acc.setdefault('_lag_msg_idx_by_flow_id', {}).clear()
    acc['_last_line_meta'] = None

# Merge one line's system/tools/messages/fields deltas onto the running family accumulator, IN
# PLACE (preserves refs — see accumulate_dual_log's own docstring). Returns this line's own
# messages_delta so the caller's flow-lookup and lag-correction steps can read it without
# re-parsing the entry.
def _merge_dual_log_entry(acc: dict, entry: dict) -> dict:
    acc['system'].update(entry.get('system_delta') or {})
    for name, val in (entry.get('tools_delta') or {}).items():
        acc['tools'][name] = val
    msgs_delta = entry.get('messages_delta') or {}
    for midx, blks in msgs_delta.items():
        if midx not in acc['messages']:
            acc['messages'][midx] = {}
        acc['messages'][midx].update(blks)
    acc['fields'].update(entry.get('fields_delta') or {})
    return msgs_delta

# '_has_content_by_flow_id': per-flow_id bool — did THIS line's delta carry any SUBSTANTIAL
# content, for the header badge. Derived from system/tools/messages_delta (fields_delta excluded —
# a field-only change must not badge; fields stay in the fields drill-down). Not fn_map. The
# messages part goes through `_msgs_delta_is_substantial`, which drops the per-request total_tokens
# nuke and "."-only filler injections — badge-only, the overlay dicts below are unaffected, so the
# expanded view still renders every span this filter hides from the header.
# '_msg_idx_by_flow_id': {flow_id -> set(msg_idx str)} — which message indices THIS line's
# messages_delta touched. Scopes span lookups so a request that did not touch a given index never
# shows a neighbor request's span there. It no longer drives any out-of-window rendering: the
# expanded body is the request's payload delta only (2026-08-30), so an index this flow touched
# outside that window is simply not drawn.
# '_sys_idx_by_flow_id' / '_tool_name_by_flow_id' (2026-09-04): the same per-flow scoping as
# '_msg_idx_by_flow_id', for the system and tools sections — which system indices / tool names
# THIS line's system_delta/tools_delta touched. Added for duallog's `msgs` sys/tool delta-tail
# feature (src/dual_log_cli/overlay.py's `build_sys_tool_overlay`); no lag correction is needed for
# either (unlike messages) — `_diff_system`/`_diff_tools` (src/proxy/diff_engine.py) compute a
# direct same-request diff of that request's own original vs. forwarded halves, never a historical
# ops chain, so there is no shape-ambiguity window for a strip to be recorded one request late.
def _record_flow_lookups(acc: dict, entry: dict, msgs_delta: dict) -> None:
    fid = entry.get('flow_id', '')
    has_content = bool(
        entry.get('system_delta') or entry.get('tools_delta')
        or _msgs_delta_is_substantial(msgs_delta, entry.get('type', ''))
    )
    acc.setdefault('_has_content_by_flow_id', {})[fid] = has_content
    acc.setdefault('_msg_idx_by_flow_id', {})[fid] = set(msgs_delta.keys())
    acc.setdefault('_sys_idx_by_flow_id', {})[fid] = set((entry.get('system_delta') or {}).keys())
    acc.setdefault('_tool_name_by_flow_id', {})[fid] = set((entry.get('tools_delta') or {}).keys())

# '_lag_msg_idx_by_flow_id': {flow_id -> set(msg_idx str)} — the WRITE-SIDE LAG CORRECTION.
# CC hangs the cache-control breakpoint on the last message, so a request's fresh trailing
# role='system' total_tokens msg arrives list-shaped; `_apply_role_system_strip` nukes it correctly
# but `_ops_from_content_change` yields no ops for list content, so the delta writer records no
# stripped span for it. The NEXT request re-sends that msg as a plain string, produces the op, and
# records the strip — one request too late (measured: 0 of 510 recorded against the request that
# performed them, 510 of 510 against the following one). This maps such a delta back onto the flow
# that actually stripped it, so `_lookup_spans` shows the olive original and green "." in-window.
# Three conditions, all required: the index is the PREVIOUS line's trailing msg (prev_count - 1),
# the count did not regress (no restart), and the delta is a total_tokens nuke. That last guard is
# load-bearing — CC overwrites a mid-conversation index in place (the task-tools nag lands on the
# index that was a previous request's trailing msg), and without the marker check the nag's text
# would be attributed to a request that stripped something else there, which is real neighbor bleed.
# Self-neutralising if the writer is ever fixed: the request would record its own strip and the next
# line's repeat would be hash-deduped away, leaving nothing to correct.
# '_last_line_meta': (flow_id, counts.messages) of the previous line of this family — the state the
# correction needs, kept in the acc dict so it survives across incremental calls.
def _apply_lag_correction(acc: dict, entry: dict, msgs_delta: dict) -> None:
    fid = entry.get('flow_id', '')
    count = (entry.get('counts') or {}).get('messages', 0)
    prev_meta = acc.get('_last_line_meta')
    if prev_meta is not None:
        prev_fid, prev_count = prev_meta
        trailing = str(prev_count - 1)
        if (count >= prev_count and prev_count > 0
                and _is_total_tokens_nuke(msgs_delta.get(trailing))):
            acc.setdefault('_lag_msg_idx_by_flow_id', {}).setdefault(
                prev_fid, set()).add(trailing)
    acc['_last_line_meta'] = (fid, count)

# Read new entries from one dual-log file (stripped or injected), accumulate per model_family.
# acc_by_family: {family -> {'system': {}, 'tools': {}, 'messages': {}, 'fields': {}}}
# Mutates acc_by_family IN-PLACE so all proxy_entries holding a reference see updates
# automatically. See `_reset_family_acc_if_first` (is_first handling), `_merge_dual_log_entry`
# (system/tools/messages/fields merge), `_record_flow_lookups` (per-flow badge/scoping lookups) and
# `_apply_lag_correction` (the write-side lag correction) for what each step of the per-line walk
# below does. Returns new file position; silently ignores missing/unreadable file.
def accumulate_dual_log(path: Optional[Path], last_pos: int, acc_by_family: dict) -> int:
    if path is None or not path.exists():
        return last_pos
    try:
        with open(path, 'r', encoding='utf-8') as f:
            f.seek(last_pos)
            while True:
                raw_line = f.readline()
                if not raw_line:
                    break
                line = raw_line.strip()
                if not line:
                    continue
                try:
                    entry = json.loads(line)
                except json.JSONDecodeError:
                    continue
                family = _infer_model_family(entry.get('model', ''))
                acc = acc_by_family.setdefault(
                    family,
                    {
                        'system': {}, 'tools': {}, 'messages': {}, 'fields': {},
                        '_has_content_by_flow_id': {}, '_msg_idx_by_flow_id': {},
                    }
                )
                _reset_family_acc_if_first(acc, entry)
                msgs_delta = _merge_dual_log_entry(acc, entry)
                _record_flow_lookups(acc, entry, msgs_delta)
                _apply_lag_correction(acc, entry, msgs_delta)
            return f.tell()
    except OSError:
        return last_pos
