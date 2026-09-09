# INFRASTRUCTURE
from .reader import local_datetime

# FUNCTIONS


def fmt_chars(count: int) -> str:
    if count >= 1_000_000:
        return f"{count / 1_000_000:.1f}M"
    if count >= 1_000:
        return f"{count / 1_000:.1f}k"
    return str(count)


def fmt_timestamp(timestamp: str) -> str:
    dt = local_datetime(timestamp)
    return dt.strftime("%Y-%m-%d %H:%M:%S") if dt else "?"


def _clock(timestamp) -> str:
    dt = local_datetime(timestamp)
    return dt.strftime("%H:%M:%S") if dt else "?"


def _window_date(data: dict, anchor: int) -> str:
    stamp = data.get("turn_times", {}).get(anchor) or data["session"].get("start", "")
    dt = local_datetime(stamp)
    return dt.strftime("%Y-%m-%d") if dt else "?"


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


def _skipped_lines(skipped: int) -> list:
    if not skipped:
        return []
    return ["", f"({skipped} session{'s' if skipped != 1 else ''} skipped — timeline could not be loaded)"]
