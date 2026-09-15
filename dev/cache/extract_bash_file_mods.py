import json
import sys
from pathlib import Path

# INFRASTRUCTURE

WORKTREE_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(WORKTREE_ROOT))

from src.constants import BASH_FILE_MODIFICATION_FORMS

MAIN_REPO_ROOT = Path('/Users/brunowinter2000/Documents/ai/monitor-cc')
LOG_DIR = MAIN_REPO_ROOT / 'src' / 'logs' / 'dual_log'
OUTPUT_DIR = Path(__file__).parent / 'jsonl'
OUTPUT_PATH = OUTPUT_DIR / 'bash_file_mods.jsonl'

# ORCHESTRATOR

def extract_workflow() -> None:
    log_paths = _all_original_logs()
    records = []
    for log_path in log_paths:
        records.extend(_extract_session_records(log_path))
    _write_records(records)

# FUNCTIONS

def _all_original_logs() -> list:
    return sorted(LOG_DIR.glob('*_original.jsonl'))

def _extract_session_records(log_path: Path) -> list:
    session_stem = log_path.name.removesuffix('_original.jsonl')
    seen_ids = set()
    records = []
    with open(log_path, encoding='utf-8') as f:
        for line in f:
            entry = _parse_line(line)
            if entry is None:
                continue
            for block in _bash_tool_use_blocks(entry):
                tool_use_id = block.get('id')
                if tool_use_id is None or tool_use_id in seen_ids:
                    continue
                seen_ids.add(tool_use_id)
                command = block.get('input', {}).get('command', '')
                matched_forms = _matching_forms(command)
                if not matched_forms:
                    continue
                records.append(_build_record(session_stem, tool_use_id, entry.get('timestamp'), command, matched_forms))
    return records

def _parse_line(line: str):
    try:
        return json.loads(line)
    except json.JSONDecodeError:
        return None

def _bash_tool_use_blocks(entry: dict) -> list:
    blocks = []
    for message in entry.get('payload', {}).get('messages', []):
        content = message.get('content')
        if not isinstance(content, list):
            continue
        for block in content:
            if isinstance(block, dict) and block.get('type') == 'tool_use' and block.get('name') == 'Bash':
                blocks.append(block)
    return blocks

def _matching_forms(command: str) -> list:
    labels = []
    tee_append_matched = False
    for form in BASH_FILE_MODIFICATION_FORMS:
        if not form['pattern'].search(command):
            continue
        if form['label'] == 'tee -a':
            tee_append_matched = True
        labels.append(form['label'])
    if tee_append_matched and 'tee (truncating)' in labels:
        labels.remove('tee (truncating)')
    return labels

def _build_record(session_stem: str, tool_use_id: str, timestamp, command: str, matched_forms: list) -> dict:
    return {
        'session': session_stem,
        'tool_use_id': tool_use_id,
        'timestamp': timestamp,
        'matched_forms': matched_forms,
        'command': command,
    }

def _write_records(records: list) -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    with open(OUTPUT_PATH, 'w', encoding='utf-8') as f:
        for record in records:
            f.write(json.dumps(record) + '\n')

if __name__ == '__main__':
    extract_workflow()
