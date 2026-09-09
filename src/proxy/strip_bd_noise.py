import re

# INFRASTRUCTURE

_BD_NOISE_MARKERS = ('issues.jsonl', 'auto-export:', 'into empty database')

_BD_NOISE_RE = re.compile(
    r'^(?:- )?(?:'
    r'auto-importing \d+ bytes from \S+/\.beads/issues\.jsonl into empty database\.{0,3}'
    r'|auto-imported \d+ issues(?: and \d+ memories)? from \S+/\.beads/issues\.jsonl'
    r'|auto-imported \d+ issues into empty database'
    r'|Exported \d+ issues(?: and \d+ memories)? to \S+/\.beads/issues\.jsonl'
    r'|auto-export: wrote \d+ issues(?: and \d+ memories)? to \S+/\.beads/issues\.jsonl'
    r'|auto-export: no changes since last export'
    r'|auto-export: throttled \([^)]+\)'
    r'|auto-export: skipping[^\n]*'
    r'|auto-import: \d+ issues(?:, \d+ memories)? from \S+/\.beads/issues\.jsonl[^\n]*'
    r')\n?',
    re.MULTILINE,
)


# ORCHESTRATOR

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

def _strip_bd_noise_from_text(text, out_removed):
    if not any(m in text for m in _BD_NOISE_MARKERS):
        return text

    def _collect(m):
        out_removed.append(m.group(0).rstrip('\n'))
        return ''

    return _BD_NOISE_RE.sub(_collect, text)
