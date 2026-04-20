#!/usr/bin/env python3
"""Replay strip-bug for entry-idx 13 (line 26) in strip-markers log.

Log structure:
  raw_payload = MODIFIED payload (post-strip) — stored by _build_entry(flow, modified_payload)
  stripped_msg_originals = summarized original content via _summarize_content_for_log
  stripped_msg_removed["24"] = 3082 chars that were wrongly stripped from block1 inner

Reconstruction: original msg[24].content = [
    tool_result(block0_inner),          # unchanged: 8853 chars
    tool_result(block1_stripped + removed),  # block1 after + 3082 removed = original 7446 chars
]

After fix: _content_contains only checks text-blocks. msg[24] has NO text blocks.
→ Trigger does not fire → msg[24] untouched → stripped_msg_removed[24] empty.

Run: python3 dev/proxy/replay_strip_bug.py
"""
import sys, os, json
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
os.environ.setdefault('MONITOR_CC_ROOT', os.path.join(os.path.dirname(__file__), '..', '..'))

LOG = '/Users/brunowinter2000/Documents/ai/Monitor_CC/src/logs/api_requests_worker_strip-markers_1776720829.jsonl'
_BUG_ENTRY_LINE = 26
_BUG_MSG_IDX = 24
_BUG_CODE_FRAGMENT = 'return "system-reminder"'
_EXPECTED_REMOVED_CHARS = 3082

from src.proxy.rules import apply_modification_rules


def _load_entry():
    with open(LOG) as f:
        lines = f.readlines()
    return json.loads(lines[_BUG_ENTRY_LINE])


def _reconstruct_original_payload(entry):
    """Rebuild original msg[24] content as list of tool_result blocks.

    raw_payload = modified payload (post-strip). block1 inner was stripped.
    Restore block1 inner by appending the removed content.
    """
    raw_payload = entry['raw_payload']
    messages = list(raw_payload.get('messages', []))
    msg24 = messages[_BUG_MSG_IDX]
    blocks = list(msg24.get('content', []))

    removed_list = entry['stripped_msg_removed'][str(_BUG_MSG_IDX)]
    assert len(removed_list) == 1, f'Expected 1 removed item, got {len(removed_list)}'
    removed_str = removed_list[0]

    # block1 (index 1) had the real SR stripped from its tail
    block1 = blocks[1]
    original_block1_inner = block1['content'] + removed_str
    restored_block1 = {**block1, 'content': original_block1_inner}

    original_msg24 = {**msg24, 'content': [blocks[0], restored_block1]}
    messages[_BUG_MSG_IDX] = original_msg24
    return {**raw_payload, 'messages': messages}


def main():
    print(f'Loading log entry (line {_BUG_ENTRY_LINE})...')
    entry = _load_entry()

    # Confirm baseline
    removed = entry['stripped_msg_removed']
    r24 = removed.get(str(_BUG_MSG_IDX), [])
    old_chars = sum(len(str(x)) for x in r24)
    print(f'  BASELINE: {len(r24)} item(s), {old_chars} chars removed from msg[{_BUG_MSG_IDX}]')
    assert old_chars == _EXPECTED_REMOVED_CHARS, f'Baseline mismatch: {old_chars} != {_EXPECTED_REMOVED_CHARS}'
    assert _BUG_CODE_FRAGMENT in str(r24[0]), 'Code fragment not found in baseline removed'
    print(f'  BASELINE confirmed: {_EXPECTED_REMOVED_CHARS} chars of code were wrongly removed')

    print(f'\nReconstructing original msg[{_BUG_MSG_IDX}] (list of 2 tool_result blocks)...')
    payload = _reconstruct_original_payload(entry)
    msg24_orig = payload['messages'][_BUG_MSG_IDX]
    blocks = msg24_orig['content']
    print(f'  block[0] inner len: {len(blocks[0]["content"])}')
    print(f'  block[1] inner len: {len(blocks[1]["content"])} (= {len(blocks[1]["content"])-_EXPECTED_REMOVED_CHARS} stripped + {_EXPECTED_REMOVED_CHARS} restored)')

    print(f'\nApplying apply_modification_rules (fixed code)...')
    model = entry.get('model', 'claude-opus')
    _, mods, _, stripped_indices, _, stripped_removed = apply_modification_rules(
        payload, model_family=model, project_path=''
    )

    r24_new = stripped_removed.get(_BUG_MSG_IDX, stripped_removed.get(str(_BUG_MSG_IDX), []))
    new_chars = sum(len(str(x)) for x in r24_new) if r24_new else 0
    msg24_in_stripped = _BUG_MSG_IDX in stripped_indices

    print(f'\n  AFTER FIX stripped_removed[{_BUG_MSG_IDX}]: {new_chars} chars, in_stripped_indices={msg24_in_stripped}')

    if new_chars == 0 and not msg24_in_stripped:
        print(f'\nRESULT: PASS — msg[{_BUG_MSG_IDX}] completely untouched by fixed code')
    elif new_chars > 0 and _BUG_CODE_FRAGMENT in str(r24_new):
        print(f'\nRESULT: FAIL — code literal still stripped ({new_chars} chars)')
        sys.exit(1)
    else:
        print(f'\nRESULT: PARTIAL — {new_chars} chars stripped (not the code literal):')
        for item in r24_new:
            print(f'  {repr(str(item)[:120])}')

    print(f'\nModifications applied: {mods}')


if __name__ == '__main__':
    main()
