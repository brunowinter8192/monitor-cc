import re

# INFRASTRUCTURE

# Match only standalone SR blocks — those starting at beginning of a line.
# Prevents matching <system-reminder> tags embedded inside code strings (e.g. `if "<system-reminder>" in text:`).
_STANDALONE_SR_RE = re.compile(r'(?m)^<system-reminder>.*?</system-reminder>\n?', re.DOTALL)

# Extract inner text from a matched SR block
_INNER_SR_RE = re.compile(r'<system-reminder>(.*?)</system-reminder>', re.DOTALL)

# IMPORTANT-line pattern for user-interrupt partial strip
_IMP_LINE_RE = re.compile(r'^[^\n]*IMPORTANT:[^\n]*\n?', re.MULTILINE)

# Template registry: template_id → (identifier_string, mode)
# mode 'full': remove entire SR block
# mode 'partial': remove only IMPORTANT line, preserve user body in SR wrapper
_SR_TEMPLATES = {
    'task-tools-nag':      ("The task tools haven't been used recently",                'full'),
    'pyright-diagnostics': ('<new-diagnostics>',                                        'full'),
    'deferred-tools':      ('The following deferred tools are now available via ToolSearch', 'full'),
    'user-interrupt':      ('The user sent a new message while you were working:',      'partial'),
    'system-notification': ('[SYSTEM NOTIFICATION - NOT USER INPUT]',                   'full'),
    'file-modified':       ('Note: ',                                                   'full'),
    'claudemd-contents':   ('Contents of ',                                             'full'),
    'date-changed':        ('The date has changed.',                                    'full'),
    'skills-available':    ('The following skills are available',                       'full'),
    'plan-mode':           ('Plan mode ',                                               'full'),
}
_ALL_TEMPLATES = frozenset(_SR_TEMPLATES.keys())

# Map old marker strings → template IDs for backward-compat wrappers
_MARKER_TO_TEMPLATE = {
    'task tools haven':                                'task-tools-nag',
    '<new-diagnostics>':                               'pyright-diagnostics',
    'deferred tools are now available via ToolSearch': 'deferred-tools',
    'user sent a new message while you were working':  'user-interrupt',
    '[SYSTEM NOTIFICATION':                            'system-notification',
    '# claudeMd':                                      'claudemd-contents',
    'Contents of ':                                    'claudemd-contents',
    'The following skills are available':              'skills-available',
    'Plan mode is active':                             'plan-mode',
}


# ORCHESTRATOR

# Strip <system-reminder> blocks from all 4 content shapes using template-based exact matching
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
            elif btype == 'tool_result':
                inner = block.get('content', '')
                if isinstance(inner, str):
                    new_inner = _apply_sr_strip(inner, enabled_templates)
                    result.append({**block, 'content': new_inner} if new_inner != inner else block)
                elif isinstance(inner, list):
                    new_sub = []
                    for sub in inner:
                        if isinstance(sub, dict) and sub.get('type') == 'text':
                            new_text = _apply_sr_strip(sub.get('text', ''), enabled_templates)
                            new_sub.append({**sub, 'text': new_text or '.'})
                        else:
                            new_sub.append(sub)
                    result.append({**block, 'content': new_sub})
                else:
                    result.append(block)
            else:
                result.append(block)
        return result
    return content


# FUNCTIONS

# Find which template matches an SR inner text; returns (template_id, mode) or (None, None)
def _match_template(inner, enabled_templates):
    for tid in enabled_templates:
        spec = _SR_TEMPLATES.get(tid)
        if spec and inner.startswith(spec[0]):
            return tid, spec[1]
    return None, None


# Strip standalone SR blocks from a string — only blocks matching enabled templates
def _apply_sr_strip(text, enabled_templates):
    if not text or '<system-reminder>' not in text:
        return text

    def _replace(m):
        full = m.group(0)
        inner_m = _INNER_SR_RE.search(full)
        if not inner_m:
            return full
        inner = inner_m.group(1).strip()
        tid, mode = _match_template(inner, enabled_templates)
        if tid is None:
            return full  # unknown template — preserve as-is
        if mode == 'full':
            return ''
        # partial: preserve user body, strip IMPORTANT line and outer tags
        cleaned = _IMP_LINE_RE.sub('', inner_m.group(1))
        return '<system-reminder>' + cleaned + '</system-reminder>\n'

    return _STANDALONE_SR_RE.sub(_replace, text)


# Remove plan-mode SR blocks; returns None if nothing meaningful remains after strip
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


# Strip ALL known SR templates from content (catch-all pass)
def _strip_all_system_reminders(content):
    return _strip_system_reminders(content)


# Strip SR blocks whose text contains marker — backward-compat wrapper for rules.py
def _strip_system_reminder(content, marker: str):
    for fragment, tid in _MARKER_TO_TEMPLATE.items():
        if fragment in marker or marker in fragment:
            return _strip_system_reminders(content, {tid})
    return _strip_system_reminders(content)


# Strip user-interrupt SR (preserve user body, remove IMPORTANT line) — compat wrapper
def _strip_user_interrupt_sr(content, marker: str):
    return _strip_system_reminders(content, {'user-interrupt'})


# Strip pyright new-diagnostics SR blocks — compat wrapper
def _strip_pyright_diagnostics(content):
    return _strip_system_reminders(content, {'pyright-diagnostics'})
