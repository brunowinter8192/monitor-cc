# INFRASTRUCTURE
from .render_format import _skipped_lines

# FUNCTIONS


def render_search(term: str, case_sensitive: bool, results: list, skipped: int = 0) -> str:
    mode = "case-sensitive" if case_sensitive else "case-insensitive"
    lines = [f'term      "{term}"  ({mode})', ""]
    if not results:
        lines.append("no match")
        return "\n".join(lines + _skipped_lines(skipped)) + "\n"
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
