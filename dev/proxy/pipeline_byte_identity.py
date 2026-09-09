"""
Byte-identity regression harness for the src/proxy/ modification pipeline
(proxy milestone A — message_passes split + helper extraction).

Replays apply_modification_rules + _strip_all_cache_control + _set_cache_breakpoints +
_build_forwarded_delta + _build_stripped_injected_deltas + _build_errors_entries over every
request payload found in a frozen, bounded-prefix copy of the newest *_original.jsonl under
src/logs/dual_log/ (main checkout, read-only — the live file can keep growing during a work
session, see the bounded-prefix + env-var-override notes below), for both worker_context="main"
and worker_context="worker:x", with timestamp-shaped fields normalized out, hashing the full
output sequence (modified payload, modifications list, forwarded/stripped/injected delta
entries, error entries) for every payload x every worker_context.

Usage (from project root):
    ./venv/bin/python dev/proxy/pipeline_byte_identity.py

Prints one HASH line. Run before and after a src/proxy/ refactor; the hash must match. Never
commits a log snapshot — only reads.
"""

# INFRASTRUCTURE
import hashlib
import json
import os
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_ROOT))

_MAIN_LOG_DIR = Path('/Users/brunowinter2000/Documents/ai/monitor-cc/src/logs/dual_log')
_PREFIX_LINES = 60  # bounded prefix — an append-only source file's own prefix never changes
_TIMESTAMP_KEYS = ('timestamp', 'ts')
_WORKER_CONTEXTS = ('main', 'worker:x')

# ORCHESTRATOR

def main():
    orig_path = _newest_original_log()
    payloads = _load_payloads(orig_path)
    digest = hashlib.sha256()
    for worker_context in _WORKER_CONTEXTS:
        _hash_pipeline_run(payloads, worker_context, digest)
    print(f'source: {orig_path.name}')
    print(f'payloads: {len(payloads)}')
    print(f'HASH: {digest.hexdigest()}')


# FUNCTIONS

# PROXY_PIPELINE_BYTE_IDENTITY_LOG overrides the source *_original.jsonl path — needed to pin a
# before/after comparison to the exact same bytes when the default (newest file under the live
# MAIN checkout) can itself be THIS very session's own actively-growing log (same pitfall class
# documented for dev/proxy_display/render_byte_identity.py and dev/workers/format_byte_identity.py
# — see their own Gotchas). Snapshot a real *_original.jsonl to a fixed path once, then point both
# runs at it via the env var for full reproducibility.
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
                continue
            payload = entry.get('payload')
            if isinstance(payload, dict):
                payloads.append(payload)
    return payloads


# Strip volatile timestamp-shaped fields from a dict/list structure so the hash is stable across
# runs made at different wall-clock times — everything else (including dict key ORDER, which
# real json.dumps(entry) writes to the JSONL byte-for-byte) stays part of the hashed signal.
def _normalize_for_hash(obj):
    if isinstance(obj, dict):
        return {k: ('<TS>' if k in _TIMESTAMP_KEYS else _normalize_for_hash(v)) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_normalize_for_hash(v) for v in obj]
    return obj


def _infer_model_family(model: str) -> str:
    m = (model or '').lower()
    if 'haiku' in m:
        return 'haiku'
    if 'sonnet' in m:
        return 'sonnet'
    return 'opus'


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


if __name__ == '__main__':
    main()
