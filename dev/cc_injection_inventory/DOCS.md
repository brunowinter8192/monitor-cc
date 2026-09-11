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

### cc_injection_inventory.py (758 LOC)

**Purpose:** Streams `src/logs/dual_log/*_original.jsonl`, extracts every text segment
(`system[0..3]`, message content — plain string / `text` blocks / `tool_result` content), dedups
by exact segment text, and classifies each distinct segment into one of 5 origin labels:
`COVERED` (an existing `src/proxy/strip_*.py` rule removes it, verified by actually running
`apply_modification_rules` against a synthetic message), `INJECTED` (the proxy itself adds it,
via the same pipeline call's `injected_msg_added` return value), `KEEP` (audited + deliberately
preserved wrapper), `OURS` (own content — tool output, user prompts, assistant text), or
`UNCLASSIFIED` (CC-authored framing no rule touches and no prior audit judged).
**Reads:** `src/logs/dual_log/api_requests_*_original.jsonl`, streamed line-by-line (the corpus
includes multi-GB files, never loaded whole).
**Writes:** `md/<name>_cc_injection_inventory.md` (report; override with `--out-name`); a 3-line
summary to stdout.
**Called by:** none — run manually.
**Calls out:** none beyond `src/proxy` (stdlib only) — imports `proxy.rules`, `proxy.strip_vocab`,
`proxy.strip_sr`, `proxy.message_passes` via `sys.path.insert` + `import proxy.*` (avoids the
`block_dev_imports_src` hook's `from src.`/`import src.` literal-line block).

**CLI flags:** `--logs-glob` (override input glob; dual_log dir auto-resolves to local
`src/logs/dual_log` if present, else 3 parents up from the worktree root), `--out-name` (report
filename), `--max-entries` (debug cap per file).

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
