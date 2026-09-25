# FUNCTIONS

def strip_content_tree(content, text_stripper, removed, rebuild_text=False):
    if isinstance(content, str):
        return text_stripper(content, removed)
    if isinstance(content, list):
        return [_strip_block(block, text_stripper, removed, rebuild_text) for block in content]
    return content


def _strip_block(block, text_stripper, removed, rebuild_text):
    if not isinstance(block, dict):
        return block
    btype = block.get('type')
    if btype == 'text':
        new_text = text_stripper(block.get('text', ''), removed)
        return _with_text(block, new_text, rebuild_text)
    if btype == 'tool_result':
        return _strip_tool_result(block, text_stripper, removed, rebuild_text)
    return block


def _strip_tool_result(block, text_stripper, removed, rebuild_text):
    inner = block.get('content', '')
    if isinstance(inner, str):
        new_inner = text_stripper(inner, removed)
        return {**block, 'content': new_inner} if new_inner != inner else block
    if isinstance(inner, list):
        new_sub = [_strip_sub_block(sub, text_stripper, removed, rebuild_text) for sub in inner]
        return {**block, 'content': new_sub}
    return block


def _strip_sub_block(sub, text_stripper, removed, rebuild_text):
    if isinstance(sub, dict) and sub.get('type') == 'text':
        new_text = text_stripper(sub.get('text', ''), removed)
        return _with_text(sub, new_text, rebuild_text)
    return sub


def _with_text(block, new_text, rebuild_text):
    if rebuild_text or new_text != block.get('text', ''):
        return {**block, 'text': new_text}
    return block
