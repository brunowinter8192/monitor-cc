# src/input/

## Role

Keyboard and mouse input handling plus the shared rules-block renderer. `click_handler.py` is the low-level stdin layer used by every interactive pane; `ui_mode.py` renders the active rules block consumed by the rules pane. Touch this package to change input handling behaviour, add new mouse modes, or modify the rules block rendering. Do NOT add pane-specific logic here — each pane owns its own render loop.

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

# Rules block rendering (ui_mode.py)
from src.input import format_rules_block        # render active rules as ANSI block
```

## Modules

### click_handler.py (142 LOC)

**Purpose:** Low-level stdin handling — sets terminal to raw mode, reads unbuffered keypresses and multi-byte SGR mouse sequences, enables/disables mouse tracking modes. Also provides `resolve_parent_key(line_map, hover_row)` (walk hover_row down to nearest mapped key) and `copy_to_clipboard(text)` (pipe to pbcopy) used by every pane's `y`-hotkey handler.
**Reads:** stdin file descriptor via `os.read(fd, 1)` (unbuffered, bypasses Python IO layer).
**Writes:** stdout (escape sequences for mouse mode enable/disable only); terminal mode via `termios`; clipboard via `pbcopy` subprocess.
**Called by:** `core/monitor.py`, `panes/token_pane.py`, `panes/rules_pane.py`, `panes/warnings_pane.py` (lazy), `panes/waste_pane.py`, `hooks/hooks_pane.py`, `workers/worker_pane.py`, `proxy_display/pane.py`, `proxy_display/worker_proxy_pane.py`.
**Calls out:** nothing external (stdlib only: `os`, `select`, `subprocess`, `sys`, `termios`, `tty`).

---

### ui_mode.py (~75 LOC)

**Purpose:** Active rules block renderer. `format_rules_block()` produces the [P]/[G]-prefixed rules list with expand/collapse, hover, and scroll for the rules pane. `_source_color()` is a helper mapping source label → color.
**Reads:** Active rules dicts, expand/line-map/hover/scroll state — all passed as arguments.
**Writes:** Returns formatted ANSI string + updated line map.
**Called by:** `panes/rules_pane.py` (`format_rules_block`, lazy).
**Calls out:** nothing external.

## Gotchas

- All stdin reads use `os.read(fd, 1)` — NOT `sys.stdin.read(1)`. Python's stdin has a 4096-byte internal buffer that makes `select()` unreliable for escape sequence detection. `os.read` bypasses this.
- `enable_mouse()` uses SGR mode 1003 (Any Event Tracking, incl. motion). This captures ALL mouse events from tmux — native tmux scroll (Ctrl+B [) stops working while mouse mode is active. Panes must handle scroll themselves via `scroll_offset`.
