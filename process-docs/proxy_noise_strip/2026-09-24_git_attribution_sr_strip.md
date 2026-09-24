# Git-attribution system-reminder strip (2026-09-24)

## Problem
Claude Code injects a second system-reminder into the first user message (msg #0), after the env-context SR. It tells the model how to attribute git commits and PRs. It reached the model unchanged in main and worker sessions.

Observed 2026-09-24 via `duallog expand permcheck_1790253575 0` (worker): msg #0 has 3 text blocks. Block 0 is the env-context SR (already stripped), block 1 is the attribution SR (580 chars), block 2 is the task prompt. Same block seen in the main session opus_monitor_cc_1790241323 and in workers gapturn and bypass. Only the model name inside varies (Sonnet 5, Opus 5.5).

Block starts with: `Attribution for git commits and pull requests you create from here on (this replaces ...`

## Fix
One template in `_SR_TEMPLATES` in `src/proxy/strip_sr.py`:
`'git-attribution': ('Attribution for git commits and pull requests you create', 'full')`

- Prefix match only (`startswith` on the stripped inner text, like every template). Never match on the model name or on the Co-Authored-By line.
- No `_MARKER_TO_TEMPLATE` entry needed. The strip runs in `_apply_final_sr_pass`, which applies the full catalog to every `role=user` message in every session type. There is no main/worker gating anywhere in this path, so main and workers are covered by the same line.
- The block does not start with `_PRESERVE_PREAMBLE`, so that guard is irrelevant here.
- No `strip_vocab.py` change. Msg #0 changes are recorded as `stripped_all_sr_msg0` (code `ALL`, empty marker list), which is the same attribution the env-context block gets. Test ga01 asserts that mod, the removed chunk and the ops.
- `tool_result` safety is inherited: the SR family only scans top-level str/text blocks. A quoted copy inside a tool_result stays untouched (ga03, str and list forms).

## Tests
`dev/proxy/test_strip_fix_cases_git_attribution.py` (ga01-ga05), registered in `dev/proxy/test_strip_fix.py` as `_seq_git_attribution`. Run: `python3 dev/proxy/test_strip_fix.py` -> 322/322 passed.
Sanity: with `strip_sr.py` reverted, 5 checks fail (GA01 attribution stripped, GA01 removed-contains, GA02, GA04 main, GA04 gapturn), so the tests do exercise the fix.

## Rollout facts
- The main session's proxy runs a frozen copy under `src/logs/.proxy_live_<id>/proxy/`. A merge does not change it; restart the proxy or copy `strip_sr.py` into the live dir.
- Each worker's proxy is frozen at spawn. Workers spawned after the merge get the strip; existing workers do not.
- Verification (after merge, by the user): spawn a worker, `duallog expand <session> 0`, msg #0 block 1 should show "stripped by REQ 1". Not done in this session.

## Hint for the next agent
Another injected SR at msg #0 is handled the same way: add a prefix template, extend the existing template test file with the verbatim block, and check tool_result preservation. Do not add per-session logic.
