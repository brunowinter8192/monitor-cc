# INFRASTRUCTURE
import hashlib
import json
import os
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_ROOT))

_MAIN_LOG_DIR = Path('/Users/brunowinter2000/Documents/ai/monitor-cc/src/logs/dual_log')
_PREFIX_LINES = 60
_TIMESTAMP_KEYS = ('timestamp', 'ts')
_WORKER_CONTEXTS = ('main', 'worker:x')

_SKIPPED_LINES = 0


# ORCHESTRATOR

def main():
    orig_path = _newest_original_log()
    payloads = _load_payloads(orig_path)
    digest = hashlib.sha256()
    process_worker_contexts(payloads, digest)
    print(f'source: {orig_path.name}')
    print(f'payloads: {len(payloads)}')
    _report_skipped_lines()
    print(f'HASH: {digest.hexdigest()}')


# FUNCTIONS

def _newest_original_log() -> Path:
    override = os.environ.get('PROXY_PIPELINE_BYTE_IDENTITY_LOG')
    if override:
        return Path(override)
    files = sorted(_MAIN_LOG_DIR.glob('*_original.jsonl'), key=lambda p: p.stat().st_mtime)
    if not files:
        raise SystemExit(f'no *_original.jsonl logs found under {_MAIN_LOG_DIR}')
    return files[-1]


def _load_payloads(orig_path: Path) -> list:
    payloads = []
    with open(orig_path, 'r', encoding='utf-8') as f:
        for i, raw_line in enumerate(f):
            if i >= _PREFIX_LINES:
                break
            line = raw_line.strip()
            if not line:
                continue
            try:
                entry = json.loads(line)
            except json.JSONDecodeError:
                _note_skipped_line()
                continue
            payload = entry.get('payload')
            if isinstance(payload, dict):
                payloads.append(payload)
    return payloads


def _note_skipped_line() -> None:
    global _SKIPPED_LINES
    _SKIPPED_LINES += 1


def process_worker_contexts(payloads, digest):
    for worker_context in _WORKER_CONTEXTS:
        _hash_pipeline_run(payloads, worker_context, digest)


def _hash_pipeline_run(payloads: list, worker_context: str, digest) -> None:
    from src.proxy.rules import apply_modification_rules
    from src.proxy.cache import _strip_all_cache_control, _set_cache_breakpoints
    from src.proxy.logging import _build_forwarded_delta, _build_errors_entries
    from src.proxy.strip_inject_delta import _build_stripped_injected_deltas
    from src.proxy.message_summary import _summarize_message

    prev_mod_messages = None
    prev_delta_hashes = None
    prev_stripped_hashes = None
    prev_injected_hashes = None
    seen_error_ids: set = set()

    for i, orig_payload in enumerate(payloads):
        model_family = _infer_model_family(orig_payload.get('model', ''))

        modified, modifications, _orig_sys2, _s_idx, _s_orig, _s_removed, _i_added, all_ops = apply_modification_rules(
            orig_payload, model_family, '', worker_context,
        )
        modified = _strip_all_cache_control(modified)
        modified = _set_cache_breakpoints(modified, prev_mod_messages)
        prev_mod_messages = [_summarize_message(m) for m in modified.get('messages', [])]

        request_id = f'req-{i}'
        fwd_entry, prev_delta_hashes = _build_forwarded_delta(modified, request_id, prev_delta_hashes)

        model_str = modified.get('model', '')
        stripped_entry, injected_entry, prev_stripped_hashes, prev_injected_hashes = _build_stripped_injected_deltas(
            orig_payload, modified, request_id, prev_stripped_hashes, prev_injected_hashes, model_str, all_ops,
        )

        err_entries = _build_errors_entries(
            orig_payload, request_id, '2026-01-01T00:00:00.000Z', seen_error_ids,
            worker_context, 'sess', 'proxy_file',
        )
        seen_error_ids = seen_error_ids | {e['tool_use_id'] for e in err_entries}

        digest.update(f'{worker_context}|{i}|'.encode())
        digest.update(json.dumps(_normalize_for_hash(modified), default=str).encode())
        digest.update(json.dumps(modifications).encode())
        digest.update(json.dumps(_normalize_for_hash(fwd_entry), default=str).encode())
        digest.update(json.dumps(_normalize_for_hash(stripped_entry), default=str).encode())
        digest.update(json.dumps(_normalize_for_hash(injected_entry), default=str).encode())
        digest.update(json.dumps(_normalize_for_hash(err_entries), default=str).encode())


def _infer_model_family(model: str) -> str:
    m = (model or '').lower()
    if 'haiku' in m:
        return 'haiku'
    if 'sonnet' in m:
        return 'sonnet'
    return 'opus'


def _normalize_for_hash(obj):
    if isinstance(obj, dict):
        return {k: ('<TS>' if k in _TIMESTAMP_KEYS else _normalize_for_hash(v)) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_normalize_for_hash(v) for v in obj]
    return obj


def _report_skipped_lines() -> None:
    print(f'skipped undecodable lines: {_SKIPPED_LINES}')


if __name__ == '__main__':
    main()
