# src/input/

## Role

Keyboard and mouse input handling. `click_handler.py` is the low-level stdin layer used by every interactive pane. Touch this package to change input handling behaviour or add new mouse modes. Do NOT add pane-specific logic here — each pane owns its own render loop.

## Public Interface

```python
# Keyboard / mouse input (click_handler.py)
from src.input import setup_keyboard_input   # set terminal to raw mode
from src.input import set_raw_stdin          # low-level raw mode toggle
from src.input import restore_terminal       # restore cooked mode on exit
from src.input import read_keypress          # read one keypress from stdin (non-blocking) — 1 byte for ASCII, up to 4 for a multi-byte UTF-8 char
from src.input import parse_digit_key        # '1'-'9' → int, else None
from src.input import get_agent_by_index     # digit → agent_id from metadata dict
from src.input import enable_mouse           # SGR 1003+1006 (Any Event Tracking)
from src.input import disable_mouse
from src.input import enable_mouse_clicks    # SGR 1000+1006 (click only)
from src.input import disable_mouse_clicks
from src.input import read_mouse_event       # parse \033[<b;col;rowM → (button, col, row) press; (-1,-1,-1) sentinel for release ('m' terminator); None for non-mouse / bare-ESC
from src.input import resolve_parent_key     # hover_row → canonical parent key in line_map
from src.input import copy_to_clipboard      # copy text to system clipboard via pbcopy
from src.input import wait_for_input         # block until stdin readable OR timeout — event-driven sleep replacement
```

## Modules

### click_handler.py (154 LOC)

**Purpose:** Low-level stdin handling — sets terminal to raw mode, reads unbuffered keypresses and multi-byte SGR mouse sequences, enables/disables mouse tracking modes. Also provides `resolve_parent_key(line_map, hover_row)` (walk hover_row down to nearest mapped key), `copy_to_clipboard(text)` (pipe to pbcopy) used by every pane's `y`-hotkey handler, and `wait_for_input(timeout)` (block on `select.select` for stdin or timeout, fallback to `time.sleep` if stdin not raw) — used in every pane's main loop instead of fixed `time.sleep` so input wakes the loop immediately.

**`read_mouse_event` return shape (2026-05-22 sentinel addition, commit `bf1f158`):** parses `\033[<b;col;rowM` (press, terminator `M`) returning `(button, col, row)`; parses `\033[<b;col;rowm` (release, terminator `m`) returning the sentinel `(-1, -1, -1)`; returns `None` for non-mouse sequences (bare-ESC keypress, malformed input). Callers that only care about press events check `event is not None and event[0] != -1`; callers that need release detection check for the sentinel. The sentinel resolves the search-bar focus-cancel bug where bare-ESC handling fired on every mouse release because both produced `None` return.

**`read_keypress` — multi-byte UTF-8 decoding (2026-08-18 fix).** Previously read exactly 1 byte and decoded it alone (`errors='replace'`) — a multi-byte UTF-8 character (em-dash = 3 bytes, ä/ö/ü = 2 bytes, most emoji = 4 bytes) arrived as N separate `os.read(fd, 1)` calls, each individually invalid UTF-8, each replaced with U+FFFD (`'�'`) — reported live as an em-dash typed into the proxy search bar rendering as three `���`. Fixed: reads the lead byte first (unchanged non-blocking-select fast path for "nothing pending" → `None`), classifies it via `_utf8_continuation_count(lead_byte)` (UTF-8 bit-pattern: `0xxxxxxx`=0 continuation bytes, `110xxxxx`=1, `1110xxxx`=2, `11110xxx`=3), then reads that many more bytes — each gated by the SAME `select.select(..., 0.005)` timeout `read_mouse_event` already uses for its own byte-wise ESC-sequence continuation reads (reused for consistency, not reinvented) — and decodes the whole sequence together. Plain ASCII (0 continuation bytes) takes the exact same code path as before, byte-for-byte — zero added latency for the overwhelming majority of keypresses. A read error now propagates to the caller's own outer `try/except Exception: log_pane_error(...)` (every pane loop wraps its drain loop in one) instead of being silently swallowed inside `read_keypress` itself. Verified against both `input.click_handler.read_keypress` directly (via a real `os.pipe()` fd, not a mock) and the full search-input path in both `proxy_display/pane.py` and `core/monitor_display.py` (confirming the shared reader fix heals BOTH search bars) — `dev/pane_search/p2_search_feature_regression_test.py`.
**Reads:** stdin file descriptor via `os.read(fd, 1)` per byte (unbuffered, bypasses Python IO layer) — 1 read for ASCII, up to 4 for a multi-byte UTF-8 keypress; `select.select` for `read_keypress`'s initial poll (timeout=0), its continuation-byte reads (timeout=0.005), and `wait_for_input` (caller-provided timeout).
**Writes:** stdout (escape sequences for mouse mode enable/disable only); terminal mode via `termios`; clipboard via `pbcopy` subprocess.
**Called by:** `core/monitor.py`, `gpu_pane/pane.py`, `news_pane/pane.py`, `panes/token_pane.py`, `panes/warnings_pane.py` (lazy), `workers/worker_pane.py`, `proxy_display/pane.py`, `proxy_display/worker_proxy_pane.py`.
**Calls out:** nothing external (stdlib only: `os`, `select`, `subprocess`, `sys`, `termios`, `tty`).
New private helper (same module): `_utf8_continuation_count`.

## Gotchas

- All stdin reads use `os.read(fd, 1)` — NOT `sys.stdin.read(1)`. Python's stdin has a 4096-byte internal buffer that makes `select()` unreliable for escape sequence detection. `os.read` bypasses this. `read_keypress` still reads ONE BYTE PER `os.read` CALL even for a multi-byte UTF-8 character — it just calls `os.read` up to 4 times in a row (lead byte + N continuation bytes) and concatenates before decoding, never requests more than 1 byte per call.
- `enable_mouse()` uses SGR mode 1003 (Any Event Tracking, incl. motion). This captures ALL mouse events from tmux — native tmux scroll (Ctrl+B [) stops working while mouse mode is active. Panes must handle scroll themselves via `scroll_offset`.
