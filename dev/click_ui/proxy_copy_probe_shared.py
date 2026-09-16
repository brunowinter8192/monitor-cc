# INFRASTRUCTURE
import importlib

_ROOT_PKG = 'src'
mod_proxy = importlib.import_module(f'{_ROOT_PKG}.proxy_display.pane')
mod_worker_proxy = importlib.import_module(f'{_ROOT_PKG}.proxy_display.worker_proxy_pane')
mod_format = importlib.import_module(f'{_ROOT_PKG}.proxy_display.format')
mod_shared = importlib.import_module(f'{_ROOT_PKG}.proxy_display.proxy_pane_shared')

_PASS = "\033[32mPASS\033[0m"
_FAIL = "\033[31mFAIL\033[0m"
_RESULTS = []


def check(label, condition):
    _RESULTS.append((label, bool(condition)))
    print(f"  {_PASS if condition else _FAIL}  {label}")
    return condition


# FUNCTIONS

def _patch_clipboard(mod):
    captured = []
    mod.copy_to_clipboard = lambda text: captured.append(text)
    return captured


def _make_entry():
    return {
        'model': 'claude-sonnet', 'message_count': 2,
        'system_total_chars': 0, 'tools_total_chars': 0, 'messages_total_chars': 100,
        'messages': [
            {'role': 'assistant', 'type': 'text', 'chars': 10, 'blocks': [
                {'type': 'text', 'chars': 10, 'full_text': 'hello world'},
                {'type': 'tool_use', 'chars': 5, 'full_text': 'Bash\n{"command":"ls"}'},
            ]},
            {'role': 'user', 'type': 'tool_result', 'chars': 20, 'blocks': [], 'content_preview': 'file contents here'},
        ],
        'schema_warnings': [], 'stripped_msg_indices': [], 'modifications': [],
        'timestamp': '2026-04-21T10:00:00Z',
    }


def _render_expanded(entries, expand_states, pane_width=120):
    line_map = {}
    copy_rows = set()
    copy_feedback = {}
    mod_format.format_proxy_block(
        entries, expand_states, line_map, None, 50, pane_width, 0,
        copy_feedback=copy_feedback, copy_rows_out=copy_rows,
    )
    mod_shared._shift_line_map_and_copy_rows(line_map, copy_rows, 1)
    return line_map, copy_rows, copy_feedback
