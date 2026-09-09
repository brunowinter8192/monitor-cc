# INFRASTRUCTURE
from .render_format import fmt_timestamp

# FUNCTIONS


def render_sessions(sessions: list) -> str:
    if not sessions:
        return "no sessions found\n"
    project_width = max(len(s["project"]) for s in sessions)
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
