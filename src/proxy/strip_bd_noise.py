# INFRASTRUCTURE
import re

from src.proxy.strip_walk import strip_content_tree

_BD_NOISE_MARKERS = ('issues.jsonl', 'auto-export:', 'into empty database')

_BD_NOISE_RE = re.compile(
    r'^(?:- )?(?:'
    r'auto-importing \d+ bytes from \S+/\.beads/issues\.jsonl into empty database\.{0,3}'
    r'|auto-imported \d+ issues(?: and \d+ memories)? from \S+/\.beads/issues\.jsonl'
    r'|auto-imported \d+ issues into empty database'
    r'|Exported \d+ issues(?: and \d+ memories)? to \S+/\.beads/issues\.jsonl'
    r'|auto-export: wrote \d+ issues(?: and \d+ memories)? to \S+/\.beads/issues\.jsonl'
    r'|auto-export: no changes since last export'
    r'|auto-export: throttled \([^)]+\)'
    r'|auto-export: skipping[^\n]*'
    r'|auto-import: \d+ issues(?:, \d+ memories)? from \S+/\.beads/issues\.jsonl[^\n]*'
    r')\n?',
    re.MULTILINE,
)


# ORCHESTRATOR

def _strip_bd_noise(content):
    removed = []
    result = strip_content_tree(content, _strip_bd_noise_from_text, removed)
    return result, removed


# FUNCTIONS

def _strip_bd_noise_from_text(text, out_removed):
    if not any(m in text for m in _BD_NOISE_MARKERS):
        return text

    def _collect(m):
        out_removed.append(m.group(0).rstrip('\n'))
        return ''

    return _BD_NOISE_RE.sub(_collect, text)
