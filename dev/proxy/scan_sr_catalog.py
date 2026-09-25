#!/usr/bin/env python3
# INFRASTRUCTURE
import json
import re
from collections import defaultdict
from pathlib import Path

LOGS_DIR = Path('/Users/brunowinter2000/Documents/ai/Monitor_CC/src/logs')
OUT_FILE = Path('/tmp/sr_catalog.md')

CODE_INDICATORS = [
    r'.*?\?',
    r'\\s\*',
    r'\.\.\.',
    're\.DOTALL',
    'return \\"',
    'in text:',
    "re.escape(",
    "re.compile(",
    "r'<system-reminder>",
    'r"<system-reminder>',
    "> = das String",
    "> = the ",
    "`: True",
    "': True",
    "': [",
    "': {",
    "positions:",
    "blocks from msg",
    "> und `",
    "hey\\n\\n",
    "hello from user",
    "\\nhello from",
    "\\nhey\\n",
    "…",
    "…",
]

_SKIPPED_LINES = 0


# ORCHESTRATOR

def scan_sr_catalog_workflow():
    print('Scanning logs...', flush=True)
    total_entries, logs, stripped_sr, stripped_tn, false_positives, missed_sr = scan_all_logs()

    print_done(logs, total_entries)
    print_stripped_sr_templates(stripped_sr)
    print_false_positives(false_positives)
    print_missed_srs(missed_sr)
    print_tns_stripped(stripped_tn)
    _report_skipped_lines()

    report = write_report(total_entries, logs, stripped_sr, stripped_tn, false_positives, missed_sr)
    OUT_FILE.write_text(report, encoding='utf-8')
    print_report()


# FUNCTIONS

def scan_all_logs():
    stripped_sr = defaultdict(lambda: {'count': 0, 'examples': [], 'locations': defaultdict(int)})
    stripped_tn = {'count': 0, 'examples': []}
    false_positives = defaultdict(lambda: {'count': 0, 'examples': []})
    missed_sr = defaultdict(lambda: {'count': 0, 'examples': [], 'locations': defaultdict(int)})

    SR_RE = re.compile(r'<system-reminder>(.*?)</system-reminder>', re.DOTALL)

    logs = sorted(LOGS_DIR.glob('api_requests_*.jsonl'))
    total_entries = 0

    for log in logs:
        with open(log, 'r', encoding='utf-8') as f:
            for line in f:
                try:
                    d = json.loads(line)
                    total_entries += 1
                    rp = d.get('raw_payload', {})
                    msgs = rp.get('messages', [])
                    removed = d.get('stripped_msg_removed', {})
                    _process_stripped_chunks(removed, msgs, stripped_sr, stripped_tn, false_positives)
                    _process_missed_srs(msgs, SR_RE, missed_sr)
                except (json.JSONDecodeError, KeyError, TypeError):
                    _note_skipped_line()
                    continue

    return total_entries, logs, stripped_sr, stripped_tn, false_positives, missed_sr


def _process_stripped_chunks(removed: dict, msgs: list, stripped_sr: dict, stripped_tn: dict,
                              false_positives: dict) -> None:
    for idx_str, chunks in removed.items():
        idx = int(idx_str)
        role, shape = location_context(msgs, idx)
        loc_key = f'{role}|{shape}'
        for chunk in chunks:
            if not isinstance(chunk, str):
                continue
            tag_class = classify_chunk(chunk)
            if tag_class == 'real-sr':
                inner = chunk[len('<system-reminder>'):].strip()
                if inner.startswith('<new-diagnostics>'):
                    nd_inner = re.search(r'<new-diagnostics>(.*?)</new-diagnostics>', inner, re.DOTALL)
                    if nd_inner:
                        nd_text = nd_inner.group(1).strip()
                        key = 'pyright-new-diagnostics'
                        stripped_sr[key]['count'] += 1
                        stripped_sr[key]['locations'][loc_key] += 1
                        if len(stripped_sr[key]['examples']) < 2:
                            stripped_sr[key]['examples'].append(chunk[:300])
                        continue
                key = first_sentence(inner)
                stripped_sr[key]['count'] += 1
                stripped_sr[key]['locations'][loc_key] += 1
                if len(stripped_sr[key]['examples']) < 2:
                    stripped_sr[key]['examples'].append(chunk[:300])
            elif tag_class == 'real-tn':
                stripped_tn['count'] += 1
                if len(stripped_tn['examples']) < 2:
                    stripped_tn['examples'].append(chunk[:300])
            elif tag_class == 'false-positive':
                inner = chunk[len('<system-reminder>'):].strip()
                key = inner[:80]
                false_positives[key]['count'] += 1
                if len(false_positives[key]['examples']) < 2:
                    false_positives[key]['examples'].append(chunk[:400])


def location_context(msgs: list, idx: int) -> tuple:
    if idx >= len(msgs):
        return ('?', 'unknown')
    msg = msgs[idx]
    role = msg.get('role', '?')
    c = msg.get('content', '')
    if isinstance(c, str):
        return (role, 'string')
    elif isinstance(c, list):
        block_types = sorted(set(b.get('type', '?') for b in c))
        return (role, 'list[' + '+'.join(block_types) + ']')
    return (role, 'other')


def classify_chunk(chunk: str):
    if chunk.startswith('<system-reminder>'):
        if is_code_false_positive(chunk):
            return 'false-positive'
        return 'real-sr'
    if chunk.startswith('<task-notification>'):
        return 'real-tn'
    return 'other'


def is_code_false_positive(chunk: str) -> bool:
    inner = chunk
    if chunk.startswith('<system-reminder>'):
        inner = chunk[len('<system-reminder>'):].strip()
    elif chunk.startswith('<task-notification>'):
        return False
    for indicator in CODE_INDICATORS:
        if indicator in inner[:300]:
            return True
    return False


def first_sentence(inner: str) -> str:
    inner = inner.strip()
    if inner.startswith('<new-diagnostics>'):
        return inner[:80]
    if inner.startswith('<task-id>'):
        return '<structured-task-notification>'
    for line in inner.split('\n'):
        line = line.strip()
        if line:
            return line[:120]
    return inner[:80]


def _process_missed_srs(msgs: list, sr_re, missed_sr: dict) -> None:
    for mi, msg in enumerate(msgs):
        role = msg.get('role', '?')
        c = msg.get('content', '')
        blocks_to_check = []
        if isinstance(c, str):
            blocks_to_check.append(('string', c))
        elif isinstance(c, list):
            for blk in c:
                bt = blk.get('type', '')
                if bt == 'text':
                    blocks_to_check.append(('text-block', blk.get('text', '')))
                elif bt == 'tool_result':
                    bc = blk.get('content', '')
                    if isinstance(bc, str):
                        blocks_to_check.append(('tool_result-str', bc))
                    elif isinstance(bc, list):
                        for sb in bc:
                            if isinstance(sb, dict):
                                blocks_to_check.append(('tool_result-nested', sb.get('text', '')))
        for block_shape, text in blocks_to_check:
            if not text or '<system-reminder>' not in text:
                continue
            for inner in sr_re.findall(text):
                inner_stripped = inner.strip()
                if is_code_false_positive('<system-reminder>' + inner):
                    continue
                if len(inner_stripped) < 5:
                    continue
                key = first_sentence(inner_stripped)
                loc_key = f'{role}|{block_shape}'
                missed_sr[key]['count'] += 1
                missed_sr[key]['locations'][loc_key] += 1
                if len(missed_sr[key]['examples']) < 2:
                    missed_sr[key]['examples'].append(('<system-reminder>' + inner + '</system-reminder>')[:300])


def _note_skipped_line() -> None:
    global _SKIPPED_LINES
    _SKIPPED_LINES += 1


def print_done(logs, total_entries):
    print(f'Done. {len(logs)} logs, {total_entries} entries.')


def print_stripped_sr_templates(stripped_sr):
    print(f'  Stripped SR templates: {len(stripped_sr)}')


def print_false_positives(false_positives):
    print(f'  False positives: {sum(d["count"] for d in false_positives.values())}')


def print_missed_srs(missed_sr):
    print(f'  Missed SRs: {sum(d["count"] for d in missed_sr.values())}')


def print_tns_stripped(stripped_tn):
    print(f'  TNs stripped: {stripped_tn["count"]}')


def _report_skipped_lines() -> None:
    print(f'skipped undecodable lines: {_SKIPPED_LINES}')


def write_report(total_entries, logs, stripped_sr, stripped_tn, false_positives, missed_sr):
    lines = ['# SR Catalog — Monitor_CC Proxy Logs\n', f'Scanned {len(logs)} log files, {total_entries} entries total.\n']
    lines += _render_stripped_sr_lines(stripped_sr)
    fp_lines, total_fp = _render_false_positives_lines(false_positives)
    lines += fp_lines
    missed_lines, total_missed = _render_missed_sr_lines(missed_sr)
    lines += missed_lines
    lines += _render_tn_and_summary_lines(stripped_tn, stripped_sr, total_fp, total_missed)
    return ''.join(lines)


def _render_stripped_sr_lines(stripped_sr: dict) -> list:
    lines = [
        '\n## System-Reminder Catalog (Stripped by Proxy)\n',
        '| Template (first sentence / type) | Count | Confidence | Locations |\n',
        '|---|---|---|---|\n',
    ]
    for key, data in sorted(stripped_sr.items(), key=lambda x: -x[1]['count']):
        loc_str = fmt_locations(data['locations'])
        lines.append(f'| `{key[:100]}` | {data["count"]} | real | {loc_str} |\n')
    lines.append(f'\n**Total distinct SR templates stripped:** {len(stripped_sr)}\n')
    lines.append('\n### SR Examples\n')
    for key, data in sorted(stripped_sr.items(), key=lambda x: -x[1]['count'])[:8]:
        lines.append(f'\n#### `{key[:80]}`\n')
        for ex in data['examples'][:1]:
            lines.append(f'```\n{ex}\n```\n')
    return lines


def fmt_locations(loc_dict: dict) -> str:
    parts = []
    for k, v in sorted(loc_dict.items(), key=lambda x: -x[1]):
        parts.append(f'{k} ({v}x)')
    return '; '.join(parts[:3])


def _render_false_positives_lines(false_positives: dict) -> tuple:
    total_fp = sum(d['count'] for d in false_positives.values())
    lines = [
        '\n## False-Positives (Proxy stripped code incorrectly)\n',
        '| Chunk Preview (first 80 chars) | Count | Why False |\n',
        '|---|---|---|\n',
    ]
    for key, data in sorted(false_positives.items(), key=lambda x: -x[1]['count']):
        reason = 'Python code / regex pattern containing <system-reminder> literal'
        lines.append(f'| `{key[:80].replace("|", "/")}` | {data["count"]} | {reason} |\n')
    lines.append(f'\n**Total false-positive strips:** {total_fp}\n')
    lines.append('\n### False-Positive Examples\n')
    fp_examples_shown = 0
    for key, data in sorted(false_positives.items(), key=lambda x: -x[1]['count'])[:3]:
        if fp_examples_shown >= 3:
            break
        lines.append(f'\n#### `{key[:60]}`\n')
        for ex in data['examples'][:1]:
            lines.append(f'```\n{ex}\n```\n')
        fp_examples_shown += 1
    return lines, total_fp


def _render_missed_sr_lines(missed_sr: dict) -> tuple:
    total_missed = sum(d['count'] for d in missed_sr.values())
    lines = [
        '\n## Missed SRs (in raw_payload, NOT stripped)\n',
        'These reached Claude after proxy processing — proxy failed to strip them.\n\n',
        '| Template | Count | Locations |\n',
        '|---|---|---|\n',
    ]
    for key, data in sorted(missed_sr.items(), key=lambda x: -x[1]['count'])[:20]:
        loc_str = fmt_locations(data['locations'])
        lines.append(f'| `{key[:100].replace("|", "/")}` | {data["count"]} | {loc_str} |\n')
    lines.append(f'\n**Total missed SR occurrences (top 20 shown):** {total_missed}\n')
    return lines, total_missed


def _render_tn_and_summary_lines(stripped_tn: dict, stripped_sr: dict, total_fp: int, total_missed: int) -> list:
    lines = [
        '\n## Task-Notification Catalog (Stripped)\n',
        f'**Count:** {stripped_tn["count"]} (structured blocks: `<task-id>`, `<tool-use-id>`, `<output-file>`, `<status>`, `<summary>`)\n',
    ]
    if stripped_tn['examples']:
        lines.append('\n### TN Example\n')
        lines.append(f'```\n{stripped_tn["examples"][0]}\n```\n')
    lines.append('\n## Summary\n')
    lines.append(f'| Category | Count |\n')
    lines.append(f'|---|---|\n')
    lines.append(f'| Distinct SR templates (stripped correctly) | {len(stripped_sr)} |\n')
    lines.append(f'| Total SR chunks stripped | {sum(d["count"] for d in stripped_sr.values())} |\n')
    lines.append(f'| False-positive strips | {total_fp} |\n')
    lines.append(f'| Missed SRs (reached Claude) | {total_missed} |\n')
    lines.append(f'| TN blocks stripped | {stripped_tn["count"]} |\n')
    return lines


def print_report():
    print(f'\nReport: {OUT_FILE}')


if __name__ == '__main__':
    scan_sr_catalog_workflow()
