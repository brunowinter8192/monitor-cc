# INFRASTRUCTURE
from ..colors import SOFT_RESET, DIM

# Split text on '\n', expandtabs(8), emit one f"{indent}{bg}{DIM}{line}{SOFT_RESET}" per line
# with a None key. An empty line (after expandtabs) renders with nothing between DIM and
# SOFT_RESET — `raw_line or ''` and the bare `{bg}{DIM}{SOFT_RESET}` spelling used at various
# former call sites produce the identical string; this is the single source for both.
# transform, when given, is applied to raw_line before embedding (e.g. suspect-tag highlight) —
# safe to apply unconditionally since a regex .sub on '' is a no-op.
def _emit_text_lines(text: str, indent: str, bg: str = '', transform=None) -> tuple:
    lines = []
    keys = []
    for raw_line in text.split('\n'):
        raw_line = raw_line.expandtabs(8)
        content = transform(raw_line) if transform else raw_line
        lines.append(f"{indent}{bg}{DIM}{content or ''}{SOFT_RESET}")
        keys.append(None)
    return lines, keys

# Emit _emit_text_lines for each span_text in a flat list (stripped/injected span chunks), same bg
# for every chunk — the "for span_text in (s_desc or []): for raw_line in span_text.split(...)"
# block repeated for every stacked yellow/green span list.
def _emit_span_lines(span_texts: list, indent: str, bg: str) -> tuple:
    lines = []
    keys = []
    for span_text in span_texts:
        t_lines, t_keys = _emit_text_lines(span_text, indent, bg)
        lines.extend(t_lines)
        keys.extend(t_keys)
    return lines, keys

# Emit _emit_text_lines for each (tag, text) pair of a new-format inline span list — tag=="injected"
# gets the given injected_bg, every other tag renders with no bg (equal/unchanged text).
def _emit_inline_spans(pairs: list, indent: str, injected_bg: str, transform=None) -> tuple:
    lines = []
    keys = []
    for tag, span_text in pairs:
        bg = injected_bg if tag == "injected" else ""
        t_lines, t_keys = _emit_text_lines(span_text, indent, bg, transform)
        lines.extend(t_lines)
        keys.extend(t_keys)
    return lines, keys
