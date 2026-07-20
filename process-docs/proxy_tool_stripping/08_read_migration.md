# Proxy Pane Read-Migration — Yellow/Green Overlay (Phase 6)

Implementation completed 2026-06. Read-side of the four-log architecture: `_stripped`/`_injected`
dual-logs consumed by the main proxy pane to drive a yellow/green highlight overlay.

## Variante A (Augment), not B (Replace)

Two designs were considered:

- **Variante A:** MAIN log (`api_requests_<log_id>.jsonl`) stays as base; pane ADDITIONALLY reads
  `_stripped`/`_injected` and attaches span data to entries. All existing machinery — turn grouping,
  lazy-load, latency merge, subprocess parse, `scan_worker_logs` — untouched.
- **Variante B:** Cut to a new COMBINED log format; main log replaced; write-side and read-side
  land in the same change.

**A chosen.** Reuses proven machinery, minimal risk, no format-flag-day. The "CUT to new format /
write+read must land together" framing from the original issue was moot in practice: the dual-log
build was ADDITIVE (the main log was never removed), so the pane never breaks if `_stripped`/
`_injected` are absent. Graceful-degrade: when dual-log paths don't exist, `accumulate_dual_log`
returns immediately; entries receive no `_stripped_spans`/`_injected_spans` key; all render code
falls through to the existing side-channel (`else:` branch) — no crash, no overlay.

## Join Key

Main log and `_stripped`/`_injected` share `request_id` (UUID from `_build_entry` via
`mc_request_id`, same as 07_stripped_injected_logs.md). Both write-side hooks write in
response-completion order, so the per-family index is consistent. The pane joins by ATTACHING
the accumulated state dict to each newly-parsed entry by reference — no explicit per-rid lookup
needed post-attach (the reference IS the live join).

## Accumulator Design — In-Place Mutation Preserving References

Dual-logs are DELTA-encoded: stable strips (sys[2] CC-prompt, sys[3], msg[0] SR-blocks) are
suppressed after the first request per family. A single accumulator dict per `model_family` is
kept in pane-level state (`_proxy_acc_stripped` / `_proxy_acc_injected`, keyed by family).

**In-place mutation:** `accumulate_dual_log` MUTATES the accumulator in-place:
`is_first` → `.clear()` + `.update()` on the existing section dicts (NOT new-dict assignment).
This preserves the Python references held by previously-parsed entries. If new-dict assignment
were used instead, old entries would hold stale references to the previous accumulator state
and never see subsequent delta updates.

**Why references, not copies:** the injected sys[2] rules blob is ~130k chars per request.
With per-request copies across hundreds of entries, memory would grow to tens-to-hundreds of MB.
References share one live dict; all entries reflecting the current accumulated state is exactly
what rendering needs.

**State vars in pane.py:**
- `_proxy_stripped_pos` / `_proxy_injected_pos` — byte-position cursors for incremental reads
- `_proxy_acc_stripped` / `_proxy_acc_injected` — `{family: {section: {...}}}` accumulators
- Reset on session change: `.clear()` on all four state vars + zero the positions

**Attach in `_refresh_proxy_data`:** after `accumulate_dual_log` calls, each newly-parsed entry
gets `entry['_stripped_spans'] = _proxy_acc_stripped[family]` and
`entry['_injected_spans'] = _proxy_acc_injected[family]` (by reference). Entries without a
matching family key get a fresh empty accumulator seeded before attach.

## Sentinel Fallback — Bounded Scope

Render code uses `if '_stripped_spans' in entry:` as a sentinel:
- **New path:** full yellow/green overlay from span data
- **`else:` path:** existing side-channel (`stripped_original`, `stripped_msg_removed`,
  `stripped_unused_tools_names`) — MOVED behind the else, NOT deleted

The worker proxy pane (`scan_worker_logs` path, `worker_proxy_pane.py`) was NOT migrated in this
phase. Worker pane entries have no `_stripped_spans` → always take the `else:` branch → keep
existing behavior. This serves as a known-good parallel reference during verification.

This is a deliberate BOUNDED SCOPE decision, not a backward-compat path for old log sessions.
Old-log support was explicitly declared out of scope (monitor-cc old logs deleted at migration
start; wise2627/gh_cli proxies on separate ports untouched).

## Render Sections Migrated

**`render_system_blocks`** (render_sections.py): all blocks now covered by span lookup
`_stripped_spans['system'].get(str(bidx))` — no more hardcoded sys[2]/sys[3] index check.
Header colored DIM_YELLOW_BG/DIM_GREEN_BG/both based on whether s_spans/i_spans are set.
Expanded block shows description then yellow span block then green span block (stacked, not
interleaved).

**`render_tools`** (render_sections.py): three cases in new path:
1. `_injected_spans['tools'][name] = {'whole': true}` → proxy-INJECTED tool (e.g. MCP) →
   DIM_GREEN_BG header + `[INJECTED]`; description shown with green background
2. `_stripped_spans['tools'][name] = {'desc': [...]}` → description stripped → DIM_YELLOW_BG
   header + `[STRIPPED]`; yellow span block after description
3. `_injected_spans['tools'][name] = {'desc': [...]}` → description injected → DIM_GREEN_BG
   header + `[INJECTED]`; green span block after description
Whole-stripped extra rows (tools not forwarded): iterates `_stripped_spans['tools']` for
`{'whole': true}` entries not in `tools_names` → DIM_YELLOW_BG `[STRIPPED]` rows.
`deferred_tools_names` kept unconditionally — CC's own SR-block deferral, not from the diff
engine.

**`render_messages`** (render_messages.py): `use_dual = '_stripped_spans' in entry` flag.
Block-level yellow/green span appending after `if full_text:` in both branches (new-messages and
diff-range). Old `_render_stripped_block` calls guarded with `and not use_dual`. Pre-loops
for old stripped messages (range [fdi, prev_msg_count) and [fdi, diff_start)) guarded with
`and not use_dual` — old sessions skip gracefully.
**EFF:RULE attribution DROPPED in new path** — dual-logs store span texts only, no rule codes.
Out of scope per explicit user decision.

**`render_fields_delta`** (render_sections.py) — NEW function: collapsible header
`('fields', entry_idx)`; one line per changed field: yellow old value (stripped-only), green new
value (injected-only), yellow+green pair for replaced. No-ops when both fields dicts are empty
or when `_stripped_spans` not in entry. Covers model-override, max_tokens, output_config,
thinking. Wired in `render_turn.py` (the production expand path) ABOVE `render_system_blocks`.
Also wired in `render_entry.py` (no-turns fallback) after the divider line.

## Intra-Block Ordering

Yellow block then green block (stacked). Full-block replacements (sys[2], sys[3], whole tools,
msg[0] SR) are exact byte copies of the stripped/injected content. Partial within-block edits
(word-level, ratio ≥ 0.1) are space-joined words with normalized whitespace. Acceptable for a
monitor; not suitable for byte-exact reconstruction (documented in 07).

## Build Path — WIP Recovery

The original worker died at 4/6 files with work committed as WIP `27131f3`:
- Done: `constants.py` (DIM_GREEN_BG), `parser.py` (accumulate_dual_log, _find_dual_log_paths),
  `pane.py` (accumulator state + attach), `render_sections.py` (render_system_blocks sentinel;
  render_fields_delta was listed as done but absent from the commit)

A successor merged the WIP and completed:
- `render_messages.py` — use_dual sentinel + span appending both branches
- `render_sections.py` — render_fields_delta added (was missing from WIP)
- `render_turn.py` — render_fields_delta wiring before render_system_blocks
- `render_entry.py` — render_fields_delta wiring in fallback path

A Phase-4 review found render_tools unmigrated (still old side-channel only). A further commit
added the full use_dual sentinel to render_tools (in-array loop + extra-row block).

## Status

**Code-complete + reviewed + syntax-OK. LIVE-VERIFY PENDING** — requires monitor restart + a
fresh monitor-cc session with the proxy running.

**Open follow-ups:**
- count-30 janitor for `_stripped`/`_injected` logs (not in `_LOG_REGISTRY` / rotation script)
- Worker proxy pane migration (`scan_worker_logs` / `worker_proxy_pane.py`) — intentionally
  deferred; old side-channel still live there as known-good reference
