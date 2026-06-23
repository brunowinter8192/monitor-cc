# INFRASTRUCTURE

# Fast-path marker — cheap contains check before block walk
_BG_LAUNCH_ACK_MARKER = 'running in background with ID'
# Anchored ack prefix: a genuine CC bg-launch ack ALWAYS starts with this exact prefix. The strip
# decision uses startswith() on the lstripped text (NOT substring-anywhere), so a large tool_result
# or user message that merely CONTAINS the phrase as data is never destroyed (was the FP-nuke bug).
_BG_LAUNCH_ACK_PREFIX = 'Command running in background with ID:'


# True only for a genuine bg-launch ack: the marker phrase anchored at the start of the text.
def _is_bg_launch_ack(text):
    return text.lstrip().startswith(_BG_LAUNCH_ACK_PREFIX)


# ORCHESTRATOR

# Replace entire content of any block whose text STARTS WITH the bg-launch-ack prefix with '.'.
# Anchored (not substring-anywhere): legitimate content that merely contains the phrase is kept.
# Covers all 4 content shapes: str, list[text], list[tool_result+str], list[tool_result+list].
# Returns (new_content, removed_chunks) — removed_chunks: original texts of replaced blocks.
def _strip_bg_launch_ack(content):
    removed = []
    if isinstance(content, str):
        if _is_bg_launch_ack(content):
            removed.append(content)
            return '.', removed
        return content, removed
    if isinstance(content, list):
        result = []
        for block in content:
            if not isinstance(block, dict):
                result.append(block)
                continue
            btype = block.get('type')
            if btype == 'text':
                text = block.get('text', '')
                if _is_bg_launch_ack(text):
                    removed.append(text)
                    result.append({**block, 'text': '.'})
                else:
                    result.append(block)
            elif btype == 'tool_result':
                inner = block.get('content', '')
                if isinstance(inner, str):
                    if _is_bg_launch_ack(inner):
                        removed.append(inner)
                        result.append({**block, 'content': '.'})
                    else:
                        result.append(block)
                elif isinstance(inner, list):
                    new_sub = []
                    sub_changed = False
                    for sub in inner:
                        if isinstance(sub, dict) and sub.get('type') == 'text':
                            text = sub.get('text', '')
                            if _is_bg_launch_ack(text):
                                removed.append(text)
                                new_sub.append({**sub, 'text': '.'})
                                sub_changed = True
                            else:
                                new_sub.append(sub)
                        else:
                            new_sub.append(sub)
                    result.append({**block, 'content': new_sub} if sub_changed else block)
                else:
                    result.append(block)
            else:
                result.append(block)
        return result, removed
    return content, removed
