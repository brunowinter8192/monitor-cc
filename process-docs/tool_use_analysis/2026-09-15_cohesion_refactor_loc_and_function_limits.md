# 2026-09-15 — Cohesion refactor of `dev/tool_use_analysis/` for the 400-LOC / 50-line limits

## Trigger

10 of the 13 `.py` files in `dev/tool_use_analysis/` violated the project's 400-LOC file limit
and/or had functions at or above 50 lines. Same mandate as the `dev/proxy_dual_log/` refactor one
milestone earlier (see that area for the general method): split by CONCERN, zero behaviour change,
no CLI/path/rename changes, scope confined to this one directory plus its own `process-docs/` area.

## Investigation

Read all 13 `.py` files in full plus the directory's DOCS.md. Grepped every script's own basename
against the whole repo first — confirmed DOCS.md's claim that "each script is standalone" holds
exactly: zero cross-script imports exist in this directory (unlike `proxy_dual_log/`'s
`composition_probe.py`, there was no hidden importer to keep compatible here).

**No real proxy-log data exists on this machine.** `dev/proxy_dual_log/`'s milestone already found
that `src/logs/api_requests_*.jsonl` (the "main log") no longer gets written (superseded by the
dual-log quartet). This directory's scripts overwhelmingly read that now-nonexistent format
(`raw_payload`/`message_count`/`diff_from_prev`/`modifications`/`stripped_msg_removed` — a schema
`src/proxy/addon.py` stopped writing). Confirmed via `find` across the whole disk (including
`/private/tmp/pre_restart_logs/`, which only holds the newer dual-log quartet format, not the old
`raw_payload` shape) — there is no real fixture left for `extract_long_calls.py`,
`extract_patterns.py`, `extract_transcript.py`, `rag_query_audit.py`, `rag_truncation_audit.py`,
`tag_presence_audit.py`, `strip_audit.py`, `sr_bypass_audit.py`, `cc_injection_audit.py`, or
`waste_repetition.py`. Only `extract_zeros.py` and `sr_session_audit.py` (session-JSONL format,
`~/.claude/projects/*/*.jsonl`) and `rs_truncation_preserve_replay.py` (dual-log format) still have
real data to run against.

## Decisions

**Built one synthetic `raw_payload`-shaped proxy-log fixture** (`/tmp/m2_fixtures/proxy_fixture.jsonl`
— NOT staged, worktree-local scratch per the dev/ convention) covering: an SR block
(`skills-available`), a role=`system` SR (`task-tools-nag`), a Bash/Grep/Read/Write tool_use each
with a matching tool_result (one zero-result "No matches found", one `is_error` validation failure),
a `rag-cli search_hybrid` call with a truncation-marker result at the CC 40-60% split fraction, and
a second snapshot entry (growth via `diff_from_prev`) plus a `stripped_msg_removed` entry so the
captured/bypassed accounting has something to count. Reused this one fixture for every
`raw_payload`-reading script's before/after diff instead of building one fixture per script — the
schema is identical across all of them, and building 10 near-identical fixtures would have been the
kind of ceremony these rules explicitly discourage.

**For `extract_zeros.py`/`sr_session_audit.py`, used real session JSONLs** from old, static
(non-growing) worktree project directories under `~/.claude/projects/` — same "frozen snapshot"
principle as `proxy_dual_log`'s live-corpus problem, except here the fix was simpler: just pick
session files from worktrees that no longer exist (so nothing can append to them), rather than
`cp -r`-snapshotting a live-growing directory.

**Same in-place-vs-new-file threshold as the previous milestone:** 5 files stayed single-file with
only their one over-50-line `_build_report`/`build_report` split into 2-4 section helpers
(`waste_repetition.py`, `cc_injection_audit.py`, `sr_session_audit.py`, `rag_query_audit.py`,
`extract_zeros.py` — all comfortably under 400 LOC afterward). 5 files were genuinely over 400 and
got a real module split:
- `rag_truncation_audit.py` → `.py` + `_data.py` (load/collect/classify) + `_report.py` (one
  `_report_<section>` fn per section).
- `tag_presence_audit.py` → `.py` + `_scan.py` (SR/TN/ND/PO template mirror + the streaming
  scanner, `_scan_entry` split into `_scan_tag_occurrences`/`_scan_captured`/`_build_req_block`, the
  55-line `_scan_tag_occurrences` split once more into `_scan_sr_in_text`/`_scan_non_sr_in_text`
  once it landed at 52 lines) + `_report.py` (aggregate tables split off their "Non-SR Tag Strip
  Verification" subsection).
- `strip_audit.py` → `.py` + `_classify.py` (load/classify/`_check_tags` split into
  `_check_sr_tags`/`_check_simple_tag`/`_tag_strip_in_delta`) + `_report.py` (header/catalog/
  delta-log/summary, `_render_req_section` split via a new `_render_req_header` helper).
- `extract_patterns.py` → `.py` + `_collect.py` (load/dedup/signature/aggregate) +
  `_wrappers.py` (naming/complexity classification, pulled out as its OWN concern rather than
  folded into `_report.py`, since "how do we name/score a wrapper candidate" is a materially
  different question from "how do we render section 6") + `_report.py` (all 6 section renderers,
  section 6 itself split into `_build_wrapper_candidates` (`_wrappers.py`-facing data assembly) vs.
  `_render_wrapper_candidates` (pure Markdown formatting) since the original 60-line function mixed
  both).
- `extract_long_calls.py` → split exactly along the file's own pre-existing
  `# --- INLINED from former src/proxy_forensics.py ---` / `# --- END INLINED ---` comment markers:
  `_lib.py` gets everything between those markers verbatim (dataclasses + collection/aggregation —
  a genuinely separable former-library concern the original author had already delineated),
  `_report.py` gets everything after (the report builders), `.py` keeps the orchestrator/CLI. This
  file had NO function over 50 lines to begin with — the split is purely for the 400-LOC file limit,
  proof that "cosmetic LOC shrinking is not a split" doesn't mean "only split files with long
  functions": a 587-line file with three well-separated concerns still needs splitting even if no
  single function forces it.

**Incidental cleanup, not a feature:** `strip_audit.py` originally imported
`BUCKETS, RULES, TAG_LITERALS, attribute_chunk, classify_req, code_for_rule, legend_markdown,
STRIP_RULE_CODES` from `src.proxy.strip_vocab` — grepped actual usage and found `BUCKETS`,
`TAG_LITERALS`, `attribute_chunk`, `code_for_rule`, `STRIP_RULE_CODES` were never referenced anywhere
in the file (dead imports, pre-existing). Split each import to only the new module that actually
uses it (`RULES`+`classify_req` → `strip_audit_classify.py`, `legend_markdown` → `strip_audit.py`);
dropped the five unused ones rather than carrying dead imports into three new files. Verified this
is behaviour-neutral: `import`ing an unused name from `strip_vocab` has no side effect beyond
executing `strip_vocab.py`'s own module body, which already runs anyway via the imports that ARE
kept.

## Verification

Same method as `proxy_dual_log`: ran every script BEFORE editing (against the synthetic fixture, or
against real static session JSONLs for the two session-based scripts) and saved stdout + any
generated report to `/tmp/m2_snapshot/out/` (worktree-external scratch, never staged), then re-ran
after each file's split and diffed. Every diff was either byte-identical or differed only in a
self-stamped `datetime.now()` line / the echoed output path — normalized out with `sed` before
comparing.

**`strip_audit.py` hits a pre-existing, data-independent bug** — `_build_rule_catalog` iterates the
full `src.proxy.strip_sr._SR_TEMPLATES` catalog unconditionally (not scoped to what the fixture
contains) and crashes with `KeyError: 'agent-types'` because the real `_SR_TEMPLATES` now has an
`agent-types` entry that `strip_audit.py`'s own hardcoded `_TEMPLATE_TO_RULE` map was never updated
for. This fires on ANY input, real or synthetic, before or after the split — confirmed the crash
happens at the identical logical point (same function, same KeyError) both before and after, then
additionally verified the actual report-building logic beneath that crash point still matches: wrote
a one-off synthetic comparison (not persisted — see Gotchas) that imported the pre-edit snapshot
module via `importlib.util.spec_from_file_location` side-by-side with the new split modules and
asserted `_build_header`/`_build_delta_log`/`_build_summary` produce byte-identical output on the
same fixture entries, bypassing the unrelated catalog bug. All three matched.

Final state: `python3 -c ast.parse` on all 33 `.py` files in the directory (syntax check), `wc -l`
on all 33 (every file 389 LOC or under), and an AST walk for any `FunctionDef`/`AsyncFunctionDef` at
50+ lines (none found) — see the WORKER's COMPLETION CHECKLIST for the exact numbers.

## Gotchas for the next agent

- If you need to test any `raw_payload`-format script in this directory again, the synthetic-fixture
  builder used this session is NOT persisted anywhere (it was a `/tmp` scratch script, per the dev/
  convention that one-off test fixtures don't get staged) — you will need to rebuild it. The schema
  is fully documented by reading any of the 10 affected scripts' own field accesses; there is no
  shortcut via real data until `src/proxy/addon.py` (if ever) starts writing the old main-log format
  again, which per the `proxy_dual_log` milestone's own finding looks intentionally retired.
- `strip_audit.py`'s `agent-types` KeyError (see Verification) is a REAL, currently-live bug in
  `strip_audit.py` against current `src/proxy/strip_sr.py` — every real invocation of this script
  will crash in `_build_rule_catalog` before it ever reaches the delta log. Out of scope for this
  refactor (behaviour must not change), but worth a fix-it issue: add `'agent-types':
  'stripped_agent_types_sr'` (or whatever the real rule name is — check
  `src/proxy/message_passes.py`/`src/proxy/strip_inject_delta.py`'s `_MSG_CODE_TO_FN` for the `AT`
  code, per `dev/proxy_dual_log/DOCS.md`'s own note about that code) to
  `strip_audit_classify.py`'s `_TEMPLATE_TO_RULE`.
- Confirmed (again) that `~/.claude/projects/<old-worktree-name>/*.jsonl` files are safe,
  non-growing fixtures for any session-JSONL-reading dev script, as long as the worktree name in the
  path no longer exists as an active worktree — check `git worktree list` before picking one, since
  an active worktree's session file grows in real time (this bit the `proxy_dual_log` milestone via
  `/tmp` filename collisions with a concurrent process, and would bite here too via a genuinely
  different mechanism: the file itself changing between the "before" and "after" run).
