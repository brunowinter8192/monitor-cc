import re


def _strip_plan_mode_blocks(content):
    """Remove only plan-mode blocks/sections from content, preserving everything else.
    Returns the remaining content, or None if nothing is left after stripping."""
    if isinstance(content, list):
        result = []
        for b in content:
            if not isinstance(b, dict):
                result.append(b)
                continue
            btype = b.get("type")
            if btype == "text" and "Plan mode is active" in b.get("text", ""):
                continue  # drop entire text block
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


def _strip_all_system_reminders(content):
    """Strip ALL <system-reminder>...</system-reminder> blocks from string or list content."""
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
            else:
                result.append(block)
        return result
    return content


def _strip_user_interrupt_sr(content, marker: str):
    """Strip only the IMPORTANT notification line from a user-interrupt SR; preserve user message body."""
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
            else:
                result.append(block)
        return result
    return content


def _strip_system_reminder(content, marker: str):
    """Strip any <system-reminder> block whose text contains marker, from string or list content."""
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
            else:
                result.append(block)
        return result
    return content


def _strip_pyright_diagnostics(content):
    """Strip <system-reminder> blocks containing Pyright <new-diagnostics> from content."""
    return _strip_system_reminder(content, "<new-diagnostics>")
