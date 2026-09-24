# dev/click_ui/

## Role
Regression coverage proving every tmux-pane control is reachable by synthetic mouse click, not
just keyboard: worker selection, copy-by-click, pane-chrome buttons, and per-server digit-key
parity. Touch it when adding or changing a click region, a chrome button, or a `_handle_*_mouse`
dispatcher.

## Public Interface
No `__init__.py` in this directory. Each `pN_*.py` script is its own entry point, run directly,
e.g. `python3 dev/click_ui/p1_worker_selection_click_probe.py`.

## Flow
Synthetic pane entries/worker lists/coordinates go in. Each `pN_*.py` seeds a real pane module's
globals directly and calls its real `_build_*_output`/`_handle_*_mouse`/`_handle_*_key` functions
— no live tmux, terminal, or OS-level mouse/keyboard event involved anywhere in this directory.
Output is stdout PASS/FAIL plus a timestamped report under `md/`.

## Modules

### p1_worker_selection_click_probe.py (260 LOC)

**Purpose:** Proves both worker panes' header click-region tables contain one entry per worker
and a synthetic click matches the corresponding digit key's state change.
**Reads:** nothing external — seeds `_worker_proxy_workers`/`_worker_tokens_workers` directly.
**Writes:** `md/p1_worker_selection_click_probe_<timestamp>.md`; throwaway IPC selection files
under `/tmp/monitor_cc_selected_worker_<hash>.txt`, removed after each check.
**Called by:** none — run manually; re-run after any change to `worker_switch_header.py` or
either pane's `_handle_*_mouse`/`_handle_*_key`.
**Calls out:** `src.proxy_display.worker_proxy_pane`, `src.workers.worker_tokens_pane` — loaded
via `importlib.import_module`.

---

### p2_copy_click_probe.py (224 LOC)

**Purpose:** Proves each pane's copy-row registry has an entry per copyable row and a click on
the symbol column copies exactly what the `y` key copies.
**Reads:** nothing external — seeds `_cache_turns`/`tool_errors`/`_worker_tokens_turns`;
`copy_to_clipboard` is monkeypatched to a capturing stub.
**Writes:** `md/p2_copy_click_probe_<timestamp>.md`; one throwaway IPC selection file, removed
after the check.
**Called by:** none — run manually; re-run after any change to `append_copy_symbol` or any
pane's `_handle_*_mouse`/`_handle_*_key`.
**Calls out:** `src.panes.token_pane`, `src.format.token_format`, `src.panes.warnings_pane`,
`src.panes.warnings_render`, `src.workers.worker_tokens_pane`, `src.utils` — loaded via
`importlib.import_module`.

---

### p3_button_click_probe.py (220 LOC)

**Purpose:** Proves the warnings `[refresh]` chrome button and the proxy pane's permanent
search-bar header both dispatch clicks identically to their keyboard equivalents.
**Reads:** nothing external — seeds `tool_errors`/`proxy_entries` directly.
**Writes:** `md/p3_button_click_probe_<timestamp>.md`.
**Called by:** none — run manually; re-run after any change to `_format_warnings_header` or
`_build_proxy_output`/`_handle_proxy_mouse`/`_undo_proxy_expand`.
**Calls out:** `src.panes.warnings_pane`, `src.panes.warnings_render`, `src.proxy_display.pane`,
`src.proxy_display.format` — loaded via `importlib.import_module`.

---

### p4_gpu_news_button_probe.py (273 LOC)

**Purpose:** Proves gpu's per-server button matches its digit key's subprocess call, and both
gpu/news `[refresh]` header buttons dispatch and yield to no other region.
**Reads:** nothing external — seeds synthetic preset/status dicts; `PRESET_NAMES` and
`subprocess.Popen` are monkeypatched.
**Writes:** `md/p4_gpu_news_button_probe_<timestamp>.md`.
**Called by:** none — run manually; re-run after any change to either pane's `_render_pane`,
`_toggle_server`, `_fire_button`, or `_fire_pipeline`.
**Calls out:** `src.gpu_pane.pane`, `src.news_pane.pane` — loaded via `importlib.import_module`.

---

### p5_proxy_message_copy_click_probe.py (86 LOC)

**Purpose:** Entry point orchestrating the message/thinking/block copy-granularity suites from
their own modules and writing the combined report.
**Reads:** nothing external.
**Writes:** `md/p5_proxy_message_copy_click_probe_<timestamp>.md`.
**Called by:** none — run manually; re-run after any change to `render_messages.py`'s row-build
sites or `proxy_pane_shared`'s serializer functions.
**Calls out:** `proxy_copy_probe_shared.py`, `proxy_copy_message_probe.py`,
`proxy_copy_thinking_probe.py`, `proxy_copy_block_probe.py`.

---

### proxy_copy_probe_shared.py (58 LOC)

**Purpose:** Shared fixtures for the P5 suite — module handles, `check()`/`_RESULTS`,
`_patch_clipboard`, `_make_entry`, `_render_expanded`.
**Reads:** nothing external.
**Writes:** nothing — mutates the shared `_RESULTS` list the entry script reads.
**Called by:** `p5_proxy_message_copy_click_probe.py`, `proxy_copy_message_probe.py`,
`proxy_copy_thinking_probe.py`, `proxy_copy_block_probe.py`.
**Calls out:** `src.proxy_display.pane`, `src.proxy_display.worker_proxy_pane`,
`src.proxy_display.format`, `src.proxy_display.proxy_pane_shared` — loaded via
`importlib.import_module`.

---

### proxy_copy_message_probe.py (114 LOC)

**Purpose:** Message-row copy granularity — key registration, click/serializer parity,
click/copy dispatch, width guard.
**Reads:** nothing external — seeds a synthetic multi-block message via the shared `_make_entry`.
**Writes:** nothing.
**Called by:** `p5_proxy_message_copy_click_probe.py`.
**Calls out:** `proxy_copy_probe_shared.py`.

---

### proxy_copy_thinking_probe.py (127 LOC)

**Purpose:** Thinking-block copy granularity — key registration, click/serializer parity, the
non-copy-click-still-toggles-expand regression, width guard.
**Reads:** nothing external — seeds a synthetic thinking-block entry.
**Writes:** nothing.
**Called by:** `p5_proxy_message_copy_click_probe.py`.
**Calls out:** `proxy_copy_probe_shared.py`.

---

### proxy_copy_block_probe.py (127 LOC)

**Purpose:** Generic-block copy granularity — key registration, click/serializer parity nested
in message and REQ copies, the non-copy-click-is-a-no-op regression, width guard.
**Reads:** nothing external — reuses the shared `_make_entry`.
**Writes:** nothing.
**Called by:** `p5_proxy_message_copy_click_probe.py`.
**Calls out:** `proxy_copy_probe_shared.py`.

---

## State
No persistent state lives in this directory. Each `pN_*.py` script mutates its target pane
module's real globals in-process (cleared and re-seeded per test) and discards them at exit;
`proxy_copy_probe_shared.py` owns the one piece of shared in-process state, `_RESULTS`, mutated
by every P5 sub-module's `check()` call and read by `p5_proxy_message_copy_click_probe.py`.
