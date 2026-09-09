"""
Regression suite for the UTC-to-LOCAL timestamp conversion this area introduced 2026-09-04
(src/dual_log_cli/reader.py's `local_datetime`, and every renderer/filter built on it:
render.py's `fmt_timestamp`/`_clock`/`_window_date`, discovery.py's `filter_sessions` day
window, usage.py's `_epoch_from_iso`).

Covers: a Z timestamp renders as this machine's LOCAL wall clock (independently cross-checked
against a fresh `datetime.fromisoformat(...).astimezone()` computation, not just re-calling
`local_datetime` on itself); a day-boundary-crossing case built DYNAMICALLY from the machine's own
current UTC offset (never hardcoded, since the crossing direction depends on which side of UTC
this machine is on) proves `filter_sessions` lists a session under its LOCAL day, not the UTC day
its timestamp string happens to carry; `render._clock`/`fmt_timestamp`/`_window_date` all agree
with `local_datetime`; and `usage._epoch_from_iso` returns the TRUE UTC epoch of a Z timestamp,
regardless of the machine's own timezone (an epoch is timezone-independent by definition, unlike a
wall-clock string).

No dual-log directory or MONITOR_CC_ROOT required — every case is built from a literal ISO string
plus this machine's own timezone.

Run (from project root):
    ./venv/bin/python dev/dual_log_cli/tests/test_local_time.py

Exit 0 = all checks pass. Exit 1 = at least one failure (printed by name).
"""

# INFRASTRUCTURE

import sys
from datetime import datetime, timezone
from pathlib import Path

_HERE = Path(__file__).parent.resolve()
sys.path.insert(0, str(_HERE.parents[2]))

from src.dual_log_cli.discovery import filter_sessions
from src.dual_log_cli.reader import local_datetime
from src.dual_log_cli.render_format import _clock, _window_date, fmt_timestamp
from src.dual_log_cli.usage import _epoch_from_iso

PASS_LIST = []
FAIL_LIST = []


# FUNCTIONS

def check(name: str, condition: bool, detail: str = "") -> None:
    if condition:
        PASS_LIST.append(name)
    else:
        FAIL_LIST.append(name)
        print(f"  FAIL  {name}" + (f": {detail}" if detail else ""))


# A Z timestamp renders as this machine's LOCAL wall clock — cross-checked against a FRESH
# datetime computation (not just re-calling local_datetime on itself, which would only prove
# self-consistency, not correctness).
def test_local_datetime_matches_independent_conversion() -> None:
    timestamp = "2026-09-04T18:16:02.582Z"
    got = local_datetime(timestamp)
    expected = datetime(2026, 9, 4, 18, 16, 2, 582000, tzinfo=timezone.utc).astimezone()
    check("local_datetime matches an independently computed UTC->local conversion",
          got == expected, (got, expected))
    offset = datetime.now().astimezone().utcoffset()
    if offset.total_seconds() != 0:
        check("the converted clock differs from the raw UTC digits sliced out of the string",
              got.strftime("%H:%M:%S") != timestamp[11:19], got)


# render._clock / fmt_timestamp / _window_date all agree with local_datetime — the SAME
# conversion, not three independent (and possibly diverging) implementations.
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


# A day-boundary-crossing case built from THIS machine's own current UTC offset — never a
# hardcoded "23:30Z", since whether that crosses a local day boundary depends on which side of
# UTC the test machine is on. Anchored at local midnight +/- 30 minutes so the UTC calendar day
# and the LOCAL calendar day provably differ whenever the offset is nonzero (the common case; a
# UTC-zero machine makes this check vacuously trivial, not wrong).
def test_late_timestamp_lands_on_correct_local_day() -> None:
    offset = datetime.now().astimezone().utcoffset()
    local_now = datetime.now().astimezone()
    if offset.total_seconds() >= 0:
        # East of UTC: local time just after midnight is still the PREVIOUS day in UTC.
        local_target = local_now.replace(hour=0, minute=30, second=0, microsecond=0)
    else:
        # West of UTC: local time just before midnight is already the NEXT day in UTC.
        local_target = local_now.replace(hour=23, minute=30, second=0, microsecond=0)
    utc_target = local_target.astimezone(timezone.utc)
    local_day = local_target.strftime("%Y-%m-%d")
    utc_day = utc_target.strftime("%Y-%m-%d")
    timestamp = utc_target.strftime("%Y-%m-%dT%H:%M:%S.000Z")

    check("setup: the UTC day and the LOCAL day actually differ here (nonzero offset), or the "
          "machine itself is at UTC (vacuous but not wrong)",
          utc_day != local_day or offset.total_seconds() == 0, (utc_day, local_day, offset))

    session = {"stem": "s", "context": "opus/x", "start": timestamp}
    kept_local_day = filter_sessions([session], since=local_day, until=local_day)
    check("session with a late/early UTC start is listed under its LOCAL day",
          kept_local_day == [session], (kept_local_day, local_day, timestamp))
    if utc_day != local_day:
        kept_utc_day = filter_sessions([session], since=utc_day, until=utc_day)
        check("session is NOT listed under the (different) UTC day",
              kept_utc_day == [], (kept_utc_day, utc_day))


# usage._epoch_from_iso returns the TRUE UTC epoch of a Z timestamp — an epoch is timezone-
# independent by definition, so this must hold on ANY machine, unlike a rendered wall-clock string.
def test_epoch_from_iso_matches_true_utc_epoch() -> None:
    timestamp = "2026-09-04T20:16:02.582Z"
    true_epoch = datetime(2026, 9, 4, 20, 16, 2, 582000, tzinfo=timezone.utc).timestamp()
    check("_epoch_from_iso matches the true UTC epoch (plain Z shape)",
          _epoch_from_iso(timestamp) == true_epoch, (_epoch_from_iso(timestamp), true_epoch))
    # The rarer "...+00:00Z" shape (offset with "Z" appended) must resolve to the same epoch.
    offset_shape = "2026-09-04T20:16:02.582+00:00Z"
    check("_epoch_from_iso matches the true UTC epoch (+00:00Z shape)",
          _epoch_from_iso(offset_shape) == true_epoch, (_epoch_from_iso(offset_shape), true_epoch))
    check("_epoch_from_iso returns None for empty/unparseable input",
          _epoch_from_iso("") is None and _epoch_from_iso("garbage") is None)


# ORCHESTRATOR

def test_local_time_workflow() -> None:
    test_local_datetime_matches_independent_conversion()
    test_render_helpers_use_local_time()
    test_late_timestamp_lands_on_correct_local_day()
    test_epoch_from_iso_matches_true_utc_epoch()

    total = len(PASS_LIST) + len(FAIL_LIST)
    print(f"{len(PASS_LIST)}/{total} checks passed")
    if FAIL_LIST:
        print(f"\nFAILED: {FAIL_LIST}")
        sys.exit(1)
    print("ALL PASS")


if __name__ == "__main__":
    test_local_time_workflow()
