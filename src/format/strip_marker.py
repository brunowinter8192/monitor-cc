# INFRASTRUCTURE
from ..colors import DIM_YELLOW_BG, SOFT_RESET

# FUNCTIONS

def highlight_stripped(text: str, stripped_chunks: list, outer_bg: str = '') -> str:
    if not stripped_chunks or not text:
        return text
    result = text
    for chunk in stripped_chunks:
        if not chunk:
            continue
        parts = result.split(chunk)
        if len(parts) == 1:
            continue
        highlighted_lines = [f"{DIM_YELLOW_BG}{raw_line}{SOFT_RESET}" for raw_line in chunk.split('\n')]
        replacement = '\n'.join(highlighted_lines) + outer_bg
        result = replacement.join(parts)
    return result

