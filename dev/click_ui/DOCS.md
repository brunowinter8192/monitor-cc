# dev/click_ui/

## Role
Regression coverage proving every tmux-pane control is reachable by synthetic mouse click, not only by keyboard: worker selection, copy-by-click, chrome buttons and per-server key parity. Touch when adding or changing a click region, a chrome button or a mouse dispatcher.

## Public Interface
No `__init__.py`. Each `pN_*.py` script is its own entry point, e.g. `python3 dev/click_ui/p1_worker_selection_click_probe.py`.

## Flow
Synthetic pane entries, worker lists and coordinates go in. Each script seeds a real pane module's globals in-process and calls its real output builders and mouse and key handlers; no tmux, terminal or OS event is involved. Output is stdout plus a timestamped report under `md/`.

## Modules

### p1_worker_selection_click_probe.py (262 LOC)

**Purpose:** Proves both worker panes' header click regions have one entry per worker and a click matches the digit key's state change.
**Reads:** nothing external; seeds worker lists directly.
**Writes:** `md/p1_worker_selection_click_probe_<timestamp>.md`; throwaway selection IPC files under the temp dir, removed per check.
**Called by:** none; re-run after worker header or handler changes.
**Calls out:** `src.proxy_display.worker_proxy_pane`, `src.workers.worker_tokens_pane` via `importlib`.

---

### p2_copy_click_probe.py (225 LOC)

**Purpose:** Proves each pane's copy-row registry has an entry per copyable row and a symbol-column click copies exactly what the key copies.
**Reads:** nothing external; seeds pane data, clipboard stubbed.
**Writes:** `md/p2_copy_click_probe_<timestamp>.md`; one throwaway selection file.
**Called by:** none; re-run after copy-symbol or handler changes.
**Calls out:** `src.panes.token_pane`, `.warnings_pane`, `.warnings_render`, `src.format.token_format`, `src.workers.worker_tokens_pane`, `src.utils`.

---

### p3_button_click_probe.py (220 LOC)

**Purpose:** Proves the warnings refresh button and the proxy pane's search-bar header dispatch clicks identically to their keyboard equivalents.
**Reads:** nothing external; seeds entries directly.
**Writes:** `md/p3_button_click_probe_<timestamp>.md`.
**Called by:** none; re-run after warnings header or proxy mouse changes.
**Calls out:** `src.panes.warnings_pane`, `.warnings_render`, `src.proxy_display.pane`, `.format`.

---

### p4_gpu_news_button_probe.py (273 LOC)

**Purpose:** Proves the gpu per-server button matches its digit key's subprocess call and both gpu and news refresh buttons dispatch without yielding to other regions.
**Reads:** nothing external; synthetic preset and status data, subprocess launching patched.
**Writes:** `md/p4_gpu_news_button_probe_<timestamp>.md`.
**Called by:** none; re-run after gpu or news render or button changes.
**Calls out:** `src.gpu_pane.pane`, `src.news_pane.pane`.

---

### p5_proxy_message_copy_click_probe.py (89 LOC)

**Purpose:** Entry point orchestrating the message, thinking and block copy-granularity suites and writing the combined report.
**Reads:** nothing external.
**Writes:** `md/p5_proxy_message_copy_click_probe_<timestamp>.md`.
**Called by:** none; re-run after row-build or serializer changes.
**Calls out:** `proxy_copy_probe_shared.py`, `proxy_copy_message_probe.py`, `proxy_copy_thinking_probe.py`, `proxy_copy_block_probe.py`.

---

### proxy_copy_probe_shared.py (59 LOC)

**Purpose:** Shared fixtures of the copy suite: module handles, check recording, clipboard patch, entry builder and expanded render.
**Reads:** nothing external.
**Writes:** mutates the shared result list read by the entry script.
**Called by:** the entry script and the three copy probe modules.
**Calls out:** `src.proxy_display.pane`, `.worker_proxy_pane`, `.format`, `.proxy_pane_shared`.

---

### proxy_copy_message_probe.py (114 LOC)

**Purpose:** Message-row copy granularity: key registration, click and serializer parity, dispatch, width guard.
**Reads:** nothing external; synthetic multi-block message.
**Writes:** nothing.
**Called by:** `p5_proxy_message_copy_click_probe.py`.
**Calls out:** `proxy_copy_probe_shared.py`.

---

### proxy_copy_thinking_probe.py (127 LOC)

**Purpose:** Thinking-block copy granularity, including the regression that a non-copy click still toggles expand.
**Reads:** nothing external; synthetic thinking entry.
**Writes:** nothing.
**Called by:** `p5_proxy_message_copy_click_probe.py`.
**Calls out:** `proxy_copy_probe_shared.py`.

---

### proxy_copy_block_probe.py (127 LOC)

**Purpose:** Generic-block copy granularity nested in message and REQ copies, including the regression that a non-copy click is a no-op.
**Reads:** nothing external.
**Writes:** nothing.
**Called by:** `p5_proxy_message_copy_click_probe.py`.
**Calls out:** `proxy_copy_probe_shared.py`.

---

## State
No persistent state. Each script mutates its target pane's real globals in-process and discards them at exit; the shared fixtures module owns the one shared result list.
