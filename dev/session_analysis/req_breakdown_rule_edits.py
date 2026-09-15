# INFRASTRUCTURE
import subprocess
from datetime import datetime, timezone
from pathlib import Path

# FUNCTIONS

def _extract_timestamp_from_path(path):
    if path is None:
        return None
    name = Path(path).stem
    for part in reversed(name.split('_')):
        if part.isdigit() and len(part) >= 9:
            return int(part)
    return None

def _find_text_overlap(context_text, file_content):
    chunk_size = 80
    step = 20
    for i in range(0, max(0, len(context_text) - chunk_size), step):
        chunk = context_text[i:i + chunk_size].strip()
        if len(chunk) < 40:
            continue
        if chunk in file_content:
            return chunk
    return None

def _fetch_git_log(shared_rules, prev_ts, curr_ts):
    is_git_repo = False
    if shared_rules.exists():
        try:
            subprocess.run(
                ['git', '-C', str(shared_rules), 'status'],
                capture_output=True, check=True,
            )
            is_git_repo = True
        except (subprocess.CalledProcessError, FileNotFoundError):
            pass

    if not (is_git_repo and prev_ts and curr_ts):
        return None
    prev_dt = datetime.fromtimestamp(prev_ts, tz=timezone.utc).strftime('%Y-%m-%d %H:%M:%S')
    curr_dt = datetime.fromtimestamp(curr_ts, tz=timezone.utc).strftime('%Y-%m-%d %H:%M:%S')
    try:
        proc = subprocess.run(
            ['git', '-C', str(shared_rules), 'log',
             f'--since={prev_dt}', f'--until={curr_dt}',
             '--name-only', '--pretty=format:%h %cI %s'],
            capture_output=True, text=True,
        )
        return proc.stdout.strip() or '(no commits in window)'
    except Exception as e:
        return f'Error: {e}'

def _scan_mtime_files(prev_ts, curr_ts):
    rule_dirs = [
        Path.home() / '.claude' / 'shared-rules' / 'global',
        Path.home() / '.claude' / 'rules',
    ]
    mtime_files = []
    for rule_dir in rule_dirs:
        if not rule_dir.exists():
            continue
        for md_file in sorted(rule_dir.glob('*.md')):
            mtime = md_file.stat().st_mtime
            if prev_ts and curr_ts and prev_ts <= mtime <= curr_ts:
                mtime_files.append({
                    'path': str(md_file),
                    'mtime': mtime,
                    'mtime_str': datetime.fromtimestamp(mtime).strftime('%Y-%m-%d %H:%M:%S'),
                    'drift_match': None,
                })
    return mtime_files

def _cross_check_drift_match(attribution, mtime_files):
    drift_match = None
    if attribution and not attribution.get('error') and mtime_files:
        drift_context = attribution.get('context', {}).get('new', '')
        for f_info in mtime_files:
            try:
                file_content = Path(f_info['path']).read_text()
                overlap = _find_text_overlap(drift_context, file_content)
                if overlap:
                    f_info['drift_match'] = overlap
                    if drift_match is None:
                        drift_match = f_info['path']
            except Exception:
                pass
    return drift_match

def compute_rule_edits(proxy_path, prev_proxy_path, attribution):
    curr_ts = _extract_timestamp_from_path(proxy_path)
    prev_ts = _extract_timestamp_from_path(prev_proxy_path) if prev_proxy_path else None

    shared_rules = Path.home() / '.claude' / 'shared-rules'
    git_log = _fetch_git_log(shared_rules, prev_ts, curr_ts)
    mtime_files = _scan_mtime_files(prev_ts, curr_ts)
    drift_match = _cross_check_drift_match(attribution, mtime_files)

    return {
        'curr_ts': curr_ts,
        'prev_ts': prev_ts,
        'git_log': git_log,
        'mtime_files': mtime_files,
        'drift_match': drift_match,
    }
