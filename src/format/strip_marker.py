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

