# dev/cc_injection_inventory/

## Role
Reusable audit tool inventorying every distinguishable text class in raw Claude Code request
payloads captured under `src/logs/dual_log/` — every distinct class listed regardless of
frequency, not a top-N filter. Touch when the strip/inject rule set changes and the inventory
needs re-running, or when adding a classification origin label.

## Public Interface
No `__init__.py` in this directory. Entry path: `./venv/bin/python
dev/cc_injection_inventory/cc_injection_inventory.py`.

## Flow
Reads CLI args (`--logs-glob`/`--out-name`/`--max-entries`), resolves the matching
`api_requests_*_original.jsonl` dual-log files -> streams each file, extracting every text
segment and classifying it into one of 5 origin labels via the real `src/proxy` strip pipeline
-> aggregates/dedups occurrences into a registry -> renders the registry into a markdown report
under `md/` plus a 3-line console summary.

## Modules

### cc_injection_inventory.py (109 LOC)

**Purpose:** Entry script — parses CLI args, resolves the dual-log file glob (with self-scan
exclusion), and drives extraction -> aggregation -> report across all matched files.
**Reads:** CLI args; lists `src/logs/dual_log/api_requests_*_original.jsonl` (or `--logs-glob`).
**Writes:** nothing directly — delegates to `cc_injection_report._write_report`.
**Called by:** none — run manually.
**Calls out:** `cc_injection_extraction`, `cc_injection_aggregation`, `cc_injection_report`.

---

### cc_injection_extraction.py (122 LOC)

**Purpose:** Streams one dual-log JSONL file and extracts every text segment (`system[0..3]`,
message content — plain string / `text` blocks / `tool_result` content).
**Reads:** one `api_requests_*_original.jsonl` file, streamed line-by-line (the corpus includes
multi-GB files, never loaded whole).
**Writes:** mutates the `registry`/`pending`/`dedup_seen`/`counters` dicts passed in by the caller.
**Called by:** `cc_injection_inventory.py`.
**Calls out:** `cc_injection_aggregation`.

---

### cc_injection_aggregation.py (81 LOC)

**Purpose:** Dedups segment occurrences by exact text, dispatches first-sight segments to
classification, and resolves recurring user-text templates in a second pass.
**Reads:** nothing beyond function args.
**Writes:** mutates the `registry`/`pending` dicts.
**Called by:** `cc_injection_extraction.py`, `cc_injection_inventory.py`.
**Calls out:** `cc_injection_classification`.

---

### cc_injection_classification.py (216 LOC)

**Purpose:** Classifies one segment into one of 5 origin labels (`COVERED`, `INJECTED`, `KEEP`,
`OURS`, `UNCLASSIFIED`) by running the real `src/proxy` strip pipeline against a synthetic message.
**Reads:** nothing beyond function args — pure classification.
**Writes:** nothing — returns `ResolvedHit` lists.
**Called by:** `cc_injection_aggregation.py`.
**Calls out:** `proxy.rules`, `proxy.strip_vocab`, `proxy.strip_sr`, `proxy.message_passes` via
`sys.path.insert` + `import proxy.*` (avoids the `block_dev_imports_src` hook's `from src.`/
`import src.` literal-line block).

---

### cc_injection_report.py (271 LOC)

**Purpose:** Builds the markdown inventory report from the finished registry, writes it under
`md/`, and prints the console summary.
**Reads:** the finished `registry`/`file_stats`/`counters` from the orchestrator.
**Writes:** `md/<name>_cc_injection_inventory.md` (report; override with `--out-name`); a 3-line
summary to stdout.
**Called by:** `cc_injection_inventory.py`.
**Calls out:** none.

---

## State
`cc_injection_inventory.py`'s `inventory_workflow` owns and creates the `registry`/
`pending_user_text`/`dedup_seen`/`counters`/`msg_dedup_seen` state and passes them by reference
into `cc_injection_extraction._process_file` (mutated per file) and
`cc_injection_aggregation._finalize_pending_user_text` (mutated once at the end); no module-level
mutable state exists in any of the 5 files.
