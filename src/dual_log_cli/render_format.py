# INFRASTRUCTURE
from .reader import local_datetime

# FUNCTIONS


# Char count as a short human string
def fmt_chars(count: int) -> str:
    if count >= 1_000_000:
        return f"{count / 1_000_000:.1f}M"
    if count >= 1_000:
        return f"{count / 1_000:.1f}k"
    return str(count)


# "YYYY-MM-DD HH:MM:SS" LOCAL wall clock for a UTC ISO timestamp (2026-09-04: was a raw
# `timestamp[:19]` UTC substring — see `reader.local_datetime`, the one shared conversion point).
# "?" for an empty/unparseable timestamp, same width (19 chars) either way.
def fmt_timestamp(timestamp: str) -> str:
    dt = local_datetime(timestamp)
    return dt.strftime("%Y-%m-%d %H:%M:%S") if dt else "?"


# LOCAL HH:MM:SS of the request that first carried a msg; "?" when it has no reliable time
# (2026-09-04: was a raw `timestamp[11:19]` UTC substring — see `reader.local_datetime`).
def _clock(timestamp) -> str:
    dt = local_datetime(timestamp)
    return dt.strftime("%H:%M:%S") if dt else "?"


# LOCAL calendar day for the window header — the anchor's own day, else the session's start day
# (2026-09-04: was a raw `stamp[:10]` UTC substring — a request near local midnight could land on
# the wrong day otherwise; see `reader.local_datetime`).
def _window_date(data: dict, anchor: int) -> str:
    stamp = data.get("turn_times", {}).get(anchor) or data["session"].get("start", "")
    dt = local_datetime(stamp)
    return dt.strftime("%Y-%m-%d") if dt else "?"


# Compact human duration: "58s" under a minute, "41m24s" under an hour, "1h05m30s" at or past one
# — grep-friendly (a letter suffix per unit, no spaces) and fixed-width only where cheap (seconds
# always 2 digits once a coarser unit is present; the leading unit is not padded, since padding it
# would widen every row for a session whose turns never reach double-digit hours). "?" for an
# unresolved duration — same width class as a real value once printed via `{:>N}`.
#
# Originally built for the `turns` command's transcript-joined durations (removed 2026-09-10, see
# process-docs/dual_log_cli/) — kept for `reqs`' own turn separator (`_session_entries_and_separators`),
# which reuses it for the send-time-only turn span, the ONE thing that survived both the 2026-09-10
# pivot and the 2026-09-16 M6 redesign (the per-request elapsed tail this once also fed did not).
def _fmt_duration(seconds) -> str:
    if seconds is None:
        return "?"
    total = int(round(seconds))
    hours, remainder = divmod(total, 3600)
    minutes, secs = divmod(remainder, 60)
    if hours:
        return f"{hours}h{minutes:02d}m{secs:02d}s"
    if minutes:
        return f"{minutes}m{secs:02d}s"
    return f"{secs}s"


# Trailing note about unreadable sessions; empty when nothing was skipped
def _skipped_lines(skipped: int) -> list:
    if not skipped:
        return []
    return ["", f"({skipped} session{'s' if skipped != 1 else ''} skipped — timeline could not be loaded)"]
