"""
Regression guard for `format._is_standalone_entry`'s coverage of the CC-internal zero-tool sidecar
call (session-titling, quota check, security-monitor) in the proxy pane's REQ numbering.

Every sidecar shape observed on disk (33/33 entries across 20 `_forwarded.jsonl` files at
investigation time, all `claude-haiku-4-5-20251001`, `tools == 0`, 1 message) is a haiku-model
call — `_is_standalone_entry`'s existing `'haiku' in model` branch already excludes every one of
them from the numbered `#N` REQ sequence, confirmed both by this file's Test 2 and by
`render_byte_identity.py` coming out byte-identical against a real log containing 2 sidecar
entries. A widened `tools == 0`-regardless-of-model predicate was tried and reverted — see
process-docs/proxy_instrumentation/ for the measurement (a repo-wide scan of every
`_forwarded.jsonl`/`_original.jsonl` on disk found zero non-haiku, zero-tool entries) and the
reasoning (the same predicate has four callers across the package, and widening it changes
behavior for a real zero-tool conversation request too, not just a hypothetical sidecar, with
nothing in real data to justify the change). `tools_total_chars == 0` (mirroring
`dual_log_cli.timeline_boundaries._is_sidecar`'s `counts.tools == 0`, model-agnostic) remains the
precise criterion to switch to if a non-haiku sidecar is ever actually observed.

Run (from project root or worktree root):
    ./venv/bin/python dev/proxy_display/test_standalone_sidecar.py
"""

# INFRASTRUCTURE
import re
import sys
from pathlib import Path

WORKTREE_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(WORKTREE_ROOT))

_PASS = "\033[32mPASS\033[0m"
_FAIL = "\033[31mFAIL\033[0m"
_RESULTS = []


def check(label, condition):
    _RESULTS.append((label, bool(condition)))
    print(f"  {_PASS if condition else _FAIL}  {label}")
    return condition


# FUNCTIONS

def _strip(line: str, ansi_re) -> str:
    return ansi_re.sub('', line)


# Test 1 — unit coverage of the shapes _is_standalone_entry actually handles today.
def test_is_standalone_entry_observed_shapes():
    from src.proxy_display.format import _is_standalone_entry
    print("\n[Test 1] _is_standalone_entry: covers every sidecar shape observed in real data")
    check("haiku model, zero tools, non-zero system -> standalone "
          "(the exact shape every sidecar on disk has: session-titling/quota calls both carry "
          "their own system prompt)",
          _is_standalone_entry({
              'model': 'claude-haiku-4-5-20251001', 'tools_total_chars': 0, 'system_total_chars': 300,
          }))
    check("non-haiku, zero tools AND zero system (old zero-context shape) -> standalone",
          _is_standalone_entry({'model': 'claude-opus-4-8', 'tools_total_chars': 0, 'system_total_chars': 0}))
    check("non-haiku, non-zero tools -> a real conversation request, NOT standalone",
          not _is_standalone_entry({
              'model': 'claude-opus-4-8', 'tools_total_chars': 500, 'system_total_chars': 300,
          }))


def _entry(model, message_count, tools_total_chars, system_total_chars, messages_added, flow_id, ts):
    return {
        'model': model,
        'message_count': message_count,
        'tools_total_chars': tools_total_chars,
        'system_total_chars': system_total_chars,
        'diff_from_prev': {'messages_added': messages_added},
        'flow_id': flow_id,
        'timestamp': ts,
        'tools_hash': None,
    }


def _labels(lines, ansi_re):
    out = []
    for line in lines:
        m = re.search(r'(#\d+(?:\.\d+)?|[HS])\s+\w', _strip(line, ansi_re))
        out.append(m.group(1) if m else None)
    return out


# Test 2 — end to end: a haiku sidecar (the only shape observed in real data) sharing the real
# conversation's non-haiku family, sitting between two real requests, must not consume a REQ
# number — REQ 1, H, REQ 2, not REQ 1, REQ 2, REQ 3.
def test_haiku_sidecar_does_not_consume_a_req_number():
    from src.proxy_display.render_turn import render_turn_expanded
    from src.utils import _ANSI_ESCAPE_RE
    print("\n[Test 2] render_turn_expanded: a haiku sidecar between two real requests keeps REQ numbering intact")
    entries = [
        _entry('claude-opus-4-8', 2, 500, 1000, 2, 'f1', '2026-09-15T10:00:00.000Z'),
        _entry('claude-haiku-4-5-20251001', 1, 0, 300, 1, 'sidecar', '2026-09-15T10:00:02.000Z'),
        _entry('claude-opus-4-8', 4, 500, 1000, 2, 'f2', '2026-09-15T10:00:04.000Z'),
    ]
    group = {'entry_pairs': list(enumerate(entries))}
    lines, keys, opus_req_num, sub_req_num = render_turn_expanded(group, entries, {}, 120, 0, 0)
    header_lines = [l for l, k in zip(lines, keys) if isinstance(k, tuple) and k[0] == 'req']
    labels = _labels(header_lines, _ANSI_ESCAPE_RE)

    check("3 REQ header lines rendered (sidecar entry IS still shown in the pane)", len(labels) == 3)
    check("REQ 1 gets '#1'", labels[0] == '#1')
    check("haiku sidecar gets 'H', not a numbered REQ", labels[1] == 'H')
    check("the request after the sidecar gets '#2', not '#3' — its number was never shifted",
          labels[2] == '#2')
    check("opus_req_num returned to the caller is 2, not 3", opus_req_num == 2)


# ORCHESTRATOR

def run_probe_workflow():
    print("=" * 70)
    print("standalone-sidecar REQ-numbering probe (src/proxy_display/format.py)")
    print("=" * 70)
    test_is_standalone_entry_observed_shapes()
    test_haiku_sidecar_does_not_consume_a_req_number()

    total = len(_RESULTS)
    passed = sum(1 for _, ok in _RESULTS if ok)
    print("\n" + "=" * 70)
    print(f"{passed}/{total} checks passed")
    print("=" * 70)
    return passed == total


if __name__ == "__main__":
    ok = run_probe_workflow()
    sys.exit(0 if ok else 1)
