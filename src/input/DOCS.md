# src/input/

## Role

Keyboard and mouse input handling: `click_handler.py` is the low-level stdin layer used by every interactive pane. Touch to change input behaviour or add mouse modes; not for pane-specific key or mouse dispatch, which each pane owns.

## Public Interface

```python
from src.input import setup_keyboard_input   # set terminal to raw/cbreak mode
from src.input import set_raw_stdin          # low-level raw mode toggle
from src.input import restore_terminal       # restore cooked mode on exit
from src.input import read_keypress          # read one keypress from stdin (non-blocking) — 1-4 bytes, UTF-8 aware
from src.input import parse_digit_key        # '1'-'9' → int, else None
from src.input import get_agent_by_index     # digit → agent_id from metadata dict
from src.input import enable_mouse           # SGR 1003+1006 (Any Event Tracking)
from src.input import disable_mouse
from src.input import enable_mouse_clicks    # SGR 1000+1006 (click only)
from src.input import disable_mouse_clicks
from src.input import read_mouse_event       # parse \033[<b;col;rowM → (button, col, row); (-1,-1,-1) on release; None for non-mouse
from src.input import resolve_parent_key     # hover_row → nearest mapped key walking upward
from src.input import copy_to_clipboard      # copy text to system clipboard
from src.input import wait_for_input         # block until stdin readable or timeout
```

## Modules

### click_handler.py (138 LOC)

**Purpose:** low-level stdin handling: raw terminal mode, keypress and SGR mouse parsing, mouse mode toggles, clipboard copy, event-driven input wait.
**Reads:** the stdin file descriptor, unbuffered.
**Writes:** stdout (mouse-mode enable/disable escape sequences); terminal mode via `termios`; clipboard via `pbcopy` subprocess.
**Called by:** `gpu_pane/pane.py`, `news_pane/pane.py`, `panes/token_pane.py`, `panes/warnings_pane.py`, `workers/worker_tokens_pane.py`, `proxy_display/pane.py`, `proxy_display/worker_proxy_pane.py`.
**Calls out:** `pbcopy` (subprocess CLI, clipboard); `pane_error_log.py`.

---
