# INFRASTRUCTURE
import sys

_reported: set = set()

# FUNCTIONS


def report_skip(source: str, target: str, reason: str) -> None:
    key = (source, target, reason)
    if key in _reported:
        return
    _reported.add(key)
    print(f"{source}: {target}: {reason}", file=sys.stderr)
