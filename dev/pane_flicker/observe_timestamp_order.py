# INFRASTRUCTURE
import json
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_ROOT))

_MAIN_LOGS = Path('/Users/brunowinter2000/Documents/ai/monitor-cc/src/logs')
_PROJECTS = Path.home() / '.claude' / 'projects'
_REPORT = Path(__file__).resolve().parent / 'md' / 'observe_timestamp_order.md'

# ORCHESTRATOR

def main():
    rows = []
    rows += [_check_forwarded(p) for p in sorted(_MAIN_LOGS.rglob('*_forwarded.jsonl'))]
    rows += [_check_transcript(p) for p in sorted(_PROJECTS.rglob('*.jsonl')) if 'subagents' not in p.parts]
    _write_report(rows)


# FUNCTIONS

def _first_disorder(stamps: list):
    for i in range(1, len(stamps)):
        if stamps[i] < stamps[i - 1]:
            return i
    return None


def _check_forwarded(path: Path) -> tuple:
    stamps = []
    for raw in path.open(encoding='utf-8'):
        try:
            e = json.loads(raw)
        except json.JSONDecodeError:
            continue
        if e.get('type') == 'forwarded_delta':
            stamps.append(e.get('timestamp', ''))
    return ('forwarded', str(path), len(stamps), _first_disorder(stamps))


def _check_transcript(path: Path) -> tuple:
    from src.jsonl import read_json_records, extract_cache_turns
    try:
        messages, _ = read_json_records(path, 0)
        turns = extract_cache_turns(messages)
    except Exception as exc:
        return ('transcript-error', str(path), 0, repr(exc))
    stamps = [t.get('timestamp', '') for t in turns]
    return ('turns', str(path), len(stamps), _first_disorder(stamps))


def _write_report(rows: list) -> None:
    lines = ['# observe_timestamp_order', '', 'kind | count files | with disorder', '---|---|---']
    for kind in ('forwarded', 'turns', 'transcript-error'):
        sel = [r for r in rows if r[0] == kind]
        lines.append(f'{kind} | {len(sel)} | {sum(1 for r in sel if r[3] is not None)}')
    lines += ['', 'Disorder rows (kind, path, n, first index):']
    lines += [f'- {r}' for r in rows if r[3] is not None]
    _REPORT.write_text('\n'.join(lines) + '\n', encoding='utf-8')
    print('\n'.join(lines))


if __name__ == '__main__':
    main()
