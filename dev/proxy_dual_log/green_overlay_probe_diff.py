# INFRASTRUCTURE
import json
from difflib import SequenceMatcher

RATIO_THRESHOLD = 0.1  # from src/proxy/diff_engine.py

# Copied from src/proxy/strip_vocab.py RULES — marker substrings only (attribution needs them)
_STRIP_RULES_MARKERS: dict[str, list[str]] = {
    'REJ': ['(rejection marker stripped by proxy)'],
    'TN':  ['<task-notification>'],
    'NAG': ["task tools haven"],
    'DEF': ['deferred tools are now available via ToolSearch'],
    'UI':  ['user sent a new message while you were working', 'IMPORTANT: After completing your current task'],
    'SK':  ['The following skills are available for use with the Skill tool'],
    'CMD': ['# claudeMd', 'Contents of ', 'The date has changed.'],
    'PYR': ['<new-diagnostics>'],
    'PM':  ['Plan mode is active', 'Plan mode '],
    'ALL': [],  # skip — no markers
    'PP':  ['Preview (first '],
    'BGK': ['Background command "'],
    'GL':  ['Another git process seems to be running'],
    'BD':  ['issues.jsonl', 'auto-export: no changes', 'auto-export: throttled', 'auto-export: skipping'],
    'ENV': ["As you answer the user's questions, you can use the following context:\n# userEmail"],
    'HP':  ['PreToolUse:', 'hook error'],
    'SN':  ['[SYSTEM NOTIFICATION'],
    'FM':  [' was modified'],
}

# Copied from src/proxy/logging.py
_MSG_CODE_TO_FN: dict[str, str] = {
    'REJ': '_apply_first_pass',    'TN':  '_apply_first_pass',
    'NAG': '_apply_first_pass',    'DEF': '_apply_first_pass',
    'UI':  '_apply_first_pass',    'PM':  '_apply_first_pass',
    'SK':  '_apply_cumulative_sr_strips', 'CMD': '_apply_cumulative_sr_strips',
    'PYR': '_apply_cumulative_sr_strips',
    'ALL': '_apply_final_sr_pass', 'ENV': '_apply_final_sr_pass',
    'SN':  '_apply_final_sr_pass', 'FM':  '_apply_final_sr_pass',
    'PP':  '_apply_po_preview_strip', 'BGK': '_apply_bg_exit_strip',
    'GL':  '_apply_git_lock_strip',   'BD':  '_apply_bd_noise_strip',
    'HP':  '_apply_hook_prefix_strip',
}

# FUNCTIONS

# Copied from src/proxy/diff_engine.py — exact production implementation
def _get_text(element) -> str:
    if element is None:
        return ""
    if isinstance(element, str):
        return element
    if isinstance(element, dict):
        t = element.get("text")
        if t is not None:
            return str(t)
        return json.dumps(element, ensure_ascii=False)
    return json.dumps(element, ensure_ascii=False)


# Copied from src/proxy/logging.py — strips cache_control recursively
def _strip_cache_control(obj):
    if isinstance(obj, dict):
        return {k: _strip_cache_control(v) for k, v in obj.items() if k != "cache_control"}
    if isinstance(obj, list):
        return [_strip_cache_control(i) for i in obj]
    return obj


# Copied from src/proxy/logging.py — normalizes single-text-block user messages
def _normalize_msg_shape(msg: dict) -> dict:
    if msg.get("role") != "user":
        return msg
    content = msg.get("content")
    if not isinstance(content, list) or len(content) != 1:
        return msg
    block = content[0]
    if not isinstance(block, dict):
        return msg
    if set(block.keys()) == {"type", "text"} and block["type"] == "text":
        return {**msg, "content": block["text"]}
    return msg


# Current (buggy) word-level _diff_text — exact copy of src/proxy/diff_engine.py
def diff_text_word(orig_text: str, fwd_text: str) -> list:
    if orig_text == fwd_text:
        return [("equal", orig_text)]
    if not orig_text:
        return [("injected", fwd_text)]
    if not fwd_text:
        return [("stripped", orig_text)]
    ratio = SequenceMatcher(None, orig_text, fwd_text).ratio()
    if ratio < RATIO_THRESHOLD:
        return [("stripped", orig_text), ("injected", fwd_text)]
    spans = []
    ow, fw = orig_text.split(), fwd_text.split()
    for tag, i1, i2, j1, j2 in SequenceMatcher(None, ow, fw).get_opcodes():
        if tag == "equal":
            spans.append(("equal", " ".join(ow[i1:i2])))
        elif tag == "delete":
            spans.append(("stripped", " ".join(ow[i1:i2])))
        elif tag == "insert":
            spans.append(("injected", " ".join(fw[j1:j2])))
        else:
            spans.append(("stripped", " ".join(ow[i1:i2])))
            spans.append(("injected", " ".join(fw[j1:j2])))
    return spans


# Candidate fix: char-level _diff_text — keeps early-exit branches, replaces word-level path
def diff_text_char(orig_text: str, fwd_text: str) -> list:
    if orig_text == fwd_text:
        return [("equal", orig_text)]
    if not orig_text:
        return [("injected", fwd_text)]
    if not fwd_text:
        return [("stripped", orig_text)]
    ratio = SequenceMatcher(None, orig_text, fwd_text).ratio()
    if ratio < RATIO_THRESHOLD:
        return [("stripped", orig_text), ("injected", fwd_text)]
    spans = []
    for tag, i1, i2, j1, j2 in SequenceMatcher(None, orig_text, fwd_text).get_opcodes():
        if tag == "equal":
            spans.append(("equal", orig_text[i1:i2]))
        elif tag == "delete":
            spans.append(("stripped", orig_text[i1:i2]))
        elif tag == "insert":
            spans.append(("injected", fwd_text[j1:j2]))
        else:
            spans.append(("stripped", orig_text[i1:i2]))
            spans.append(("injected", fwd_text[j1:j2]))
    return spans


# Copied from src/proxy/strip_vocab.py:attribute_chunk — marker-based rule attribution
def _attribute_chunk_probe(chunk: str):
    if chunk.startswith('<task-notification>'):
        return 'TN'
    for code, markers in _STRIP_RULES_MARKERS.items():
        if code in ('TN', 'ALL'):
            continue
        for marker in markers:
            if marker in chunk:
                return code
    return None


# Mirrored from src/proxy/logging.py inject-attribution block (~line 421)
def _fn_for_inject(i_text: str) -> str:
    if not i_text:
        return "unknown"
    if "background done" in i_text:
        return "_apply_bg_exit_strip"
    code = _attribute_chunk_probe(i_text)
    return _MSG_CODE_TO_FN.get(code, "unknown") if code else "unknown"


# Level-2 fix: char-level diff + gate phantom injected spans via attribution
# Injected span with fn="unknown" → reclassify to equal (grey).
# Injected span with known fn → keep green. Maintains fidelity (gated equal still in fwd recon).
def diff_text_char_gated(orig_text: str, fwd_text: str) -> list:
    raw = diff_text_char(orig_text, fwd_text)
    result = []
    for tag, text in raw:
        if tag == "injected" and _fn_for_inject(text) == "unknown":
            result.append(("equal", text))  # phantom → grey
        else:
            result.append((tag, text))
    return result


# Verify char-level reconstruction fidelity — equal+stripped must rebuild o_text, equal+injected must rebuild f_text
def check_fidelity(o_text: str, f_text: str, char_spans: list) -> tuple:
    orig_recon = "".join(t for tag, t in char_spans if tag in ("equal", "stripped"))
    fwd_recon  = "".join(t for tag, t in char_spans if tag in ("equal", "injected"))
    return (orig_recon == o_text), (fwd_recon == f_text)


# Format span list for report (truncate long values)
def fmt_spans(spans: list, max_text: int = 120) -> str:
    lines = []
    for tag, text in spans:
        preview = repr(text[:max_text]) + ("..." if len(text) > max_text else "")
        lines.append(f"  ({tag!r:10s}, {preview})")
    return "\n".join(lines)


# Run all three variants on a pair and return comparison record
def compare_pair(label: str, o_text: str, f_text: str) -> dict:
    word_spans  = diff_text_word(o_text, f_text)
    char_spans  = diff_text_char(o_text, f_text)
    gated_spans = diff_text_char_gated(o_text, f_text)
    fid_o, fid_f = check_fidelity(o_text, f_text, char_spans)
    # gated fidelity: gated equal (was injected) counts toward fwd; stripped+equal count toward orig
    gated_orig_recon = "".join(t for tag, t in gated_spans if tag in ("equal", "stripped"))
    gated_fwd_recon  = "".join(t for tag, t in gated_spans if tag in ("equal", "injected"))
    gated_fid_ok = (gated_orig_recon == o_text) and (gated_fwd_recon == f_text)
    return {
        "label":       label,
        "o_len":       len(o_text),
        "f_len":       len(f_text),
        "word_spans":  word_spans,
        "char_spans":  char_spans,
        "gated_spans": gated_spans,
        "word_count":  len(word_spans),
        "char_count":  len(char_spans),
        "gated_count": len(gated_spans),
        "fid_ok":      fid_o and fid_f,
        "fid_detail":  f"orig_ok={fid_o} fwd_ok={fid_f}",
        "gated_fid_ok": gated_fid_ok,
    }
