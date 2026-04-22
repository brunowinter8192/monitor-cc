"""Shared vocabulary for proxy strip semantics.

Single source of truth for bucket codes, rule codes, tag literal codes,
chunk→rule attribution, and Markdown legend rendering. Used by
dev/tool_use_analysis/strip_audit.py and src/proxy_display/ (monitor).

MUST be updated in lockstep with rules.py when rules or markers change.
"""

# INFRASTRUCTURE

# Bucket codes — 5 semantic buckets for per-REQ strip signals
BUCKETS: dict[str, str] = {
    'EFF':   'Effective strip (rule fired + chunk attributed)',
    'INERT': 'Rule fired but 0 chunks captured (phantom firing)',
    'IDX':   'Indexed in smi but no chunks — Final-Pass tracking gap',
    'LEAK':  'Tag in raw_payload after rule fired (strip survived elsewhere)',
    'SUS':   'Tag in raw_payload, no rule fired',
}

# Rule codes — 10 strip rules
# Order defines attribution priority for attribute_chunk (first match wins)
# Each entry: code -> (full_name_in_modifications[], [marker_substrings])
# TN: starts-with check handled explicitly in attribute_chunk (not substring loop)
# ALL: Final-Pass — never writes stripped_msg_removed; listed for code→fullname only
RULES: dict[str, tuple[str, list[str]]] = {
    'REJ': ('stripped_rejection_message',   ['(rejection marker stripped by proxy)']),
    'TN':  ('trimmed_task_notification',    ['<task-notification>']),
    'NAG': ('stripped_task_tools_nag',      ["task tools haven"]),
    'DEF': ('stripped_deferred_tools_sr',   ['deferred tools are now available via ToolSearch']),
    'UI':  ('stripped_user_interrupt_sr',   ['user sent a new message while you were working']),
    'SK':  ('stripped_skills_sr',           ['The following skills are available for use with the Skill tool']),
    'CMD': ('stripped_claudemd_sr',         ['# claudeMd', 'Contents of ']),
    'PYR': ('stripped_pyright_diagnostics', ['<new-diagnostics>']),
    'PM':  ('removed_plan_mode_sr',         ['Plan mode is active', 'Plan mode ']),
    'ALL': ('stripped_all_sr_msg0',         []),
}

# Tag literal codes — 4 raw tags tracked for LEAK/SUSPECT detection
TAG_LITERALS: dict[str, str] = {
    'PO': '<persisted-output>',
    'SR': '<system-reminder>',
    'TN': '<task-notification>',
    'ND': '<new-diagnostics>',
}

# All rule codes eligible for effective/inert classification
STRIP_RULE_CODES: frozenset[str] = frozenset(RULES.keys())

# Reverse map: full modifications[] name → code (built once at import)
_FULL_NAME_TO_CODE: dict[str, str] = {fn: code for code, (fn, _) in RULES.items()}

# Rule names that indicate an SR-wrapping strip (for LEAK:<SR> detection in classify_tags)
_SR_STRIP_RULES: frozenset[str] = frozenset(
    fn for code, (fn, _) in RULES.items() if code not in ('TN',)
)


# FUNCTIONS

# Attribute a removed chunk to a rule code via marker substring match
def attribute_chunk(chunk: str) -> str | None:
    if chunk.startswith('<task-notification>'):
        return 'TN'
    for code, (_full_name, markers) in RULES.items():
        if code in ('TN', 'ALL'):
            continue
        for marker in markers:
            if marker in chunk:
                return code
    return None


# Reverse lookup: full modifications[] name → rule code (or None if unknown)
def code_for_rule(full_name: str) -> str | None:
    return _FULL_NAME_TO_CODE.get(full_name)


# Scan parsed entry messages (monitor format) for leaked/suspect tag literals
# Returns (leak_signals, sus_signals) — compact LEAK:<TAG> / SUS:<TAG> strings
# Scans blocks[*].full_text instead of raw_payload (raw_payload discarded by monitor parser)
def classify_tags(entry: dict) -> tuple[list[str], list[str]]:
    mods = set(entry.get('modifications', []))
    messages = entry.get('messages', [])

    texts: list[str] = []
    for msg in messages:
        for blk in msg.get('blocks', []):
            t = blk.get('full_text', blk.get('preview', ''))
            if t:
                texts.append(t)
        for field in ('content_preview', 'content_tail'):
            t = msg.get(field, '')
            if t:
                texts.append(t)

    combined = '\n'.join(texts)
    leak_signals: list[str] = []
    sus_signals: list[str] = []

    if '<task-notification>' in combined:
        if 'trimmed_task_notification' in mods:
            leak_signals.append('LEAK:<TN>')
        else:
            sus_signals.append('SUS:<TN>')

    if '<new-diagnostics>' in combined:
        if 'stripped_pyright_diagnostics' in mods:
            leak_signals.append('LEAK:<ND>')
        else:
            sus_signals.append('SUS:<ND>')

    if '<system-reminder>' in combined:
        if mods & _SR_STRIP_RULES:
            leak_signals.append('LEAK:<SR>')
        else:
            sus_signals.append('SUS:<SR>')

    if '<persisted-output>' in combined:
        sus_signals.append('SUS:<PO>')

    return leak_signals, sus_signals


# Generate Markdown legend block for audit report header
def legend_markdown() -> str:
    lines = []
    lines.append('## Legend')
    lines.append('')
    lines.append('### Buckets')
    lines.append('| Code | Meaning |')
    lines.append('|---|---|')
    for code, label in BUCKETS.items():
        lines.append(f'| `{code}` | {label} |')
    lines.append('')
    lines.append('### Rules (code → modifications name → attribution markers)')
    lines.append('| Code | Rule | Markers |')
    lines.append('|---|---|---|')
    for code, (full_name, markers) in RULES.items():
        mk = ', '.join(f'`{m}`' for m in markers) if markers else '*(Final-Pass — no capture tracking)*'
        lines.append(f'| `{code}` | `{full_name}` | {mk} |')
    lines.append('')
    lines.append('### Tag Literals (for LEAK / SUS)')
    lines.append('| Code | Literal | Notes |')
    lines.append('|---|---|---|')
    lines.append('| `<PO>` | `<persisted-output>` | No active rule (rolled back) — always SUS |')
    lines.append('| `<SR>` | `<system-reminder>` | Classified via template startswith; rule suffix added: `SUS:<SR>/CMD` |')
    lines.append('| `<TN>` | `<task-notification>` | Paired with `TN` rule |')
    lines.append('| `<ND>` | `<new-diagnostics>` | Paired with `PYR` rule |')
    lines.append('')
    lines.append('**Compact notation:** `BUCKET:RULE` e.g. `EFF:CMD`, `INERT:TN`, `LEAK:<TN>`, `SUS:<PO>`, `SUS:<SR>/UI`.')
    lines.append('')
    return '\n'.join(lines)
