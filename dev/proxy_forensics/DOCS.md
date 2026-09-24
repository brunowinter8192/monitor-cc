# dev/proxy_forensics/

## Role
Forensic audit for one proxy logging invariant: every message index recorded as stripped must also carry a non-empty removal record. Touch when auditing a real proxy JSONL for that invariant or adding another invariant check over the same log shape.

## Public Interface
No `__init__.py`. Entry point: `python dev/proxy_forensics/strip_tracking_audit.py <jsonl_path>`.

## Flow
Reads a proxy JSONL line by line, checks stripped indices against removal records and prints one violation line per missing index plus a summary count.

## Modules

### strip_tracking_audit.py (53 LOC)

**Purpose:** Verifies that each stripped message index has a non-empty removal record and reports violations.
**Reads:** the proxy JSONL file given as first argument.
**Writes:** stdout; exit 0 for no violations, exit 1 for violations or an unreadable file.
**Called by:** none; run manually.
**Calls out:** none; stdlib only.

---

## State
None.
