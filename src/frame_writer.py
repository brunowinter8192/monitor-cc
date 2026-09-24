# INFRASTRUCTURE
import sys

SYNC_BEGIN = '\033[?2026h'
SYNC_END = '\033[?2026l'
CURSOR_HOME = '\033[H'
ERASE_BELOW = '\033[J'
ERASE_EOL = '\033[K'
CURSOR_HIDE = '\033[?25l'
CURSOR_SHOW = '\033[?25h'
SGR_RESET = '\033[0m'

# ORCHESTRATOR

def write_frame(output: str) -> None:
    frame = build_frame(output)
    emit_frame(frame)

# FUNCTIONS

def build_frame(output: str) -> str:
    body = '\n'.join(_erase_terminated_row(row) for row in output.split('\n')) + '\n' if output else ''
    return f"{SYNC_BEGIN}{CURSOR_HIDE}{CURSOR_HOME}{body}{ERASE_BELOW}{SYNC_END}"

def _erase_terminated_row(row: str) -> str:
    if ERASE_EOL in row:
        return row
    return f"{row}{SGR_RESET}{ERASE_EOL}"

def emit_frame(frame: str) -> None:
    sys.stdout.write(frame)
    sys.stdout.flush()

def hide_cursor() -> None:
    emit_frame(CURSOR_HIDE)

def show_cursor() -> None:
    emit_frame(CURSOR_SHOW)
