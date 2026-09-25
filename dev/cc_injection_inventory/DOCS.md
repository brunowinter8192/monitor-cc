# dev/cc_injection_inventory/

## Role
Reusable audit tool inventorying every distinguishable text class in raw Claude Code request payloads of the dual log, all classes regardless of frequency. Touch when the strip/inject rule set changes and the inventory needs re-running, or when adding an origin label.

## Public Interface
No `__init__.py`. Entry path: `./venv/bin/python dev/cc_injection_inventory/cc_injection_inventory.py`.

## Flow
CLI args select the dual-log files. Each file is streamed, every text segment is extracted and classified by the real `src/proxy` strip pipeline, occurrences are deduplicated into a registry, and the registry is rendered to a Markdown report plus a short console summary.

## Modules

### cc_injection_inventory.py (121 LOC)

**Purpose:** Entry script: parses CLI args, resolves the dual-log file set and drives extraction, aggregation and report.
**Reads:** CLI args; the dual-log directory listing.
**Writes:** nothing directly; delegates to the report module.
**Called by:** none; run manually.
**Calls out:** `cc_injection_extraction.py`, `cc_injection_aggregation.py`, `cc_injection_report.py`.

---

### cc_injection_extraction.py (122 LOC)

**Purpose:** Streams one dual-log file and extracts every text segment from system and message content.
**Reads:** one original dual-log file, streamed line by line (multi-GB files exist).
**Writes:** mutates the registry and counter dicts passed in.
**Called by:** `cc_injection_inventory.py`.
**Calls out:** `cc_injection_aggregation.py`.

---

### cc_injection_aggregation.py (81 LOC)

**Purpose:** Deduplicates segments by exact text, dispatches first-seen segments to classification and resolves recurring user-text templates.
**Reads:** nothing beyond arguments.
**Writes:** mutates the registry and pending dicts.
**Called by:** `cc_injection_extraction.py`, `cc_injection_inventory.py`.
**Calls out:** `cc_injection_classification.py`.

---

### cc_injection_classification.py (216 LOC)

**Purpose:** Classifies one segment into one of five origin labels by running the real proxy strip pipeline against a synthetic message.
**Reads:** nothing beyond arguments.
**Writes:** nothing; returns hit lists.
**Called by:** `cc_injection_aggregation.py`.
**Calls out:** `proxy.rules`, `proxy.strip_vocab`, `proxy.strip_sr`, `proxy.message_passes`, imported via a path insert to satisfy the dev-imports-src hook.

---

### cc_injection_report.py (271 LOC)

**Purpose:** Builds the Markdown inventory report from the finished registry, writes it under `md/` and prints the summary.
**Reads:** the finished registry, file stats and counters.
**Writes:** `md/<name>_cc_injection_inventory.md`; a short summary to stdout.
**Called by:** `cc_injection_inventory.py`.
**Calls out:** none.

---

## State
The entry script owns and creates all mutable state and passes it by reference into extraction and aggregation. No module-level mutable state exists in any file.
