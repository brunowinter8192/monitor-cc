# INFRASTRUCTURE
from test_strip_fix_fixtures import (
    check, tool_result_str, tool_result_list, text_block,
    _apply_first_pass, _apply_interrupt_marker_strip, _WAKEUP_TEXT,
    _strip_bg_launch_ack, _strip_interrupt_marker,
    _INTERRUPT_MARKER, _INTERRUPT_MARKER_TOOL_USE,
)

# FUNCTIONS

# ── LAUNCH-ACK ID + PATH RECOVERY, TN ID LINE (2026-07-29 milestone) ──────────
# Both bg-launch-ack (strip_bg_launch_ack.py) and TN termination (_apply_first_pass) now emit a
# 3-line message: <line1>, then 'Output: <path>' (if extracted), then 'ID: <id>' (if extracted) —
# same fixed order in both places. Extraction verified against real recorded ack/TN bodies from
# src/logs/dual_log/ (api_requests_opus_monitor_cc_1785336796_original.jsonl +
# api_requests_opus_posts_1785338463_original.jsonl) — W18/W19 pin the exact real bodies.

# W15 — genuine ack, id + path both present (the only shape seen in real data) → 3 lines, fixed order
def w15_launch_ack_id_and_path_full():
    ack = ('Command running in background with ID: bg_01ABC. '
           'Output is being written to: /tmp/output_01ABC.txt. '
           'You will be notified when it completes. '
           'To check interim output, use Read on that file path.')
    new_content, removed = _strip_bg_launch_ack(ack)
    check('W15_msg_line', new_content.startswith('Command is running in the background.'), repr(new_content))
    check('W15_output_line', 'Output: /tmp/output_01ABC.txt' in new_content, repr(new_content))
    check('W15_id_line', 'ID: bg_01ABC' in new_content, repr(new_content))
    check('W15_line_order', new_content.index('Output:') < new_content.index('ID:'), repr(new_content))
    check('W15_removed_is_original_ack', removed == [ack])


# W16 — synthetic: id token empty → ID line omitted, no 'ID: None', Output line unaffected
def w16_launch_ack_missing_id_omits_id_line():
    ack = ('Command running in background with ID: . '
           'Output is being written to: /tmp/out.txt. '
           'You will be notified when it completes. '
           'To check interim output, use Read on that file path.')
    new_content, _removed = _strip_bg_launch_ack(ack)
    check('W16_no_id_line', 'ID:' not in new_content, repr(new_content))
    check('W16_no_dangling_none', 'None' not in new_content, repr(new_content))
    check('W16_output_line_present', 'Output: /tmp/out.txt' in new_content, repr(new_content))


# W17 — synthetic: no "Output is being written to:" segment → Output line omitted, ID unaffected
def w17_launch_ack_missing_path_omits_output_line():
    ack = 'Command running in background with ID: bg_02DEF. You will be notified when it completes.'
    new_content, _removed = _strip_bg_launch_ack(ack)
    check('W17_no_output_line', 'Output:' not in new_content, repr(new_content))
    check('W17_id_line_present', 'ID: bg_02DEF' in new_content, repr(new_content))


# W18 — real recorded ack body (src/logs/dual_log/api_requests_opus_monitor_cc_1785336796_original.jsonl)
def w18_launch_ack_real_corpus_body_exact():
    ack = (
        'Command running in background with ID: bg6wod7up. Output is being written to: '
        '/private/tmp/claude-501/-Users-brunowinter2000-Documents-ai-monitor-cc/'
        '80b146dd-9d9e-4cae-83c0-a1bbebb9e0cb/tasks/bg6wod7up.output. '
        'You will be notified when it completes. To check interim output, use Read on that file path.'
    )
    expected = (
        'Command is running in the background. Do NOT check, poll, or read its output — '
        'just wait until it finishes (you will get a completion notice).\n'
        'Output: /private/tmp/claude-501/-Users-brunowinter2000-Documents-ai-monitor-cc/'
        '80b146dd-9d9e-4cae-83c0-a1bbebb9e0cb/tasks/bg6wod7up.output\n'
        'ID: bg6wod7up\n'
    )
    new_content, _removed = _strip_bg_launch_ack(ack)
    check('W18_real_corpus_launch_exact', new_content == expected, repr(new_content))


# W19 — real recorded TN body (same corpus, failed status) → exact 3-line termination text
def w19_tn_real_corpus_body_exact():
    tn = (
        '<task-notification>\n<task-id>biw31morg</task-id>\n'
        '<tool-use-id>toolu_014Z5hrjf2UxcVLCKJqZyQ1U</tool-use-id>\n'
        '<output-file>/private/tmp/claude-501/-Users-brunowinter2000-Documents-ai-monitor-cc/'
        '80b146dd-9d9e-4cae-83c0-a1bbebb9e0cb/tasks/biw31morg.output</output-file>\n'
        '<status>failed</status>\n'
        '<summary>Background command "Rechenschleife bis Signal oder 30min-Timeout" failed with exit code 42</summary>\n'
        '</task-notification>'
    )
    expected = (
        'background done — check worker or other process\n'
        'Output: /private/tmp/claude-501/-Users-brunowinter2000-Documents-ai-monitor-cc/'
        '80b146dd-9d9e-4cae-83c0-a1bbebb9e0cb/tasks/biw31morg.output\n'
        'ID: biw31morg\n'
    )
    msgs = [{'role': 'user', 'content': tn}]
    new_msgs, mods, _, _c, _, _ops = _apply_first_pass(msgs)
    check('W19_real_corpus_tn_exact', new_msgs[0]['content'] == expected, repr(new_msgs[0]['content']))
    check('W19_mod_replaced', 'replaced_task_notification' in mods, f'mods: {mods}')


# W20 — TN block with <output-file> but no <task-id> → ID line omitted, Output line present
def w20_tn_missing_task_id_omits_id_line():
    tn = '<task-notification>\n<output-file>/tmp/foo.output</output-file>\n<status>completed</status>\n<summary>x</summary>\n</task-notification>\n'
    msgs = [{'role': 'user', 'content': tn}]
    new_msgs, mods, _, _c, _, _ops = _apply_first_pass(msgs)
    result = new_msgs[0]['content']
    check('W20_no_id_line', 'ID:' not in result, repr(result))
    check('W20_no_dangling_none', 'None' not in result, repr(result))
    check('W20_output_line_present', 'Output: /tmp/foo.output' in result, repr(result))


# W21 — TN block with <task-id> but no <output-file> → Output line omitted, ID line present
def w21_tn_missing_output_file_omits_output_line():
    tn = '<task-notification>\n<task-id>abc999</task-id>\n<status>completed</status>\n<summary>x</summary>\n</task-notification>\n'
    msgs = [{'role': 'user', 'content': tn}]
    new_msgs, mods, _, _c, _, _ops = _apply_first_pass(msgs)
    result = new_msgs[0]['content']
    check('W21_no_output_line', 'Output:' not in result, repr(result))
    check('W21_id_line_present', 'ID: abc999' in result, repr(result))


# W22 — neither <task-id> nor <output-file> → reduces to exactly _WAKEUP_TEXT (regression guard for
# the lines-list refactor: unconditional join must collapse back to the original bare-wakeup shape)
def w22_tn_no_id_no_output_reduces_to_bare_wakeup():
    tn = '<task-notification>\n<status>completed</status>\n<summary>x</summary>\n</task-notification>\n'
    msgs = [{'role': 'user', 'content': tn}]
    new_msgs, mods, _, _c, _, _ops = _apply_first_pass(msgs)
    check('W22_bare_wakeup_only', new_msgs[0]['content'] == _WAKEUP_TEXT, repr(new_msgs[0]['content']))


# ── LAUNCH-ACK WORDING 2 RECOGNITION (2026-07-29 milestone-2) ─────────────────
# Second CC wording ("Command was manually backgrounded by user with ID: ...") — fired when the
# user manually backgrounds an already-running Bash call, distinct from the wording-1 initial-
# launch ack. Measured in dev/bg_wakeup_id_line/md/launch_ack_wordings_20260729.md (2026-07-29):
# no ". You will be notified..." trailing sentence, ack IS the complete block in the only measured
# occurrence. W23 pins the exact 220-char live-observed text verbatim (not a paraphrase). W24 pins
# the trailing-content-in-same-block shape the M1 blast-radius classification flagged as possible
# but unobserved ("ANY trailing content after the ack in that block is also discarded").

# W23 — real live-observed wording-2 body, verbatim (2026-07-29 live observation) — exact 3-line output
def w23_launch_ack_wording2_real_body_exact():
    ack = (
        'Command was manually backgrounded by user with ID: bsxpatpam. Output is being written '
        'to: /private/tmp/claude-501/-Users-brunowinter2000-Documents-ai-monitor-cc/'
        '587284d6-c174-4432-a8d0-b5e2bcf10f0b/tasks/bsxpatpam.output'
    )
    check('W23_input_length_220', len(ack) == 220, f'len={len(ack)}')
    expected = (
        'Command is running in the background. Do NOT check, poll, or read its output — '
        'just wait until it finishes (you will get a completion notice).\n'
        'Output: /private/tmp/claude-501/-Users-brunowinter2000-Documents-ai-monitor-cc/'
        '587284d6-c174-4432-a8d0-b5e2bcf10f0b/tasks/bsxpatpam.output\n'
        'ID: bsxpatpam\n'
    )
    new_content, removed = _strip_bg_launch_ack(ack)
    check('W23_wording2_real_body_exact', new_content == expected, repr(new_content))
    check('W23_removed_is_original_ack', removed == [ack])
    check('W23_same_msg_line_as_wording1', new_content.startswith(
        'Command is running in the background. Do NOT check, poll, or read its output'
    ))


# W24 — wording-2 ack followed by trailing content in the SAME block (unobserved in the measured
# corpus, but the pass's own replacement mechanism discards "ANY trailing content after the ack in
# that block" per the M1 blast-radius classification — regression guard for the fix: without a
# newline bound on _ACK_PATH_RE's no-sentence fallback, this trailing text was swallowed into the
# Output line instead of being cleanly discarded with the rest of the block)
def w24_launch_ack_wording2_trailing_content_not_swallowed_into_path():
    ack = (
        'Command was manually backgrounded by user with ID: bsxpatpam. Output is being written '
        'to: /private/tmp/y/tasks/bsxpatpam.output'
    )
    ack_with_trailing = ack + '\nsome trailing note'
    new_content, _removed = _strip_bg_launch_ack(ack_with_trailing)
    check('W24_output_line_path_only',
          'Output: /private/tmp/y/tasks/bsxpatpam.output\n' in new_content, repr(new_content))
    check('W24_trailing_note_not_swallowed', 'some trailing note' not in new_content, repr(new_content))
    check('W24_id_line_present', 'ID: bsxpatpam' in new_content, repr(new_content))


# ── LAUNCH-ACK WORDING 3: AUTO-BACKGROUNDED ON TIMEOUT (2026-09-14 milestone) ─────────────────
# Third CC wording — Bash auto-backgrounds a call that exceeded its own timeout (not a deliberate
# run_in_background launch, not a manual user backgrounding). Distinct anchored prefix ("Command did
# not complete within its"), distinct ID shape ("(ID: <id>)" instead of "with ID: <id>."), and a
# trailing "Session cwd remains ..." sentence in the SAME block that wording 1/2 never carry. The
# replacement message names the timeout cause explicitly so it reads differently from a deliberate
# background launch.

# W34 — real recorded wording-3 body, verbatim (src/logs/dual_log/
# api_requests_opus_monitor_cc_1789383190_original.jsonl, 2026-09-14) → exact 3-line output, trailing
# cwd sentence discarded along with the rest of the matched ack (same discard behavior as W24).
def w34_launch_ack_wording3_real_corpus_body_exact():
    ack = (
        'Command did not complete within its 120s timeout and was moved to the background (ID: '
        'b1mahby4a). Output is being written to: /private/tmp/claude-501/'
        '-Users-brunowinter2000-Documents-ai-monitor-cc/d7b0d213-0c28-4e53-baf8-c11fa7838f0b/'
        'tasks/b1mahby4a.output. You will be notified when it completes. To check interim output, '
        'use Read on that file path.\n'
        'Session cwd remains /Users/brunowinter2000/Documents/ai/monitor-cc; directory changes made '
        'by the backgrounded command do not apply to subsequent commands.'
    )
    expected = (
        'Command exceeded its timeout and was moved to the background. Do NOT check, poll, or read '
        'its output — just wait until it finishes (you will get a completion notice).\n'
        'Output: /private/tmp/claude-501/-Users-brunowinter2000-Documents-ai-monitor-cc/'
        'd7b0d213-0c28-4e53-baf8-c11fa7838f0b/tasks/b1mahby4a.output\n'
        'ID: b1mahby4a\n'
    )
    new_content, removed = _strip_bg_launch_ack(ack)
    check('W34_real_corpus_wording3_exact', new_content == expected, repr(new_content))
    check('W34_removed_is_original_ack_incl_cwd_sentence', removed == [ack])


# ── INTERRUPT-MARKER TESTS (strip_interrupt_marker.py, 2026-07-30, re-measured 2026-07-31) ────
# CC records the proxy's bg_escape.py tmux-Escape into a worker's pane as
# "[Request interrupted by user]" or "[Request interrupted by user for tool use]" — never a
# genuine user interrupt. Both real corpus wordings carry a trailing '\n' (11/11 occurrences,
# src/logs/dual_log/*_original.jsonl, 2026-07-31 re-measurement). Whole-block match anchored
# (ignoring only surrounding whitespace), NOT substring-anywhere — same FP-nuke class as
# bg_launch_ack / sn_notice / plan_mode.
_INTERRUPT_MARKER_NL = _INTERRUPT_MARKER + '\n'
_INTERRUPT_MARKER_TOOL_USE_NL = _INTERRUPT_MARKER_TOOL_USE + '\n'

# W25 — real measured shape: tool_result / marker(+trailing '\n') / injected wake-up (3 blocks).
# Marker emptied to '.'; neighbors byte-identical.
def w25_interrupt_marker_real_shape_neighbors_intact():
    tool_result_block = {'type': 'tool_result', 'tool_use_id': 'toolu_01', 'content': 'prior output'}
    marker_block = {'type': 'text', 'text': _INTERRUPT_MARKER_NL}
    wakeup_block = {'type': 'text', 'text': _WAKEUP_TEXT}
    content = [tool_result_block, marker_block, wakeup_block]
    new_content, removed = _strip_interrupt_marker(content)
    check('W25_removed_is_marker', removed == [_INTERRUPT_MARKER_NL])
    check('W25_block_count_unchanged', len(new_content) == 3)
    check('W25_marker_block_emptied', new_content[1] == {'type': 'text', 'text': '.'})
    check('W25_preceding_block_identical', new_content[0] == tool_result_block)
    check('W25_following_block_identical', new_content[2] == wakeup_block)


# W26 — 4 content shapes, each with the real newline-terminated marker.
def w26_interrupt_marker_four_shapes():
    s, r = _strip_interrupt_marker(_INTERRUPT_MARKER_NL)
    check('W26_str_shape', s == '.' and r == [_INTERRUPT_MARKER_NL])
    lt, r = _strip_interrupt_marker(text_block(_INTERRUPT_MARKER_NL))
    check('W26_list_text_shape', lt[0]['text'] == '.' and r == [_INTERRUPT_MARKER_NL])
    trs, r = _strip_interrupt_marker(tool_result_str(_INTERRUPT_MARKER_NL))
    check('W26_tool_result_str_shape', trs[0]['content'] == '.' and r == [_INTERRUPT_MARKER_NL])
    trl, r = _strip_interrupt_marker(tool_result_list(_INTERRUPT_MARKER_NL))
    check('W26_tool_result_list_shape', trl[0]['content'][0]['text'] == '.' and r == [_INTERRUPT_MARKER_NL])


# W26b — the 2nd real wording ("for tool use"), newline-terminated and bare, both strip.
def w26b_interrupt_marker_tool_use_wording():
    s, r = _strip_interrupt_marker(_INTERRUPT_MARKER_TOOL_USE_NL)
    check('W26b_tool_use_wording_nl_stripped', s == '.' and r == [_INTERRUPT_MARKER_TOOL_USE_NL])
    s2, r2 = _strip_interrupt_marker(_INTERRUPT_MARKER_TOOL_USE)
    check('W26b_tool_use_wording_bare_stripped', s2 == '.' and r2 == [_INTERRUPT_MARKER_TOOL_USE])


# W27 — false-positive class: marker embedded inside longer text must survive untouched, incl.
# a real corpus-derived 180-char user message that quotes the bracketed marker mid-sentence
# (src/logs/dual_log/api_requests_opus_monitor_cc_1785431184_original.jsonl, msg 11).
def w27_interrupt_marker_embedded_in_longer_text_untouched():
    longer = f'Note earlier: {_INTERRUPT_MARKER} was quoted from a transcript.'
    new_tb, r1 = _strip_interrupt_marker(text_block(longer))
    check('W27_top_level_text_untouched', new_tb[0]['text'] == longer and r1 == [])
    new_tr, r2 = _strip_interrupt_marker(tool_result_str(longer))
    check('W27_tool_result_untouched', new_tr[0]['content'] == longer and r2 == [])
    new_str, r3 = _strip_interrupt_marker(longer)
    check('W27_top_level_str_untouched', new_str == longer and r3 == [])

    corpus_quote = (
        '[Image #3] ok live verify da. hast du  [Request interrupted by user] gesehen? wenn ja '
        'funktionniert der strip nicht. wenn nein funktionniert der strip aber das rendering ist broken'
    )
    new_cq, r4 = _strip_interrupt_marker(text_block(corpus_quote))
    check('W27_corpus_quote_untouched', new_cq[0]['text'] == corpus_quote and r4 == [])


# W28 — message-pass wiring: role='user' only, mod name, removed-chunk attribution — real
# newline-terminated marker.
def w28_interrupt_marker_pass_role_gate_and_mod():
    msgs = [
        {'role': 'assistant', 'content': text_block(_INTERRUPT_MARKER_NL)},
        {'role': 'user', 'content': [
            {'type': 'tool_result', 'tool_use_id': 'toolu_02', 'content': 'output'},
            {'type': 'text', 'text': _INTERRUPT_MARKER_NL},
            {'type': 'text', 'text': _WAKEUP_TEXT},
        ]},
    ]
    new_msgs, mods, removed_by_idx, changed, _inj, ops = _apply_interrupt_marker_strip(msgs)
    check('W28_assistant_role_untouched', new_msgs[0] == msgs[0])
    check('W28_user_msg_changed', changed == [1])
    check('W28_mod_name', mods == ['stripped_interrupt_marker'])
    check('W28_removed_chunk', removed_by_idx[1] == [_INTERRUPT_MARKER_NL])
    check('W28_ops_recorded_block1', 1 in ops.get(1, {}))


# W29 — message-pass wiring for the "for tool use" wording (previously untested — the gap the
# false-negative shipped through).
def w29_interrupt_marker_pass_tool_use_wording():
    msgs = [
        {'role': 'user', 'content': [
            {'type': 'tool_result', 'tool_use_id': 'toolu_03', 'content': 'output'},
            {'type': 'text', 'text': _INTERRUPT_MARKER_TOOL_USE_NL},
            {'type': 'text', 'text': _WAKEUP_TEXT},
        ]},
    ]
    new_msgs, mods, removed_by_idx, changed, _inj, ops = _apply_interrupt_marker_strip(msgs)
    check('W29_user_msg_changed', changed == [0])
    check('W29_mod_name', mods == ['stripped_interrupt_marker'])
    check('W29_removed_chunk', removed_by_idx[0] == [_INTERRUPT_MARKER_TOOL_USE_NL])
    check('W29_marker_block_emptied', new_msgs[0]['content'][1]['text'] == '.')
