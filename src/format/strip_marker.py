# INFRASTRUCTURE
from ..constants import DIM_YELLOW_BG, SOFT_RESET

# FUNCTIONS

# Wrap all occurrences of each chunk in text with DIM_YELLOW_BG; restore outer_bg after each
def highlight_stripped(text: str, stripped_chunks: list, outer_bg: str = '') -> str:
    if not stripped_chunks or not text:
        return text
    result = text
    for chunk in stripped_chunks:
        if not chunk:
            continue
        parts = result.split(chunk)
        if len(parts) == 1:
            continue  # chunk not found in text — graceful skip (e.g. truncation at 50k boundary)
        # Wrap each line individually: downstream renderers split on \n and apply per-line zebra BG,
        # so a single DIM_YELLOW_BG…SOFT_RESET around the whole chunk would only colour line 1.
        # outer_bg is appended once after the final highlighted line to restore the caller's row BG.
        highlighted_lines = [f"{DIM_YELLOW_BG}{raw_line}{SOFT_RESET}" for raw_line in chunk.split('\n')]
        replacement = '\n'.join(highlighted_lines) + outer_bg
        result = replacement.join(parts)
    return result


# Extract pre-strip text and removed chunks for msg_idx from a proxy entry
def get_stripped_data(entry: dict, msg_idx: int) -> tuple:
    stripped_indices = entry.get('stripped_msg_indices', [])
    if msg_idx not in stripped_indices:
        return None, []
    pre_strip = entry.get('stripped_msg_originals', {}).get(str(msg_idx))
    removed = entry.get('stripped_msg_removed', {}).get(str(msg_idx), [])
    return pre_strip, removed


# Build tool_use_id → (pre_strip_text, removed_chunks) lookup from raw proxy events
def build_tool_result_strip_lookup(events: list) -> dict:
    lookup = {}
    for event in events:
        stripped_indices = event.get('stripped_msg_indices', [])
        if not stripped_indices:
            continue
        stripped_originals = event.get('stripped_msg_originals', {})
        stripped_removed = event.get('stripped_msg_removed', {})
        messages = event.get('raw_payload', {}).get('messages', [])
        for idx in stripped_indices:
            if idx >= len(messages):
                continue
            msg = messages[idx]
            content = msg.get('content', [])
            if not isinstance(content, list):
                continue
            pre_strip = stripped_originals.get(str(idx))
            chunks = stripped_removed.get(str(idx), [])
            for block in content:
                if not isinstance(block, dict) or block.get('type') != 'tool_result':
                    continue
                tid = block.get('tool_use_id')
                if tid and tid not in lookup:
                    lookup[tid] = (pre_strip, chunks)
    return lookup


# Build tool_use_id → (pre_strip_text, removed_chunks) lookup from parsed proxy entries (main-pane use)
def build_tool_id_strip_lookup(entries: list) -> dict:
    lookup = {}
    for entry in entries:
        stripped_indices = entry.get('stripped_msg_indices', [])
        if not stripped_indices:
            continue
        messages = entry.get('messages', [])
        for msg_idx in stripped_indices:
            if msg_idx >= len(messages):
                continue
            pre_strip, chunks = get_stripped_data(entry, msg_idx)
            if pre_strip is None:
                continue
            msg = messages[msg_idx]
            for blk in msg.get('blocks', []):
                if blk.get('type') != 'tool_result':
                    continue
                tid = blk.get('tool_use_id')
                if tid and tid not in lookup:
                    lookup[tid] = (pre_strip, chunks)
    return lookup
