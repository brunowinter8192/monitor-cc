# 13 — Worker Pane Dual-Log Migration

## What we did

Brought `worker_proxy_pane.py` to parity with `pane.py` for the yellow/green strip/inject overlay.

The main pane (`pane.py`) was already migrated: it reads per-session `_stripped`/`_injected` dual-logs via `accumulate_dual_log`, builds per-family accumulator dicts, and attaches `_stripped_spans`/`_injected_spans` references to every parsed entry. The renderer (`render_messages.py`, `render_sections.py`) gates on `'_stripped_spans' in entry` — overlay fires automatically for any entry carrying those keys.

The worker pane (`worker_proxy_pane.py`) lacked the accumulator state and the attach loop entirely.

## What we found

**Investigation (Step 1) — 4 questions:**

1. **Renderer already gated** — confirmed. `render_messages.py:97`, `render_sections.py:26`, `render_sections.py:130`, `render_sections.py:274` all use `'_stripped_spans' in entry` (or `use_dual` derived from it). No renderer change needed.

2. **Only missing piece** — confirmed. The delta between `pane.py` and `worker_proxy_pane.py` was exactly: 4 module-level state vars + their resets in both reset blocks + the accumulate+attach loop inside `if log_path:`.

3. **`_find_dual_log_paths` produces correct names** — confirmed. Worker log path `…/logs/api_requests_worker_<sid>_<name>_<ts>.jsonl` → `_find_dual_log_paths` derives `…/logs/dual_log/api_requests_worker_<sid>_<name>_<ts>_stripped.jsonl` and `…_injected.jsonl`. Exact match to on-disk files. No write-side work needed.

4. **Divergences** — all handled cleanly:
   - Worker pane has TWO reset blocks (worker-change + time-triggered reparse vs main pane's one session-change reset). Both now zero/clear all 4 dual-log vars.
   - Worker pane uses `new_entries` directly (no session-start timestamp filter like main pane's `filtered`). Attach loop iterates `new_entries`.
   - Dual-log calls placed INSIDE `if log_path:` block (not unconditional like main pane) — clean graceful degrade when no worker log found.
   - Family seeding (`if family not in _worker_proxy_acc_stripped`) ensures entries get a valid dict ref even when dual-log has no record for that family yet.

## Implementation

`src/proxy_display/worker_proxy_pane.py` — 32 lines added, no other files changed.

Changes:
- Import: added `accumulate_dual_log`, `_find_dual_log_paths`, `_infer_model_family` to `.parser` import
- Module state: `_worker_proxy_stripped_pos`, `_worker_proxy_injected_pos`, `_worker_proxy_acc_stripped`, `_worker_proxy_acc_injected`
- `_refresh_worker_proxy_data` global declaration extended
- Worker-change reset block: 4 vars zeroed/cleared
- Time-triggered reparse reset block: same 4 vars zeroed/cleared
- Inside `if log_path:`, after `worker_proxy_entries.extend(new_entries)`: `_find_dual_log_paths` → `accumulate_dual_log` × 2 → family-seeded attach loop over `new_entries`
- `_worker_proxy_ram_state`: 4 new vars added

## Smoke result

Real log pair: `api_requests_worker_25c51a2e_fn-materialize_1780535555.jsonl` + dual-log pair in `src/logs/dual_log/`.

- 70 entries parsed
- `_find_dual_log_paths` derived exact paths; both files confirmed present
- All 70 entries carry `_stripped_spans` / `_injected_spans` after attach loop
- All 70 have non-empty spans (families: haiku, sonnet; sample entry[1] sonnet: `system:2, tools:9, messages:18, fields:3`)

## dev/ scripts

None — investigation was pure code-read; attach-logic proof was a one-shot heredoc smoke against real data, no permanent dev/ artifact needed.

## Commit

`8495da8` — `feat: mirror dual-log span attach to worker proxy pane`
