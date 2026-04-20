# INFRASTRUCTURE
import re

_REJECTION_MARKER = "The user doesn't want to proceed with this tool use"

# FUNCTIONS

# Remove only plan-mode blocks/sections from content, preserving everything else.
# Returns the remaining content, or None if nothing is left after stripping.
def _strip_plan_mode_blocks(content):
    if isinstance(content, list):
        result = []
        for b in content:
            if not isinstance(b, dict):
                result.append(b)
                continue
            btype = b.get("type")
            if btype == "text" and "Plan mode is active" in b.get("text", ""):
                continue  # drop entire text block
            elif btype == "tool_result":
                inner = b.get("content", "")
                if isinstance(inner, str) and "Plan mode is active" in inner:
                    new_inner = re.sub(
                        r'<system-reminder>\s*Plan mode .*?</system-reminder>\s*',
                        '', inner, flags=re.DOTALL
                    )
                    result.append({**b, "content": new_inner} if new_inner != inner else b)
                elif isinstance(inner, list):
                    new_sub = [
                        s for s in inner
                        if not (isinstance(s, dict) and s.get("type") == "text"
                                and "Plan mode is active" in s.get("text", ""))
                    ]
                    if len(new_sub) != len(inner):
                        result.append({**b, "content": new_sub if new_sub else "."})
                    else:
                        result.append(b)
                else:
                    result.append(b)
            else:
                result.append(b)
        if not result:
            return None
        for i, b in enumerate(result):
            if isinstance(b, dict) and b.get("type") == "text" and not b.get("text", "").strip():
                result[i] = {**b, "text": "."}
        return result
    if isinstance(content, str):
        stripped = re.sub(
            r'<system-reminder>\s*Plan mode .*?</system-reminder>\s*',
            '', content, flags=re.DOTALL
        )
        return stripped.strip() or None
    return None


# Strip ALL <system-reminder>...</system-reminder> blocks from string or list content
def _strip_all_system_reminders(content):
    pattern = re.compile(r'<system-reminder>.*?</system-reminder>\s*', re.DOTALL)
    if isinstance(content, str):
        return pattern.sub('', content) or "."
    if isinstance(content, list):
        result = []
        for block in content:
            if not isinstance(block, dict):
                result.append(block)
                continue
            btype = block.get("type")
            if btype == "text":
                new_text = pattern.sub('', block.get("text", ""))
                if not new_text.strip():
                    new_text = "."
                result.append({**block, "text": new_text})
            elif btype == "tool_result":
                inner = block.get("content", "")
                if isinstance(inner, str):
                    new_inner = pattern.sub('', inner)
                    result.append({**block, "content": new_inner} if new_inner != inner else block)
                elif isinstance(inner, list):
                    new_sub_blocks = []
                    for sub in inner:
                        if isinstance(sub, dict) and sub.get("type") == "text":
                            new_text = pattern.sub('', sub.get("text", ""))
                            new_sub_blocks.append({**sub, "text": new_text})
                        else:
                            new_sub_blocks.append(sub)
                    result.append({**block, "content": new_sub_blocks})
                else:
                    result.append(block)
            else:
                result.append(block)
        return result
    return content


# Strip only the IMPORTANT notification line from a user-interrupt SR; preserve user message body
def _strip_user_interrupt_sr(content, marker: str):
    sr_pat = re.compile(r'<system-reminder>.*?' + re.escape(marker) + r'.*?</system-reminder>', re.DOTALL)
    imp_line_pat = re.compile(r'^[^\n]*IMPORTANT:[^\n]*\n?', re.MULTILINE)

    def _remove_marker_line(m):
        stripped = imp_line_pat.sub('', m.group(0))
        return stripped if stripped.strip() else '<system-reminder>.</system-reminder>'

    if isinstance(content, str):
        result = sr_pat.sub(_remove_marker_line, content)
        return result if result.strip() else '.'
    if isinstance(content, list):
        result = []
        for block in content:
            if not isinstance(block, dict):
                result.append(block)
                continue
            btype = block.get('type')
            if btype == 'text':
                new_text = sr_pat.sub(_remove_marker_line, block.get('text', ''))
                if not new_text.strip():
                    new_text = '.'
                result.append({**block, 'text': new_text})
            elif btype == 'tool_result':
                inner = block.get('content', '')
                if isinstance(inner, str):
                    new_inner = sr_pat.sub(_remove_marker_line, inner)
                    result.append({**block, 'content': new_inner} if new_inner != inner else block)
                elif isinstance(inner, list):
                    new_sub = []
                    for sub in inner:
                        if isinstance(sub, dict) and sub.get('type') == 'text':
                            new_text = sr_pat.sub(_remove_marker_line, sub.get('text', ''))
                            new_sub.append({**sub, 'text': new_text})
                        else:
                            new_sub.append(sub)
                    result.append({**block, 'content': new_sub})
                else:
                    result.append(block)
            else:
                result.append(block)
        return result
    return content


# Strip any <system-reminder> block whose text contains marker, from string or list content
def _strip_system_reminder(content, marker: str):
    pattern = re.compile(r'<system-reminder>.*?' + re.escape(marker) + r'.*?</system-reminder>\s*', re.DOTALL)
    if isinstance(content, str):
        return pattern.sub('', content) or "."
    if isinstance(content, list):
        result = []
        for block in content:
            if not isinstance(block, dict):
                result.append(block)
                continue
            btype = block.get("type")
            if btype == "text":
                new_text = pattern.sub('', block.get("text", ""))
                if not new_text.strip():
                    new_text = "."
                result.append({**block, "text": new_text})
            elif btype == "tool_result":
                inner = block.get("content", "")
                if isinstance(inner, str):
                    new_inner = pattern.sub('', inner)
                    result.append({**block, "content": new_inner} if new_inner != inner else block)
                elif isinstance(inner, list):
                    new_sub_blocks = []
                    for sub in inner:
                        if isinstance(sub, dict) and sub.get("type") == "text":
                            new_text = pattern.sub('', sub.get("text", ""))
                            new_sub_blocks.append({**sub, "text": new_text})
                        else:
                            new_sub_blocks.append(sub)
                    result.append({**block, "content": new_sub_blocks})
                else:
                    result.append(block)
            else:
                result.append(block)
        return result
    return content


# Check if user message content contains a tool_result block with the rejection marker
def _message_has_rejection(content) -> bool:
    if isinstance(content, str):
        return _REJECTION_MARKER in content
    if isinstance(content, list):
        for block in content:
            if not isinstance(block, dict) or block.get("type") != "tool_result":
                continue
            tool_content = block.get("content", "")
            if isinstance(tool_content, str):
                if _REJECTION_MARKER in tool_content and len(tool_content) <= 200:
                    return True
            elif isinstance(tool_content, list):
                for sub in tool_content:
                    if not isinstance(sub, dict):
                        continue
                    sub_text = sub.get("text", "")
                    if _REJECTION_MARKER in sub_text and len(sub_text) <= 200:
                        return True
    return False


# Replace rejection tool_result block content with '.'
def _strip_rejection_message(content):
    if isinstance(content, str):
        return "."
    if isinstance(content, list):
        result = []
        for block in content:
            if isinstance(block, dict) and block.get("type") == "tool_result":
                tool_content = block.get("content", "")
                has_rejection = (isinstance(tool_content, str) and _REJECTION_MARKER in tool_content) or (
                    isinstance(tool_content, list) and any(
                        _REJECTION_MARKER in sub.get("text", "")
                        for sub in tool_content if isinstance(sub, dict)
                    )
                )
                result.append({**block, "content": "."} if has_rejection else block)
            else:
                result.append(block)
        return result
    return content


# Extract SessionStart system-reminder block from MSG[0] content. Returns (modified_content, extracted_text_or_None).
def _extract_session_start_block(content):
    _RULES_MARKER = "SessionStart hook additional context:"
    _TAG_OPEN = "<system-reminder>"
    _TAG_CLOSE = "</system-reminder>"

    def _extract_from_text(text: str):
        if _RULES_MARKER not in text:
            return text, None
        marker_idx = text.index(_RULES_MARKER)
        open_idx = text.rfind(_TAG_OPEN, 0, marker_idx)
        if open_idx == -1:
            return text, None
        close_idx = text.find(_TAG_CLOSE, marker_idx)
        if close_idx == -1:
            return text, None
        close_end = close_idx + len(_TAG_CLOSE)
        extracted = text[open_idx:close_end]
        remaining = (text[:open_idx] + text[close_end:]).strip() or "."
        return remaining, extracted

    if isinstance(content, str):
        return _extract_from_text(content)
    if isinstance(content, list):
        for i, block in enumerate(content):
            if not isinstance(block, dict) or block.get("type") != "text":
                continue
            new_text, extracted = _extract_from_text(block.get("text", ""))
            if extracted:
                new_blocks = list(content)
                new_blocks[i] = {**block, "text": new_text}
                return new_blocks, extracted
    return content, None


# Remove '# Session-specific guidance' section from text, keeping '# Environment' onward.
def _strip_session_guidance(text: str) -> str:
    marker = "# Session-specific guidance"
    env_marker = "# Environment"
    if marker not in text:
        return text
    start = text.index(marker)
    env_idx = text.find(env_marker, start)
    if env_idx == -1:
        return text[:start].strip() or "."
    return (text[:start] + text[env_idx:]).strip()


# Strip <system-reminder> blocks containing Pyright <new-diagnostics> from content
def _strip_pyright_diagnostics(content):
    return _strip_system_reminder(content, "<new-diagnostics>")


# Strip gitStatus section (always at bottom of sys[3]) from text — everything from 'gitStatus:' to end.
def _strip_git_status(text: str) -> str:
    marker = "gitStatus:"
    idx = text.find(marker)
    if idx == -1:
        return text
    return text[:idx].rstrip()
