# news_pane — Implementation Trail

## Phase Plan Discussion

Architectural decisions made before implementation:

**log_parser.py as package constants anchor.** Both `pane.py` and `log_pane.py` need `SEARXNG_ROOT`, `LOG_DIR`, `LAST_RUN_FILE`, `TARGET_COLLECTION`. Putting them in `log_parser.py` avoids a separate `_config.py` and avoids circular imports — both panes import `log_parser` for parsing functions anyway, so constants ride along cleanly.

**No `_toggle_state` dict.** gpu_pane needs a dict because multiple servers can be toggling simultaneously and transitions are slow (30-90s model load). News pane has one pipeline. `_pipeline_proc` handle ownership is sufficient; the button region is simply not registered while running — no guard flag needed.

**NEWS-LOG pane uses plain `time.sleep`**, not `setup_keyboard_input`. No keyboard interaction in the log pane, so raw stdin is unnecessary. This means Ctrl+C delivers SIGINT cleanly to the signal handler in `startup.py`.

**Stage decomposition:** Window infra + skeleton (Stage 1) → log parser + log pane (Stage 2) → button + subprocess (Stage 3). Chosen so each stage produces a verifiable tmux window state.

## Stage 2 — Whitelist Bug

**Problem:** `filter_events()` produced 7 events instead of 9. The `[OK]` precondition lines were missing.

**Root cause:** `_LOG_LINE_RE` pattern `\s+(.*)`'s `\s+` group before the message capture group consumes ALL whitespace between the log level and the message. Log line `[2026-06-08 00:53:47] INFO   [OK] Internet reachable…` → `msg = '[OK] Internet reachable…'` (no leading spaces). The whitelist pattern `re.compile(r'  \[(OK|FAIL)\]')` expected two leading spaces that weren't there.

**Fix:** Changed to `re.compile(r'\[(OK|FAIL)\]')`. This matches the bracket at any position in `msg`, which is correct because `[OK]`/`[FAIL]` only appear as precondition check results.

**Lesson:** when `_LOG_LINE_RE` extracts `msg`, the message has NO leading whitespace regardless of log file indentation. Whitelist patterns must be written against the stripped message, not the raw log line.

## Stage 3 — Button Region Coordinate Verification

Button placed at end of a line using the gpu_pane pattern:
- `vis_len = len(_strip_ansi(content))` — visual width of prefix
- `pad = max(1, pane_width - vis_len - len(btn))` — fill to right edge
- `phys_row = len(lines) + 1` — 1-indexed physical row
- Region key: `(vis_len + pad + 1, vis_len + pad + len(btn), phys_row)`

Live verification at 120-wide pane: region `(107, 120, 7)`, `stripped[sc-1:ec] == '[run pipeline]'` exact match. The `sc-1` offset converts 1-indexed terminal column to 0-indexed string slice.

Subprocess verification: `_fire_pipeline()` → `poll() is None = True` → `terminate()` → `poll() = -15` (SIGTERM) → `_is_running() = False`. Confirmed the handle state machine works end-to-end.

## Post-Merge — Log Rendering Direction (User Follow-up)

First live end-to-end run (user-triggered) pulled 45 articles, indexed 37 (108 chunks) into `searxng_crypto`. Button + subprocess + live log all confirmed working against a real run.

**Change:** `_render_log_pane()` initially pinned events to the pane BOTTOM (blank padding above, events sticking to the bottom edge). User wanted top-down growth. Removed the top-padding loop — events now render directly under the header + filename line and grow downward; on overflow the oldest drop and the newest stay visible, still top-anchored (`recent = events[-MAX_LOG_LINES:][-max(1, available):]`). Single-function change, no logic touched beyond padding removal.
