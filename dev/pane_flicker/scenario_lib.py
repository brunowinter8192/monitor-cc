# INFRASTRUCTURE
import hashlib
import inspect
import json
import os
import shutil
import sys
import tempfile
from pathlib import Path

_LOG_DIR = Path(os.environ.get(
    'PANE_FLICKER_LOG_DIR',
    '/Users/brunowinter2000/Documents/ai/monitor-cc/src/logs/dual_log',
))
_STEM = os.environ.get('PANE_FLICKER_STEM', 'api_requests_opus_monitor_cc_1790241323')
_ORIGINAL_TAIL_LINES = 2
_ENTRIES_PER_TURN = 7
_PANE_HEIGHT = 50
_FAR_FUTURE = 4_000_000_000.0
_PAST = 1.0


def _read_lines(kind: str) -> list:
    with open(_LOG_DIR / f'{_STEM}_{kind}.jsonl', 'r', encoding='utf-8') as f:
        return f.readlines()


# FUNCTIONS

def load_root(root: str) -> None:
    sys.path.insert(0, root)
    os.environ['MONITOR_CC_ROOT'] = root


class Sim:
    def __init__(self, root: str):
        load_root(root)
        from src.proxy_display import proxy_pane_shared as shared
        from src.proxy_display import forwarded_parser, dual_log_accumulator, format as fmt
        from src import pane_error_log
        self.shared, self.fwd_mod, self.acc_mod, self.fmt = shared, forwarded_parser, dual_log_accumulator, fmt
        self.tmp = Path(tempfile.mkdtemp(prefix='pane_flicker_'))
        pane_error_log.PANE_ERROR_LOG_PATH = str(self.tmp / 'pane_error.log')
        (self.tmp / 'dual_log').mkdir()
        self.log_path = self.tmp / f'{_STEM}.jsonl'
        self.src = {k: _read_lines(k) for k in ('forwarded', 'stripped', 'injected', 'response')}
        self.src['original'] = _read_original_tail()
        self.request_id_of_flow = {json.loads(l)['flow_id']: json.loads(l)['request_id'] for l in self.src['response']}
        self.calls = {'render_turn_expanded': 0}
        self.turn_cache = _new_cache(fmt)
        self.cache_supported = self.turn_cache is not None
        self._patch_counter()
        self.reset_state()

    def _patch_counter(self) -> None:
        try:
            from src.proxy_display import frozen_turns
            target = frozen_turns
        except ImportError:
            from src.proxy_display import render_turn as target
        original = target.render_turn_expanded
        calls = self.calls

        def counted(*a, **k):
            calls['render_turn_expanded'] += 1
            return original(*a, **k)
        target.render_turn_expanded = counted

    def reset_state(self) -> None:
        for p in (self.tmp / 'dual_log').glob('*'):
            p.unlink()
        self.written = {k: 0 for k in self.src}
        self.pos = {'fwd': 0, 'strip': 0, 'inj': 0, 'orig': 0, 'resp': 0}
        self.entries, self.expand, self.line_map, self.copy_rows = [], {}, {}, set()
        self.acc_fwd, self.acc_strip, self.acc_inj, self.acc_orig = {}, {}, {}, {}
        self.rid_by_flow, self.status_by_flow = {}, {}
        self.turn_dicts, self.turns = [], []
        self.scroll, self.just_expanded = 0, None
        self.feedback, self.search_matches, self.search_set, self.search_query, self.search_current = {}, [], set(), '', None
        self.undo = []
        if self.turn_cache is not None:
            self.turn_cache.clear()

    def write_upto(self, counts: dict) -> None:
        for kind, n in counts.items():
            n = min(n, len(self.src[kind]))
            if n > self.written[kind]:
                path = self.tmp / 'dual_log' / f'{_STEM}_{kind}.jsonl'
                with open(path, 'a', encoding='utf-8') as f:
                    f.writelines(self.src[kind][self.written[kind]:n])
                self.written[kind] = n

    def refresh(self, counts: dict) -> None:
        self.write_upto(counts)
        fwd_path = self.tmp / 'dual_log' / f'{_STEM}_forwarded.jsonl'
        new_entries, self.pos['fwd'] = self.fwd_mod._parse_forwarded_log(fwd_path, self.pos['fwd'], self.acc_fwd)
        for e in new_entries:
            e['_source_file'] = fwd_path.name
        self.entries.extend(new_entries)
        from src.proxy_display.parser import _find_response_log_path, _find_original_log_path
        self.pos['resp'] = self.shared._accumulate_request_ids(
            _find_response_log_path(self.log_path), self.pos['resp'], self.rid_by_flow, self.status_by_flow)
        self.shared._attach_http_status(self.entries, self.status_by_flow)
        self.pos['orig'] = self.acc_mod.accumulate_original_tools(_find_original_log_path(self.log_path), self.pos['orig'], self.acc_orig)
        self.pos['strip'], self.pos['inj'] = self.shared._accumulate_dual_logs_and_attach(
            new_entries, self.entries, self.expand, self.log_path, self.acc_strip, self.acc_inj,
            self.pos['strip'], self.pos['inj'], self.fwd_mod._infer_model_family, self.acc_orig)
        self.rebuild_turns()

    def rebuild_turns(self, unsorted_pair: int = None) -> None:
        n_turns = (len(self.entries) + _ENTRIES_PER_TURN - 1) // _ENTRIES_PER_TURN
        while len(self.turn_dicts) < n_turns:
            self.turn_dicts.append(None)
        for t in range(n_turns):
            lo, hi = t * _ENTRIES_PER_TURN, min(len(self.entries), (t + 1) * _ENTRIES_PER_TURN)
            calls = [self._call(i) for i in range(lo, hi) if self.entries[i].get('flow_id') in self.request_id_of_flow]
            stale = self.turn_dicts[t]
            if stale is None or len(stale['api_calls']) != len(calls):
                self.turn_dicts[t] = {'prompt': f'prompt number {t} ' + 'x' * (t % 30), 'timestamp': self.entries[lo]['timestamp'], 'api_calls': calls, 'thinking_chars': 0}
        self.turns = list(self.turn_dicts[:n_turns])

    def _call(self, i: int) -> dict:
        e = self.entries[i]
        blocks = [{'type': 'thinking', 'sig_chars': 100}] if i % 5 == 0 else []
        return {'request_id': self.request_id_of_flow[e['flow_id']], 'timestamp': e['timestamp'], 'cache_read': 1, 'cache_creation': 0, 'direct': 1, 'output_tokens': 5, 'content_blocks': blocks}

    def swap_turn_timestamps(self, t: int) -> None:
        a, b = dict(self.turn_dicts[t]), dict(self.turn_dicts[t + 1])
        a['timestamp'], b['timestamp'] = b['timestamp'], a['timestamp']
        self.turn_dicts[t], self.turn_dicts[t + 1] = a, b
        self.turns = list(self.turn_dicts[:len(self.turns)])

    def render(self, hover=None, width=80, height=_PANE_HEIGHT, feedback=None) -> tuple:
        before = self.calls['render_turn_expanded']
        self.copy_rows.clear()
        body_height = height - 1
        viewport = max(1, body_height - 1)
        current = self.search_matches[self.search_current] if self.search_matches and self.search_current < len(self.search_matches) else None
        fb = self.feedback if feedback is None else feedback

        def _render(scroll_offset, want_positions):
            item_positions = {} if want_positions else None
            kwargs = dict(
                turns=self.turns, item_positions_out=item_positions, copy_feedback=fb, copy_rows_out=self.copy_rows,
                search_match_set=self.search_set, search_current_entry_idx=current, search_query=self.search_query,
                request_id_by_flow=self.rid_by_flow)
            if self.cache_supported:
                kwargs['turn_cache'] = self.turn_cache
            body, total = self.fmt.format_proxy_block(self.entries, self.expand, self.line_map, hover, body_height, width, scroll_offset, **kwargs)
            return body, total, item_positions
        body, self.scroll = self.shared._render_and_scroll_body(_render, self.line_map, self.copy_rows, 1, self.just_expanded, self.scroll, viewport)
        self.just_expanded = None
        calls = self.calls['render_turn_expanded'] - before
        digest = hashlib.sha256()
        digest.update(body.encode())
        digest.update(self._render_everything(width, fb, current).encode())
        digest.update(repr((self.scroll, sorted(self.line_map.items(), key=repr), sorted(self.copy_rows))).encode())
        return digest.hexdigest(), calls

    def _render_everything(self, width: int, feedback, current) -> str:
        kwargs = dict(
            turns=self.turns, item_positions_out={}, copy_feedback=feedback, copy_rows_out=set(),
            search_match_set=self.search_set, search_current_entry_idx=current, search_query=self.search_query,
            request_id_by_flow=self.rid_by_flow)
        if self.cache_supported:
            kwargs['turn_cache'] = self.turn_cache
        body, total = self.fmt.format_proxy_block(self.entries, self.expand, {}, None, 100000, width, 0, **kwargs)
        return f'{total}|{body}'

    def scale_up(self, factor: int) -> None:
        base = list(self.entries)
        grown = list(base)
        for k in range(1, factor):
            for e in base:
                copy = dict(e)
                copy['timestamp'] = f"{2026 + k}{e['timestamp'][4:]}"
                copy['flow_id'] = f"{e['flow_id']}#{k}"
                if e['flow_id'] in self.request_id_of_flow:
                    self.request_id_of_flow[copy['flow_id']] = f"{self.request_id_of_flow[e['flow_id']]}#{k}"
                    self.rid_by_flow[copy['flow_id']] = self.request_id_of_flow[copy['flow_id']]
                    self.status_by_flow[copy['flow_id']] = 200
                grown.append(copy)
        self.entries[:] = grown
        self.turn_dicts = []
        self.rebuild_turns()
        self.shared._attach_http_status(self.entries, self.status_by_flow)

    def render_timed(self, hover) -> None:
        self.copy_rows.clear()
        body_height = _PANE_HEIGHT - 1
        viewport = max(1, body_height - 1)

        def _render(scroll_offset, want_positions):
            item_positions = {} if want_positions else None
            kwargs = dict(
                turns=self.turns, item_positions_out=item_positions, copy_feedback=self.feedback, copy_rows_out=self.copy_rows,
                search_match_set=self.search_set, search_current_entry_idx=None, search_query=self.search_query,
                request_id_by_flow=self.rid_by_flow)
            if self.cache_supported:
                kwargs['turn_cache'] = self.turn_cache
            body, total = self.fmt.format_proxy_block(self.entries, self.expand, self.line_map, hover, body_height, 80, scroll_offset, **kwargs)
            return body, total, item_positions
        self.shared._render_and_scroll_body(_render, self.line_map, self.copy_rows, 1, None, self.scroll, viewport)

    def toggle(self, key) -> None:
        entry_idx = self.shared._entry_idx_from_key(key)
        self.undo.append((key, self.expand.get(key, False)))
        if self.shared._toggle_expand_and_lazy_load(key, entry_idx, self.entries, self.log_path, self.expand):
            self.just_expanded = key

    def search(self, query: str) -> None:
        from src import search_bar
        state = search_bar.SearchState()
        state.query = query
        self.shared._run_pane_search(state, self.entries, self.expand, 80, self.log_path, lambda: None)
        self.search_query, self.search_matches, self.search_set = state.query, state.matches, state.match_set
        self.search_current = 0
        if state.matches:
            self.just_expanded = ('req', state.matches[0])

    def clear_search(self) -> None:
        self.search_query, self.search_matches, self.search_set, self.search_current = '', [], set(), 0

    def cleanup(self) -> None:
        shutil.rmtree(self.tmp, ignore_errors=True)


def _read_original_tail() -> list:
    return _tail_lines(_LOG_DIR / f'{_STEM}_original.jsonl', _ORIGINAL_TAIL_LINES)


def _tail_lines(path: Path, n: int) -> list:
    with open(path, 'rb') as f:
        f.seek(0, os.SEEK_END)
        size = f.tell()
        block = min(size, 64 * 1024 * 1024)
        f.seek(size - block)
        data = f.read().decode('utf-8', errors='replace').splitlines(True)
    return data[-n:]


def _new_cache(fmt):
    if 'turn_cache' not in inspect.signature(fmt.format_proxy_block).parameters:
        return None
    from src.proxy_display.turn_cache import TurnCache
    return TurnCache('scenario')
