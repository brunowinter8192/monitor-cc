# INFRASTRUCTURE
from ..constants import (
    RESET, RED, WHITE, DIM, DIM_YELLOW_BG,
)

# FUNCTIONS

# Render new/modified/removed messages for an expanded request entry, returning (lines, keys)
def render_messages(entry: dict, prev_entry_for_delta, entries: list, expand_states: dict, pane_width: int) -> tuple:
    lines = []
    keys = []
    messages = entry.get('messages', [])
    stripped_indices = set(entry.get('stripped_msg_indices', []))
    prev_msg_count = prev_entry_for_delta.get('message_count', 0) if prev_entry_for_delta is not None else 0
    wrap_width = max(20, pane_width - 8)
    if prev_msg_count < len(messages):
        for msg_idx in range(prev_msg_count, len(messages)):
            msg = messages[msg_idx]
            role = msg.get('role', '?')[:4]
            msg_type = msg.get('type', 'text')
            chars = msg.get('chars', 0)
            chars_fmt = f"{chars:,}c"
            is_stripped = msg_idx in stripped_indices
            if is_stripped:
                lines.append(f"    {WHITE}[{msg_idx:3d}] {role:<4}  {msg_type:<20} {chars_fmt:>8}  [STRIPPED]{RESET}")
                keys.append(None)
                originals = entry.get('stripped_msg_originals', {})
                orig_text = originals.get(str(msg_idx), '')
                if orig_text:
                    for raw_line in orig_text.split('\n')[:15]:
                        if not raw_line:
                            lines.append(f"      {DIM_YELLOW_BG}{DIM}{RESET}")
                            keys.append(None)
                            continue
                        for chunk_start in range(0, len(raw_line), wrap_width):
                            lines.append(f"      {DIM_YELLOW_BG}{DIM}{raw_line[chunk_start:chunk_start + wrap_width]}{RESET}")
                            keys.append(None)
                continue
            else:
                blocks = msg.get('blocks', [])
                type_label = f"{len(blocks)} blocks" if len(blocks) > 1 else msg_type
                lines.append(f"    {WHITE}[{msg_idx:3d}] {role:<4}  {type_label:<20} {chars_fmt:>8}{RESET}")
            keys.append(None)
            blocks = msg.get('blocks', [])
            if blocks:
                for bidx, blk in enumerate(blocks):
                    btype = blk.get('type', 'text')
                    bchars = blk.get('chars', 0)
                    bcc = ' [CC]' if blk.get('has_cc') else ''
                    lines.append(f"      {DIM}[{bidx}] {btype:<12} {bchars:>6,}c{bcc}{RESET}")
                    keys.append(None)
                    full_text = blk.get('full_text', blk.get('preview', ''))
                    if full_text:
                        for raw_line in full_text.split('\n'):
                            if not raw_line:
                                lines.append(f"        {DIM}{RESET}")
                                keys.append(None)
                                continue
                            for chunk_start in range(0, len(raw_line), wrap_width):
                                lines.append(f"        {DIM}{raw_line[chunk_start:chunk_start + wrap_width]}{RESET}")
                                keys.append(None)
            else:
                preview = msg.get('content_preview', '')
                if preview:
                    for raw_line in preview.split('\n'):
                        if not raw_line:
                            lines.append(f"      {DIM}{RESET}")
                            keys.append(None)
                            continue
                        for chunk_start in range(0, len(raw_line), wrap_width):
                            lines.append(f"      {DIM}{raw_line[chunk_start:chunk_start + wrap_width]}{RESET}")
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
                lines.append(f"    {WHITE}[{msg_idx:3d}] {role:<4}  {msg_type:<20}  [STRIPPED]{RESET}")
                keys.append(None)
                originals = entry.get('stripped_msg_originals', {})
                orig_text = originals.get(str(msg_idx), '')
                if orig_text:
                    for raw_line in orig_text.split('\n')[:15]:
                        if not raw_line:
                            lines.append(f"      {DIM_YELLOW_BG}{DIM}{RESET}")
                            keys.append(None)
                            continue
                        for chunk_start in range(0, len(raw_line), wrap_width):
                            lines.append(f"      {DIM_YELLOW_BG}{DIM}{raw_line[chunk_start:chunk_start + wrap_width]}{RESET}")
                            keys.append(None)
                continue
            else:
                blocks = msg.get('blocks', [])
                type_label = f"{len(blocks)} blocks" if len(blocks) > 1 else msg_type
                lines.append(f"    {DIM}[{msg_idx:3d}] {role:<4}  {type_label:<20}{RESET}")
            keys.append(None)
            blocks = msg.get('blocks', [])
            if blocks:
                for bidx, blk in enumerate(blocks):
                    btype = blk.get('type', 'text')
                    bchars = blk.get('chars', 0)
                    bcc = ' [CC]' if blk.get('has_cc') else ''
                    lines.append(f"      {DIM}[{bidx}] {btype:<12} {bchars:>6,}c{bcc}{RESET}")
                    keys.append(None)
                    full_text = blk.get('full_text', blk.get('preview', ''))
                    if full_text:
                        for raw_line in full_text.split('\n'):
                            if not raw_line:
                                lines.append(f"        {DIM}{RESET}")
                                keys.append(None)
                                continue
                            for chunk_start in range(0, len(raw_line), wrap_width):
                                lines.append(f"        {DIM}{raw_line[chunk_start:chunk_start + wrap_width]}{RESET}")
                                keys.append(None)
            else:
                tail = msg.get('content_tail', '')
                if tail:
                    for raw_line in tail.split('\n'):
                        if not raw_line:
                            lines.append(f"      {DIM}{RESET}")
                            keys.append(None)
                            continue
                        for chunk_start in range(0, len(raw_line), wrap_width):
                            lines.append(f"      {DIM}{raw_line[chunk_start:chunk_start + wrap_width]}{RESET}")
                            keys.append(None)
        removed_from_prev = prev_messages[len(messages):]
        for m_offset, msg in enumerate(removed_from_prev):
            m_idx = len(messages) + m_offset
            role = msg.get('role', '?')[:4]
            m_type = msg.get('type', 'text')
            m_chars = msg.get('chars', 0)
            lines.append(f"    {RED}removed:{RESET} {DIM}[{m_idx:3d}] {role:<4}  {m_type:<20} {m_chars:,}c{RESET}")
            keys.append(None)
    return lines, keys
