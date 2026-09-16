# INFRASTRUCTURE
import json
import re
from collections import Counter
from pathlib import Path

MAIN_REPO_ROOT = Path('/Users/brunowinter2000/Documents/ai/monitor-cc')
LOG_DIR = MAIN_REPO_ROOT / 'src' / 'logs' / 'dual_log'

STEMS = [
    'api_requests_opus_wise2627_1788612045',
    'api_requests_opus_websearch_1788611995',
    'api_requests_opus_monitor_cc_1788611156',
]

_ENDS_WITH_TAG_RE = re.compile(r'<total_tokens>(\d+) tokens left</total_tokens>\s*\Z')

REPORT_DIR = Path(__file__).parent / 'md'
REPORT_PATH = REPORT_DIR / 'trailing_message_shapes_report.md'

# FUNCTIONS

def _all_stripped_texts(path: Path) -> list:
    texts = []
    with open(path, encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            entry = json.loads(line)
            msgs_delta = entry.get('messages_delta') or {}
            for blks in msgs_delta.values():
                if not isinstance(blks, dict):
                    continue
                for blk in blks.values():
                    if not isinstance(blk, list):
                        continue
                    for t in blk:
                        if isinstance(t, str):
                            texts.append(t)
    return texts


def _normalize(text: str) -> str:
    return _ENDS_WITH_TAG_RE.sub('<total_tokens>N tokens left</total_tokens>', text)


# ORCHESTRATOR
def main() -> None:
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    lines = ['# Trailing-message shape probe (total_tokens tag)', '']
    overall = Counter()

    for stem in STEMS:
        path = LOG_DIR / f'{stem}_stripped.jsonl'
        texts = _all_stripped_texts(path)
        qualifying = [t for t in texts if _ENDS_WITH_TAG_RE.search(t)]
        shapes = Counter(_normalize(t) for t in qualifying)
        overall.update(shapes)

        print(f'\n{stem}')
        print(f'  total stripped texts scanned: {len(texts)}')
        print(f'  ending-with-tag texts: {len(qualifying)}')
        print(f'  distinct shapes: {len(shapes)}')
        lines.append(f'## {stem}')
        lines.append('')
        lines.append(f'- total stripped texts scanned: {len(texts)}')
        lines.append(f'- ending-with-tag texts: {len(qualifying)}')
        lines.append(f'- distinct shapes: {len(shapes)}')
        lines.append('')
        lines.append('| count | shape (repr, truncated to 200 chars) |')
        lines.append('|---|---|')
        for shape, count in shapes.most_common():
            display = repr(shape)
            if len(display) > 200:
                display = display[:200] + '...'
            print(f'    {count:>4}  {display}')
            lines.append(f'| {count} | `{display}` |')
        lines.append('')

    print(f'\nOVERALL distinct shapes across all 3 sessions: {len(overall)}')
    lines.append('## Overall (union across sessions)')
    lines.append('')
    lines.append(f'- distinct shapes across all 3 sessions: {len(overall)}')
    lines.append('')
    lines.append('| total count | shape (repr, truncated to 200 chars) |')
    lines.append('|---|---|')
    for shape, count in overall.most_common():
        display = repr(shape)
        if len(display) > 200:
            display = display[:200] + '...'
        lines.append(f'| {count} | `{display}` |')

    REPORT_PATH.write_text('\n'.join(lines))
    print(f'\nReport written: {REPORT_PATH}')


if __name__ == '__main__':
    main()
