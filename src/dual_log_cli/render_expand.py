# INFRASTRUCTURE
from .render_format import _clock, _window_date, fmt_chars

# FUNCTIONS


# expand: the complete content of each selected msg in the window, plus the proxy's own
# transformations of it when an overlay is supplied. `overlay` is {(msg, blk): {stripped, injected,
# req}} from overlay.py; an empty/absent one renders exactly the pre-overlay output, which is what
# keeps an untouched msg byte-identical.
def render_expand_full(data: dict, anchor: int, start: int, end: int,
                       only: str, dumped: list, overlay: dict = None) -> str:
    msgs = data["turns"]
    times = data.get("turn_times", {})
    scope = (f"msgs {start}-{end} of 0-{len(msgs) - 1}, anchor #{anchor}, "
             f"{_window_date(data, anchor)}")
    lines = [
        f"session   {data['session']['stem']}",
        f"project   {data['session']['project']}",
        f"window    {scope}" + (f", only {only}" if only else ""),
        "",
    ]
    if not dumped:
        lines.append(f"no msg in the window matches --only {only}" if only else "window is empty")
        return "\n".join(lines) + "\n"
    for msg, blocks in dumped:
        marker = "▶" if msg["index"] == anchor else " "
        lines.append(
            f"{marker} ═══ msg #{msg['index']} {_clock(times.get(msg['index']))} "
            f"{msg['role']} {fmt_chars(msg['chars'])} chars, {len(blocks)} block(s) ═══"
        )
        for position, (label, chars, text) in enumerate(blocks):
            lines.append(f"── block {position}  {label}  {fmt_chars(chars)} chars ──")
            lines.append(text)
            lines.extend(_overlay_lines((overlay or {}).get((msg["index"], position))))
        lines.append("")
    return "\n".join(lines) + "\n"


# The proxy's transformations of one block: what it removed from the text above, and what it put
# there instead. Labels carry the meaning — this output is read by agents through pipes, so there
# is no colour anywhere in it. Empty for a block the proxy never touched.
def _overlay_lines(slot) -> list:
    if not slot:
        return []
    req = slot.get("req")
    tag = f"REQ {req}" if req else "REQ ?"
    lines = []
    for text in slot.get("stripped") or []:
        lines.append(f"── stripped by {tag} ──")
        lines.append(text)
    for text in slot.get("injected") or []:
        lines.append(f"── injected by {tag} ──")
        lines.append(text)
    return lines
