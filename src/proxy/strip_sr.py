import re

# INFRASTRUCTURE

_STANDALONE_SR_RE = re.compile(r'(?m)^<system-reminder>.*?</system-reminder>\n?', re.DOTALL)

_INNER_SR_RE = re.compile(r'<system-reminder>(.*?)</system-reminder>', re.DOTALL)

_IMP_LINE_RE = re.compile(r'^[^\n]*IMPORTANT:[^\n]*\n?', re.MULTILINE)

_SR_TEMPLATES = {
    'task-tools-nag':      ("The task tools haven't been used recently",                'full'),
    'pyright-diagnostics': ('<new-diagnostics>',                                        'full'),
    'deferred-tools':      ('The following deferred tools are now available via ToolSearch', 'full'),
    'user-interrupt':      ('The user sent a new message while you were working:',      'partial'),
    'system-notification': ('[SYSTEM NOTIFICATION - NOT USER INPUT]',                   'full'),
    'file-modified':       ('Note: ', 'full', ' was modified'),
    'claudemd-contents':   (["As you answer the user's questions", 'Contents of '],     'full'),
    'date-changed':        ('The date has changed.',                                    'full'),
    'skills-available':    ('The following skills are available',                       'full'),
    'agent-types':         ('Available agent types for the Agent tool',                 'full'),
    'plan-mode':           ('Plan mode ',                                               'full'),
}
_ALL_TEMPLATES = frozenset(_SR_TEMPLATES.keys())

_PRESERVE_PREAMBLE = "As you answer the user's questions, you can use the following context:"

_ENV_CONTEXT_RE = re.compile(
    r"As you answer the user's questions, you can use the following context:\n"
    r"# userEmail\n"
    r"The user's email address is brunowinter7934@gmail\.com\.[^\n]*\n"
    r"# currentDate\n"
    r"Today's date is \d{4}-\d{2}-\d{2}\.\s+"
    r"IMPORTANT: this context may or may not be relevant to your tasks\. "
    r"You should not respond to this context unless it is highly relevant to your task\.",
)

_MARKER_TO_TEMPLATE = {
    'task tools haven':                                'task-tools-nag',
    '<new-diagnostics>':                               'pyright-diagnostics',
    'deferred tools are now available via ToolSearch': 'deferred-tools',
    'user sent a new message while you were working':  'user-interrupt',
    '[SYSTEM NOTIFICATION':                            'system-notification',
    '# claudeMd':                                      'claudemd-contents',
    'Contents of ':                                    'claudemd-contents',
    'The following skills are available':              'skills-available',
    'Available agent types for the Agent tool':        'agent-types',
    'Plan mode is active':                             'plan-mode',
}


# ORCHESTRATOR

def _strip_system_reminders(content, enabled_templates=None):
    if enabled_templates is None:
        enabled_templates = _ALL_TEMPLATES
    if isinstance(content, str):
        return _apply_sr_strip(content, enabled_templates) or '.'
    if isinstance(content, list):
        result = []
        for block in content:
            if not isinstance(block, dict):
                result.append(block)
                continue
            btype = block.get('type')
            if btype == 'text':
                new_text = _apply_sr_strip(block.get('text', ''), enabled_templates)
                result.append({**block, 'text': new_text or '.'})
            else:
                result.append(block)
        return result
    return content


# FUNCTIONS

def _match_template(inner, enabled_templates):
    for tid in enabled_templates:
        spec = _SR_TEMPLATES.get(tid)
        if not spec:
            continue
        identifiers = spec[0] if isinstance(spec[0], list) else [spec[0]]
        required_fragment = spec[2] if len(spec) > 2 else None
        for identifier in identifiers:
            if inner.startswith(identifier):
                if required_fragment is None or required_fragment in inner:
                    return tid, spec[1]
    return None, None


def _apply_sr_strip(text, enabled_templates):
    if not text or '<system-reminder>' not in text:
        return text

    def _replace(m):
        full = m.group(0)
        inner_m = _INNER_SR_RE.search(full)
        if not inner_m:
            return full
        inner = inner_m.group(1).strip()
        if _ENV_CONTEXT_RE.fullmatch(inner):
            return ''
        if inner.startswith(_PRESERVE_PREAMBLE):
            return full
        tid, mode = _match_template(inner, enabled_templates)
        if tid is None:
            return full
        if mode == 'full':
            return ''
        cleaned = _IMP_LINE_RE.sub('', inner_m.group(1))
        trailing_nl = '\n' if full.endswith('\n') else ''
        return '<system-reminder>' + cleaned + '</system-reminder>' + trailing_nl

    return _STANDALONE_SR_RE.sub(_replace, text)


def _strip_plan_mode_blocks(content):
    stripped = _strip_system_reminders(content, {'plan-mode'})
    if isinstance(stripped, str):
        clean = stripped.strip()
        return clean if clean and clean != '.' else None
    if isinstance(stripped, list):
        for b in stripped:
            if not isinstance(b, dict):
                return stripped
            btype = b.get('type')
            if btype == 'text':
                t = b.get('text', '').strip()
                if t and t != '.':
                    return stripped
            elif btype in ('tool_result', 'image', 'document'):
                return stripped
        return None
    return None


def _strip_all_system_reminders(content):
    return _strip_system_reminders(content)


def _strip_system_reminder(content, marker: str):
    for fragment, tid in _MARKER_TO_TEMPLATE.items():
        if fragment in marker or marker in fragment:
            return _strip_system_reminders(content, {tid})
    return _strip_system_reminders(content)


def _strip_user_interrupt_sr(content, marker: str):
    return _strip_system_reminders(content, {'user-interrupt'})


def _strip_pyright_diagnostics(content):
    return _strip_system_reminders(content, {'pyright-diagnostics'})
