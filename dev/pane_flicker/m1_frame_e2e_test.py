# INFRASTRUCTURE
import re
import subprocess
import sys
import tempfile
import time
import traceback
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

AREA_DIR = Path(__file__).resolve().parent
WORKTREE_ROOT = AREA_DIR.parents[1]
DRIVER = AREA_DIR / 'm1_frame_e2e_driver.py'
REPORT_DIR = AREA_DIR / 'md'
OLD_REF = '0ce370df'
PANES = ['tokens', 'worker_tokens', 'proxy', 'worker_proxy']
TREES = ['old', 'new']
WIDTH, HEIGHT = 100, 30
QUIET_SECONDS = 0.6
POLL_SECONDS = 0.05
DEADLINE_SECONDS = 30
FRAME_MARKERS = (b'\033[?2026h', b'\033[2J')
_SGR_OR_CHAR_RE = re.compile(r'\x1b\[([0-9;]*)m|(.)', re.S)

# ORCHESTRATOR

def test_workflow() -> int:
    with tempfile.TemporaryDirectory(prefix='flicker_m1_') as tmp:
        work_dir = Path(tmp)
        old_root = extract_old_tree(work_dir)
        results = run_all_strands({'old': old_root, 'new': WORKTREE_ROOT}, work_dir)
    verdicts = evaluate(results)
    write_report(verdicts, results)
    return 0 if all(ok for _, ok, _ in verdicts) else 1

# FUNCTIONS

def run_all_strands(roots: dict, work_dir: Path) -> dict:
    strands = [(pane, tree) for pane in PANES for tree in TREES]
    with ThreadPoolExecutor(max_workers=len(strands)) as pool:
        futures = {s: pool.submit(run_strand_guarded, s[0], s[1], roots[s[1]], work_dir) for s in strands}
        return {s: f.result() for s, f in futures.items()}

def run_strand_guarded(pane: str, tree: str, root: Path, work_dir: Path) -> dict:
    try:
        return run_strand(pane, tree, root, work_dir)
    except Exception:
        return {'aborted': traceback.format_exc()[-800:]}

def extract_old_tree(work_dir: Path) -> Path:
    old_root = work_dir / 'old_tree'
    old_root.mkdir()
    archive = subprocess.run(['git', '-C', str(WORKTREE_ROOT), 'archive', OLD_REF], capture_output=True, check=True).stdout
    subprocess.run(['tar', '-x', '-C', str(old_root)], input=archive, check=True)
    return old_root

def hover(row: int) -> str:
    return f"\033[<35;12;{row}M"

def click(row: int) -> str:
    return f"\033[<0;12;{row}M\033[<0;12;{row}m"

def scroll(button: int, row: int) -> str:
    return f"\033[<{button};12;{row}M"

def build_steps(pane: str) -> list:
    steps = [('boot', [])]
    for row in (4, 5, 6, 7, 8, 9):
        steps.append((f'hover_row_{row}', [('lit', hover(row))]))
    steps.append(('click_expand_row_5', [('lit', click(5))]))
    steps.append(('hover_row_8_after_expand', [('lit', hover(8))]))
    steps.append(('click_collapse_row_5', [('lit', click(5))]))
    steps.append(('scroll_up', [('lit', scroll(64, 8)), ('lit', scroll(64, 8))]))
    steps.append(('scroll_down_past_end', [('lit', scroll(65, 8))] * 6))
    steps.append(('search_type', [('lit', '/'), ('lit', 'abcdefgh')]))
    steps.append(('search_backspace', [('key', 'BSpace')] * 6))
    steps.append(('search_commit', [('key', 'Enter')]))
    if pane in ('worker_tokens', 'worker_proxy'):
        steps.append(('switch_worker_2_shorter_frame', [('lit', '2')]))
        steps.append(('switch_worker_1_longer_frame', [('lit', '1')]))
    steps.append(('hover_after_all', [('lit', hover(6))]))
    return steps

def tmux(sock: str, *args) -> subprocess.CompletedProcess:
    return subprocess.run(['tmux', '-L', sock, *args], capture_output=True, text=True)

def send(sock: str, kind: str, payload: str) -> None:
    if kind == 'lit':
        tmux(sock, 'send-keys', '-t', 'flk', '-l', payload)
    else:
        tmux(sock, 'send-keys', '-t', 'flk', payload)

def run_strand(pane: str, tree: str, root: Path, work_dir: Path) -> dict:
    sock = f'flk_m1_{pane}_{tree}'
    try:
        return drive_strand(sock, pane, root, work_dir / f'{pane}_{tree}.raw', f'/tmp/flk_m1_proj_{pane}_{tree}')
    finally:
        tmux(sock, 'kill-server')

def drive_strand(sock: str, pane: str, root: Path, raw_path: Path, project: str) -> dict:
    tmux(sock, 'kill-server')
    tmux(sock, 'new-session', '-d', '-s', 'flk', '-x', str(WIDTH), '-y', str(HEIGHT))
    tmux(sock, 'pipe-pane', '-t', 'flk', f'cat >> {raw_path}')
    cmd = f"cd {root} && {sys.executable} {DRIVER} {root} {pane} {project}"
    shell_flag = cursor_flag(sock)
    start_pane(sock, cmd, raw_path)
    boot_flag = cursor_flag(sock)
    screens = []
    step_flags = []
    raw_marks = []
    for name, actions in build_steps(pane):
        for kind, payload in actions:
            send(sock, kind, payload)
        wait_quiet(sock, raw_path)
        screens.append((name, tmux(sock, 'capture-pane', '-p', '-e', '-N', '-t', 'flk').stdout))
        step_flags.append(cursor_flag(sock))
        raw_marks.append(raw_path.stat().st_size if raw_path.exists() else 0)
    raw_main = read_raw(raw_path)
    burst_flags = burst_hover_flags(sock)
    tmux(sock, 'respawn-pane', '-k', '-t', 'flk')
    respawn_flag = wait_flag(sock, '1')
    start_pane(sock, cmd, raw_path)
    rerun_flag = cursor_flag(sock)
    tmux(sock, 'send-keys', '-t', 'flk', 'C-c')
    exit_flag = wait_flag(sock, '1')
    wait_quiet(sock, raw_path)
    raw_full = read_raw(raw_path)
    return {
        'screens': screens, 'raw': raw_main, 'raw_full': raw_full, 'raw_marks': raw_marks,
        'flags': {'shell': shell_flag, 'boot': boot_flag, 'steps': step_flags, 'burst': burst_flags,
                  'respawn': respawn_flag, 'rerun': rerun_flag, 'exit': exit_flag},
    }

def start_pane(sock: str, cmd: str, raw_path: Path) -> None:
    offset = raw_path.stat().st_size if raw_path.exists() else 0
    tmux(sock, 'send-keys', '-t', 'flk', cmd, 'Enter')
    deadline = time.monotonic() + DEADLINE_SECONDS
    while not any(m in read_raw_bytes(raw_path)[offset:] for m in FRAME_MARKERS):
        if time.monotonic() > deadline:
            raise TimeoutError(f'{sock}: no frame within {DEADLINE_SECONDS}s after start')
        time.sleep(POLL_SECONDS)
    wait_quiet(sock, raw_path)

def wait_quiet(sock: str, raw_path: Path) -> None:
    deadline = time.monotonic() + DEADLINE_SECONDS
    last_state = None
    last_change = time.monotonic()
    while True:
        state = (raw_path.stat().st_size if raw_path.exists() else 0, tmux(sock, 'capture-pane', '-p', '-e', '-N', '-t', 'flk').stdout)
        now = time.monotonic()
        if state != last_state:
            last_state, last_change = state, now
        elif now - last_change >= QUIET_SECONDS:
            return
        if now > deadline:
            raise TimeoutError(f'{sock}: output never settled within {DEADLINE_SECONDS}s')
        time.sleep(POLL_SECONDS)

def wait_flag(sock: str, expected: str) -> str:
    deadline = time.monotonic() + DEADLINE_SECONDS
    flag = cursor_flag(sock)
    while flag != expected and time.monotonic() < deadline:
        time.sleep(POLL_SECONDS)
        flag = cursor_flag(sock)
    return flag

def cursor_flag(sock: str) -> str:
    return tmux(sock, 'display-message', '-p', '-t', 'flk', '#{cursor_flag}').stdout.strip()

def read_raw_bytes(raw_path: Path) -> bytes:
    return raw_path.read_bytes() if raw_path.exists() else b''

def read_raw(raw_path: Path) -> str:
    return raw_path.read_bytes().decode('utf-8', errors='replace') if raw_path.exists() else ''

def burst_hover_flags(sock: str) -> list:
    flags = []
    for i in range(40):
        send(sock, 'lit', hover(4 + i % 8))
        flags.append(cursor_flag(sock))
    return flags

def evaluate(results: dict) -> list:
    verdicts = []
    for pane in PANES:
        old, new = results[(pane, 'old')], results[(pane, 'new')]
        if 'aborted' in old or 'aborted' in new:
            verdicts.append((f'{pane}: strands ran', False, (old.get('aborted') or new.get('aborted'))))
            continue
        verdicts.append((f'{pane}: harness sanity, old tree emits clear-screen', '\033[2J' in old['raw'], ''))
        verdicts.extend(cursor_verdicts(pane, old, new))
        verdicts.append((f'{pane}: new tree emits no 2J', '\033[2J' not in new['raw'], ''))
        verdicts.append((f'{pane}: new tree emits no 3J', '\033[3J' not in new['raw'], ''))
        begins = new['raw'].count('\033[?2026h')
        ends = new['raw'].count('\033[?2026l')
        verdicts.append((f'{pane}: new tree frames wrapped in 2026 pairs ({begins} begin / {ends} end)', begins == ends and begins > 5, ''))
        verdicts.append((f'{pane}: new tree nests correctly (no begin before previous end)', proper_nesting(new['raw']), ''))
        verdicts.append((f'{pane}: new tree has no text outside a sync pair besides boot noise', outside_sync_clean(new['raw']), ''))
        for (name, old_screen), (_, new_screen) in zip(old['screens'], new['screens']):
            verdicts.append((f'{pane}: screen identical at step {name}', normalize(old_screen) == normalize(new_screen), diff_hint(normalize(old_screen), normalize(new_screen))))
    return verdicts

def normalize(screen: str) -> str:
    rows = []
    state = {}
    for line in screen.split('\n'):
        cells = []
        for match in _SGR_OR_CHAR_RE.finditer(line):
            params, char = match.group(1), match.group(2)
            if params is not None:
                apply_sgr(state, params)
            else:
                cells.append((char, tuple(sorted(state.items()))))
        while cells and cells[-1] == (' ', ()):
            cells.pop()
        rows.append(' '.join(f'{c!r}{st}' for c, st in cells))
    return '\n'.join(rows)

def apply_sgr(state: dict, params: str) -> None:
    codes = [int(p) if p else 0 for p in params.split(';')] if params else [0]
    i = 0
    while i < len(codes):
        code = codes[i]
        if code == 0:
            state.clear()
        elif code in (38, 48) and i + 1 < len(codes):
            span = 5 if codes[i + 1] == 2 else 3
            state['fg' if code == 38 else 'bg'] = tuple(codes[i + 1:i + span])
            i += span - 1
        elif code == 39:
            state.pop('fg', None)
        elif code == 49:
            state.pop('bg', None)
        elif code in (22,):
            state.pop('bold', None)
            state.pop('dim', None)
        elif code in (23, 24, 25, 27, 29):
            state.pop(f'attr{code - 20}', None)
        elif code in (1, 2):
            state['bold' if code == 1 else 'dim'] = True
        elif 30 <= code <= 37 or 90 <= code <= 97:
            state['fg'] = (code,)
        elif 40 <= code <= 47 or 100 <= code <= 107:
            state['bg'] = (code,)
        else:
            state[f'attr{code}'] = True
        i += 1

def cursor_verdicts(pane: str, old: dict, new: dict) -> list:
    of, nf = old['flags'], new['flags']
    frames = new['raw'].split('\033[?2026h')[1:]
    return [
        (f'{pane}: harness sanity, shell cursor visible before the pane starts', nf['shell'] == '1' and of['shell'] == '1', ''),
        (f'{pane}: harness sanity, old tree never hides the cursor', set(of['steps']) == {'1'} and of['boot'] == '1', f"{of['steps']}"),
        (f'{pane}: hide sequence reaches the pane before the first frame', 0 <= new['raw'].find('\033[?25l') < new['raw'].find('\033[?2026h'), ''),
        (f'{pane}: every frame carries the hide sequence ({len(frames)} frames)', all(fr.startswith('\033[?25l') for fr in frames), ''),
        (f'{pane}: cursor hidden after boot', nf['boot'] == '0', ''),
        (f'{pane}: cursor hidden after every step', set(nf['steps']) == {'0'}, f"{nf['steps']}"),
        (f'{pane}: cursor hidden across a 40-event hover burst', set(nf['burst']) == {'0'}, f"{nf['burst']}"),
        (f'{pane}: respawn-pane resets to visible cursor', nf['respawn'] == '1', ''),
        (f'{pane}: cursor hidden again after the pane restarts', nf['rerun'] == '0', ''),
        (f'{pane}: cursor visible again after the pane exits (Ctrl+C)', nf['exit'] == '1' and '\033[?25h' in new['raw_full'], ''),
    ]

def proper_nesting(raw: str) -> bool:
    depth = 0
    for token in split_tokens(raw):
        if token == 'B':
            depth += 1
            if depth > 1:
                return False
        elif token == 'E':
            depth -= 1
            if depth < 0:
                return False
    return depth == 0

def split_tokens(raw: str) -> list:
    tokens = []
    i = 0
    while i < len(raw):
        if raw.startswith('\033[?2026h', i):
            tokens.append('B')
            i += 8
        elif raw.startswith('\033[?2026l', i):
            tokens.append('E')
            i += 8
        else:
            i += 1
    return tokens

def outside_sync_clean(raw: str) -> bool:
    first = raw.find('\033[?2026h')
    if first < 0:
        return False
    rest = raw[first:]
    outside = []
    pos = 0
    while True:
        b = rest.find('\033[?2026h', pos)
        if b < 0:
            outside.append(rest[pos:])
            break
        outside.append(rest[pos:b])
        e = rest.find('\033[?2026l', b)
        if e < 0:
            return False
        pos = e + 8
    return all(chunk.replace('\r', '').replace('\n', '') == '' for chunk in outside)

def diff_hint(old_norm: str, new_norm: str) -> str:
    if old_norm == new_norm:
        return ''
    old_lines, new_lines = old_norm.split('\n'), new_norm.split('\n')
    for i, (a, b) in enumerate(zip(old_lines, new_lines)):
        if a != b:
            old_cells, new_cells = a.split(' '), b.split(' ')
            for j, (ca, cb) in enumerate(zip(old_cells, new_cells)):
                if ca != cb:
                    return f'row {i + 1} token {j}/{len(old_cells)}vs{len(new_cells)}: old={ca[:60]!r} new={cb[:60]!r}'
            return f'row {i + 1} length old={len(old_cells)} new={len(new_cells)} tailold={" ".join(old_cells[-9:])!r} tailnew={" ".join(new_cells[-9:])!r}'
    return f'line count old={len(old_lines)} new={len(new_lines)}'

def write_report(verdicts: list, results: dict) -> None:
    REPORT_DIR.mkdir(exist_ok=True)
    ref = subprocess.run(['git', '-C', str(WORKTREE_ROOT), 'rev-parse', '--short', OLD_REF], capture_output=True, text=True).stdout.strip()
    passed = sum(1 for _, ok, _ in verdicts if ok)
    lines = [f'# m1_frame_e2e_test report', '', f'Old tree: git archive {OLD_REF} ({ref}); new tree: working tree',
             f'Terminal: {WIDTH}x{HEIGHT} private tmux sockets flk_m1_<pane>_<tree>', '',
             f'Result: {passed}/{len(verdicts)} checks passed', '']
    for label, ok, hint in verdicts:
        lines.append(f"- {'PASS' if ok else 'FAIL'}  {label}" + (f'  ({hint})' if hint else ''))
    frames = {p: results[(p, 'new')].get('raw', '').count('\033[?2026h') for p in PANES}
    lines += ['', 'Frames written by new tree per pane: ' + ', '.join(f'{p}={n}' for p, n in frames.items())]
    (REPORT_DIR / 'm1_frame_e2e_test.md').write_text('\n'.join(lines) + '\n', encoding='utf-8')
    for label, ok, hint in verdicts:
        if not ok:
            print(f'FAIL {label} {hint}')
    print(f'{passed}/{len(verdicts)} checks passed')

if __name__ == '__main__':
    sys.exit(test_workflow())
