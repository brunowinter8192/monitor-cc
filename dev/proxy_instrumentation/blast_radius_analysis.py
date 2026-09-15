# INFRASTRUCTURE
import importlib
import re
import statistics
import sys
from pathlib import Path

WORKTREE_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(WORKTREE_ROOT / 'src'))

from proxy.diff_engine import compose_block

# proxy_display/pane.py (pulled in by proxy_display/__init__.py) uses a 2-level relative
# import ("from ..constants") that requires proxy_display to be resolved as a SUBPACKAGE of
# the project root, not as a flat top-level package like the src/proxy/* imports above —
# resolved via a second sys.path root + dynamic import (dodges static "from src." rewriting).
sys.path.insert(0, str(WORKTREE_ROOT))
_src_pkg = 'src'
_render_messages_mod = importlib.import_module(_src_pkg + '.proxy_display.render_messages')
_render_span_content = _render_messages_mod._render_span_content

_ANSI_RE = re.compile(r'\x1b\[[0-9;]*m')


# FUNCTIONS

def _trimmed(rec):
    bt = rec['bt']
    s = len(bt) - rec['offset'] - len(rec['removed'])
    return rec['offset'] > 0 or s > 0


def _ratio(rec):
    bt = rec['bt']
    return (len(rec['removed']) / len(bt)) if bt else None


def _dist(values):
    if not values:
        return None
    values = sorted(values)
    return {
        'n': len(values), 'min': values[0], 'max': values[-1],
        'median': statistics.median(values),
        'mean': round(statistics.mean(values), 3),
    }


# Render one op through the REAL compose_block + _render_span_content pipeline — "recorded"
# uses today's actual op (possibly prefix/suffix-trimmed); "hypothetical" uses a synthetic
# full-block op (0, bt, at) to show how a full-replacement-aware _extract_block_op would render
# the SAME underlying change. Returns (recorded_lines, hypothetical_lines), ANSI stripped.
def _render_comparison(rec):
    bt = rec['bt']
    recorded_op = [(rec['offset'], rec['removed'], rec['injected'])]
    hypothetical_op = [(0, bt, rec['at'])]

    def _lines_for(ops):
        spans = compose_block(bt, ops)
        s_texts = [t for tag, t in spans if tag == 'stripped' and t]
        i_spans = [(tag, t) for tag, t in spans if tag in ('equal', 'injected') and t]
        lines, _keys = _render_span_content('', i_spans, s_texts, '      ')
        return [_ANSI_RE.sub('', ln) for ln in lines]

    return _lines_for(recorded_op), _lines_for(hypothetical_op)
