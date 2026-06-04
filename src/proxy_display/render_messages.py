# INFRASTRUCTURE
import re
from collections import Counter
from ..constants import (
    SOFT_RESET, RED, WHITE, DIM, DIM_YELLOW_BG, DIM_GREEN_BG, LIGHT_RED_BG, RESET,
)
from ..proxy.strip_vocab import attribute_chunk, classify_req

_SUSPECT_TAG_RE = re.compile(
    r'(<(?:new-diagnostics|persisted-output|system-reminder|task-notification)>)'
)

# FUNCTIONS

# Aggregate tag labels for entries where a strip rule fired in the delta range
def _aggregate_entry_tags(entry: dict) -> list[str]:
    diff = entry.get('diff_from_prev') or {}
    fdi = diff.get('first_diff_index')
    if fdi is None:
        start = 0  # First REQ — all msgs are new, no diff_from_prev key
    elif fdi < 0:
        return []  # Byte-identical re-fire — no new strip activity
    else:
        # Truly new messages start at prev_message_count, not first_diff_index.
        # first_diff_index can regress into old messages when a prior msg changes
        # by even 1 char (re-serialization, trailing-newline drift after TN strip);
        # using it as the gate causes double-firing of the same strip.
        start = entry.get('message_count', 0) - (diff.get('messages_added') or 0)
    smr = entry.get('stripped_msg_removed') or {}
    found = set()
    for idx_str, chunks in smr.items():
        if int(idx_str) < start:
            continue
        for chunk in (chunks or []):
            if '<system-reminder>' in chunk:
                found.add('SR')
            if '<task-notification>' in chunk:
                found.add('TN')
            if '<new-diagnostics>' in chunk:
                found.add('ND')
    return sorted(found)

# Render header + stripped chunks for one message, returning (lines, keys) with len==len
# show_chars=True adds chars_fmt to the header line (Branch 1 style); False omits it (Branch 2 style)
# Header key is appended last (matches render_messages loop convention)
def _render_stripped_block(entry: dict, msg_idx: int, msg: dict, show_chars: bool = True) -> tuple:
    lines = []
    keys = []
    role = msg.get('role', '?')[:4]
    msg_type = msg.get('type', 'text')
    removed_map = entry.get('stripped_msg_removed')
    removed_chunks = removed_map.get(str(msg_idx), []) if removed_map is not None else []
    if removed_chunks:
        if show_chars:
            chars_fmt = f"{msg.get('chars', 0):,}c"
            lines.append(f"    {WHITE}[{msg_idx:3d}] {role:<4}  {msg_type:<20} {chars_fmt:>8}  [STRIPPED]{SOFT_RESET}")
        else:
            lines.append(f"    {WHITE}[{msg_idx:3d}] {role:<4}  {msg_type:<20}  [STRIPPED]{SOFT_RESET}")
        for chunk in removed_chunks:
            rule_code = attribute_chunk(chunk)
            label = f'EFF:{rule_code}' if rule_code else 'EFF:?'
            lines.append(f"      {WHITE}{label}{SOFT_RESET}")
            keys.append(None)
            for raw_line in chunk.split('\n'):
                raw_line = raw_line.expandtabs(8)
                if not raw_line:
                    lines.append(f"      {DIM_YELLOW_BG}{DIM}{SOFT_RESET}")
                    keys.append(None)
                    continue
                lines.append(f"      {DIM_YELLOW_BG}{DIM}{raw_line}{SOFT_RESET}")
                keys.append(None)
    else:
        originals = entry.get('stripped_msg_originals', {})
        orig_text = originals.get(str(msg_idx), '')
        if show_chars:
            chars_fmt = f"{msg.get('chars', 0):,}c"
            lines.append(f"    {WHITE}[{msg_idx:3d}] {role:<4}  {msg_type:<20} {chars_fmt:>8}  [STRIPPED]  IDX{SOFT_RESET}")
        else:
            lines.append(f"    {WHITE}[{msg_idx:3d}] {role:<4}  {msg_type:<20}  [STRIPPED]  IDX{SOFT_RESET}")
        if orig_text:
            for raw_line in orig_text.split('\n'):
                raw_line = raw_line.expandtabs(8)
                if not raw_line:
                    lines.append(f"      {DIM_YELLOW_BG}{DIM}{SOFT_RESET}")
                    keys.append(None)
                    continue
                lines.append(f"      {DIM_YELLOW_BG}{DIM}{raw_line}{SOFT_RESET}")
                keys.append(None)
    keys.append(None)  # key for header line
    return lines, keys

# Render new/modified/removed messages for an expanded request entry, returning (lines, keys)
def render_messages(entry: dict, prev_entry_for_delta, entries: list, expand_states: dict, pane_width: int) -> tuple:
    lines = []
    keys = []
    messages = entry.get('messages', [])
    stripped_indices = set(entry.get('stripped_msg_indices', []))
    prev_msg_count = prev_entry_for_delta.get('message_count', 0) if prev_entry_for_delta is not None else 0
    diff = entry.get('diff_from_prev') or {}
    fdi = diff.get('first_diff_index')
    if fdi is None:
        fdi = 0
    use_dual = '_stripped_spans' in entry
    if prev_msg_count < len(messages):
        # Render stripped messages from [fdi, prev_msg_count) skipped by the new-range loop below
        if fdi >= 0 and not use_dual:
            for msg_idx in sorted(s for s in stripped_indices if fdi <= s < prev_msg_count):
                s_lines, s_keys = _render_stripped_block(entry, msg_idx, messages[msg_idx], show_chars=True)
                lines.extend(s_lines)
                keys.extend(s_keys)
        for msg_idx in range(prev_msg_count, len(messages)):
            msg = messages[msg_idx]
            is_stripped = msg_idx in stripped_indices
            blocks = msg.get('blocks', [])
            if is_stripped and not use_dual:
                s_lines, s_keys = _render_stripped_block(entry, msg_idx, msg, show_chars=True)
                lines.extend(s_lines)
                keys.extend(s_keys)
            else:
                role = msg.get('role', '?')[:4]
                msg_type = msg.get('type', 'text')
                chars_fmt = f"{msg.get('chars', 0):,}c"
                type_label = f"{len(blocks)} blocks" if len(blocks) > 1 else msg_type
                lines.append(f"    {WHITE}[{msg_idx:3d}] {role:<4}  {type_label:<20} {chars_fmt:>8}{SOFT_RESET}")
                keys.append(None)
            if blocks:
                for bidx, blk in enumerate(blocks):
                    btype = blk.get('type', 'text')
                    bchars = blk.get('chars', 0)
                    bcc = ' [CC]' if blk.get('has_cc') else ''
                    full_text = blk.get('full_text', blk.get('preview', ''))
                    if btype == 'thinking':
                        sig_chars = blk.get('sig_chars', 0)
                        lines.append(f"      {DIM}[{bidx}] {btype:<12} text:{bchars:>5,}c sig:{sig_chars:>4,}c{bcc}{SOFT_RESET}")
                    else:
                        lines.append(f"      {DIM}[{bidx}] {btype:<12} {bchars:>6,}c{bcc}{SOFT_RESET}")
                    keys.append(None)
                    i_blk = (entry['_injected_spans']['messages'].get(str(msg_idx), {}).get(str(bidx)) or []) if use_dual else []
                    s_blk = (entry['_stripped_spans']['messages'].get(str(msg_idx), {}).get(str(bidx)) or []) if use_dual else []
                    if i_blk and isinstance(i_blk[0], (list, tuple)):
                        # New format: inline render — equal=DIM, injected=DIM_GREEN_BG, no gray preview
                        for tag, span_text in i_blk:
                            bg = DIM_GREEN_BG if tag == "injected" else ""
                            for raw_line in span_text.split('\n'):
                                raw_line = raw_line.expandtabs(8)
                                if not raw_line:
                                    lines.append(f"        {bg}{DIM}{SOFT_RESET}")
                                    keys.append(None)
                                    continue
                                highlighted = _SUSPECT_TAG_RE.sub(
                                    lambda m: f'{LIGHT_RED_BG}{m.group(0)}{RESET}{DIM}', raw_line
                                )
                                lines.append(f"        {bg}{DIM}{highlighted}{SOFT_RESET}")
                                keys.append(None)
                        for span_text in s_blk:
                            for raw_line in span_text.split('\n'):
                                raw_line = raw_line.expandtabs(8)
                                lines.append(f"        {DIM_YELLOW_BG}{DIM}{raw_line or ''}{SOFT_RESET}")
                                keys.append(None)
                    else:
                        if full_text:
                            for raw_line in full_text.split('\n'):
                                raw_line = raw_line.expandtabs(8)
                                if not raw_line:
                                    lines.append(f"        {DIM}{SOFT_RESET}")
                                    keys.append(None)
                                    continue
                                highlighted = _SUSPECT_TAG_RE.sub(
                                    lambda m: f'{LIGHT_RED_BG}{m.group(0)}{RESET}{DIM}', raw_line
                                )
                                lines.append(f"        {DIM}{highlighted}{SOFT_RESET}")
                                keys.append(None)
                        if use_dual:
                            for span_text in s_blk:
                                for raw_line in span_text.split('\n'):
                                    raw_line = raw_line.expandtabs(8)
                                    lines.append(f"        {DIM_YELLOW_BG}{DIM}{raw_line or ''}{SOFT_RESET}")
                                    keys.append(None)
                            for span_text in i_blk:
                                for raw_line in span_text.split('\n'):
                                    raw_line = raw_line.expandtabs(8)
                                    lines.append(f"        {DIM_GREEN_BG}{DIM}{raw_line or ''}{SOFT_RESET}")
                                    keys.append(None)
            else:
                preview = msg.get('content_preview', '')
                if preview:
                    for raw_line in preview.split('\n'):
                        raw_line = raw_line.expandtabs(8)
                        if not raw_line:
                            lines.append(f"      {DIM}{SOFT_RESET}")
                            keys.append(None)
                            continue
                        lines.append(f"      {DIM}{raw_line}{SOFT_RESET}")
                        keys.append(None)
    else:
        prev_messages = prev_entry_for_delta.get('messages', []) if prev_entry_for_delta is not None else []
        diff_start = len(messages)
        for j in range(1, min(len(messages), len(prev_messages)) + 1):
            curr_msg = messages[-j]
            prev_msg = prev_messages[-j]
            if curr_msg.get('chars', 0) != prev_msg.get('chars', 0) or curr_msg.get('type', '') != prev_msg.get('type', ''):
                diff_start = len(messages) - j
            else:
                break
        # Render stripped messages from [fdi, diff_start) skipped by the diff-range loop below
        if fdi >= 0 and not use_dual:
            for msg_idx in sorted(s for s in stripped_indices if fdi <= s < diff_start):
                s_lines, s_keys = _render_stripped_block(entry, msg_idx, messages[msg_idx], show_chars=False)
                lines.extend(s_lines)
                keys.extend(s_keys)
        for msg_idx in range(diff_start, len(messages)):
            msg = messages[msg_idx]
            is_stripped = msg_idx in stripped_indices
            blocks = msg.get('blocks', [])
            if is_stripped and not use_dual:
                s_lines, s_keys = _render_stripped_block(entry, msg_idx, msg, show_chars=False)
                lines.extend(s_lines)
                keys.extend(s_keys)
            else:
                role = msg.get('role', '?')[:4]
                msg_type = msg.get('type', 'text')
                type_label = f"{len(blocks)} blocks" if len(blocks) > 1 else msg_type
                lines.append(f"    {DIM}[{msg_idx:3d}] {role:<4}  {type_label:<20}{SOFT_RESET}")
                keys.append(None)
            if blocks:
                for bidx, blk in enumerate(blocks):
                    btype = blk.get('type', 'text')
                    bchars = blk.get('chars', 0)
                    bcc = ' [CC]' if blk.get('has_cc') else ''
                    full_text = blk.get('full_text', blk.get('preview', ''))
                    if btype == 'thinking':
                        sig_chars = blk.get('sig_chars', 0)
                        lines.append(f"      {DIM}[{bidx}] {btype:<12} text:{bchars:>5,}c sig:{sig_chars:>4,}c{bcc}{SOFT_RESET}")
                    else:
                        lines.append(f"      {DIM}[{bidx}] {btype:<12} {bchars:>6,}c{bcc}{SOFT_RESET}")
                    keys.append(None)
                    i_blk = (entry['_injected_spans']['messages'].get(str(msg_idx), {}).get(str(bidx)) or []) if use_dual else []
                    s_blk = (entry['_stripped_spans']['messages'].get(str(msg_idx), {}).get(str(bidx)) or []) if use_dual else []
                    if i_blk and isinstance(i_blk[0], (list, tuple)):
                        # New format: inline render — equal=DIM, injected=DIM_GREEN_BG, no gray preview
                        for tag, span_text in i_blk:
                            bg = DIM_GREEN_BG if tag == "injected" else ""
                            for raw_line in span_text.split('\n'):
                                raw_line = raw_line.expandtabs(8)
                                if not raw_line:
                                    lines.append(f"        {bg}{DIM}{SOFT_RESET}")
                                    keys.append(None)
                                    continue
                                highlighted = _SUSPECT_TAG_RE.sub(
                                    lambda m: f'{LIGHT_RED_BG}{m.group(0)}{RESET}{DIM}', raw_line
                                )
                                lines.append(f"        {bg}{DIM}{highlighted}{SOFT_RESET}")
                                keys.append(None)
                        for span_text in s_blk:
                            for raw_line in span_text.split('\n'):
                                raw_line = raw_line.expandtabs(8)
                                lines.append(f"        {DIM_YELLOW_BG}{DIM}{raw_line or ''}{SOFT_RESET}")
                                keys.append(None)
                    else:
                        if full_text:
                            for raw_line in full_text.split('\n'):
                                raw_line = raw_line.expandtabs(8)
                                if not raw_line:
                                    lines.append(f"        {DIM}{SOFT_RESET}")
                                    keys.append(None)
                                    continue
                                highlighted = _SUSPECT_TAG_RE.sub(
                                    lambda m: f'{LIGHT_RED_BG}{m.group(0)}{RESET}{DIM}', raw_line
                                )
                                lines.append(f"        {DIM}{highlighted}{SOFT_RESET}")
                                keys.append(None)
                        if use_dual:
                            for span_text in s_blk:
                                for raw_line in span_text.split('\n'):
                                    raw_line = raw_line.expandtabs(8)
                                    lines.append(f"        {DIM_YELLOW_BG}{DIM}{raw_line or ''}{SOFT_RESET}")
                                    keys.append(None)
                            for span_text in i_blk:
                                for raw_line in span_text.split('\n'):
                                    raw_line = raw_line.expandtabs(8)
                                    lines.append(f"        {DIM_GREEN_BG}{DIM}{raw_line or ''}{SOFT_RESET}")
                                    keys.append(None)
            else:
                tail = msg.get('content_tail', '')
                if tail:
                    for raw_line in tail.split('\n'):
                        raw_line = raw_line.expandtabs(8)
                        if not raw_line:
                            lines.append(f"      {DIM}{SOFT_RESET}")
                            keys.append(None)
                            continue
                        lines.append(f"      {DIM}{raw_line}{SOFT_RESET}")
                        keys.append(None)
        removed_from_prev = prev_messages[len(messages):]
        for m_offset, msg in enumerate(removed_from_prev):
            m_idx = len(messages) + m_offset
            role = msg.get('role', '?')[:4]
            m_type = msg.get('type', 'text')
            m_chars = msg.get('chars', 0)
            lines.append(f"    {RED}removed:{SOFT_RESET} {DIM}[{m_idx:3d}] {role:<4}  {m_type:<20} {m_chars:,}c{SOFT_RESET}")
            keys.append(None)
    return lines, keys


# Compute aggregated strip bucket signals for an expanded REQ header (INERT/IDX/LEAK/SUS)
# Delegates to classify_req; effective chunks are not used here (per-chunk attribution
# happens inline in the render loop above)
def _aggregate_req_buckets(entry: dict, prev_entry) -> dict:
    cls = classify_req(entry, prev_entry)
    return {
        'inert_codes':  cls['inert'],
        'idx_msgs':     cls['idx_msgs'],
        'leak_signals': cls['leak_signals'],
        'sus_signals':  cls['sus_signals'],
    }
