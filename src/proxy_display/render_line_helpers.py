# INFRASTRUCTURE
from ..colors import SOFT_RESET, DIM

def _emit_text_lines(text: str, indent: str, bg: str = '', transform=None) -> tuple:
    lines = []
    keys = []
    for raw_line in text.split('\n'):
        raw_line = raw_line.expandtabs(8)
        content = transform(raw_line) if transform else raw_line
        lines.append(f"{indent}{bg}{DIM}{content or ''}{SOFT_RESET}")
        keys.append(None)
    return lines, keys

def _emit_span_lines(span_texts: list, indent: str, bg: str) -> tuple:
    lines = []
    keys = []
    for span_text in span_texts:
        t_lines, t_keys = _emit_text_lines(span_text, indent, bg)
        lines.extend(t_lines)
        keys.extend(t_keys)
    return lines, keys

def _emit_inline_spans(pairs: list, indent: str, injected_bg: str, transform=None) -> tuple:
    lines = []
    keys = []
    for tag, span_text in pairs:
        bg = injected_bg if tag == "injected" else ""
        t_lines, t_keys = _emit_text_lines(span_text, indent, bg, transform)
        lines.extend(t_lines)
        keys.extend(t_keys)
    return lines, keys
