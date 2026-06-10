# LOC-Refactor Campaign

Process record for the codebase-wide LOC-ceiling cleanup driven by the `iterative-dev-refactor`
scan (2026-06-09). Clears files >400 LOC (hard ceiling) and functions ≥100 LOC. Distinct from
`refactor_roadmap.md` (that tracks FUNCTIONAL refactors — menubar/blank/logging-janitor/dolt).
This campaign is purely structural, behavior-preserving.

## Scan Baseline (2026-06-09, pre-campaign)

**File HARD (>400 LOC):** `proxy/rules.py` 628, `proxy_display/parser.py` 530, `proxy/logging.py` 468,
`menubar/app.py` 461, `menubar/queue_controller.py` 448, `proxy_display/worker_proxy_pane.py` 426.

**Function HARD (≥100 LOC, top):** `render_messages` 209, `_render_entry_lines` 193,
`_build_stripped_injected_deltas` 190, `run_main_loop` 179, `format_cache_tracker` 177,
`apply_modification_rules` 123 … (14 total ≥100).

Scan also surfaced 10 doc-drift findings (→ issue) and 3 silent-fallback (2.8) candidates (→ debugging-hell work below).

## Debugging-Hell Predecessor Work (2.8 findings)

Done BEFORE the LOC splits — the silent-fallback / redundant-derivation candidates. Methodology:
prove redundancy (which route is primary, classify each fallback as (a) dead / (b) live-redundant /
(c) live-masking), then eliminate. No dev/-equivalence-proof (the existing routes already work; we
decide one canonical route and delete the rest). User decision: a monitor must not carry a fallback
that masks a normal-operation failure.

- **`parser.py:find_worker_proxy_log`** — 3 routes → 1. Route 3 (legacy pre-Stage-3 main-log glob)
  and Route 2 (unprefixed forwarded glob) proven (a) DEAD: writer always session-id-prefixes worker
  logs (`tmux_spawn.sh:422`, `md5(project_root)[:8]` = same formula as reader `parser.py:22`); caller
  never invokes with empty `project_filter`. Collapsed to the single prefixed route. See
  `proxy_tool_stripping/18_worker_log_route_consolidation.md`.
- **`gpu_pane/status.py:_discover_preset_names`** — hardcoded `['embedding','reranker','splade']`
  fallback on rag-cli failure proven (c) MASKING (already drifted: real presets are 6 versioned names,
  only `splade` overlapped). Removed → returns `[]` on failure; pane shows empty preset block, no
  fabricated names (mirrors `_fetch_collections`). Also removed the GPU-pane footer legend. See
  `gpu_pane_collections.md` + `decisions/gpu_pane_collections.md`.
- **`menubar/discover.py`** — flagged by textual scan but reviewed as a FALSE POSITIVE: the worker-name
  fallback is documented graceful degradation (lossy name only when cwd unreadable, no aliveness impact);
  the status detection is a priority cascade (hook→JSONL→proxy), not redundant derivation. Left untouched.

## File Splits Done This Session

All behavior-preserving. Workers merged onto `dev`; each split independently verified by Opus.

### `proxy/logging.py` 468 → 235

Split the stripped/injected-delta concern into new `proxy/strip_inject_delta.py` (280 LOC). The
190-LOC `_build_stripped_injected_deltas` decomposed into 4 pure-return section helpers
(system/tools/messages/fields) + ~50-LOC orchestrator, merged via `{**a,**b}` (disjoint loc_key
prefixes → order-independent). Shared helpers `_strip_cache_control`/`_normalize_msg_shape_for_hash`/
`_delta_hash` stay in logging.py, imported one-directional by the new module. Verify: Stage-1 verbatim
move AST-identical (`ast.dump` hash); Stage-2 differential — Stage-1 vs Stage-2 byte-identical 8-tuple
over 240 real requests (4 log pairs, ≤85 MB).

### `proxy/rules.py` 628 → 119

Two new modules: `message_passes.py` (385, the 8 `_apply_*` passes + `_dedup_wakeup_blocks`),
`rule_ops.py` (70, op-recording helpers — neutral leaf to avoid rules↔passes cycle). Orchestrator
`apply_modification_rules` 124 → ~52: the 8 near-identical per-pass blocks collapsed to a loop over a
`_passes` list (`_dedup_wakeup_blocks` 2-tuple + `_apply_system_passes` special-cased after; 8-tuple
return + early-return preserved). `_strip_blocked_tool_references` re-export to addon.py preserved.
Dropped dead imports `_strip_tool_descriptions`/`_strip_sys3`; restored a pre-existing broken test
(`dev/proxy/test_strip_fix.py` W01-W06, stale 5-tuple unpack → 6). Verify: `test_composition_invariant.py`
12/12 before+after each stage (fixture-based) + differential 8-tuple+`_all_ops` byte-identical over 9
fixtures; Opus re-ran the invariant on merged dev independently (12/12, ALL PASS).

### `proxy_display/worker_proxy_pane.py` 426 → 382

State constraint: 23 module-level variables mutated via `global` across 5 functions
(`run_worker_proxy_loop`, `_handle_worker_proxy_mouse`, `_handle_worker_proxy_key`,
`_refresh_worker_proxy_data`, `_build_worker_proxy_output`). Two further functions read state
without `global` (`_serialize_worker_proxy`, `_worker_proxy_ram_state`). All 7 must stay in
`worker_proxy_pane.py`. The 4 remaining functions are pure (all inputs via parameters, no `global`,
no module-state reads): `_format_worker_proxy_header`, `_wp_entry_idx_from_key`,
`_resolve_prev_same_wp`, `_strip_inactive_wp_messages`. These 4 moved verbatim to new
`worker_proxy_helpers.py` (55 LOC). State ownership unchanged — 100% stays in `worker_proxy_pane.py`;
no `global` semantics are affected. Verify: all 4 functions AST-identical (`ast.dump` hash pre/post);
import smoke on all `proxy_display` modules + `__init__` entry point — all OK.

### `proxy_display/parser.py` 512 → 239

Forwarded-reconstruction concern (8 functions incl. `_infer_model_family` + `_proxy_session_id_for_project`)
moved to new `forwarded_parser.py` (287, clean leaf). `parser.py` re-exports the moved symbols →
ZERO caller edits (pane/worker_proxy_pane/format/__init__/warnings_pane/token_pane). Verify: all 8
moved functions AST-identical (verbatim); import smoke on all callers; live parse of a real
`_forwarded.jsonl` (217 entries, fields OK). NOTE: first attempt (reused worker) died at 4% context
with "Prompt is too long" mid-edit, uncommitted+botched → killed, fresh worker re-ran the (already-
converged) plan from dev. Fresh worker initially duplicated `_proxy_session_id_for_project` (leaf can't
import from parser); corrected to single-source-in-leaf + re-export (same pattern as `_infer_model_family`).

## Methodology Notes

- One file per worker; fresh worker for orthogonal-concept files, reuse for same-file follow-ups.
- Staged execution for multi-part refactors (e.g. logging/rules: Stage-1 in-place change → verify →
  Stage-2 split → verify), each stage independently committable.
- Byte-exact verification is mandatory for the proxy delta/modification files: AST-identity proves
  verbatim moves; differential tests (pre vs post on real data) prove non-verbatim restructures;
  `dev/proxy_dual_log/{test_composition_invariant,composition_probe}.py` are the byte-critical harnesses
  (fixture-based, no live logs needed). `verify_strip_inject.py` has a pre-existing `KeyError: 'spans'`
  crash (out of scope) — use the invariant/differential instead.

## Render-Cluster Function Splits (stages 1–5 on dev)

Five proxy_display render functions decomposed into orchestrators + private same-module helpers.
Stages committed `676c2ae`..`b2f5b96`, merged `6fa9e6c`.

| Function | File | Before | After (orchestrator) | Helpers |
|---|---|---|---|---|
| `render_messages` | render_messages.py | 210 LOC | 12-LOC orchestrator | `_render_stripped_block` 45, `_render_block_spans` 60, `_render_new_messages` 40, `_render_modified_messages` 56 |
| `_render_entry_lines` | render_entry.py | 194 LOC | 74-LOC orchestrator | `_compute_entry_warnings` 37, `_render_entry_delta` 64, `_render_entry_msg_list` 28 |
| `render_tools` | render_sections.py | 169 LOC | 63-LOC orchestrator | `_render_tool_dual` 69, `_render_tool_legacy` 52 |
| `render_turn_expanded` | render_turn.py | 141 LOC | 48-LOC orchestrator | `_compute_req_delta_str` 19, `_compute_req_mods_str` 12, `_build_req_header_line` 27, `_render_req_expanded` 34 |
| `format_proxy_block` | format.py | 129 LOC | 68-LOC orchestrator | `_assign_turns_to_entries` 15, `_render_entries_no_turns` 27, `_apply_row_backgrounds` 33 |

**Verification:** `dev/proxy_dual_log/A_render_refactor_proof.py` — 14 cases covering all 5 targets
transitively via `format_proxy_block` entry point; 14/14 byte-identical against
`A_render_refactor_proof_reports/baseline_20260610.json`. All orchestrators below 100 LOC; all
helpers private to their module (no cross-module exports added).

**Process notes:** Two predecessor workers died at the context wall during this cluster; staged
commits made recovery lossless (each stage independently committable). Stage-0 (`676c2ae`)
established the harness + baseline capture. Predecessor-2 committed all 5 stage refactors
(`bdda986`..`b2f5b96`) and ran final 14/14 verify before dying; Opus merged the branch (`6fa9e6c`).
Docs completion (this section + DOCS.md LOC sync) deferred to successor worker.

## Remaining HARD Files

- `menubar/app.py` (461) + `menubar/queue_controller.py` (448) — entangled with the menubar
  controller-composition refactor (`refactor_roadmap.md` stage 1, Queue "in flight"). Address those via
  THAT campaign, NOT a standalone LOC-split, to avoid merge collision.

**Remaining function-HARD (≥100 LOC):**
- `run_main_loop` 180 (`src/core/monitor.py`)
- `format_cache_tracker` 178 (`src/format/token_format.py`)
- `_strip_impl` 147 (`src/hooks/_shell_strip.py`)
- `extract_cache_turns` 128 (`src/jsonl/jsonl_cache_turns.py`)
- `request` 127 (`src/proxy/addon.py`, class method col=4) — BYTE-CRITICAL
- `_rebuild_inner` 154 (`src/menubar/queue_controller.py`) — separate block, falls with queue_controller file split (menubar campaign)
