# INFRASTRUCTURE
import os
import sys
import time
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path

_HERE = Path(__file__).parent.resolve()

sys.path.insert(0, str(_HERE.parents[2]))
from src.dual_log_cli.discovery import filter_sessions
from src.dual_log_cli.reader import local_datetime
from src.dual_log_cli.render_format import _clock, _window_date, fmt_timestamp
from src.dual_log_cli.usage import _epoch_from_iso
from dev.refactoring.strand_runner import strand_workflow

_ZONE_CLOCKS = [("Asia/Tokyo", "2026-09-05 03:16:02"), ("America/Los_Angeles", "2026-09-04 11:16:02")]
_DAY_BOUNDARY_CASES = [
    ("Asia/Tokyo", "2026-09-04T15:30:00.000Z", "2026-09-05", "2026-09-04"),
    ("America/Los_Angeles", "2026-09-05T06:30:00.000Z", "2026-09-04", "2026-09-05"),
]

_STRANDS = [
    'test_local_datetime_matches_independent_conversion',
    'test_render_helpers_use_local_time',
    'test_late_timestamp_lands_on_correct_local_day',
    'test_epoch_from_iso_matches_true_utc_epoch',
]

# ORCHESTRATOR

def test_local_time_workflow() -> int:
    return strand_workflow(globals(), __file__, _STRANDS, title='test_local_time')

# FUNCTIONS

def check(name, condition, detail=""):
    if not condition:
        print(f"  FAIL  {name}" + (f": {detail}" if detail != "" else ""))
        raise AssertionError(name)
    print(f"  PASS  {name}")
    return True

@contextmanager
def _fixed_zone(zone: str):
    previous = os.environ.get("TZ")
    os.environ["TZ"] = zone
    time.tzset()
    try:
        yield
    finally:
        if previous is None:
            del os.environ["TZ"]
        else:
            os.environ["TZ"] = previous
        time.tzset()

def test_local_datetime_matches_independent_conversion() -> None:
    for zone, expected_clock in _ZONE_CLOCKS:
        with _fixed_zone(zone):
            timestamp = "2026-09-04T18:16:02.582Z"
            got = local_datetime(timestamp)
            expected = datetime(2026, 9, 4, 18, 16, 2, 582000, tzinfo=timezone.utc).astimezone()
            check(f"{zone}: local_datetime matches an independently computed UTC->local conversion",
                  got == expected, (got, expected))
            check(f"{zone}: the converted clock is the known local time, not the raw UTC digits",
                  got.strftime("%Y-%m-%d %H:%M:%S") == expected_clock, got)

def test_render_helpers_use_local_time() -> None:
    timestamp = "2026-09-04T18:16:02Z"
    dt = local_datetime(timestamp)
    check("_clock renders the local HH:MM:SS", _clock(timestamp) == dt.strftime("%H:%M:%S"), _clock(timestamp))
    check("fmt_timestamp renders the local YYYY-MM-DD HH:MM:SS",
          fmt_timestamp(timestamp) == dt.strftime("%Y-%m-%d %H:%M:%S"), fmt_timestamp(timestamp))
    check("_clock/fmt_timestamp show '?' for an empty timestamp", _clock("") == "?" and fmt_timestamp("") == "?")
    data = {"turn_times": {}, "session": {"start": timestamp}}
    check("_window_date falls back to the session start day, in LOCAL time",
          _window_date(data, 0) == dt.strftime("%Y-%m-%d"), _window_date(data, 0))

def test_late_timestamp_lands_on_correct_local_day() -> None:
    for zone, utc_timestamp, local_day, utc_day in _DAY_BOUNDARY_CASES:
        with _fixed_zone(zone):
            session = {"stem": "s", "context": "opus/x", "start": utc_timestamp}
            kept_local_day = filter_sessions([session], since=local_day, until=local_day)
            check(f"{zone}: session with a start on a different UTC day is listed under its LOCAL day",
                  kept_local_day == [session], (kept_local_day, local_day, utc_timestamp))
            kept_utc_day = filter_sessions([session], since=utc_day, until=utc_day)
            check(f"{zone}: session is NOT listed under the (different) UTC day",
                  kept_utc_day == [], (kept_utc_day, utc_day))

def test_epoch_from_iso_matches_true_utc_epoch() -> None:
    timestamp = "2026-09-04T20:16:02.582Z"
    true_epoch = datetime(2026, 9, 4, 20, 16, 2, 582000, tzinfo=timezone.utc).timestamp()
    check("_epoch_from_iso matches the true UTC epoch (plain Z shape)",
          _epoch_from_iso(timestamp) == true_epoch, (_epoch_from_iso(timestamp), true_epoch))
    offset_shape = "2026-09-04T20:16:02.582+00:00Z"
    check("_epoch_from_iso matches the true UTC epoch (+00:00Z shape)",
          _epoch_from_iso(offset_shape) == true_epoch, (_epoch_from_iso(offset_shape), true_epoch))
    check("_epoch_from_iso returns None for empty/unparseable input",
          _epoch_from_iso("") is None and _epoch_from_iso("garbage") is None)

if __name__ == '__main__':
    sys.exit(test_local_time_workflow())
