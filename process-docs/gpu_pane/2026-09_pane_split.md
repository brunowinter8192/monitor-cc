# src/gpu_pane/pane.py concern split (2026-09)

## Task

`pane.py` was 459 LOC (over the 400 ceiling), with `run_gpu_loop` at 136 LOC and `_render_pane` at
110 LOC (both flagged HARD — real multi-step extraction needed, not a single cut, to get under the
50-LOC function ceiling). Split by concern into sibling modules, byte-identical behavior.

## Investigation before implementing

Read every `.py` in `src/gpu_pane/`, `src/gpu_pane/DOCS.md`, `src/panes/token_pane.py` (the
established `_poll_*_input`/`_handle_*_mouse` shape from the panes-split milestone), and the three
required probes (`p8_warnings_gpu_news_parity_test.py`, `p3_button_click_probe.py`,
`p1_pane_loop_survives_exception_probe.py`). Grepped all three plus
`dev/click_ui/p4_gpu_news_button_probe.py` for `inspect.getsource` pins — none found (unlike the
prior panes-split milestone's `warnings_render._format_warnings_pane` conflict) — so no equivalent
literal-source-introspection constraint applied here.

**`p3_button_click_probe.py` was checked per the brief's own instruction ("may also reference gpu
names — check") and confirmed to have ZERO gpu references** (grep-confirmed) — it covers workers/
warnings/proxy only.

## Key finding: `_toggle_server`'s PRESET_NAMES dependency

`dev/click_ui/p4_gpu_news_button_probe.py` is not in the 3 required probes and not under
`dev/gpu_pane/` (which didn't exist before this milestone — the brief said to check it, it was
empty), but it is a real, currently-passing regression test living in `dev/click_ui/` that
extensively references gpu internals (`_render_pane`, `_toggle_state`, `_button_regions`,
`_fire_button`, `PRESET_NAMES`, `_toggle_server`). It calls `mod_gpu._toggle_server(idx, presets)`
— a 2-arg call — after monkeypatching `mod_gpu.PRESET_NAMES = [...]` directly. `_toggle_server`
reads `PRESET_NAMES[idx]` internally. Had `_toggle_server` moved to the new `gpu_actions.py` module
and imported `PRESET_NAMES` there separately (`from .status import PRESET_NAMES`), the
monkeypatch on `pane.py`'s own copy of the name would never reach it — the exact same staleness
class as the `build_cache_turns`/`cache_turns.py` and `_toggle_server`-signature risks already
catalogued in the panes-split milestone's own process-docs entry. **Resolution: `_toggle_server`
stayed physically in `pane.py`**, the one function in the "server control actions" concern that
did not move to `gpu_actions.py` — reported in the pre-Go plan, confirmed correct by Main at Go
("Keep p4_gpu_news_button_probe passing").

## What moved

`gpu_actions.py` (new, leaf module, no dependency on `pane.py`/`gpu_render.py`): `TOGGLE_TIMEOUT`,
`_toggle_state`, `_expire_toggle_states`, `_fire_button` — none of these three functions reference
`PRESET_NAMES`, confirmed by reading their bodies before moving them, so none carried the same risk
`_toggle_server` did.

`gpu_render.py` (new): every rendering helper (`_badge`, `_status_text`, `_format_countdown`,
`_button_label`, `_strip_ansi`, `_ANSI_RE`, `IDLE_TIMEOUT`, `_button_regions`) plus `_render_pane`
itself, split into one helper per section per the brief's own hint: `_build_status_row` (the
shared row-builder, parameterized by prefix/name_width/button/action/target — preset and arbitrary
rows were near-duplicates differing only in those 5 values), `_render_gpu_header`,
`_render_preset_rows`, `_render_arbitrary_rows`, `_render_collections_block`,
`_render_errors_block`, `_render_anomalies_line`, `_apply_gpu_search_highlight`. `_status_text`
needed `_toggle_state` — imported from `gpu_actions.py` (read-only in this module, no rebind).

`pane.py` kept: the event loop, `_toggle_server` (see finding above), the search wrappers
(`_gpu_search_on_commit`, `_jump_gpu_search_match`, `_render_gpu_search_bar` — matching the
panes-split precedent of keeping thin `SearchState`-coupled wrappers in the pane module itself,
since this pane has no substantial matching algorithm worth its own module the way
`token_search.py` did). `run_gpu_loop`'s inline `if button == 0: ...` block (the real-button-event
case only — release/cancel handling stayed inline in the poll loop, mirroring
`token_pane._poll_tokens_input`'s own precedent) became `_handle_gpu_mouse(button, col, row) ->
(input_changed, force_refresh_hit)`; the drain loop became `_poll_gpu_input(...)` (stays local —
monkeypatch constraint: `dev/pane_error_log/p1_pane_loop_survives_exception_probe.py` patches
`read_keypress` etc. as `pane.py` module attributes); the status+collections refresh became one
combined `_refresh_gpu_data(...)` (mirrors `token_pane._refresh_tokens_data`/
`warnings_pane._refresh_warnings_data`'s pattern — care taken that each section only overwrites
its own outputs when its own interval fires, since a naive helper resetting `anomalies`/
`today_errors`/`error_counts`/`collections` to `[]`/`{}` unconditionally at the top would have
silently wiped state on every tick where only ONE of the two intervals fired); the render+shift+
diff+print tail became `_build_gpu_output(...)`.

## Verification

New harness `dev/gpu_pane/render_byte_identity.py` (`dev/gpu_pane/` didn't exist before this
milestone): calls `_render_pane` with synthetic presets (healthy/unhealthy/stopped) + one
arbitrary server + toggle_state overlays (fresh + old-looking, set directly rather than via
`_toggle_server`) + 3 errors + 2 collections + 1 anomaly, at 2 widths, with and without a search
query, hashing `(output, _button_regions)` for all 4 combinations per width.
`time.time()` monkeypatched to a constant per the brief's explicit instruction — noted in the
harness's own docstring that no code path `_render_pane` actually calls currently reads it (kept
as a defensive guard rather than removed, since the instruction was explicit and the cost is
zero). Hash `e33158d622d325e1ece673c5afbfc79217c7dd3842b4243225a338df58a14a52` — identical before
and after.

3/3 required probes plus the extra `p4_gpu_news_button_probe.py` (not required, kept passing per
Main's explicit Go instruction) all passed unchanged after the split.

## Recap-time correction

The pre-Go plan and the task brief both said "Byte-identity harness `dev/gpu_pane/render_byte_identity.py`
(+ DOCS.md entry there)" — the script was created and verified during the task, but its
`dev/gpu_pane/DOCS.md` entry was missed in the task commit and written during recap instead.
