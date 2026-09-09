# INFRASTRUCTURE
import atexit
import gc
import os
import resource
import signal
import sys
import tracemalloc
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Callable


# FUNCTIONS

def _rss_line() -> str:
    pid = os.getpid()
    try:
        import psutil as _psutil
        rss = _psutil.Process(pid).memory_info().rss
        rss_src = 'psutil'
    except ImportError:
        raw = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
        rss = raw if sys.platform == 'darwin' else raw * 1024
        rss_src = 'resource'
    rss_str = f'{rss:,} bytes ({rss // 1024 // 1024} MB) [{rss_src}]'
    return f'rss:       {rss_str}'

def _gc_top_lines() -> list:
    lines = ['## Top-30 gc objects by class']
    counts = Counter(type(o).__name__ for o in gc.get_objects()).most_common(30)
    lines.append(f'{"class":<40}  {"count":>8}')
    lines.append('-' * 52)
    for cls, cnt in counts:
        lines.append(f'{cls:<40}  {cnt:>8}')
    return lines

def _tracemalloc_lines() -> list:
    lines = ['## Top-30 tracemalloc by lineno']
    if tracemalloc.is_tracing():
        snapshot = tracemalloc.take_snapshot()
        stats = snapshot.statistics('lineno')[:30]
        lines.append(f'{"file:line":<60}  {"size_bytes":>12}  {"count":>8}')
        lines.append('-' * 84)
        for stat in stats:
            frame_ = stat.traceback[0]
            loc = f'{frame_.filename}:{frame_.lineno}'
            lines.append(f'{loc:<60}  {stat.size:>12,}  {stat.count:>8,}')
    else:
        lines.append('## tracemalloc not active (set MONITOR_CC_RAM_AUDIT=1 to enable)')
    return lines

def _module_state_lines(module_state_provider: Callable[[], list]) -> list:
    lines = []
    for name, val in module_state_provider():
        if isinstance(val, (list, dict, set)):
            lines.append(f'{name:<40}  len={len(val):>6}  sizeof={sys.getsizeof(val):>10,}')
        else:
            lines.append(f'{name:<40}  {val}')
    return lines

def _resolve_dump_path(pane_name: str, ts: str) -> Path:
    root = os.environ.get('MONITOR_CC_ROOT', '')
    if not root:
        root = str(Path(__file__).resolve().parent.parent.parent)
    dump_dir = Path(root) / 'dev' / 'ram_audit' / 'dumps'
    dump_dir.mkdir(parents=True, exist_ok=True)
    return dump_dir / f'{ts}_{pane_name}.txt'

def register_ram_dump(pane_name: str, module_state_provider: Callable[[], list]) -> None:
    if os.environ.get('MONITOR_CC_RAM_AUDIT') == '1':
        if not tracemalloc.is_tracing():
            tracemalloc.start(25)

    pid_file = f'/tmp/.monitor_cc_pid_{pane_name}'
    with open(pid_file, 'w') as _f:
        _f.write(str(os.getpid()))
    atexit.register(lambda: os.path.exists(pid_file) and os.remove(pid_file))

    def _handle_ram_dump(signum, frame) -> None:
        now = datetime.now()
        ts = now.strftime('%Y%m%d_%H%M%S')
        pid = os.getpid()
        dump_path = _resolve_dump_path(pane_name, ts)

        out = []
        out.append(f'# {pane_name} RAM dump')
        out.append(f'timestamp: {now.isoformat()}')
        out.append(f'pid:       {pid}')
        out.append(_rss_line())
        out.append('')
        out.extend(_gc_top_lines())
        out.append('')
        out.extend(_tracemalloc_lines())
        out.append('')
        out.append(f'## {pane_name} module state')
        out.extend(_module_state_lines(module_state_provider))

        dump_path.write_text('\n'.join(out) + '\n', encoding='utf-8')
        print(f'[ram-dump] wrote {dump_path}', file=sys.stderr, flush=True)

    signal.signal(signal.SIGUSR1, _handle_ram_dump)
