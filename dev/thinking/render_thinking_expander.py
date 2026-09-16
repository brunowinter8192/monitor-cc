# INFRASTRUCTURE
import importlib
import re
import subprocess
import sys
import tempfile
from datetime import datetime
from pathlib import Path

WORKTREE_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(WORKTREE_ROOT))

_ROOT_PKG = 'src'
mod_fwd_parser = importlib.import_module(f'{_ROOT_PKG}.proxy_display.forwarded_parser')
mod_render_turn = importlib.import_module(f'{_ROOT_PKG}.proxy_display.render_turn')
mod_render_messages = importlib.import_module(f'{_ROOT_PKG}.proxy_display.render_messages')
mod_format = importlib.import_module(f'{_ROOT_PKG}.proxy_display.format')
mod_utils = importlib.import_module(f'{_ROOT_PKG}.utils')

DEFAULT_LOG = WORKTREE_ROOT / 'src' / 'logs' / 'dual_log' / 'api_requests_opus_monitor_cc_1787931850_forwarded.jsonl'

BEFORE_COMMIT_SHA = '1f0eb6ec79b2af663569e6fa9696d1fccf57a429'

WIDTH_CASES = (180, 60)

# ORCHESTRATOR
def render_thinking_expander_workflow(log_path: Path) -> None:
    if not log_path.exists():
        print(f"Log not found: {log_path}")
        sys.exit(1)
    entries = parse_all_entries(log_path)
    collapsed_rows, expanded_rows = check_thinking_toggle(entries)
    identity_rows = check_non_thinking_byte_identical(entries)
    write_report(log_path, collapsed_rows, expanded_rows, identity_rows)

# FUNCTIONS

def parse_all_entries(log_path: Path) -> list:
    entries, _pos = mod_fwd_parser._parse_forwarded_log(log_path, 0, {}, keep_last=None)
    return entries

def _owning_entry_thinking_blocks(entries: list) -> list:
    owned = []
    for eidx, entry in enumerate(entries):
        is_standalone = mod_format._is_standalone_entry(entry)
        prev_same = mod_render_turn._resolve_prev_same_family(entries, eidx)
        lines_c, keys_c = mod_render_turn._render_req_expanded(eidx, entry, entries, is_standalone, prev_same, {}, 180)
        key_set = set(keys_c)
        for midx, msg in enumerate(entry.get('messages') or []):
            for bidx, blk in enumerate(msg.get('blocks', [])):
                if blk.get('type') == 'thinking' and ('think', eidx, midx, bidx) in key_set:
                    owned.append((eidx, midx, bidx))
    return owned

def check_thinking_toggle(entries: list) -> tuple:
    owned = _owning_entry_thinking_blocks(entries)
    collapsed_rows = []
    expanded_rows = []
    for eidx, midx, bidx in owned:
        entry = entries[eidx]
        blk = entry['messages'][midx]['blocks'][bidx]
        full_text = blk.get('full_text', '')
        think_key = ('think', eidx, midx, bidx)
        is_standalone = mod_format._is_standalone_entry(entry)
        prev_same = mod_render_turn._resolve_prev_same_family(entries, eidx)
        lines_c, keys_c = mod_render_turn._render_req_expanded(eidx, entry, entries, is_standalone, prev_same, {}, 180)
        idx_c = keys_c.index(think_key)
        header_stripped = mod_utils._ANSI_ESCAPE_RE.sub('', lines_c[idx_c])
        no_leak = (not full_text) or (full_text[:30] not in header_stripped)
        for pane_width in WIDTH_CASES:
            lines_c2, keys_c2 = mod_render_turn._render_req_expanded(eidx, entry, entries, is_standalone, prev_same, {}, pane_width)
            lines_e, keys_e = mod_render_turn._render_req_expanded(eidx, entry, entries, is_standalone, prev_same, {think_key: True}, pane_width)
            idx_c2 = keys_c2.index(think_key)
            idx_e = keys_e.index(think_key)
            prefix_ok = lines_c2[:idx_c2] == lines_e[:idx_e]
            extra = len(lines_e) - len(lines_c2)
            suffix_ok = lines_c2[idx_c2 + 1:] == lines_e[idx_e + 1 + extra:]
            exactly_one_line = prefix_ok and suffix_ok
            if pane_width == WIDTH_CASES[0]:
                collapsed_rows.append({
                    'eidx': eidx, 'midx': midx, 'bidx': bidx,
                    'exactly_one_line': exactly_one_line, 'no_leak': no_leak,
                })
            content_lines_raw = lines_e[idx_e + 1: idx_e + 1 + extra]
            content_lines = [mod_utils._ANSI_ESCAPE_RE.sub('', l) for l in content_lines_raw]
            joined = ' '.join(l.strip() for l in content_lines)
            norm = lambda s: re.sub(r'\s+', ' ', s).strip()
            text_present = norm(joined) == norm(full_text)
            max_w = max((sum(mod_utils._cell_width(c) for c in l) for l in content_lines), default=0)
            expanded_rows.append({
                'eidx': eidx, 'midx': midx, 'bidx': bidx, 'pane_width': pane_width,
                'text_present': text_present, 'max_w': max_w, 'width_ok': max_w <= pane_width,
                'chars': blk.get('chars', 0),
            })
    return collapsed_rows, expanded_rows

def check_non_thinking_byte_identical(entries: list) -> list:
    old_rm = _load_old_render_messages(BEFORE_COMMIT_SHA)
    samples = _find_non_thinking_samples(entries)
    rows = []
    for btype, (eidx, midx, bidx) in samples.items():
        entry = entries[eidx]
        blk = entry['messages'][midx]['blocks'][bidx]
        old_lines, old_keys = old_rm._render_block_spans(midx, bidx, blk, entry, False)
        new_lines, new_keys = mod_render_messages._render_block_spans(eidx, midx, bidx, blk, entry, False, {}, 180)
        rows.append({
            'btype': btype, 'eidx': eidx, 'midx': midx, 'bidx': bidx,
            'identical': old_lines == new_lines and old_keys == new_keys,
            'line_count': len(new_lines),
        })
    return rows

def _find_non_thinking_samples(entries: list) -> dict:
    samples = {}
    wanted = {'text', 'tool_use', 'tool_result', 'image'}
    for eidx, entry in enumerate(entries):
        for midx, msg in enumerate(entry.get('messages') or []):
            for bidx, blk in enumerate(msg.get('blocks', [])):
                btype = blk.get('type')
                if btype in wanted and btype not in samples and blk.get('chars', 0) > 20:
                    samples[btype] = (eidx, midx, bidx)
        if len(samples) == len(wanted):
            break
    return samples

def _git_show(commit_sha: str, rel_path: str) -> str:
    return subprocess.check_output(
        ['git', '-C', str(WORKTREE_ROOT), 'show', f'{commit_sha}:{rel_path}'], text=True
    )

def _load_old_render_messages(commit_sha: str):
    tmp_root = Path(tempfile.mkdtemp(prefix='thinking_old_snapshot_'))
    pkg_root = tmp_root / 'old_snapshot'
    src_dir = pkg_root / 'src'
    pd_dir = src_dir / 'proxy_display'
    proxy_dir = src_dir / 'proxy'
    for d in (pkg_root, src_dir, pd_dir, proxy_dir):
        d.mkdir(parents=True, exist_ok=True)
        (d / '__init__.py').write_text('')
    (src_dir / 'constants.py').write_text(_git_show(commit_sha, 'src/constants.py'))
    (proxy_dir / 'strip_vocab.py').write_text(_git_show(commit_sha, 'src/proxy/strip_vocab.py'))
    (pd_dir / 'render_messages.py').write_text(_git_show(commit_sha, 'src/proxy_display/render_messages.py'))
    sys.path.insert(0, str(tmp_root))
    return importlib.import_module('old_snapshot.src.proxy_display.render_messages')

def write_report(log_path: Path, collapsed_rows: list, expanded_rows: list, identity_rows: list) -> None:
    n_collapsed_ok = sum(1 for r in collapsed_rows if r['exactly_one_line'] and r['no_leak'])
    n_expanded_ok = sum(1 for r in expanded_rows if r['text_present'] and r['width_ok'])
    n_identical = sum(1 for r in identity_rows if r['identical'])

    lines = _report_summary_lines(
        log_path, n_collapsed_ok, len(collapsed_rows), n_expanded_ok, len(expanded_rows),
        n_identical, len(identity_rows),
    )
    lines += _collapsed_table_lines(collapsed_rows)
    lines += _expanded_table_lines(expanded_rows)
    lines += _identity_table_lines(identity_rows)

    report_path = _write_report_file(lines)

    print(f"collapsed: {n_collapsed_ok}/{len(collapsed_rows)} ok")
    print(f"expanded:  {n_expanded_ok}/{len(expanded_rows)} ok")
    print(f"identical: {n_identical}/{len(identity_rows)} ok")
    print(f"Report written to: {report_path}")
    if n_collapsed_ok < len(collapsed_rows) or n_expanded_ok < len(expanded_rows) or n_identical < len(identity_rows):
        sys.exit(1)


def _report_summary_lines(log_path: Path, n_collapsed_ok: int, n_collapsed_total: int,
                           n_expanded_ok: int, n_expanded_total: int,
                           n_identical: int, n_identity_total: int) -> list:
    return [
        f"# Thinking expander render check — {log_path.name}",
        "",
        f"Source log: `{log_path}`",
        f"Before-commit (byte-identical baseline): `{BEFORE_COMMIT_SHA}`",
        "",
        "## Deliverable numbers (real render path — render_turn._render_req_expanded)",
        "",
        f"- collapsed check: {n_collapsed_ok}/{n_collapsed_total} thinking blocks — exactly one line, no text leak",
        f"- expanded check: {n_expanded_ok}/{n_expanded_total} (block x pane_width combos) — full text present, no line over pane_width",
        f"- byte-identical check: {n_identical}/{n_identity_total} non-thinking block types identical to pre-change render",
        "",
    ]


def _collapsed_table_lines(collapsed_rows: list) -> list:
    lines = [
        "## Collapsed — per thinking block",
        "",
        "| entry | msg | blk | exactly 1 line | no text leak |",
        "|---|---|---|---|---|",
    ]
    for r in collapsed_rows:
        lines.append(f"| {r['eidx']} | {r['midx']} | {r['bidx']} | {'yes' if r['exactly_one_line'] else 'FAIL'} | {'yes' if r['no_leak'] else 'FAIL'} |")
    return lines


def _expanded_table_lines(expanded_rows: list) -> list:
    lines = ["", "## Expanded — per thinking block x pane_width", "",
             "| entry | msg | blk | chars | pane_width | text present | max content width | width ok |",
             "|---|---|---|---|---|---|---|---|"]
    for r in expanded_rows:
        lines.append(
            f"| {r['eidx']} | {r['midx']} | {r['bidx']} | {r['chars']} | {r['pane_width']} | "
            f"{'yes' if r['text_present'] else 'FAIL'} | {r['max_w']} | {'yes' if r['width_ok'] else 'FAIL'} |"
        )
    return lines


def _identity_table_lines(identity_rows: list) -> list:
    lines = ["", "## Byte-identical (non-thinking blocks, pre- vs post-milestone)", "",
             "| type | entry | msg | blk | identical | line count |",
             "|---|---|---|---|---|---|"]
    for r in identity_rows:
        lines.append(f"| {r['btype']} | {r['eidx']} | {r['midx']} | {r['bidx']} | {'yes' if r['identical'] else 'FAIL'} | {r['line_count']} |")
    return lines


def _write_report_file(lines: list) -> Path:
    report_dir = Path(__file__).resolve().parent / 'md'
    report_dir.mkdir(parents=True, exist_ok=True)
    ts = datetime.now().strftime('%Y%m%d_%H%M%S')
    report_path = report_dir / f'render_thinking_expander_{ts}.md'
    report_path.write_text('\n'.join(lines) + '\n', encoding='utf-8')
    return report_path


if __name__ == '__main__':
    arg_path = Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_LOG
    render_thinking_expander_workflow(arg_path)
