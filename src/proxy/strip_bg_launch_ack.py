# INFRASTRUCTURE

# Fast-path marker — cheap contains check before block walk
_BG_LAUNCH_ACK_MARKER = 'running in background with ID'


# ORCHESTRATOR

# Replace entire content of any block containing the background-launch-ack marker with '.'.
# Covers all 4 content shapes: str, list[text], list[tool_result+str], list[tool_result+list].
# Returns (new_content, removed_chunks) — removed_chunks: original texts of replaced blocks.
def _strip_bg_launch_ack(content):
    removed = []
    if isinstance(content, str):
        if _BG_LAUNCH_ACK_MARKER in content:
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
                if _BG_LAUNCH_ACK_MARKER in text:
                    removed.append(text)
                    result.append({**block, 'text': '.'})
                else:
                    result.append(block)
            elif btype == 'tool_result':
                inner = block.get('content', '')
                if isinstance(inner, str):
                    if _BG_LAUNCH_ACK_MARKER in inner:
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
                            if _BG_LAUNCH_ACK_MARKER in text:
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
