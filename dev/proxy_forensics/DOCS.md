# dev/proxy_forensics/

## Role
Forensic audit for one proxy logging invariant: every message index the proxy records as
"stripped" must also carry a non-empty removal record. Touch this directory when auditing a real
proxy JSONL for that invariant, or when adding a new invariant check over the same log shape.

## Public Interface
No `__init__.py` in this directory. Entry point is direct invocation: `python dev/proxy_forensics/strip_tracking_audit.py <jsonl_path>`.

## Flow
Reads a proxy JSONL file line by line, checks each entry carrying `stripped_msg_indices` against `stripped_msg_removed`, and prints one violation line per missing index plus a summary count.

## Modules

### strip_tracking_audit.py (53 LOC)

**Purpose:** For every log entry carrying a non-empty `stripped_msg_indices`, verifies each index
has a corresponding non-empty entry in `stripped_msg_removed`; prints one violation line per
missing index plus a summary count.
**Reads:** the proxy JSONL file given as `sys.argv[1]`.
**Writes:** stdout (violation lines, summary count); exit 0 = no violations, exit 1 = violations
found or the file could not be opened.
**Called by:** none — run manually (`python dev/proxy_forensics/strip_tracking_audit.py <jsonl_path>`).
**Calls out:** none (stdlib only).

---

## State
No persistent state. All data is local to the `audit()` call.
