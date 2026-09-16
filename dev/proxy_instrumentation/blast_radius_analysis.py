# INFRASTRUCTURE
import importlib
import re
import statistics
import sys
from pathlib import Path

WORKTREE_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(WORKTREE_ROOT / 'src'))

from proxy.diff_engine import compose_block

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
