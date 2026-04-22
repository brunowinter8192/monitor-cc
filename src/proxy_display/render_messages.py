# INFRASTRUCTURE
import re
from ..constants import (
    SOFT_RESET, RED, WHITE, DIM, DIM_YELLOW_BG, LIGHT_RED_BG, RESET,
)

_SUSPECT_TAGS = [
    ('<new-diagnostics>', 'ND'),
    ('<persisted-output>', 'PO'),
    ('<system-reminder>', 'SR'),
    ('<task-notification>', 'TN'),
]
_SUSPECT_TAG_RE = re.compile(
    r'(<(?:new-diagnostics|persisted-output|system-reminder|task-notification)>)'
)

# FUNCTIONS

# Return sorted list of suspect tag labels found in text
def _detect_suspect_tags(text: str) -> list[str]:
    if not text:
        return []
    return [label for tag, label in _SUSPECT_TAGS if tag in text]

# Render new/modified/removed messages for an expanded request entry, returning (lines, keys)
def render_messages(entry: dict, prev_entry_for_delta, entries: list, expand_states: dict, pane_width: int) -> tuple:
    lines = []
    keys = []
    messages = entry.get('messages', [])
    stripped_indices = set(entry.get('stripped_msg_indices', []))
    prev_msg_count = prev_entry_for_delta.get('message_count', 0) if prev_entry_for_delta is not None else 0
    if prev_msg_count < len(messages):
        for msg_idx in range(prev_msg_count, len(messages)):
            msg = messages[msg_idx]
            role = msg.get('role', '?')[:4]
            msg_type = msg.get('type', 'text')
            chars = msg.get('chars', 0)
            chars_fmt = f"{chars:,}c"
            is_stripped = msg_idx in stripped_indices
            if is_stripped:
                lines.append(f"    {WHITE}[{msg_idx:3d}] {role:<4}  {msg_type:<20} {chars_fmt:>8}  [STRIPPED]{SOFT_RESET}")
                removed_map = entry.get('stripped_msg_removed')
                if removed_map is not None:
                    removed_chunks = removed_map.get(str(msg_idx), [])
                    for chunk_idx, chunk in enumerate(removed_chunks):
                        if chunk_idx > 0:
                            lines.append(f"      {DIM_YELLOW_BG}{DIM}{SOFT_RESET}")
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
                    if orig_text:
                        for raw_line in orig_text.split('\n'):
                            raw_line = raw_line.expandtabs(8)
                            if not raw_line:
                                lines.append(f"      {DIM_YELLOW_BG}{DIM}{SOFT_RESET}")
                                keys.append(None)
                                continue
                            lines.append(f"      {DIM_YELLOW_BG}{DIM}{raw_line}{SOFT_RESET}")
                            keys.append(None)
            else:
                blocks = msg.get('blocks', [])
                type_label = f"{len(blocks)} blocks" if len(blocks) > 1 else msg_type
                lines.append(f"    {WHITE}[{msg_idx:3d}] {role:<4}  {type_label:<20} {chars_fmt:>8}{SOFT_RESET}")
            keys.append(None)
            blocks = msg.get('blocks', [])
            if blocks:
                for bidx, blk in enumerate(blocks):
                    btype = blk.get('type', 'text')
                    bchars = blk.get('chars', 0)
                    bcc = ' [CC]' if blk.get('has_cc') else ''
                    full_text = blk.get('full_text', blk.get('preview', ''))
                    labels = _detect_suspect_tags(full_text)
                    badge = f' {RED}⚠{",".join(labels)}{SOFT_RESET}' if labels else ''
                    if btype == 'thinking':
                        sig_chars = blk.get('sig_chars', 0)
                        lines.append(f"      {DIM}[{bidx}] {btype:<12} text:{bchars:>5,}c sig:{sig_chars:>4,}c{bcc}{SOFT_RESET}")
                    else:
                        lines.append(f"      {DIM}[{bidx}] {btype:<12} {bchars:>6,}c{bcc}{badge}{SOFT_RESET}")
                    keys.append(None)
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
        for msg_idx in range(diff_start, len(messages)):
            msg = messages[msg_idx]
            role = msg.get('role', '?')[:4]
            msg_type = msg.get('type', 'text')
            is_stripped = msg_idx in stripped_indices
            if is_stripped:
                lines.append(f"    {WHITE}[{msg_idx:3d}] {role:<4}  {msg_type:<20}  [STRIPPED]{SOFT_RESET}")
                removed_map = entry.get('stripped_msg_removed')
                if removed_map is not None:
                    removed_chunks = removed_map.get(str(msg_idx), [])
                    for chunk_idx, chunk in enumerate(removed_chunks):
                        if chunk_idx > 0:
                            lines.append(f"      {DIM_YELLOW_BG}{DIM}{SOFT_RESET}")
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
                    if orig_text:
                        for raw_line in orig_text.split('\n'):
                            raw_line = raw_line.expandtabs(8)
                            if not raw_line:
                                lines.append(f"      {DIM_YELLOW_BG}{DIM}{SOFT_RESET}")
                                keys.append(None)
                                continue
                            lines.append(f"      {DIM_YELLOW_BG}{DIM}{raw_line}{SOFT_RESET}")
                            keys.append(None)
            else:
                blocks = msg.get('blocks', [])
                type_label = f"{len(blocks)} blocks" if len(blocks) > 1 else msg_type
                lines.append(f"    {DIM}[{msg_idx:3d}] {role:<4}  {type_label:<20}{SOFT_RESET}")
            keys.append(None)
            blocks = msg.get('blocks', [])
            if blocks:
                for bidx, blk in enumerate(blocks):
                    btype = blk.get('type', 'text')
                    bchars = blk.get('chars', 0)
                    bcc = ' [CC]' if blk.get('has_cc') else ''
                    full_text = blk.get('full_text', blk.get('preview', ''))
                    labels = _detect_suspect_tags(full_text)
                    badge = f' {RED}⚠{",".join(labels)}{SOFT_RESET}' if labels else ''
                    if btype == 'thinking':
                        sig_chars = blk.get('sig_chars', 0)
                        lines.append(f"      {DIM}[{bidx}] {btype:<12} text:{bchars:>5,}c sig:{sig_chars:>4,}c{bcc}{SOFT_RESET}")
                    else:
                        lines.append(f"      {DIM}[{bidx}] {btype:<12} {bchars:>6,}c{bcc}{badge}{SOFT_RESET}")
                    keys.append(None)
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
