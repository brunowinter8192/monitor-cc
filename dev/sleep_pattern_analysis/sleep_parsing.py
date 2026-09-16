# INFRASTRUCTURE
import os
import re

_SLEEP_RE = re.compile(r'\bsleep\s+(\d+(?:\.\d+)?)\b')
_OP_RE    = re.compile(r'(&&|\|\||;|\n)')
_LOOP_RE  = re.compile(r'\b(while|for|until)\b')


# FUNCTIONS

def _parse_all_sleeps(events: list) -> list:
    records = []
    for ev in events:
        if not ev["cmd"]:
            continue
        for rec in _sleep_contexts(ev["cmd"]):
            rec["timestamp"] = ev["timestamp"]
            rec["project"]   = ev["project"]
            rec["cmd_snippet"] = ev["cmd"][:200].replace("\n", " ")
            records.append(rec)
    return records


def _sleep_contexts(cmd: str) -> list:
    # Pre-detect heredoc spans: list of (start, end) byte ranges that are heredoc bodies
    heredoc_spans = _heredoc_spans(cmd)

    results = []
    for m in _SLEEP_RE.finditer(cmd):
        results.append(_build_sleep_context(cmd, m, heredoc_spans))
    return results


def _build_sleep_context(cmd: str, m, heredoc_spans: list) -> dict:
    duration = float(m.group(1))
    pos    = m.start()
    before = cmd[:pos]
    after  = cmd[m.end():]

    # Flag sleeps that land inside a heredoc body (hook FP — regex scanner too broad)
    in_heredoc = any(s <= pos < e for s, e in heredoc_spans)

    chain_op, cmd_before = _resolve_chain_before(before)
    cmd_after = _resolve_cmd_after(after)

    is_canonical = bool(re.match(r"\s*sleep\s+\d+(?:\.\d+)?\s*&&\s*echo\s+done\s*$", cmd.strip()))
    in_loop      = bool(_LOOP_RE.search(before[-200:]))

    return {
        "duration":     int(duration) if duration == int(duration) else duration,
        "cmd_before":   cmd_before,
        "cmd_after":    cmd_after,
        "chain_op":     chain_op,
        "in_loop":      in_loop,
        "is_canonical": is_canonical,
        "in_heredoc":   in_heredoc,
    }


# chain_op and cmd_before
def _resolve_chain_before(before: str) -> tuple:
    ops = list(_OP_RE.finditer(before))
    if ops:
        last_op  = ops[-1]
        chain_op = last_op.group(1)
        seg_after_op = before[last_op.end():]
        # If nothing between last operator and sleep, cmd_before is the segment
        # ending at the operator (e.g. "cmd2\n sleep" → cmd_before = "cmd2")
        if seg_after_op.strip():
            segment = seg_after_op
        elif len(ops) >= 2:
            segment = before[ops[-2].end(): last_op.start()]
        else:
            segment = before[: last_op.start()]
    else:
        chain_op = "start"
        segment  = before
    return chain_op, _first_token(segment)


# cmd_after: first token after the operator following sleep
def _resolve_cmd_after(after: str) -> str:
    op_after = re.match(r"\s*(&&|\|\||;|\n)\s*", after)
    rest      = after[op_after.end():] if op_after else after
    return _first_token(rest)


def _heredoc_spans(cmd: str) -> list:
    """Return list of (start, end) for heredoc body regions in cmd."""
    spans = []
    for hm in re.finditer(r"<<['\"]?(\w+)['\"]?\n", cmd):
        delim = hm.group(1)
        body_start = hm.end()
        end_pat = re.compile(r"^" + re.escape(delim) + r"\s*$", re.MULTILINE)
        em = end_pat.search(cmd, body_start)
        if em:
            spans.append((body_start, em.start()))
    return spans


def _first_token(text: str) -> str:
    text = text.strip()
    if not text:
        return "(empty)"
    # Strip variable assignments (VAR=val ...)
    text = re.sub(r"^[A-Z_][A-Z_0-9]*=\S*\s*", "", text).strip()
    if not text:
        return "(assignment)"
    first = text.split()[0]
    first = first.lstrip("$(")          # strip subshell prefixes
    if first.startswith("./"):
        first = first[2:]
    if "/" in first:
        first = os.path.basename(first)  # normalize paths to basename
    return first or "(empty)"
