# INFRASTRUCTURE
from .render_format import fmt_timestamp

# FUNCTIONS


# One line per session, newest first. PROJECT (2026-09-10, replaces CONTEXT) is the real project
# directory `discovery.project_for_stem` resolved — a path can run much longer than the old
# `worker/<label>/<name>` rendering ever did, so the column WIDENS to fit the longest one rather
# than truncating (right-trimming a path is not acceptable — a wide column is). SESSION prints the
# stem's DISPLAY form (`discovery.display_stem`, sid8 stripped for a worker) — the on-disk stem is
# unchanged, this is presentation only, and `resolve_stem` already accepts a substring of either
# form, so a name copied from this column resolves.
def render_sessions(sessions: list) -> str:
    if not sessions:
        return "no sessions found\n"
    project_width = max(len(s["project"]) for s in sessions)
    # SESSION is the last column — left unpadded so no line carries trailing whitespace
    lines = [f"{'START':19}  {'PROJECT':{project_width}}  SESSION"]
    for session in sessions:
        lines.append(
            f"{fmt_timestamp(session['start']):19}  "
            f"{session['project']:{project_width}}  "
            f"{session['display_stem']}"
        )
    lines.append("")
    lines.append(f"{len(sessions)} sessions")
    return "\n".join(lines) + "\n"
