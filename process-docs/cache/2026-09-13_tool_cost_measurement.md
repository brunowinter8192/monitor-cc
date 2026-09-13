# Cache cost per tool call — main session, 2026-09-13

## What was measured and why

Issue 117 recorded a single observation from 2026-09-08: a Bash tool_result request came back at CC 117, a Write tool_result request at CC 141, for files of equal content. One data point, no cause named.

A web and paper search found nothing on the question. OpenAlex returns general agent token-efficiency work only, and the closest article, Claude Code Camp from 2026-02-25, measures cache hit versus miss on the system prompt, never cost per tool. The vendor docs price tool DEFINITIONS (tool-use system prompt 286 tokens on Opus 5, built-in bash schema 325 tokens) but say nothing about the per-call envelope of a tool_result. The question is therefore a measurement question, not a research question.

## Corpus

20 markdown files cut from `trading-reference`, stored under `dev/cache/samples/`. Sizes deliberately spread from 119 to 7852 bytes, 36279 bytes in total. The spread is what separates a fixed per-call cost from a content-proportional one. Uniform sizes would not.

## Method

One worker per run, `claude-sonnet-5`, effort high, thinking disabled. One tool call per message, so each request carries exactly one file and CC is attributable per file. Alignment was verified rather than assumed: pairing REQ 5+k with sample k+1 gives a correlation of 0.979 against file size, the off-by-one alternative gives 0.28.

Every write run was checked with `diff -r` against the samples. All were byte-identical.

## Results

Reading the same 36279 bytes:

| lane | CC | requests |
|---|---|---|
| Read tool, 20 calls | 17110 | 20 |
| Bash `cat`, 20 calls | 16552 | 20 |
| Bash `cat`, 1 chained call | 16277 | 2 |

Writing the same 36279 bytes:

| lane | CC | requests |
|---|---|---|
| Write tool, 20 calls | 18647 | 20 |
| Bash heredoc, 20 calls | 17319 | 20 |
| Bash heredoc, 1 chained call | 15549 | 1 |

Editing, one line replaced per file:

| lane | CC | calls |
|---|---|---|
| Edit tool | 8115 | 22 |
| `sed -i '' '1s/.*/ZZMARKERZZ/'` | 4245 | 20 |

Linear fits over the 20 points, CC against bytes:

- Read: `245.1 + 0.3365 * bytes`
- Bash read: `224.6 + 0.3324 * bytes`
- Write: `331.0 + 0.3315 * bytes`
- Bash heredoc: `265.9 + 0.3308 * bytes`

## Findings

The slopes are identical across all four lanes, at 0.331 to 0.337 tokens per byte. The content costs the same however it travels. The entire difference between tools sits in the intercept, meaning the per-call envelope.

Write against Bash heredoc is the pair Issue 117 asked for: 65 tokens of fixed overhead per call, flat across the whole size range from 119 to 7852 bytes. The per-file difference stayed between -55 and -80 with no trend. The original single observation of 24 tokens understated it.

Edit against sed is the largest gap of all, 157 tokens per call, or 47.7 percent. The cause is structural: Edit must carry the old text verbatim so it can locate it, sed addresses the line by number and carries nothing but `1s/.*/MARKER/`. Edit also needed two extra calls because two samples share the first line "# Springer Series in Statistics", which appears more than once inside those files, so `old_string` was rejected as non-unique. sed had no such failure mode.

Chaining behaves differently for reading and writing. Writing 20 files in one Bash call costs 15549 in a single request, 16.6 percent below the Write tool. Reading 20 files in one Bash call saves only 1.7 percent, because the combined output crossed the inline threshold, was persisted to a file, and had to be pulled back with a second request. The saving on the read side is capped by that threshold, the write side has no such ceiling.

## Landmine: positional drift in the read comparison

The per-file difference between the Read tool and Bash `cat` runs monotonically from +16 on sample 01 to -78 on sample 20. It tracks the position in the run, not the file size. The same comparison on the write side is flat, so this is not a property of the tools.

The cause was not established. The working hypothesis is shifted cache breakpoints, since the proxy sets them itself in `src/proxy/cache.py`. Until that is cleared up, the 3.3 percent read-side difference between Read and Bash must not be attributed to the tool. The write-side and edit-side numbers are unaffected, they show no drift.

## What a successor should not repeat

The first measurement run died before doing anything, with a 400 reading `clear_thinking_20251015 strategy requires thinking to be enabled or adaptive`. Claude Code sends that context-management edit itself while also sending adaptive thinking; the proxy overwrote thinking with disabled and left the edit standing. The fix lives in `src/proxy/inject_helpers.py`. If a thinking-disabled run ever fails this way again, check the injected payload first, not the worker.

The worker prompt for the read run named the samples only by glob pattern. The Read tool cannot list a directory and `ls` was forbidden, so the worker correctly stopped and reported instead of guessing. Hand a worker the exact filenames.

A worker asked to read 20 files does not chain them on its own. It used 20 separate calls in both the Read run and the Bash run, without being told either way. Chaining has to be asked for explicitly.

## Consequence taken on the same day

Read, Edit and Write were removed from the model's tool list entirely, via `TOOL_BLOCKLIST` in `src/constants.py`. The shared rule files were rewritten to describe file work in Bash terms. See `process-docs/proxy_tool_stripping/` and `process-docs/model_selector/` for that thread.
