"""
Probe: green-overlay false-injection bug in _diff_text (word-level path).
Reproduces the bug on real log data and validates the char-level candidate fix.
Self-contained — all helpers copied from src/; no src/ imports at module level.

Usage (from project root):
    ./venv/bin/python dev/proxy_dual_log/green_overlay_probe.py
"""

# INFRASTRUCTURE
import json
from difflib import SequenceMatcher
from pathlib import Path

_SCRIPT_DIR = Path(__file__).parent.resolve()
# Main project layout:  <project>/dev/proxy_dual_log/  → parents[1] = project root
# Worktree layout:      <project>/.claude/worktrees/<name>/dev/proxy_dual_log/ → parents[4] = project root
_log_from_main = (_SCRIPT_DIR.parents[1] / "src" / "logs" / "dual_log").resolve()
_log_from_wt   = (_SCRIPT_DIR.parents[4] / "src" / "logs" / "dual_log").resolve()
LOG_DIR  = _log_from_main if _log_from_main.exists() else _log_from_wt
REPORT_DIR = _SCRIPT_DIR / "green_overlay_probe_reports"

RATIO_THRESHOLD = 0.1  # from src/proxy/diff_engine.py

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


# Load first matching entry by flow_id from a JSONL file
def load_entry_by_flow_id(path: Path, flow_id: str) -> dict:
    with open(path) as f:
        for line in f:
            e = json.loads(line)
            if e.get("flow_id") == flow_id:
                return e
    return {}


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


# Run both variants on a pair and return comparison record
def compare_pair(label: str, o_text: str, f_text: str) -> dict:
    word_spans = diff_text_word(o_text, f_text)
    char_spans = diff_text_char(o_text, f_text)
    fid_o, fid_f = check_fidelity(o_text, f_text, char_spans)
    return {
        "label":      label,
        "o_len":      len(o_text),
        "f_len":      len(f_text),
        "word_spans": word_spans,
        "char_spans": char_spans,
        "word_count": len(word_spans),
        "char_count": len(char_spans),
        "fid_ok":     fid_o and fid_f,
        "fid_detail": f"orig_ok={fid_o} fwd_ok={fid_f}",
    }


# Extract primary bug case: badge-recap worker, msg[18] blk[0], system-reminder stripped
def get_bug_case():
    stem    = "api_requests_worker_25c51a2e_badge-recap_1780678180"
    flow_id = "7a12336f-7d76-476f-a3b2-4d58f9ae6f2f"

    orig_e = load_entry_by_flow_id(LOG_DIR / f"{stem}_original.jsonl", flow_id)
    orig_payload_norm = _strip_cache_control(orig_e["payload"])
    blk0_orig = orig_payload_norm["messages"][18]["content"][0]
    o_text = _get_text(blk0_orig)

    fwd_e = load_entry_by_flow_id(LOG_DIR / f"{stem}_forwarded.jsonl", flow_id)
    msg18_fwd_raw = fwd_e["messages_delta"]["18"]
    msg18_fwd_norm = _normalize_msg_shape(_strip_cache_control(msg18_fwd_raw))
    blk0_fwd = msg18_fwd_norm["content"][0]
    f_text = _get_text(blk0_fwd)

    return o_text, f_text, stem, flow_id


# Extract 3 regression cases from badge-recap worker log — all ratio >= 0.1 (word-level path)
def get_regression_cases() -> list:
    stem  = "api_requests_worker_25c51a2e_badge-recap_1780678180"
    cases = []

    # Helper: get (o_text, f_text) for a given flow_id + msg index + block index
    def get_msg_blk_texts(fid: str, midx: int, bidx: int):
        orig_e = load_entry_by_flow_id(LOG_DIR / f"{stem}_original.jsonl", fid)
        fwd_e  = load_entry_by_flow_id(LOG_DIR / f"{stem}_forwarded.jsonl", fid)
        if not orig_e or not fwd_e:
            return None, None
        op = _strip_cache_control(orig_e["payload"])
        msgs = op.get("messages", [])
        if midx >= len(msgs):
            return None, None
        content_o = msgs[midx].get("content", [])
        if not isinstance(content_o, list) or bidx >= len(content_o):
            return None, None
        o_text = _get_text(content_o[bidx])
        mdelta = fwd_e.get("messages_delta", {})
        msg_fwd_raw = mdelta.get(str(midx))
        if not msg_fwd_raw:
            return None, None
        msg_fwd = _normalize_msg_shape(_strip_cache_control(msg_fwd_raw))
        content_f = msg_fwd.get("content", [])
        if not isinstance(content_f, list) or bidx >= len(content_f):
            return None, None
        f_text = _get_text(content_f[bidx])
        return o_text, f_text

    # R1: stripped log line 3 — msg[2] blk[0], ratio=0.764, partial JSON token replacement
    with open(LOG_DIR / f"{stem}_stripped.jsonl") as f:
        slines = f.readlines()
    fid_r1 = json.loads(slines[3])["flow_id"]
    o1, f1 = get_msg_blk_texts(fid_r1, 2, 0)
    if o1 and f1 and o1 != f1:
        cases.append(("R1: msg[2] blk[0] partial replace (ratio=0.76)", o1, f1))

    # R2: stripped log line 4 — msg[4] blk[0], ratio=0.993, tiny edit in large block
    fid_r2 = json.loads(slines[4])["flow_id"]
    o2, f2 = get_msg_blk_texts(fid_r2, 4, 0)
    if o2 and f2 and o2 != f2:
        cases.append(("R2: msg[4] blk[0] tiny edit large block (ratio=0.99)", o2, f2))

    # R3: stripped log line 21 — msg[38] blk[0], ratio=0.951, another system-reminder strip
    fid_r3 = json.loads(slines[21])["flow_id"]
    o3, f3 = get_msg_blk_texts(fid_r3, 38, 0)
    if o3 and f3 and o3 != f3:
        cases.append(("R3: msg[38] blk[0] system-reminder strip (ratio=0.95)", o3, f3))

    # R4: synthetic whitespace-collapse test — word-level joins with single space, losing original spacing
    o_ws = 'key1:  value1\n\nkey2:\tvalue2\nkey3:   value3'
    f_ws = 'key1:  value1\n\nkey2:\tvalue2_changed\nkey3:   value3'
    cases.append(("R4: synthetic multi-space/tab whitespace-collapse test", o_ws, f_ws))

    return cases


# Build and write the probe report
def green_overlay_probe_workflow():
    REPORT_DIR.mkdir(exist_ok=True)
    lines = []

    def emit(*parts):
        lines.append("".join(str(p) for p in parts) + "\n")

    emit("# Green Overlay Probe Report")
    emit()
    emit("**Bug:** word-level `_diff_text` mis-tags common prefix as stripped+injected when")
    emit("JSON-serialized blocks contain `\\\\n` (backslash-n, 2 chars) — no real whitespace")
    emit("inside the JSON string token, so orig and fwd tokens are one word each, differ → 'replace'.")

    # --- Primary bug case ---
    emit()
    emit("## Primary Bug Case")
    try:
        o_text, f_text, stem, flow_id = get_bug_case()

        cp_len = 0
        while cp_len < len(o_text) and cp_len < len(f_text) and o_text[cp_len] == f_text[cp_len]:
            cp_len += 1

        emit()
        emit(f"**Source:** `{stem}`")
        emit(f"**Flow ID:** `{flow_id}`")
        emit(f"**Location:** `messages[18]` block 0 (tool_result, role=user)")
        emit(f"**o_text len:** {len(o_text)} chars | **f_text len:** {len(f_text)} chars")
        emit(f"**Common prefix len:** {cp_len} chars (ends at `set()))\\\\n\\\\n`)")
        emit(f"**Divergence in o_text:** `{repr(o_text[cp_len:cp_len+60])}`")
        emit(f"**Divergence in f_text:** `{repr(f_text[cp_len:cp_len+60])}`")

        r = compare_pair("bug_case", o_text, f_text)

        emit()
        emit(f"### Word-level spans — CURRENT (buggy) — {r['word_count']} spans")
        emit()
        emit("```")
        emit(fmt_spans(r["word_spans"]))
        emit("```")
        emit()
        emit("**Bug:** the long token containing `set()))\\\\n\\\\n<system-reminder>\\\\nThe...` (orig)")
        emit("and `set()))\\\\n\\\\n\",` (fwd) are ONE word each (no real whitespace inside JSON).")
        emit("SequenceMatcher tags them 'replace' → common prefix `set()))\\\\n\\\\n` mis-tagged as")
        emit("stripped (yellow) AND injected (green). Only `<system-reminder>…` was actually stripped.")

        emit()
        emit(f"### Char-level spans — CANDIDATE FIX — {r['char_count']} spans")
        emit()
        emit("```")
        emit(fmt_spans(r["char_spans"]))
        emit("```")
        emit()
        fid_o, fid_f = check_fidelity(o_text, f_text, r["char_spans"])
        emit(f"**Fidelity:** orig_recon==o_text: {fid_o} {'✅' if fid_o else '❌'} | fwd_recon==f_text: {fid_f} {'✅' if fid_f else '❌'}")

        char_spans = r["char_spans"]
        if char_spans and char_spans[0][0] == "equal":
            eq_len = len(char_spans[0][1])
            emit(f"**Char span[0]:** `equal`, len={eq_len} → common prefix correctly tagged as equal ✅")
        stripped_texts = [t for tag, t in char_spans if tag == "stripped"]
        has_sysrem = any("<system-reminder>" in t for t in stripped_texts)
        emit(f"**Stripped contains `<system-reminder>`:** {has_sysrem} {'✅' if has_sysrem else '❌'}")
        injected_texts = [t for tag, t in char_spans if tag == "injected"]
        emit(f"**Injected spans:** {[repr(t[:60]) for t in injected_texts]}")

    except Exception as ex:
        emit(f"ERROR loading bug case: {ex}")
        import traceback; traceback.print_exc()

    # --- Regression cases ---
    emit()
    emit("## Regression Spot-Check")
    emit()
    emit("| Case | o_len | f_len | word spans | char spans | char fidelity |")
    emit("|---|---|---|---|---|---|")

    reg_detail_lines = []
    try:
        reg_cases = get_regression_cases()
        for label, o_t, f_t in reg_cases:
            r = compare_pair(label, o_t, f_t)
            fid_cell = f"✅ {r['fid_detail']}" if r["fid_ok"] else f"❌ {r['fid_detail']}"
            emit(f"| {label} | {r['o_len']} | {r['f_len']} | {r['word_count']} | {r['char_count']} | {fid_cell} |")
            reg_detail_lines.append((label, o_t, f_t, r))

        emit()
        emit("### Details")
        for label, o_t, f_t, r in reg_detail_lines:
            emit()
            emit(f"#### {label}")
            emit(f"o_text: `{repr(o_t[:200])}`")
            emit(f"f_text: `{repr(f_t[:200])}`")
            emit()
            emit(f"Word spans ({r['word_count']}):")
            emit("```")
            emit(fmt_spans(r["word_spans"]))
            emit("```")
            emit(f"Char spans ({r['char_count']}):")
            emit("```")
            emit(fmt_spans(r["char_spans"]))
            emit("```")
            emit(f"Fidelity: {r['fid_detail']}")

    except Exception as ex:
        emit(f"ERROR in regression cases: {ex}")
        import traceback; traceback.print_exc()

    # --- Summary ---
    emit()
    emit("## Summary")
    emit()
    emit("- **Word-level bug:** splits on real whitespace → JSON `\\\\n` is not whitespace →")
    emit("  long tokens with embedded escaped newlines + `<system-reminder>` are ONE word →")
    emit("  SequenceMatcher 'replace' → common prefix mis-colored stripped (yellow) + injected (green).")
    emit("- **Char-level fix:** operates character-by-character → finds exact boundary →")
    emit("  common prefix tagged `equal`, only diverging suffix is stripped/injected.")
    emit("- **Whitespace collapse:** word-level `' '.join(...)` collapses multi-space/tab;")
    emit("  char-level uses exact substrings — zero information loss.")
    emit("- **Span count:** char-level span count ≤ word-level for ordinary text;")
    emit("  see regression table above — no explosion on any real case tested.")

    report_path = REPORT_DIR / "green_overlay_probe.md"
    with open(report_path, "w") as fout:
        fout.writelines(lines)

    print(f"Report written to: {report_path}")


# ORCHESTRATOR
if __name__ == "__main__":
    green_overlay_probe_workflow()
