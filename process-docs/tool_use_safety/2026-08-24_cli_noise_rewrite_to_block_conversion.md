# CLI-noise rewrite-to-block conversion + cross-CLI relax (2026-08-24)

**Topic:** the 5 `rewrite_*_noise.py` hooks protecting bounded/context-destined CLI output
(`websearch scrape_url`, `gh-cli get_issue`/`list_issues`, `rag-cli search`,
`worker-cli capture`/`response`) converted from silent-rewrite to block; `rewrite_bd_invalid_repo.py`
deleted separately (bd retired); a shared cross-CLI allow-predicate added so chaining
different known CLIs in one Bash call is no longer treated as "foreign".

## Motivation

Proven incident: `websearch scrape_url URL > /tmp/f.md 2>&1; wc -l /tmp/f.md; head -120
/tmp/f.md` — `rewrite_websearch_scrape_noise.py` silently stripped the redirect (correct
per its own rule: scrape output must land in context, not a file), but the two DEPENDENT
segments (`wc`, `head`) still assumed the file existed. They failed against a nonexistent
path, and the whole multi-segment Bash call exited 1 and surfaced as `[ERROR]` even
though the scrape itself succeeded. Root cause is structural, not a regex bug: a rewrite
hook can only edit the ONE segment it targets, but a multi-segment command's segments
can be semantically coupled (later segments consuming earlier ones' output-to-file) — an
edit to one segment can silently desync the others. Blocking instead of rewriting removes
the coupling risk entirely: the model must re-issue the protected call standalone, so no
dependent segment can ever reference a file that no longer gets written.

## Design decisions

**Redirect explicitly forbidden, not just pipes.** None of the pre-existing isolation
hooks (`block_rag_cli_index_isolated.py`, `block_pipe_scraper_isolated.py`,
`block_linkedin_cli_isolated.py`) forbid redirects — `_SEPARATOR_RE` never splits on `>`,
so a redirect always stays glued into its own segment and passes untouched by the
existing "is every segment legal" checks. This family's target class (`scrape_url`,
`get_issue`/`list_issues`, `search`, `capture`/`response`) is different from those three:
their whole point is BOUNDED, CONTEXT-DESTINED output — redirecting it to a file to read
back piecemeal is the anti-pattern being eliminated, not a legitimate escape (unlike
`rag-cli index`'s multi-minute run, which legitimately needs `> logfile` for progress
polling). Each of the 4 target/extended hooks therefore adds an explicit
`_REDIRECT_RE` check scoped ONLY to its protected segment(s) — pipes need no separate
check, since `_SEPARATOR_RE` already splits on `|`, turning a piped protected call into a
structurally foreign trailing segment.

**Two old "legitimate" redirect/pipe allowances retired.** `rewrite_gh_cli_read_noise.py`
and `rewrite_worker_cli_capture_noise.py` both explicitly preserved `> /tmp/file` as
"legitimate — save output to disk", and `worker-cli capture X | tail -40` was documented
as a "guaranteed no-op... documented legitimate fallback". Both predate their targets'
2026-06 clean-output redesigns (capture in particular — see the `process-docs/worker_orchestration/`
area's `worker-cli capture` clean+scope redesign entry, a different area) that made the raw output
context-ready; the workaround's original rationale (messy/truncated raw output needing a
tail filter) no longer applies. Retiring them was a deliberate scope decision, not an
oversight — matches the family's now-uniform "standalone, no redirect, no pipe" rule.

**Extend vs new hook, decided per tool:**
- `gh-cli get_issue`/`list_issues` → EXTEND `block_gh_cli_chained.py`. That hook already
  had the exact segment-splitting/trigger-gate machinery; get_issue/list_issues simply
  join the trigger set as a second, redirect-protected segment class, while the existing
  7 search/research tools keep their pre-existing redirect-ALLOWED behavior untouched
  (no regression risk — the new redirect check is regex-scoped to the 2 read commands
  only).
- `rag-cli search` → EXTEND `block_rag_cli_chained.py`, same reasoning: one new
  `_RAG_SEARCH_SEGMENT_RE` + `_REDIRECT_RE` pair scoped to `search`, other subcommands
  (`index`, `delete`, `list_documents`) untouched.
- `websearch scrape_url` and `worker-cli capture`/`response` → NEW hooks
  (`block_websearch_scrape_chained.py`, `block_worker_cli_read_chained.py`) — no existing
  block hook touched either surface, so nothing to extend. `capture`+`response` share ONE
  new hook (not two) since the deleted rewrite hooks were themselves documented as direct
  clones of each other.

**Cross-CLI relax — a mid-task scope change, not part of the original design.** The
initial plan (per the first design pass) kept every hook's OLD same-tool-only chaining
rule (block_gh_cli_chained's 7-tool "combine with each other" allowance,
block_rag_cli_chained's "trailing segments must also start with rag-cli"). A follow-up
instruction inverted this: cross-CLI combinations in one Bash call are now explicitly
ALLOWED — a segment passes if it's a call to ANY known CLI tool (not specifically the
SAME protected tool) or a leading `cd`/`test`/bracket-test guard. New shared module
`src/hooks/_known_cli.py` (`is_known_cli_segment`, `is_guard_segment`) sourced by
grepping every CLI token actually referenced across `src/hooks/*.py`: `gh-cli`,
`rag-cli`, `worker-cli`, `reddit-cli`, `linkedin`, `websearch`. `bd` deliberately
excluded from the known-CLI list — retired (this is why `rewrite_bd_invalid_repo.py` was
deleted in the same task, an explicit scope addition, not an unrelated cleanup).

This relax had a nice side effect: `block_gh_cli_chained.py`'s dedicated
`repo_freshness`-may-join-the-chain carve-out (added 2026-08-07, see
`2026-08-07_gh_cli_repo_freshness_segment_and_message_clarity.md` in this area) became
REDUNDANT — any gh-cli subcommand, including `repo_freshness`, now passes the generic
`is_known_cli_segment()` check without a dedicated regex branch. Removed rather than kept
as unreachable code; the smoke suite's repo_freshness cases (from that earlier entry)
still pass, now via the generic path.

**Guard positional rule relaxed too.** `block_rag_cli_chained.py`'s old rule allowed `cd`/
guards only BEFORE the first `rag-cli` segment (trailing segments had no such allowance).
The new `is_guard_segment()` check applies uniformly regardless of position — simpler,
and the previously-disallowed case (a guard AFTER a protected call) is harmless, not a
new risk surface.

**`worker-cli` gets a `cd` allowance the other 3 new/extended hooks don't.**
`websearch`/`linkedin`/`gh-cli`/`rag-cli search` are `$PATH`-global CLIs with no
legitimate reason to `cd` first. `worker-cli capture`/`response` are different: reading
the real CLI source (`resolve_project_path` in the `worker-cli` script) confirmed they
resolve the target project via an optional `project_path` positional that falls back to
`cwd` when omitted — so `cd /path/to/project && worker-cli capture X` is a genuine
pattern, not a habit to discourage. This is `is_guard_segment()`'s pre-existing `cd`
branch being exercised, not a hook-specific carve-out.

## Verification

85 smoke cases across the 4 target/extended hooks (30 gh-cli, 17 rag-cli, 18 websearch,
20 worker-cli), all passing, including the verbatim incident command
(`test_block_websearch_scrape_chained.py`) asserting it now BLOCKS. Cross-checked no
regression on 6 adjacent/unrelated hook suites (`block_gh_cli_local_path`,
`block_rag_cli_index_isolated`, `block_rag_docs_layer`, `block_linkedin_cli_isolated`,
`block_rag_cli_document_repeat`, `hook_setup` main-branch gate) and the dedicated
`probe_gh_cli_repo_freshness_incident.py` content-check probe (updated for the new
`_BLOCK_MESSAGE` wording — the old "repo_freshness may join" phrase check swapped for a
"cross-CLI chains ARE allowed" phrase check, matching the message's actual new text).

One pre-existing, unrelated test failure discovered and confirmed via `git stash`
(reproduces identically before this task's changes): `test_fire_log.py`'s
`_test_tool_error_writer` subtest fails with `ModuleNotFoundError: No module named
'src.panes.warnings_persist'` — that source file does not exist in this worktree. Not
fixed (out of scope); the other 3 subtests in that file (block-fire, rewrite-fire,
env-var-override) pass, and the rewrite-fire subtest's fixture was swapped from the
deleted `rewrite_bd_invalid_repo.py` to `rewrite_chained_sleep.py` (still exercises the
same generic `log_fire` "rewrite" decision path).
