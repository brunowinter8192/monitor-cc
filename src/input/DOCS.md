# src/input/

## Role

Keyboard and mouse input handling. `click_handler.py` is the low-level stdin layer used by every
interactive pane. Touch this package to change input handling behaviour or add new mouse modes.
Do NOT add pane-specific logic here — each pane owns its own render loop and its own key/mouse
dispatch table.

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
from src.input import copy_to_clipboard      # copy text to system clipboard via pbcopy
from src.input import wait_for_input         # block until stdin readable or timeout
```

## Modules

### click_handler.py (154 LOC)

**Purpose:** Low-level stdin handling — raw terminal mode, unbuffered keypress reads (UTF-8 multi-byte aware), SGR mouse sequence parsing, mouse tracking mode toggles, clipboard copy, and an event-driven `wait_for_input` sleep replacement.
**Reads:** stdin file descriptor via `os.read(fd, 1)` per byte (unbuffered, bypasses Python's IO layer); `select.select` for the initial poll, UTF-8 continuation-byte reads, and `wait_for_input`'s caller-provided timeout.
**Writes:** stdout (mouse-mode enable/disable escape sequences); terminal mode via `termios`; clipboard via `pbcopy` subprocess.
**Called by:** `core/monitor.py`, `gpu_pane/pane.py`, `news_pane/pane.py`, `panes/token_pane.py`, `panes/warnings_pane.py`, `workers/worker_pane.py`, `proxy_display/pane.py`, `proxy_display/worker_proxy_pane.py`.
**Calls out:** `pbcopy` (subprocess CLI, clipboard).

---

## Gotchas

- All stdin reads use `os.read(fd, 1)`, never `sys.stdin.read(1)` — Python's stdin has a 4096-byte internal buffer that makes `select()` unreliable for escape-sequence detection; `os.read` bypasses it.
- `read_keypress` still issues one `os.read` call per byte even for a multi-byte UTF-8 character — it reads the lead byte, classifies continuation-byte count from the UTF-8 bit pattern, then reads that many more bytes (each gated by the same 0.005s `select.select` timeout `read_mouse_event` uses) before decoding the whole sequence together.
- `enable_mouse()` uses SGR mode 1003 (Any Event Tracking, incl. motion) — this captures ALL mouse events from tmux, so native tmux scroll (Ctrl+B `[`) stops working while mouse mode is active. Panes must handle scroll themselves via their own `scroll_offset`.
- `read_mouse_event` returns `(-1, -1, -1)` (not `None`) for a release event (`m` terminator) — callers that only care about press events must check `event[0] != -1`, not just `event is not None`.
