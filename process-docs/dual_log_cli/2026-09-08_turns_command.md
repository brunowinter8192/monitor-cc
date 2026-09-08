# New command: `duallog turns` — per-turn duration split into model time and tool wall time, 2026-09-08

Continues this area's command-surface line, alongside `reqs`. Motivation: worker turns of 30-40
minutes were observed on 2026-09-06 in the trading project, and whether that time was model
generation, shell commands, or token intake could only be guessed from `reqs`/`msgs` alone — both
show requests and gaps, neither groups them into the unit a human/orchestrator actually experiences
(one prompt in, one text answer + idle out).

## What a "turn" is, and where its data lives

The milestone fixed the definition: a turn opens at a `user` msg carrying a `text` block and no
`tool_result` block (a real prompt, never a tool-result relay); its requests are every REQ whose
group belongs to it, until the next opener. The dual log only ever records a request's SEND time
(`request_markers`' own `timestamp`) — stream-end time and output tokens live exclusively in CC's
own transcript, the same store `usage.build_usage_by_flow`'s CR/CC join already reads. So `turns`
needed a SECOND join through that same transcript, reading different fields off the same assistant
records (`timestamp` for stream end, `message.usage.output_tokens` for tokens) — `usage.py`'s
three-hop preamble (`_response` → anchor requestId → candidate project dirs → transcript file) was
split into `_resolve_session_transcript` so both joins share it rather than duplicating the walk.

## The turn-assignment bug this investigation found and fixed

The milestone's own prose describes turn membership as: a REQ belongs to turn N when its
`request_markers` msg-index KEY (`start_index`) is `>= opener_N` and `< opener_{N+1}`. Implemented
literally, this OVER-counted turn 1 of `api_requests_worker_1dda1c81_reldist-power_1788726467` by
exactly one request (78 instead of the verified 77) and inflated its duration by about a minute
(42.5m instead of 41.4m).

Root cause, found by comparing every marker's own resolved requestId/timestamp against the
independent reference probe's turn boundaries: `request_markers` keys a group by the SMALLEST msg
index its owning request's send first reveals — but a request that answers with plain TEXT and
goes idle is never itself sent onward. Its reply becomes visible only retroactively, bundled into
whatever the NEXT api call happens to send. On this session, the request that answers turn 1 with
its final idle text reply and the request that opens turn 2 (sent after the human typed "recap")
turned out to be the SAME `_forwarded` entry: its `start_index` (230) sits before the "recap"
opener's msg index (231), so the literal start_index-range rule keeps it in turn 1 — but its own
`message_count` (233) already includes msg 231 (the "recap" prompt) and 232 (a system reminder),
meaning its SEND happened after "recap" was typed, not before.

The fix: assign a REQ to the turn given by `bisect_right(openers, marker["message_count"] - 1)` —
the count of turn-opener indices ALREADY CONTAINED in that request's own SENT payload — rather than
testing its `start_index` key against the opener range. This needed `request_markers` extended
with `message_count` (additive; no existing caller reads it, confirmed by re-running every existing
suite unchanged). A hand-built regression fixture reproducing the exact shape (a request whose
`start_index` sits before the next opener but whose `message_count` reaches past it) is now
`test_turns.py::test_assignment_uses_message_count_not_start_index`.

## Preview: the LAST text block, not the first

The spawn prompt (msg 0 of both sessions checked) carries TWO text blocks: a leading
`<system-reminder>...</system-reminder>`-wrapped one, then the real prompt ("You are a WORKER.").
It is the ONLY multi-text-block opener observed in either ground-truth session. Taking the preview
from the first text block (the naive read of "the opener's text block") surfaces the reminder
wrapper instead of the actual prompt; taking the LAST text block's preview instead gives "You are a
WORKER." and is a no-op for every other (single-text-block) opener in the corpus checked.

## Verification against the milestone's own ground truth

An orchestrator-provided reference probe (transcript-only, not production code) gave independently
computed numbers for two real sessions. `turns` was run against both after implementation:

- `api_requests_worker_1dda1c81_reldist-power_1788726467`: turn 1 at `22:27:49` local, `41m27s`
  (probe: 41.4m), model `20m23s` (probe: 20.4m), tool `21m04s` (probe: 21.0m), **77 requests**
  (exact), **102,389 output tokens** (exact); turn 2 (`recap`) at `23:10:14`, `1m04s`, **2
  requests** (exact), **5,115 tokens** (exact).
- `api_requests_worker_1dda1c81_k-ratio_1788698865`: **20 turns** (exact); the longest, turn 8 at
  `18:34:40` local, `11m33s` (probe: 11.6m), model `9m18s` (probe: 9.4m), tool `2m15s` (probe:
  2.2m), **58 requests** (exact), **57,070 output tokens** (exact).

Every request-count and token-total figure matches exactly; every duration figure agrees to within
a few seconds (expected — the probe times off CC's own transcript-recorded user-prompt event,
`turns` off the proxy's own `_forwarded` send timestamp, two different but equivalent clocks on the
same underlying instants).

## What stayed untouched

`sessions`, `search`, `reqs`, `msgs`, `expand` were confirmed byte-identical before/after via
`git stash` on one real invocation of each (`reldist-power`) — none of their own render/discovery
functions were edited, only new functions added alongside them (`usage._resolve_session_transcript`
is a pure refactor of `build_usage_by_flow`'s existing preamble, re-verified against
`test_msgs_usage.py`'s full suite). All 12 suites under `dev/dual_log_cli/tests/` pass (215 checks
total, 38 of them new in `test_turns.py`).

## Relevant Symbols / Paths

- `timeline.turn_openers`, `_is_turn_opener`, `_turn_preview`, `build_turn_rows` (`src/dual_log_cli/timeline.py`)
- `usage._resolve_session_transcript`, `_transcript_stream_ends`, `build_request_times_by_flow` (`src/dual_log_cli/usage.py`)
- `render.render_turns`, `_turn_line`, `_fmt_duration`, `_fmt_tokens` (`src/dual_log_cli/render.py`)
- `_run_turns` (`src/dual_log_cli/__main__.py`)
- Ground truth: `api_requests_worker_1dda1c81_reldist-power_1788726467_*.jsonl` /
  `api_requests_worker_1dda1c81_k-ratio_1788698865_*.jsonl` under `src/logs/dual_log/`, joined
  against `~/.claude/projects/-Users-brunowinter2000-Documents-ai-trading--claude-worktrees-{reldist-power,k-ratio}/*.jsonl`
- Area: this same area's `2026-09-03_msgs_req_usage_join.md` — the sibling transcript join this
  feature's own join is modeled on, reading different fields off the identical transcript
