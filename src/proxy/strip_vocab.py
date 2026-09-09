"""Shared vocabulary for proxy strip semantics.

Single source of truth for bucket codes, rule codes, tag literal codes,
chunk→rule attribution, and Markdown legend rendering. Used by
dev/tool_use_analysis/strip_audit.py and src/proxy_display/ (monitor).

MUST be updated in lockstep with rules.py when rules or markers change.
"""

# INFRASTRUCTURE

from collections import Counter

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
    'UI':  ('stripped_user_interrupt_sr',   ['user sent a new message while you were working', 'IMPORTANT: After completing your current task']),
    'SK':  ('stripped_skills_sr',           ['The following skills are available for use with the Skill tool']),
    'AT':  ('stripped_agent_types_sr',      ['Available agent types for the Agent tool']),
    'CMD': ('stripped_claudemd_sr',         ['# claudeMd', 'Contents of ', 'The date has changed.']),
    'PYR': ('stripped_pyright_diagnostics', ['<new-diagnostics>']),
    'PM':  ('removed_plan_mode_sr',         ['Plan mode is active', 'Plan mode ']),
    'ALL': ('stripped_all_sr_msg0',         []),
    'PP':  ('stripped_po_preview',          ['Preview (first ']),  # PO wrapper kept, Preview content removed
    'BGK': ('stripped_bg_exit_notification', ['Background command "']),  # SIGTERM/SIGKILL kill notification from user-aborted sleep timer
    'BL':  ('stripped_bg_launch_ack',        ['running in background with ID', 'backgrounded by user with ID']),  # launch-ack: wording 1 'Command running in background with ID: <id>...', wording 2 'Command was manually backgrounded by user with ID: <id>...'
    'GL':  ('stripped_git_lock_advice',      ['Another git process seems to be running']),  # constant git index.lock advice block in tool_result
    'BD':  ('stripped_bd_noise',             ['issues.jsonl', 'auto-export: no changes', 'auto-export: throttled', 'auto-export: skipping']),  # bd informational auto-import/export lines
    'ENV': ('stripped_env_context_sr',        ["As you answer the user's questions, you can use the following context:\n# userEmail"]),
    'HP':  ('stripped_hook_error_prefix',     ['PreToolUse:', 'hook error']),
    'SN':  ('stripped_system_notification_sr', ['[SYSTEM NOTIFICATION']),
    'SNP': ('stripped_sn_notice_paragraph',    ['[SYSTEM NOTIFICATION - NOT USER INPUT]\nThis is an automated background-task event']),  # bare paragraph ahead of <task-notification>, NOT SR-wrapped — see attribute_chunk startswith special-case (shares '[SYSTEM NOTIFICATION' text with SN, disambiguated structurally, not by marker order)
    'FM':  ('stripped_file_modified_sr',       [' was modified']),
    'RS':  ('stripped_role_system_msg',        []),  # role-gated, no content marker — attribution via om_norm.role in _process_messages_section
    'IM':  ('stripped_interrupt_marker',       ['[Request interrupted by user]', '[Request interrupted by user for tool use]']),  # tmux-Escape (bg_escape.py) CC records as if a genuine user interrupt — never one; 2 wordings measured (2026-07-31), removed chunk substring-matches whichever wording fired
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
# Excludes TN (tag-strip, not SR), PP (PO-preview — wrapper preserved, not SR-wrapped), and SNP
# (bare-paragraph strip, never wrapped in <system-reminder> tags — distinct from SN)
_SR_STRIP_RULES: frozenset[str] = frozenset(
    fn for code, (fn, _) in RULES.items() if code not in ('TN', 'PP', 'SNP')
)


# FUNCTIONS

# Attribute a removed chunk to a rule code via marker substring match
def attribute_chunk(chunk: str) -> str | None:
    if chunk.startswith('<task-notification>'):
        return 'TN'
    # Bare SN-notice paragraph (strip_sn_notice.py) is never <system-reminder>-wrapped, unlike the
    # SN template chunk (strip_sr.py) which always starts with the '<system-reminder>' tag literal —
    # both chunks contain '[SYSTEM NOTIFICATION' as a substring, so this startswith check must run
    # before the generic marker loop to avoid the SN entry winning by dict-iteration order.
    if chunk.startswith('[SYSTEM NOTIFICATION - NOT USER INPUT]\nThis is an automated background-task event'):
        return 'SNP'
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


# Collect scannable text from delta-range messages — blocks[*].full_text (fallback preview) plus
# content_preview/content_tail — the same text set classify_tags scans for tag literals.
def _collect_delta_texts(messages: list) -> list[str]:
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
    return texts


# One tag's LEAK/SUS verdict: None when tag_literal isn't present at all; 'LEAK:<code>' when the
# relevant strip rule fired in the delta range (unless leak_on_strip=False — PO's wrapper-preserved
# case, which is a silent no-op rather than a leak); 'SUS:<code>' otherwise.
def _tag_signal(combined: str, tag_literal: str, code: str, strip_marker: str, tag_strip_fn, leak_on_strip: bool = True):
    if tag_literal not in combined:
        return None
    if tag_strip_fn(strip_marker):
        return f'LEAK:<{code}>' if leak_on_strip else None
    return f'SUS:<{code}>'


# Scan delta messages (monitor format) for leaked/suspect tag literals
# Returns (leak_signals, sus_signals) — compact LEAK:<TAG> / SUS:<TAG> strings
# Delta-scoped: only truly new messages [prev_message_count, message_count).
# prev_message_count derived as message_count - messages_added (avoids first_diff_index
# regression: fdi can point into old msgs when a prior msg shifts by 1 char).
# Scans blocks[*].full_text instead of raw_payload (raw_payload discarded by monitor parser)
# LEAK iff the relevant strip rule fired on a msg in delta range (smr key >= start)
def classify_tags(entry: dict) -> tuple[list[str], list[str]]:
    diff = entry.get('diff_from_prev') or {}
    fdi = diff.get('first_diff_index', 0) if diff else 0
    if fdi < 0:
        return [], []
    start = entry.get('message_count', 0) - (diff.get('messages_added') or 0) if diff else 0
    messages = entry.get('messages', [])[start:]
    smr = entry.get('stripped_msg_removed') or {}

    def _tag_strip_in_delta(tag: str) -> bool:
        for idx_str, chunks in smr.items():
            if int(idx_str) < start:
                continue
            for chunk in (chunks or []):
                if tag in chunk:
                    return True
        return False

    combined = '\n'.join(_collect_delta_texts(messages))
    leak_signals: list[str] = []
    sus_signals: list[str] = []
    for sig in (
        _tag_signal(combined, '<task-notification>', 'TN', '<task-notification>', _tag_strip_in_delta),
        _tag_signal(combined, '<new-diagnostics>', 'ND', '<new-diagnostics>', _tag_strip_in_delta),
        _tag_signal(combined, '<system-reminder>', 'SR', '<system-reminder>', _tag_strip_in_delta),
        _tag_signal(combined, '<persisted-output>', 'PO', 'Preview (first ', _tag_strip_in_delta, leak_on_strip=False),
    ):
        if sig is None:
            continue
        (leak_signals if sig.startswith('LEAK') else sus_signals).append(sig)

    return leak_signals, sus_signals


# EFFECTIVE — new/changed chunks (not already in prev_removed) attributed to a rule code.
# Returns (rule_to_chunks, unattributed).
def _compute_effective_chunks(curr_removed: dict, prev_removed: dict) -> tuple:
    prev_pairs: set[tuple[str, str]] = set()
    for idx_str, chunks in prev_removed.items():
        for chunk in (chunks or []):
            prev_pairs.add((idx_str, chunk))
    rule_to_chunks: dict[str, list[tuple[int, str]]] = {}
    unattributed: list[tuple[int, str]] = []
    for idx_str, chunks in curr_removed.items():
        for chunk in (chunks or []):
            if (idx_str, chunk) in prev_pairs:
                continue
            code = attribute_chunk(chunk)
            if code:
                rule_to_chunks.setdefault(code, []).append((int(idx_str), chunk))
            else:
                unattributed.append((int(idx_str), chunk))
    return rule_to_chunks, unattributed


# INERT — rule codes with counter-delta > 0 but 0 captured chunks in ALL curr chunks
def _compute_inert_codes(entry: dict, prev_entry, curr_removed: dict) -> list:
    prev_mods_ctr = Counter((prev_entry or {}).get('modifications', []))
    curr_mods_ctr = Counter(entry.get('modifications', []))
    new_strip_codes = {
        code_for_rule(rule)
        for rule in curr_mods_ctr
        if curr_mods_ctr[rule] > prev_mods_ctr.get(rule, 0)
        and code_for_rule(rule) is not None
        and code_for_rule(rule) in STRIP_RULE_CODES
    }
    codes_with_any_chunks: set[str] = set()
    for idx_str, chunks in curr_removed.items():
        for chunk in (chunks or []):
            c = attribute_chunk(chunk)
            if c:
                codes_with_any_chunks.add(c)
    return sorted(c for c in new_strip_codes if c not in codes_with_any_chunks)


# IDX — new stripped_msg_indices entries with no chunks in stripped_msg_removed
def _compute_idx_msgs(entry: dict, prev_entry, curr_removed: dict) -> list:
    prev_smi = set((prev_entry or {}).get('stripped_msg_indices', []))
    curr_smi = set(entry.get('stripped_msg_indices', []))
    new_smi = curr_smi - prev_smi
    return [idx for idx in sorted(new_smi) if not curr_removed.get(str(idx))]


# Classify one REQ into 5 buckets; EFFECTIVE uses chunk-diff against prev_removed
def classify_req(entry: dict, prev_entry: dict | None) -> dict:
    """Return per-REQ bucket classification dict.

    effective: dict[rule_code, list[tuple[idx, chunk]]]
        — chunks NEW or CHANGED since prev.stripped_msg_removed
    inert: list[rule_code] (sorted)
        — rule codes with counter-delta > 0 but 0 captured chunks in ALL curr chunks
    idx_msgs: list[int] (sorted)
        — msg indices newly in smi but no chunks in stripped_msg_removed
    leak_signals: list[str]
    sus_signals: list[str]
    unattributed: list[tuple[idx, chunk]]
        — NEW chunks that no rule marker matched
    """
    curr_removed = entry.get('stripped_msg_removed') or {}
    prev_removed = (prev_entry or {}).get('stripped_msg_removed') or {}

    rule_to_chunks, unattributed = _compute_effective_chunks(curr_removed, prev_removed)
    inert_codes = _compute_inert_codes(entry, prev_entry, curr_removed)
    idx_msgs = _compute_idx_msgs(entry, prev_entry, curr_removed)
    leak_signals, sus_signals = classify_tags(entry)

    return {
        'effective':    rule_to_chunks,
        'inert':        inert_codes,
        'idx_msgs':     idx_msgs,
        'leak_signals': leak_signals,
        'sus_signals':  sus_signals,
        'unattributed': unattributed,
    }


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
    lines.append('| `<PO>` | `<persisted-output>` | Paired with `PP` rule — Preview stripped, wrapper preserved |')
    lines.append('| `<SR>` | `<system-reminder>` | Classified via template startswith; rule suffix added: `SUS:<SR>/CMD` |')
    lines.append('| `<TN>` | `<task-notification>` | Paired with `TN` rule |')
    lines.append('| `<ND>` | `<new-diagnostics>` | Paired with `PYR` rule |')
    lines.append('')
    lines.append('**Compact notation:** `BUCKET:RULE` e.g. `EFF:CMD`, `INERT:TN`, `LEAK:<TN>`, `SUS:<PO>`, `SUS:<SR>/UI`.')
    lines.append('')
    return '\n'.join(lines)
