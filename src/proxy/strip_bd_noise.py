import re

# INFRASTRUCTURE

# Fast-path markers — cheap contains check before regex.
# 'issues.jsonl'     — path-containing variants (auto-importing/auto-imported from/Exported/wrote)
# 'auto-export:'     — no-path auto-export status (no changes / throttled / skipping / wrote)
# 'into empty database' — auto-imported N issues into empty database (no path, no auto-export:)
_BD_NOISE_MARKERS = ('issues.jsonl', 'auto-export:', 'into empty database')

# Match all informational bd auto-import/export lines. Does NOT match Warning:/warning: prefixed
# error lines — those start with 'Warning:' or 'warning:', never 'auto-import'/'auto-export'/'Exported'.
# '^(?:- )?' handles the '- ' bullet prefix present for import variants in hook-captured tool_result.
# '\n?' at end consumes trailing newline so no orphan blank line remains after strip.
_BD_NOISE_RE = re.compile(
    r'^(?:- )?(?:'
    # import-start: '...' is literal in bd source (auto-importing %d bytes ... into empty database...)
    r'auto-importing \d+ bytes from \S+/\.beads/issues\.jsonl into empty database\.{0,3}'
    # import-done: with path, with/without memories
    r'|auto-imported \d+ issues(?: and \d+ memories)? from \S+/\.beads/issues\.jsonl'
    # import-done: into empty database (no path in message)
    r'|auto-imported \d+ issues into empty database'
    # export-done: plain bd export, with/without memories
    r'|Exported \d+ issues(?: and \d+ memories)? to \S+/\.beads/issues\.jsonl'
    # export-done: auto-export hook, with/without memories
    r'|auto-export: wrote \d+ issues(?: and \d+ memories)? to \S+/\.beads/issues\.jsonl'
    # no-op export
    r'|auto-export: no changes since last export'
    # throttled: '(last export 5m ago, interval 15m)' style
    r'|auto-export: throttled \([^)]+\)'
    # skipping with optional trailing reason
    r'|auto-export: skipping[^\n]*'
    # upgrade-recovery import variants (GH#2994)
    r'|auto-import: \d+ issues(?:, \d+ memories)? from \S+/\.beads/issues\.jsonl[^\n]*'
    r')\n?',
    re.MULTILINE,
)


# ORCHESTRATOR

# Strip bd informational auto-import/export noise from all 4 content shapes.
# Returns (new_content, removed_chunks) — removed_chunks for stripped_bd_noise mod attribution.
def _strip_bd_noise(content):
    removed = []
    if isinstance(content, str):
        return _strip_bd_noise_from_text(content, removed), removed
    if isinstance(content, list):
        result = []
        for block in content:
            if not isinstance(block, dict):
                result.append(block)
                continue
            btype = block.get('type')
            if btype == 'text':
                new_text = _strip_bd_noise_from_text(block.get('text', ''), removed)
                result.append({**block, 'text': new_text} if new_text != block.get('text', '') else block)
            elif btype == 'tool_result':
                inner = block.get('content', '')
                if isinstance(inner, str):
                    new_inner = _strip_bd_noise_from_text(inner, removed)
                    result.append({**block, 'content': new_inner} if new_inner != inner else block)
                elif isinstance(inner, list):
                    new_sub = []
                    for sub in inner:
                        if isinstance(sub, dict) and sub.get('type') == 'text':
                            new_text = _strip_bd_noise_from_text(sub.get('text', ''), removed)
                            new_sub.append({**sub, 'text': new_text} if new_text != sub.get('text', '') else sub)
                        else:
                            new_sub.append(sub)
                    result.append({**block, 'content': new_sub})
                else:
                    result.append(block)
            else:
                result.append(block)
        return result, removed
    return content, removed


# FUNCTIONS

# Strip bd noise lines from a single string; append removed lines (sans trailing \n) to out_removed.
def _strip_bd_noise_from_text(text, out_removed):
    if not any(m in text for m in _BD_NOISE_MARKERS):
        return text

    def _collect(m):
        out_removed.append(m.group(0).rstrip('\n'))
        return ''

    return _BD_NOISE_RE.sub(_collect, text)
