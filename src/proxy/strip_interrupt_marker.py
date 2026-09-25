# INFRASTRUCTURE
from src.proxy.payload_helpers import _walk_replace_marker_blocks

_INTERRUPT_MARKERS = frozenset({
    '[Request interrupted by user]',
    '[Request interrupted by user for tool use]',
})


# ORCHESTRATOR

def _strip_interrupt_marker(content):
    return _walk_replace_marker_blocks(content, _is_interrupt_marker, _replace_with_dot)


# FUNCTIONS

def _is_interrupt_marker(text):
    return text.strip() in _INTERRUPT_MARKERS


def _replace_with_dot(_text):
    return '.'
