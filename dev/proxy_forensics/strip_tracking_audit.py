"""
Audit proxy JSONL for stripped_msg_removed invariant violations.

Invariant: for every idx in stripped_msg_indices, stripped_msg_removed[str(idx)] must
exist and be a non-empty list.

Usage:
    python dev/proxy_forensics/strip_tracking_audit.py <jsonl_path>

Exit codes:
    0 — no violations
    1 — violations found (or file unreadable)
"""

# INFRASTRUCTURE
import json
import sys

# FUNCTIONS

# Check one log entry; return list of violation strings (empty = OK)
def _check_entry(line_no, entry):
    indices = entry.get("stripped_msg_indices") or []
    if not indices:
        return []
    removed = entry.get("stripped_msg_removed") or {}
    mods_list = entry.get("modifications") or []
    ts = entry.get("timestamp", "?")
    violations = []
    for idx in indices:
        key = str(idx)
        if key not in removed or not removed[key]:
            violations.append(f"LINE {line_no} TS {ts}\n  idx={idx} mods={mods_list} → missing from stripped_msg_removed")
    return violations


# Run audit against a proxy JSONL file; print report and return violation count
def audit(path: str) -> int:
    all_violations = []
    entries_checked = 0
    try:
        with open(path) as fh:
            for line_no, raw in enumerate(fh, 1):
                raw = raw.strip()
                if not raw:
                    continue
                try:
                    entry = json.loads(raw)
                except json.JSONDecodeError:
                    continue
                if not entry.get("stripped_msg_indices"):
                    continue
                entries_checked += 1
                all_violations.extend(_check_entry(line_no, entry))
    except OSError as exc:
        print(f"ERROR: cannot open {path}: {exc}", file=sys.stderr)
        return 1

    for v in all_violations:
        print(v)
    print(f"\n{len(all_violations)} violation(s) across {entries_checked} entries checked")
    return 1 if all_violations else 0


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print(f"Usage: {sys.argv[0]} <jsonl_path>", file=sys.stderr)
        sys.exit(1)
    sys.exit(audit(sys.argv[1]))
