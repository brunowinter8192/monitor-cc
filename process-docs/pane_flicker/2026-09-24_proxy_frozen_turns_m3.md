# Proxy and worker-proxy panes: frozen turn groups (M3), 2026-09-24

## Problem
Every hover motion event (button >= 32) returns "changed" and triggers a full `_build_proxy_output()`. `format_proxy_block` re-rendered every entry of every turn, re-assigned entries to turns (O(entries x turns)) and rebuilt the request-number/time maps (`request_times_by_id` calls `format_timestamp` per API call: astimezone + strftime). Measured on the real 297-entry log: 8.2 ms per `format_proxy_block`, 11.7 ms per `_build_proxy_output`; on a synthetic 10x replication (2970 entries) 97.7 ms and 126 ms.

## Design (src/proxy_display/frozen_turns.py, turn_cache.py)
`format_proxy_block(..., turn_cache=None)`. Without a cache it builds a throwaway `TurnCache`, so there is one code path. Each pane owns a `TurnCache` and clears it in its `_reset_*positions`.

Per render: assign groups (see below), compute the flow maps (cached by the tuple of turn identities), then one pass over all entries computing (a) the REQ label with the same running `label_counts` as `_req_label`, (b) the time string, (c) a per-entry fingerprint. A group is re-rendered via the unchanged `render_turn_expanded` (new optional argument `labels` skips the label computation) only if its fingerprint differs from the cached record. If every record is the same object as last time, the flattened lines, keys, item positions, collision set and prefix counts are reused. Then slice viewport and `_apply_row_backgrounds` (hover, zebra, copy rows) on the visible slice only.

Fingerprint inputs, and why each is there (all observed data paths, see the late-data table):
- pane width, `copy_feedback is None`, turn index, `(id(turn), len(api_calls))` for the header.
- per entry: `id(entry)`, label (this also covers the `REQ #N.k` suffix that depends on earlier turns), time string, `http_status` presence and value, `badge_flags(entry)`, `messages_total_chars`, search (is match, is current, query only if match), the set of currently flashing copy-feedback keys of that entry, the frozenset of truthy expand keys of that entry.
- only for entries whose `('req', idx)` is expanded: `overlay_epoch()`, `id`/`len` of `messages` of the entry and of its `prev_same`, `id(prev_same)`.

Late-data table (what can change a finished turn's output):
| Source | Detection |
|---|---|
| request number / time arriving via `_response` join | label and time string in fingerprint |
| `http_status` (`_attach_http_status`, every refresh) | presence and value |
| strip/inject badge (per-flow lookup dicts in the shared accumulator, also cleared by `is_first`) | `badge_flags` for every entry |
| overlay spans in expanded REQs (accumulator dicts shared by reference, overwritten per message index by later log lines) | module-level `overlay_epoch()` in `dual_log_accumulator`, bumped per processed line of `accumulate_dual_log` and `accumulate_original_tools`; only expanded groups react |
| lazy-loaded `messages`, `_strip_inactive_messages`, search reconstruction | `id`/`len` of messages (entry and prev_same) for expanded entries, `messages_total_chars` for all |
| growing last turn | turn dict identity plus call count. `build_cache_turns` never mutates turn dicts, the merged last turn is a new dict |
| hourly reparse, session/worker switch | entries are new objects (id differs) plus explicit `TurnCache.clear()` |

Entry fields `stripped_msg_removed`, `modifications` etc. are never set after parsing (the forwarded parser only writes empty defaults), so they are not fingerprinted.

## Decisions under the fallback/tripwire rule
- Unclassifiable expand or feedback key: `_key_entry_idx` raises `ValueError`, no full-render fallback. The pane loop's `log_pane_error` catches it. Recognized shapes: int, `(str, int, ...)`, `(int, ...)`.
- Turn timestamp order: entry timestamps were sorted in all 8 forwarded logs and are irrelevant to bisect anyway. Turn timestamps were unsorted in 4 of 435 transcripts (gh-cli project, a `/clear` pair a few ms apart: `...38.781Z` before `...38.779Z`). So both paths exist: `bisect_right` on the timestamps when they are nondecreasing, otherwise the original `_assign_turns_to_entries`. The chosen path is logged with `log_pane_note` (`/tmp/monitor_cc_error.log`, `[proxy] note: turn assignment path: ...`) at first use and on every change.
- No version-stamp shortcut. Measured after implementation: hover 0.82 ms (297 entries) and 5.6 ms (2970 synthetic) in `format_proxy_block`, dominated by the fingerprint pass (~2 us per entry). Add change flags in the pane loops only if hover under 1 ms at several thousand entries is required.

## Tests (dev/pane_flicker/)
`run_scenarios.py`: 10 scenarios plus tripwire, old tree = `git archive` of the pre-M3 commit at `/tmp/pf_old` (must be extracted first), new = working tree, run as parallel processes. The data is a real quartet (`api_requests_opus_monitor_cc_1790241323`, 297 entries, 3.3 MB forwarded); the `_original` log is 425 MB so only its last 2 lines are used; turns are synthetic (7 entries per turn, request ids from the `_response` log). Every step hashes body, line_map, copy rows, scroll AND a second render with height 100000 (full output). The full hash is required: with the viewport only, stale off-screen turns were invisible (a removed fingerprint part passed).
Negative controls (each fingerprint part removed, scenario must fail): http_status/badge_flags fails late_response and late_overlay; the overlay epoch only fails once expanded entries sit inside the lagging window (`('req',150)`..`('req',197)` in late_overlay). That is an observed mechanism (accumulator entries overwritten by later lines), the scenario now covers it.
Observed group-render counts: hover 0; new entry / new turn 1; expand or collapse 1; late response burst re-renders every group whose entries got a response (29 of 43 at the first burst); overlay lag steps 3-5 groups; width change and warm render all groups.
Existing checks unchanged: `render_byte_identity.py` hash `d19681d9...` before and after, `test_req_prefix_turn_headers.py` 55 PASS, `test_standalone_sidecar.py` 8 PASS.

Timing (`bench_hover_render.py`, median of 30 hover rows, sequential runs, pane mode inside `tmux -L pfbench` because `_terminal_size` needs a tty):
| data | old block | new block | old pane | new pane |
|---|---|---|---|---|
| real, 297 entries, 43 turns | 8.2 ms | 0.82 ms | 11.7 ms | 1.28 ms |
| synthetic x10 (copied entries, fresh flow ids, no overlays for copies) | 97.7 ms | 5.6 ms | 126 ms | 6.2 ms |
Nine expanded old keys did not change the new numbers.

## Combined state with the flicker worker's M1+M2 (merge 8e0d0db9)
The merge of integration (480e6098) into this branch had no conflicts. `run_scenarios.py` on the combined tree: PASS. `m1_frame_e2e_test.py` as shipped compares against `git archive integration`; since integration now already contains M1 its harness-sanity check "old tree emits clear-screen" fails for all four panes (88/92, the four failures are exactly that check). Re-run with `OLD_REF='0ce370df'` (pre-M1, pre-M3 commit, patched via a small wrapper, report file restored afterwards): 92/92 checks passed. Hypothesis, not tested: the shipped test needs `OLD_REF` pointing at a pre-M1 commit from now on.

## Gotchas for a successor
- A hook rewrote `from ..x` in a heredoc-written file into `from ../x`; write new modules with absolute `from src.x import y` (also the code standard).
- Piping a python run into `tail` is blocked by a hook, redirect to a file.
- `_parse_forwarded_log` restarts `req_idx` at 0 on every call; harmless, same in old and new.
- Circular import: `format.py` imports `frozen_turns` lazily inside `format_proxy_block` because `frozen_turns` imports helpers from `format`.
