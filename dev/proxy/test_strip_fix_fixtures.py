# INFRASTRUCTURE
import importlib
import sys
import os
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
os.environ.setdefault('MONITOR_CC_ROOT', os.path.join(os.path.dirname(__file__), '..', '..'))

_sr_mod = importlib.import_module('src.proxy.strip_sr')
_strip_system_reminders = _sr_mod._strip_system_reminders
_strip_system_reminder = _sr_mod._strip_system_reminder
_strip_all_system_reminders = _sr_mod._strip_all_system_reminders
_strip_plan_mode_blocks = _sr_mod._strip_plan_mode_blocks
_strip_user_interrupt_sr = _sr_mod._strip_user_interrupt_sr
_strip_pyright_diagnostics = _sr_mod._strip_pyright_diagnostics

_ph_mod = importlib.import_module('src.proxy.payload_helpers')
_content_contains = _ph_mod._content_contains
_find_system_reminder_blocks = _ph_mod._find_system_reminder_blocks

_rules_mod = importlib.import_module('src.proxy.message_passes')
_simple_mod = importlib.import_module('src.proxy.message_passes_simple')
_apply_first_pass = _rules_mod._apply_first_pass
_apply_bg_exit_strip = _simple_mod._apply_bg_exit_strip
_apply_sn_notice_strip = _simple_mod._apply_sn_notice_strip
_apply_final_sr_pass = _rules_mod._apply_final_sr_pass
_apply_role_system_strip = _rules_mod._apply_role_system_strip
_apply_interrupt_marker_strip = _simple_mod._apply_interrupt_marker_strip

_bgk_mod = importlib.import_module('src.proxy.strip_bg_completed')
_WAKEUP_TEXT = _bgk_mod._WAKEUP_TEXT
_sn_mod = importlib.import_module('src.proxy.strip_sn_notice')
_SN_NOTICE_PARAGRAPH = _sn_mod._SN_NOTICE_PARAGRAPH
_bg_ack_mod = importlib.import_module('src.proxy.strip_bg_launch_ack')
_strip_bg_launch_ack = _bg_ack_mod._strip_bg_launch_ack
_im_mod = importlib.import_module('src.proxy.strip_interrupt_marker')
_strip_interrupt_marker = _im_mod._strip_interrupt_marker

apply_modification_rules = importlib.import_module('src.proxy.rules').apply_modification_rules

_O = '<system-reminder>'
_C = '</system-reminder>'
_INTERRUPT_MARKER = '[Request interrupted by user]'
_INTERRUPT_MARKER_TOOL_USE = '[Request interrupted by user for tool use]'

PASS = []
FAIL = []


def check(name, condition, msg=''):
    if condition:
        PASS.append(name)
        print(f'  PASS  {name}')
    else:
        FAIL.append(name)
        print(f'  FAIL  {name}' + (f': {msg}' if msg else ''))


# FUNCTIONS

def mk_sr(body):
    return f'{_O}\n{body}\n{_C}'


def real_sr_text(body):
    return mk_sr(body)


def fp_inline(body):
    # Code-literal: <system-reminder> appears mid-line inside a string
    return f'if "{_O}" in text:\n    return "system-reminder"\n    # rest of code\n\n{mk_sr(body)}'


def tool_result_str(text):
    return [{'type': 'tool_result', 'tool_use_id': 'x', 'content': text}]


def tool_result_list(text):
    return [{'type': 'tool_result', 'tool_use_id': 'x', 'content': [{'type': 'text', 'text': text}]}]


def text_block(text):
    return [{'type': 'text', 'text': text}]
