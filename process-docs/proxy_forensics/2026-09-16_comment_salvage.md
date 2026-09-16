## Salvage from dev/proxy_forensics/strip_tracking_audit.py

```
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
```

```
# Check one log entry; return list of violation strings (empty = OK)
```

```
# Run audit against a proxy JSONL file; print report and return violation count
```

## Salvage from dev/proxy_forensics/DOCS.md

Nothing cut — the pre-existing `## Role` and `## Modules` sections already fit the required format. No `## Gotchas` or other section existed to relocate.

## Notes for successor

- 1 file, 2 comments + 1 docstring — matches the measured state exactly. Both comments are standalone one-liners directly preceding a `def`.
- No load-bearing docstring: grepped `__doc__` — zero hits, no `argparse` in this file (it parses `sys.argv` directly). Docstring deleted outright.
- **Run directly** (safe): pure read-only audit — reads one JSONL path given as `sys.argv[1]`, prints violation lines and a summary count, exits 0/1. Tested with a synthetic 3-line fixture at `/tmp/c4_5_verify/pf_fixture.jsonl` (not committed) covering all three code paths: an index with a real violation, an entry with no `stripped_msg_indices` (skipped), and an index whose `stripped_msg_removed` entry is an empty list (also a violation).
- Verification: ran before and after the comment/docstring strip against the identical fixture file — stdout and exit code identical.
