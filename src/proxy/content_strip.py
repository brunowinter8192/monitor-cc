# INFRASTRUCTURE
import re

_REJECTION_MARKER = "The user doesn't want to proceed with this tool use"

# FUNCTIONS

# Remove only plan-mode blocks/sections from content, preserving everything else.
# Returns the remaining content, or None if nothing is left after stripping.
def _strip_plan_mode_blocks(content):
    if isinstance(content, list):
        kept = [b for b in content if not (isinstance(b, dict) and "Plan mode is active" in b.get("text", ""))]
        if not kept:
            return None
        for i, b in enumerate(kept):
            if isinstance(b, dict) and not b.get("text", "").strip():
                kept[i] = {**b, "text": "."}
        return kept
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
            if isinstance(block, dict) and block.get("type") == "text":
                new_text = pattern.sub('', block.get("text", ""))
                if not new_text.strip():
                    new_text = "."
                result.append({**block, "text": new_text})
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
            if isinstance(block, dict) and block.get("type") == "text":
                new_text = pattern.sub('', block.get("text", ""))
                if not new_text.strip():
                    new_text = "."
                result.append({**block, "text": new_text})
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
