# RS Pass Content-Blind Nuke of Read-Truncation Notices, 2026-07-21

Sibling of the other entries in this folder — SAME class (over-broad strip destroys content it shouldn't), DIFFERENT direction: here the strip was correct on delivery until an upstream CC version change introduced a NEW content class through the SAME delivery channel.

## Symptom

CC 2.1.205 introduced a Read-truncation notice — a plain `role='system'` string starting with `[Truncated: PARTIAL view — <path>: showing lines X-Y of Z total (…tokens, cap …). Call Read with offset=… …]` — telling the agent a `Read` call returned only a partial view of a file. `_apply_role_system_strip` (`src/proxy/message_passes.py`) replaces the content of EVERY `role='system'` message with `"."` unconditionally. Prior to CC 2.1.205, role=system content was always pure noise (deferred-tools list, date-changed, agent-types, skills) so blanket-nuking was correct. Post-2.1.205 the same pass also nukes the truncation notice, so the agent silently works on a partial file as if it were complete — no crash, no error, just wrong downstream reasoning about file contents.

## Root cause — confirmed via dual-log replay

Measured against `src/logs/dual_log/api_requests_opus_trading_1784579551_original.jsonl`: the truncation notice arrives EXCLUSIVELY as a standalone `role='system'` message whose `content` is a plain string starting with the literal `[Truncated:`. In that log: 1 unique truncation-notice body, resent across 23 requests as conversation history replays (not 23 distinct notices — CC resends full history each turn). The other `role='system'` string bodies observed in the same log were `The following deferred tools are now available…` (deferred-tools) and `The date has changed…` (date-changed) — both correctly still noise, both correctly still nuked.

## Fix

Added a preserve-guard in `_apply_role_system_strip`, mirroring the `_PRESERVE_PREAMBLE` pattern in `strip_sr.py` (content-anchored preserve-exemption inside a strip):

- `_TRUNCATION_NOTICE_MARKER = "[Truncated:"` (module constant).
- Guard placed before the `.`-nuke, after the existing empty/already-`.` idempotency guard: `if isinstance(old_content, str) and old_content.startswith(_TRUNCATION_NOTICE_MARKER): result.append(msg); continue`.
- Deliberately `startswith` on the prefix, NOT a substring `in` check — anchoring on the exact prefix avoids a false-positive on a doc/tool_result that merely quotes the marker (the same FP-nuke class documented elsewhere in this folder for `bg_launch_ack_anchor.md` and `plan_mode_branch.md` — substring-anywhere matching is the recurring root cause across this whole class of bugs).

## Downstream attribution — confirmed no separate change needed

`strip_inject_delta.py`'s `RS` attribution code path (role=system → code `'RS'`) only executes inside a `block_diffs` entry, which is only produced for blocks whose stripped content differs from the original. A preserved (unchanged) truncation-notice message produces `old_content == new_content`, so no diff entry is ever generated for it upstream — the attribution branch is structurally unreachable for preserved messages. `strip_vocab.py`'s `'RS'` entry is a passive code→rule-name lookup, never invoked absent a diff. Both files confirmed unchanged.

## Verification — paper/replay only, this session

Replay script `dev/tool_use_analysis/rs_truncation_preserve_replay.py` ran the real `_apply_role_system_strip` against every request's real logged messages in the dual-log file above: 23/23 truncation-notice occurrences passed through byte-identical (still starting with `[Truncated:`), 71/71 noise role=system messages (deferred-tools, date-changed) still reduced to `"."`, 0 failures. `py_compile` clean on `message_passes.py`.

Live-verify (real proxy restart, real CC session hitting a genuine large-file Read) is deferred to a next session — this session's proof covers the pass logic against real historical payloads, not the live routing/proxy-restart path.
