# dev/cc_injection_inventory/

## Role

Reusable audit tool that produces a complete inventory of every distinguishable text class
present in the raw request payloads Claude Code sends, as captured in `src/logs/dual_log/`. An
inventory, not a top-N filter — every distinct class found is listed regardless of frequency or
size. Answers "what text classes exist and are any of them unhandled?", complementing
`dev/proxy_dual_log/attribution_coverage.py` (which answers "does every entry our proxy already
strips have a named function?" — that tool never sees content the proxy does NOT touch; this one
does, by classification rather than log-diff). Touch this directory when the strip/inject rule
set changes and the inventory needs re-running, or when adding a new classification origin label.

## Modules

### cc_injection_inventory.py (117 LOC)

**Purpose:** Entry script — parses CLI args, resolves the dual-log file glob (with self-scan
exclusion), and drives extraction -> aggregation -> report across all matched files.
**Reads:** CLI args; lists `src/logs/dual_log/api_requests_*_original.jsonl` (or `--logs-glob`).
**Writes:** nothing directly — delegates to `cc_injection_report._write_report`.
**Called by:** none — run manually.
**Calls out:** `cc_injection_extraction`, `cc_injection_aggregation`, `cc_injection_report`.

**CLI flags:** `--logs-glob` (override input glob; dual_log dir auto-resolves to local
`src/logs/dual_log` if present, else 3 parents up from the worktree root), `--out-name` (report
filename), `--max-entries` (debug cap per file).

### cc_injection_extraction.py (125 LOC)

**Purpose:** Streams one dual-log JSONL file and extracts every text segment (`system[0..3]`,
message content — plain string / `text` blocks / `tool_result` content).
**Reads:** one `api_requests_*_original.jsonl` file, streamed line-by-line (the corpus includes
multi-GB files, never loaded whole).
**Writes:** mutates the `registry`/`pending`/`dedup_seen`/`counters` dicts passed in by the caller.
**Called by:** `cc_injection_inventory.py`.
**Calls out:** `cc_injection_aggregation`.

### cc_injection_aggregation.py (92 LOC)

**Purpose:** Dedups segment occurrences by exact text, dispatches first-sight segments to
classification, and resolves recurring user-text templates in a second pass.
**Reads:** nothing beyond function args.
**Writes:** mutates the `registry`/`pending` dicts.
**Called by:** `cc_injection_extraction.py`, `cc_injection_inventory.py`.
**Calls out:** `cc_injection_classification`.

### cc_injection_classification.py (250 LOC)

**Purpose:** Classifies one segment into one of 5 origin labels (`COVERED`, `INJECTED`, `KEEP`,
`OURS`, `UNCLASSIFIED`) by running the real `src/proxy` strip pipeline against a synthetic message.
**Reads:** nothing beyond function args — pure classification.
**Writes:** nothing — returns `ResolvedHit` lists.
**Called by:** `cc_injection_aggregation.py`.
**Calls out:** `proxy.rules`, `proxy.strip_vocab`, `proxy.strip_sr`, `proxy.message_passes` via
`sys.path.insert` + `import proxy.*` (avoids the `block_dev_imports_src` hook's `from src.`/
`import src.` literal-line block).

### cc_injection_report.py (271 LOC)

**Purpose:** Builds the markdown inventory report from the finished registry, writes it under
`md/`, and prints the console summary.
**Reads:** the finished `registry`/`file_stats`/`counters` from the orchestrator.
**Writes:** `md/<name>_cc_injection_inventory.md` (report; override with `--out-name`); a 3-line
summary to stdout.
**Called by:** `cc_injection_inventory.py`.
**Calls out:** none.

---

## Gotchas

**The dual_log directory is gitignored and lives only in the main repo**, not copied into a
worktree — the auto-resolve fallback assumes the fixed `.claude/worktrees/<name>/` nesting; pass
`--logs-glob` with an absolute path if that assumption doesn't hold.

**Self-scan exclusion depends on the same worktree-nesting assumption.** The default glob
excludes this session's own worker log (any `api_requests_worker_*` file that also embeds the
current task/worktree name) since it's written live while the script runs. Running directly from
a non-worktree checkout disables the exclusion (no task name to match against) — nothing gets
excluded in that case. An explicit `--logs-glob` bypasses the exclusion entirely.

**`system[2]`/`system[3]` are always fully replaced regardless of content** — one `COVERED` row
each, never split by content. `system[0]`/`system[1]` are never touched anywhere in
`src/proxy/*.py` — always `UNCLASSIFIED`.

**`role=system` bare-content messages are unconditionally wiped by the RS pass** (except the
`[Truncated:` guard) before any content-specific rule gets a chance to match — content that would
otherwise map to a different rule (deferred-tools, file-modified) classifies as `COVERED` via RS
specifically, since RS fires first.
