# 2026-09-16 — Comment/docstring salvage for dev/cc_injection_inventory/ standards conformance

## Context for whoever picks this up

Milestone: bring `dev/cc_injection_inventory/` into conformance with the project's three-marker
comment standard (`# INFRASTRUCTURE` / `# ORCHESTRATOR` / `# FUNCTIONS`, nothing else). Every
comment and docstring below was relocated here verbatim before deletion from the code.

**File-count note:** the milestone brief stated "4 .py files"; there are actually **5** on disk
(`cc_injection_aggregation.py`, `cc_injection_classification.py`, `cc_injection_extraction.py`,
`cc_injection_inventory.py`, `cc_injection_report.py`). The pre-existing `DOCS.md` already
documented all 5. All 5 were processed. The stated comment/docstring counts (58 comments, 1
docstring) matched my own independent count exactly across the 5 real files, so the "4" in the
brief was very likely just a miscount by whoever authored the milestone — flagging it here rather
than silently correcting it upstream.

**Load-bearing docstring found and rewired:** `cc_injection_inventory.py` passed
`description=__doc__` to `argparse.ArgumentParser`. The exact docstring text now lives in a
module-level string constant in `# INFRASTRUCTURE` (a plain assignment, not a docstring position,
so it is not itself a standards violation) and the argparse call was rewired to reference that
constant. Verified byte-identical `--help` output before and after the change (see the recap /
completion checklist in the task response for the exact command).

---

## Salvage from dev/cc_injection_inventory/cc_injection_aggregation.py

Was lines 7-8 (above `_process_segment_occurrence`):
```
# Dispatch one segment occurrence: replay cached classification on a dedup repeat (chars-only),
# classify fresh on first sight (registers count + chars + sample).
```

Was lines 53-56 (above `_distinct_variant_count`):
```
# Collapse variants where one is a verbatim substring of another (prefix, suffix, or mid-string
# extension) before counting distinctness — a message a human edited/extended between two sends
# is still ONE evolving message, not two occurrences of a recurring CC template. Longest-first so
# a shorter variant merges into whichever longer kept variant already contains it.
```

Was lines 66-70 (above `_finalize_pending_user_text`):
```
# Two-phase resolution for top-level user text: signatures with >=2 SUBSTANTIVELY DISTINCT
# variants (containment-collapsed, see `_distinct_variant_count`) are CC-authored templates
# humans don't retype verbatim -> UNCLASSIFIED, one row each. Everything else (singletons, and
# same-message-grew-longer pairs collapsing to 1 distinct variant) is genuinely unique -> folded
# into one OURS aggregate row (enumerating each would be a laundry-list, not a class).
```

## Salvage from dev/cc_injection_inventory/cc_injection_classification.py

Was lines 11-12 (above `import proxy.rules as rules`):
```
# From src/proxy/rules.py: real proxy strip pipeline — run against synthetic single-block
# messages to get ground-truth COVERED/removed-chunk decisions instead of hardcoded markers
```

Was line 14 (above `import proxy.strip_vocab as strip_vocab`):
```
# From src/proxy/strip_vocab.py: rule-code <-> marker <-> full-name vocabulary (attribute_chunk)
```

Was line 16 (above `import proxy.strip_sr as strip_sr`):
```
# From src/proxy/strip_sr.py: SR regexes + CLAUDE.md preserve-guard preamble
```

Was line 18 (above `import proxy.message_passes as message_passes`):
```
# From src/proxy/message_passes.py: role=system truncation-notice marker
```

Was lines 27-28 (above `ResolvedHit = namedtuple(...)`):
```
# A resolved classification hit for one segment occurrence.
# kind: 'CLASS' (goes straight into the registry) | 'PENDING' (deferred two-phase user-text resolution)
```

Was lines 31-35 (above `_TOP_LEVEL_SHAPES = (...)`):
```
# Content shapes where CC genuinely delivers top-level framing/wrappers (plain user-typed text
# or a CC-appended text block). tool_result content is OUR tool's own return value — an SR-looking
# literal inside it is quoted DATA (a fetched issue body, a `strings` dump, RAG content, source
# code containing the tag as a string), never a CC-injected wrapper, so the CLAUDE.md-preserve and
# leftover-SR extraction below must not run against tool_result content.
```

Was line 41 (above `_classify_segment`):
```
# Route a fresh segment to the right classifier by (role, section)
```

Was lines 55-57 (above `_classify_system_segment`):
```
# system[] block — sys[2]/sys[3] are unconditionally fully replaced (COVERED); sys[0]/sys[1]
# are never touched by any proxy function (verified: grep for system[0]/system[1] mutation
# across src/proxy/*.py returns nothing) -> UNCLASSIFIED.
```

Was lines 77-79 (above `_classify_role_system_segment`):
```
# role=system message (message-level, bare content) — RS rule (_apply_role_system_strip) wipes
# ALL role=system content unconditionally, EXCEPT the Read-tool truncation notice (KEEP, guarded
# in production by `content.startswith('[Truncated:')`).
```

Was lines 97-99 (above `_classify_user_segment`):
```
# role=user segment — run the real proxy strip pipeline on a synthetic single-block message,
# then peel off KEEP wrappers / leftover unmatched SR blocks from the residual, then bucket
# whatever's left as OURS (tool/user content) or defer top-level text for two-phase resolution.
```

Was line 109, trailing on a statement (inside `_classify_user_segment`):
```
        return hits  # PO block content is entirely the wrapper; nothing else to classify
```

Was lines 129-133 (inside `_extract_covered_and_injected`):
```
    # Text the PROXY ITSELF added (e.g. TN/BGK wake-up replacement) — ground truth is the
    # pipeline's own injected_msg_added output, same principle as removed_chunks for COVERED.
    # It round-trips back into a LATER request's history (CC persists what was actually sent,
    # not what CC intended) and would otherwise misread as a CC-authored recurring template.
    # Subtracted from residual so it isn't ALSO counted as OURS/UNCLASSIFIED below.
```

Was lines 214-216 (above `_extract_claudemd_blocks`):
```
# Peel out CLAUDE.md-context SR blocks (strip_sr._PRESERVE_PREAMBLE guard) from residual text.
# Only called for top-level shapes (see `_TOP_LEVEL_SHAPES`) — CLAUDE.md context is delivered as
# its own top-level message block, never nested inside a tool_result's own content.
```

Was lines 233-236 (above `_extract_leftover_sr_blocks`):
```
# Any <system-reminder> block still standing after the full pipeline matched no known template —
# a genuine gap: proxy strips nothing here, no strip_vocab entry exists for it. Only called for
# top-level shapes (see `_TOP_LEVEL_SHAPES`) — inside tool_result this would be quoted OUR data,
# not a CC wrapper.
```

Was line 244 (above `_normalize_template`):
```
# Normalize variable data (ids/paths/numbers) to placeholders for template-signature grouping
```

## Salvage from dev/cc_injection_inventory/cc_injection_extraction.py

Was line 9 (above `_process_file`):
```
# Stream one dual-log file, extracting + classifying every segment; returns per-file corpus stats
```

Was line 33 (above `_build_tool_name_map`):
```
# tool_use_id -> tool name, rebuilt per-entry from all assistant tool_use blocks in that snapshot
```

Was line 100, trailing/standalone inside `_process_content_blocks`:
```
        # tool_use / image / document — out of scope, skipped
```

## Salvage from dev/cc_injection_inventory/cc_injection_inventory.py

Module docstring (was lines 1-16) — LOAD-BEARING, passed as `argparse.ArgumentParser(description=__doc__)`
at (former) line 65. Moved verbatim into a module-level `# INFRASTRUCTURE` string constant; the
argparse call now references that constant instead of `__doc__`. `--help` output verified
byte-identical before/after.

```
cc_injection_inventory.py — complete inventory of every distinguishable text class present
in raw Claude Code request payloads, as captured in the proxy dual-logs.

INVENTORY, not a filter: every class found gets a row, however rare or small. Each class is
labelled COVERED (existing strip rule handles it), KEEP (audited + deliberately preserved),
INJECTED (text the PROXY ITSELF adds — e.g. a background-task wake-up replacement, which then
round-trips back into a LATER request's history since CC persists what was actually sent), OURS
(our own content — bash/tool output, user prompts, assistant text), or UNCLASSIFIED (CC-authored
framing/notices no rule touches and no prior audit judged).

Usage (from project root):
    ./venv/bin/python dev/cc_injection_inventory/cc_injection_inventory.py

Output: dev/cc_injection_inventory/md/<YYYYMMDD>_injection_inventory.md
```

Was lines 74-75 (above `_default_log_dir`):
```
# Resolve the dual_log directory — local (main repo) or via the fixed worktree nesting
# (.claude/worktrees/<name>/ -> 3 parents up = main repo), matching dev/proxy_dual_log precedent.
```

Was lines 86-88 (above `_current_task_name`):
```
# Task/worktree name if running inside .claude/worktrees/<name>/, else None. Used only to
# recognize (and exclude, default-glob path only) THIS session's own still-growing worker log —
# never applied when the user passes an explicit --logs-glob.
```

Was lines 96-97 (above `_is_own_live_session_log`):
```
# A worker log file is THIS session's own (live, still being appended to as this script runs)
# iff it uses the worker naming convention AND embeds the current task/worktree name.
```

Was line 104 (above `_resolve_log_files`):
```
# Returns (included_files, excluded_files) — excluded is always [] when logs_glob is explicit.
```

## Salvage from dev/cc_injection_inventory/cc_injection_report.py

(no comments or docstrings in this file beyond the three section markers — the `#`/`##`-prefixed
strings in this file, e.g. `f"# CC Injection Inventory — {ts}"`, `"## Summary"`, `"## Corpus"`,
are markdown report-body content returned/appended by the report-building functions, not Python
comments; they are untouched)

## Salvage from dev/cc_injection_inventory/DOCS.md

The pre-rewrite `DOCS.md` carried a "CLI flags:" sub-bullet under the `cc_injection_inventory.py`
module entry that doesn't fit the mandated per-module format (Purpose/Reads/Writes/Called by/Calls
out only). Cut verbatim:

```
**CLI flags:** `--logs-glob` (override input glob; dual_log dir auto-resolves to local
`src/logs/dual_log` if present, else 3 parents up from the worktree root), `--out-name` (report
filename), `--max-entries` (debug cap per file).
```

It also carried a trailing `## Gotchas` section that has no place in the mandated DOCS.md format
(Role / Public Interface / Flow / Modules / State only). Cut verbatim:

```
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
```

This content is preserved here in full; it is not carried into the rewritten DOCS.md.
