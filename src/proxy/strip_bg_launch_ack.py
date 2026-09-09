import re

from .payload_helpers import _walk_replace_marker_blocks

# INFRASTRUCTURE

_BG_LAUNCH_ACK_MARKER = 'running in background with ID'
_BG_LAUNCH_ACK_MARKER_2 = 'backgrounded by user with ID'
_BG_LAUNCH_ACK_PREFIX = 'Command running in background with ID:'
_BG_LAUNCH_ACK_PREFIX_2 = 'Command was manually backgrounded by user with ID:'

_BG_LAUNCH_ACK_MSG = (
    'Command is running in the background. Do NOT check, poll, or read its output — '
    'just wait until it finishes (you will get a completion notice).'
)

_BG_LAUNCH_ACK_MSG_MAIN = (
    'Command is running in the background. Do NOT check, poll, or read its output, and do NOT '
    'arm another background timer — go idle now and wait; you will get a completion notice for '
    'this exact task ID when it finishes.'
)

_ACK_ID_RE = re.compile(r'with ID:\s*([^.]*)\.')
_ACK_PATH_RE = re.compile(
    r'Output is being written to:\s*(.*?)(?:\.\s*You will be notified|\n|\s*$)', re.DOTALL
)


def _is_bg_launch_ack(text):
    stripped = text.lstrip()
    return stripped.startswith(_BG_LAUNCH_ACK_PREFIX) or stripped.startswith(_BG_LAUNCH_ACK_PREFIX_2)


# ORCHESTRATOR

def _strip_bg_launch_ack(content, is_main=False):
    return _walk_replace_marker_blocks(
        content, _is_bg_launch_ack, lambda text: _build_launch_ack_replacement(text, is_main)
    )


# FUNCTIONS

def _build_launch_ack_replacement(ack_text, is_main=False):
    id_match = _ACK_ID_RE.search(ack_text)
    path_match = _ACK_PATH_RE.search(ack_text)
    task_id = id_match.group(1).strip() if id_match else ''
    path = path_match.group(1).strip() if path_match else ''
    lines = [_BG_LAUNCH_ACK_MSG_MAIN if is_main else _BG_LAUNCH_ACK_MSG]
    if path:
        lines.append('Output: ' + path)
    if task_id:
        lines.append('ID: ' + task_id)
    return '\n'.join(lines) + '\n'
