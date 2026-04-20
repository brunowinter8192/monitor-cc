# src/input/

## Role

Keyboard and mouse input handling plus shared UI state management. `click_handler.py` is the low-level stdin layer used by every interactive pane; `ui_mode.py` provides higher-level state tracking (subagent metadata) and the rules block renderer shared between the main loop and the rules pane. Touch this package to change input handling behaviour, add new mouse modes, or modify the rules block rendering. Do NOT add pane-specific logic here — each pane owns its own render loop.

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

# UI state + rules rendering (ui_mode.py)
from src.input import track_subagent_metadata   # update agent maps from tool call
from src.input import format_rules_block        # render active rules as ANSI block
```

## Modules

### click_handler.py (127 LOC)

**Purpose:** Low-level stdin handling — sets terminal to raw mode, reads unbuffered keypresses and multi-byte SGR mouse sequences, enables/disables mouse tracking modes.
**Reads:** stdin file descriptor via `os.read(fd, 1)` (unbuffered, bypasses Python IO layer).
**Writes:** stdout (escape sequences for mouse mode enable/disable only); terminal mode via `termios`.
**Called by:** `panes/token_pane.py`, `panes/rules_pane.py`, `panes/warnings_pane.py` (lazy), `panes/waste_pane.py`, `hooks/hooks_pane.py`, `workers/worker_pane.py`, `proxy_display/pane.py`, `proxy_display/worker_proxy_pane.py`, `subagents/subagent_pane.py`.
**Calls out:** nothing external (stdlib only: `os`, `select`, `sys`, `termios`, `tty`).

---

### ui_mode.py (104 LOC)

**Purpose:** Subagent metadata tracking and active rules block rendering. `track_subagent_metadata()` updates agent-to-task/type maps from tool call events. `format_rules_block()` renders the [P]/[G]-prefixed rules list with expand/collapse, hover, and scroll for use in both the rules pane and the legacy UI mode.
**Reads:** Tool call dicts, active rules dicts, expand/line-map/hover/scroll state — all passed as arguments or shared via `subagents.subagent_ui.subagent_states`.
**Writes:** Mutates caller-owned state dicts (`subagent_metadata`, `agent_to_task`, `agent_to_type`); returns formatted ANSI string + updated line map from `format_rules_block()`.
**Called by:** `core/monitor_session.py` (`track_subagent_metadata`); `panes/rules_pane.py` (`format_rules_block`, lazy).
**Calls out:** `subagents.subagent_ui`, `subagents.subagent_ui_format`.

## Gotchas

- All stdin reads use `os.read(fd, 1)` — NOT `sys.stdin.read(1)`. Python's stdin has a 4096-byte internal buffer that makes `select()` unreliable for escape sequence detection. `os.read` bypasses this.
- `enable_mouse()` uses SGR mode 1003 (Any Event Tracking, incl. motion). This captures ALL mouse events from tmux — native tmux scroll (Ctrl+B [) stops working while mouse mode is active. Panes must handle scroll themselves via `scroll_offset`.
- `ui_mode.py` imports from `subagents/` — a cross-package dependency that creates coupling. If `subagents/` is ever removed, `ui_mode.py` needs refactoring.
