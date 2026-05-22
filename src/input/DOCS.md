# src/input/

## Role

Keyboard and mouse input handling. `click_handler.py` is the low-level stdin layer used by every interactive pane. Touch this package to change input handling behaviour or add new mouse modes. Do NOT add pane-specific logic here — each pane owns its own render loop.

## Public Interface

```python
# Keyboard / mouse input (click_handler.py)
from src.input import setup_keyboard_input   # set terminal to raw mode
from src.input import set_raw_stdin          # low-level raw mode toggle
from src.input import restore_terminal       # restore cooked mode on exit
from src.input import read_keypress          # read one byte from stdin (non-blocking)
from src.input import parse_digit_key        # '1'-'9' → int, else None
from src.input import get_agent_by_index     # digit → agent_id from metadata dict
from src.input import enable_mouse           # SGR 1003+1006 (Any Event Tracking)
from src.input import disable_mouse
from src.input import enable_mouse_clicks    # SGR 1000+1006 (click only)
from src.input import disable_mouse_clicks
from src.input import read_mouse_event       # parse \033[<b;col;rowM → (button, col, row)
from src.input import resolve_parent_key     # hover_row → canonical parent key in line_map
from src.input import copy_to_clipboard      # copy text to system clipboard via pbcopy
from src.input import wait_for_input         # block until stdin readable OR timeout — event-driven sleep replacement
```

## Modules

### click_handler.py (150 LOC)

**Purpose:** Low-level stdin handling — sets terminal to raw mode, reads unbuffered keypresses and multi-byte SGR mouse sequences, enables/disables mouse tracking modes. Also provides `resolve_parent_key(line_map, hover_row)` (walk hover_row down to nearest mapped key), `copy_to_clipboard(text)` (pipe to pbcopy) used by every pane's `y`-hotkey handler, and `wait_for_input(timeout)` (block on `select.select` for stdin or timeout, fallback to `time.sleep` if stdin not raw) — used in every pane's main loop instead of fixed `time.sleep` so input wakes the loop immediately.
**Reads:** stdin file descriptor via `os.read(fd, 1)` (unbuffered, bypasses Python IO layer); `select.select` for both `read_keypress` (timeout=0) and `wait_for_input` (caller-provided timeout).
**Writes:** stdout (escape sequences for mouse mode enable/disable only); terminal mode via `termios`; clipboard via `pbcopy` subprocess.
**Called by:** `core/monitor.py`, `panes/token_pane.py`, `panes/warnings_pane.py` (lazy), `workers/worker_pane.py`, `proxy_display/pane.py`, `proxy_display/worker_proxy_pane.py`.
**Calls out:** nothing external (stdlib only: `os`, `select`, `subprocess`, `sys`, `termios`, `tty`).

## Gotchas

- All stdin reads use `os.read(fd, 1)` — NOT `sys.stdin.read(1)`. Python's stdin has a 4096-byte internal buffer that makes `select()` unreliable for escape sequence detection. `os.read` bypasses this.
- `enable_mouse()` uses SGR mode 1003 (Any Event Tracking, incl. motion). This captures ALL mouse events from tmux — native tmux scroll (Ctrl+B [) stops working while mouse mode is active. Panes must handle scroll themselves via `scroll_offset`.
