# INFRASTRUCTURE
from .render_format import _skipped_lines

# FUNCTIONS


# Search result: header plus one line per matching block
# Search results across one or more sessions. results is [(session, hits), …] in listing order,
# already filtered to sessions that HAVE hits. The term line is printed once overall; each session
# then contributes its own "session <stem>" line plus its hit lines. skipped counts sessions whose
# timeline could not be loaded — reported only when non-zero, so a clean run stays clean.
#
# A hit line is `#msg role label  chars` — msg index, role, block label, and the block's original
# chars (`f"{n:,}c"`, the same digit-grouped spelling `msgs`' block sub-lines use for the same
# value) — an eyeball filter for deciding which msg is worth `expand`ing, not a text preview: a
# genuine small artifact and a large prose hit differ in chars at a glance, no snippet needed.
def render_search(term: str, case_sensitive: bool, results: list, skipped: int = 0) -> str:
    mode = "case-sensitive" if case_sensitive else "case-insensitive"
    lines = [f'term      "{term}"  ({mode})', ""]
    if not results:
        lines.append("no match")
        return "\n".join(lines + _skipped_lines(skipped)) + "\n"
    # one width across ALL sessions, so hit lines stay aligned when several sessions are shown
    label_width = max(len(hit["label"]) for _session, hits in results for hit in hits)
    chars_width = max(len(f"{hit['chars']:,}c") for _session, hits in results for hit in hits)
    for session, hits in results:
        lines.append(f"session   {session['stem']}")
        for hit in hits:
            chars = f"{hit['chars']:,}c"
            lines.append(
                f"#{hit['turn']:<4} {hit['role']:9} {hit['label']:{label_width}}  "
                f"{chars:>{chars_width}}"
            )
        lines.append("")
    return "\n".join(lines[:-1] + _skipped_lines(skipped)) + "\n"
