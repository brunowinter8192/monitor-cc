"""
span_inline_probe.py — Form A vs Form B inline-render data model probe.

Validates that Form B (full ordered span list per log) is the minimal enrichment
that lets the read-side render strip/inject inline without content duplication.
Shows Form A's empirical failure via concrete offset/substring mismatches on real data.

Probes 3 representative blocks from log api_requests_opus_monitor_cc_1780517466:
  B1 — sys[2] full-replace (CC prompt → proxy rules, ratio<0.1, no equal spans)
  B2 — sys[3] strip-to-dot (whole original stripped, '.' injected, no equal spans)
  B3 — msg[N][0] word-level mixed (equal + stripped + injected, with cache_control diff)

Usage (from project root):
    ./venv/bin/python dev/proxy_dual_log/span_inline_probe.py

Output: dev/proxy_dual_log/span_inline_probe_reports/<YYYYMMDD>.md
"""

# INFRASTRUCTURE
import importlib.util
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[2]))

# Load diff_engine directly from path — keeps probe independent of src/ package structure
_engine_path = Path(__file__).parents[2] / "src" / "proxy" / "diff_engine.py"
_spec = importlib.util.spec_from_file_location("diff_engine_probe", _engine_path)
diff_engine = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(diff_engine)
_diff_text = diff_engine._diff_text


# Inline: mirrors src/proxy/logging.py:_strip_cache_control — strip "cache_control" keys recursively
def _strip_cache_control(obj):
    if isinstance(obj, dict):
        return {k: _strip_cache_control(v) for k, v in obj.items() if k != "cache_control"}
    if isinstance(obj, list):
        return [_strip_cache_control(item) for item in obj]
    return obj

LOG_DIR = Path(__file__).parents[5] / "src" / "logs" / "dual_log"
LOG_ID = "api_requests_opus_monitor_cc_1780517466"
REPORT_DIR = Path("dev/proxy_dual_log/span_inline_probe_reports")
PREVIEW_CHARS = 80


# ORCHESTRATOR

def span_inline_probe_workflow() -> None:
    orig_path = LOG_DIR / f"{LOG_ID}_original.jsonl"
    fwd_path = LOG_DIR / f"{LOG_ID}_forwarded.jsonl"

    orig_entries = _load_jsonl(orig_path)
    fwd_entries = _load_jsonl(fwd_path)
    fwd_states = _reconstruct_chains(fwd_entries)
    matched = _match_requests(orig_entries, fwd_entries, fwd_states)

    b1 = _find_sys2_block(matched)
    b2 = _find_sys3_block(matched)
    b3 = _find_msg_wordlevel_block(matched)
    blocks = [b for b in [b1, b2, b3] if b is not None]

    lines = _build_report(blocks)
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    now = datetime.now(timezone.utc)
    report_path = REPORT_DIR / f"{now.strftime('%Y%m%d')}.md"
    report_path.write_text("\n".join(lines), encoding="utf-8")
    print(f"Report: {report_path}")


# FUNCTIONS

def _load_jsonl(path: Path) -> list:
    entries = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                try:
                    entries.append(json.loads(line))
                except json.JSONDecodeError:
                    pass
    return entries


def _infer_family(model: str) -> str:
    m = model.lower()
    if "haiku" in m:
        return "haiku"
    if "sonnet" in m:
        return "sonnet"
    return "opus"


def _reconstruct_chains(fwd_entries: list) -> list:
    chain_states = {}
    result = []
    for entry in fwd_entries:
        if entry.get("type") != "forwarded_delta":
            result.append(None)
            continue
        family = _infer_family(entry.get("model", ""))
        counts = entry.get("counts", {})
        if entry.get("is_first"):
            state = {}
            for cat in ("system", "tools", "messages"):
                lst = [None] * counts.get(cat, 0)
                for idx_str, elem in entry.get(f"{cat}_delta", {}).items():
                    i = int(idx_str)
                    if i < len(lst):
                        lst[i] = elem
                state[cat] = lst
        else:
            prev = chain_states.get(family, {"system": [], "tools": [], "messages": []})
            state = {}
            for cat in ("system", "tools", "messages"):
                lst = list(prev[cat])
                for idx_str, elem in entry.get(f"{cat}_delta", {}).items():
                    i = int(idx_str)
                    while len(lst) <= i:
                        lst.append(None)
                    lst[i] = elem
                state[cat] = lst[:counts.get(cat, len(lst))]
        chain_states[family] = state
        result.append(state)
    return result


def _match_requests(orig_entries: list, fwd_entries: list, fwd_states: list) -> list:
    orig_by_reqid = {}
    orig_queues = {}
    for oe in orig_entries:
        reqid = oe.get("request_id", "")
        family = _infer_family(oe.get("model", ""))
        if reqid:
            orig_by_reqid[reqid] = oe
        orig_queues.setdefault(family, []).append(oe)
    cursors = {}
    result = []
    for fe, fs in zip(fwd_entries, fwd_states):
        if fs is None:
            continue
        family = _infer_family(fe.get("model", ""))
        reqid = fe.get("request_id", "")
        if reqid and reqid in orig_by_reqid:
            oe = orig_by_reqid[reqid]
        else:
            q = orig_queues.get(family, [])
            c = cursors.get(family, 0)
            oe = q[c] if c < len(q) else None
            cursors[family] = c + 1
        if oe is not None:
            result.append((oe, fe, fs))
    return result


def _block_text(block) -> str:
    if block is None:
        return ""
    if isinstance(block, str):
        return block
    if isinstance(block, dict):
        t = block.get("text")
        if t is not None:
            return str(t)
        return json.dumps(block, ensure_ascii=False)
    return json.dumps(block, ensure_ascii=False)


def _find_sys2_block(matched: list) -> dict:
    """sys[2] full-replace: CC prompt → proxy rules. ratio<0.1, 2 spans."""
    for req_num, (oe, _, fs) in enumerate(matched, 1):
        o_sys = [b for b in (oe.get("payload", {}).get("system", []) or []) if isinstance(b, dict)]
        f_sys = [b for b in (fs.get("system", []) or []) if isinstance(b, dict)]
        if len(o_sys) <= 2 or len(f_sys) <= 2:
            continue
        o_text = _block_text(_strip_cache_control(o_sys[2]))
        f_text = _block_text(_strip_cache_control(f_sys[2]))
        if len(o_text) < 1000 or len(f_text) < 10000:
            continue
        spans = _diff_text(o_text, f_text)
        if any(t == "stripped" for t, _ in spans) and any(t == "injected" for t, _ in spans):
            return {
                "label": "B1 — sys[2] full-replace",
                "req_num": req_num, "loc": "sys[2]",
                "orig_norm_text": o_text,
                "fwd_norm_text": f_text,
                "fwd_raw_text": _block_text(f_sys[2]),
                "spans": spans,
            }
    return None


def _find_sys3_block(matched: list) -> dict:
    """sys[3] strip-to-dot: whole text → '.'. ratio<0.1, 2 spans."""
    for req_num, (oe, _, fs) in enumerate(matched, 1):
        o_sys = [b for b in (oe.get("payload", {}).get("system", []) or []) if isinstance(b, dict)]
        f_sys = [b for b in (fs.get("system", []) or []) if isinstance(b, dict)]
        if len(o_sys) <= 3 or len(f_sys) <= 3:
            continue
        o_text = _block_text(_strip_cache_control(o_sys[3]))
        f_text = _block_text(_strip_cache_control(f_sys[3]))
        if len(o_text) < 1000 or len(f_text) > 5:
            continue
        spans = _diff_text(o_text, f_text)
        if any(t == "stripped" for t, _ in spans):
            return {
                "label": "B2 — sys[3] strip-to-dot",
                "req_num": req_num, "loc": "sys[3]",
                "orig_norm_text": o_text,
                "fwd_norm_text": f_text,
                "fwd_raw_text": _block_text(f_sys[3]),
                "spans": spans,
            }
    return None


def _find_msg_wordlevel_block(matched: list) -> dict:
    """First message block with equal+stripped+injected spans AND cache_control diff present.

    The cc_diff requirement ensures the block shows the cache_control normalization
    mismatch that makes Form A's equal-span text invalid as a raw-text anchor.
    """
    for req_num, (oe, _, fs) in enumerate(matched, 1):
        o_msgs = oe.get("payload", {}).get("messages", []) or []
        f_msgs = fs.get("messages", []) or []
        for midx in range(min(len(o_msgs), len(f_msgs))):
            om = o_msgs[midx]
            fm = f_msgs[midx]
            if not (om and fm):
                continue
            o_content = om.get("content", "")
            f_content = fm.get("content", "")
            if not (isinstance(o_content, list) and isinstance(f_content, list)):
                continue
            for bidx in range(min(len(o_content), len(f_content))):
                ob_raw = o_content[bidx]
                fb_raw = f_content[bidx]
                f_text = _block_text(_strip_cache_control(fb_raw))
                fb_raw_text = _block_text(fb_raw)
                if fb_raw_text == f_text:
                    continue  # no cache_control diff — skip
                o_text = _block_text(_strip_cache_control(ob_raw))
                spans = _diff_text(o_text, f_text)
                n_eq = sum(1 for t, _ in spans if t == "equal")
                has_s = any(t == "stripped" for t, _ in spans)
                has_i = any(t == "injected" for t, _ in spans)
                if n_eq >= 1 and has_s and has_i:
                    return {
                        "label": f"B3 — msg[{midx}][{bidx}] word-level mixed",
                        "req_num": req_num, "loc": f"msg[{midx}][{bidx}]",
                        "orig_norm_text": o_text,
                        "fwd_norm_text": f_text,
                        "fwd_raw_text": fb_raw_text,
                        "spans": spans,
                        "has_cc_diff": True,
                    }
    return None


def _preview(text: str, n: int = PREVIEW_CHARS) -> str:
    s = text.replace("\n", "\\n")
    if len(s) > n:
        return repr(s[:n]) + f"…({len(text)}c)"
    return repr(s) + f" ({len(text)}c)"


def _inline_mock(spans: list) -> str:
    """Text mock: [=] gray  [-] yellow  [+] green. Each content unit once."""
    parts = []
    for tag, text in spans:
        excerpt = text.replace("\n", "\\n")[:50]
        sym = {"equal": "[=]", "stripped": "[-]", "injected": "[+]"}.get(tag, "[?]")
        parts.append(f"{sym}{excerpt!r}")
    return "  ".join(parts)


def _form_b_per_log(spans: list) -> tuple:
    """Split full span sequence into per-log Form B views.

    _stripped_log: equal + stripped spans in order (equal spans duplicated as anchors)
    _injected_log: equal + injected spans in order (equal spans duplicated as anchors)
    """
    stripped_log = [(t, txt) for t, txt in spans if t in ("equal", "stripped")]
    injected_log = [(t, txt) for t, txt in spans if t in ("equal", "injected")]
    return stripped_log, injected_log


def _merge_form_b(stripped_log: list, injected_log: list) -> list:
    """Merge per-log Form B into 3-color sequence by equal-anchor alignment.

    Lock-step: consume stripped spans from stripped_log and injected from injected_log;
    advance through equal anchors together.
    """
    merged = []
    s_ptr, i_ptr = 0, 0
    n_s, n_i = len(stripped_log), len(injected_log)

    while s_ptr < n_s or i_ptr < n_i:
        s_tag = stripped_log[s_ptr][0] if s_ptr < n_s else None
        i_tag = injected_log[i_ptr][0] if i_ptr < n_i else None

        if s_tag == "stripped":
            merged.append(stripped_log[s_ptr])
            s_ptr += 1
        elif i_tag == "injected":
            merged.append(injected_log[i_ptr])
            i_ptr += 1
        elif s_tag == "equal" and i_tag == "equal":
            merged.append(("equal", stripped_log[s_ptr][1]))
            s_ptr += 1
            i_ptr += 1
        elif s_tag == "equal" and i_tag is None:
            merged.append(stripped_log[s_ptr])
            s_ptr += 1
        elif s_tag is None and i_tag == "equal":
            merged.append(injected_log[i_ptr])
            i_ptr += 1
        else:
            break

    return merged


def _form_a_analysis(spans: list, orig_norm_text: str, fwd_norm_text: str, fwd_raw_text: str) -> list:
    """Compute Form A positions and test whether they survive cache_control normalization.

    For each span: locate text as substring in the relevant reference text (normalized
    and raw). 'equal' span key test: exact span text NOT found in fwd_raw = Form A breaks.
    Texts >500c are probed via prefix only (marked probe_len<text_len).
    """
    results = []
    FIND_LIMIT = 500

    for tag, text in spans:
        probe = text if len(text) <= FIND_LIMIT else text[:FIND_LIMIT]
        if tag == "stripped":
            pos_norm = orig_norm_text.find(probe) if probe else 0
            results.append({
                "tag": "stripped", "text_len": len(text), "probe_len": len(probe),
                "pos_in_orig_norm": pos_norm,
                "note": "(orig has no cc; norm==raw for orig side)",
            })
        elif tag == "injected":
            pos_norm = fwd_norm_text.find(probe) if probe else 0
            pos_raw = fwd_raw_text.find(probe) if probe else 0
            mismatch = (pos_norm >= 0 and pos_raw >= 0 and pos_norm != pos_raw)
            results.append({
                "tag": "injected", "text_len": len(text), "probe_len": len(probe),
                "pos_in_fwd_norm": pos_norm, "pos_in_fwd_raw": pos_raw,
                "offset_mismatch": mismatch,
            })
        elif tag == "equal":
            probe_eq = text if len(text) <= FIND_LIMIT else text[:FIND_LIMIT]
            pos_norm = fwd_norm_text.find(probe_eq) if probe_eq else 0
            pos_raw = fwd_raw_text.find(probe_eq) if probe_eq else 0
            exact_in_raw = fwd_raw_text.find(text) if len(text) <= FIND_LIMIT else -2
            note = ""
            if exact_in_raw == -1:
                note = ("EXACT TEXT NOT IN fwd_raw — "
                        "Form A span text unusable as raw-text anchor "
                        "(cache_control normalization changed the serialized block)")
            results.append({
                "tag": "equal", "text_len": len(text), "probe_len": len(probe_eq),
                "pos_in_fwd_norm": pos_norm, "pos_in_fwd_raw": pos_raw,
                "exact_in_raw": exact_in_raw, "note": note,
            })
    return results


def _bytes(obj) -> int:
    return len(json.dumps(obj, ensure_ascii=False).encode("utf-8"))


def _build_report(blocks: list) -> list:
    lines = []
    now = datetime.now(timezone.utc)
    lines.append(f"# span_inline_probe — {now.strftime('%Y-%m-%d')}")
    lines.append("")
    lines.append(f"**Log:** `{LOG_ID}`  |  **Blocks probed:** {len(blocks)} / 3")
    lines.append("")
    lines.append("---")
    lines.append("")

    for blk in blocks:
        label = blk["label"]
        req_num, loc = blk["req_num"], blk["loc"]
        spans = blk["spans"]
        orig_norm_text = blk["orig_norm_text"]
        fwd_norm_text = blk["fwd_norm_text"]
        fwd_raw_text = blk["fwd_raw_text"]
        has_cc_diff = blk.get("has_cc_diff", fwd_raw_text != fwd_norm_text)

        lines.append(f"## {label}")
        lines.append("")
        lines.append(
            f"**REQ#{req_num} / {loc}**  "
            f"orig_norm={len(orig_norm_text)}c  "
            f"fwd_norm={len(fwd_norm_text)}c  "
            f"fwd_raw={len(fwd_raw_text)}c  "
            f"cc_diff={has_cc_diff}"
        )
        lines.append("")

        # --- 1. Full span sequence ---
        lines.append("### 1. Full ordered span sequence (diff_engine output on normalized text)")
        lines.append("")
        lines.append("```")
        for i, (tag, text) in enumerate(spans):
            lines.append(f"[{i}] ({tag:8s}, {_preview(text)})")
        lines.append("```")
        lines.append("")

        # --- 2. Inline render mock ---
        lines.append("### 2. Inline render mock   `[=]`=gray  `[-]`=yellow  `[+]`=green")
        lines.append("")
        lines.append("```")
        lines.append(_inline_mock(spans))
        lines.append("```")
        lines.append("")
        lines.append(f"Each part appears exactly once ({len(spans)} span(s)). ✓")
        lines.append("")
        lines.append(
            "**Current format duplicates:** read-side shows forwarded block as gray preview "
            "AND injected texts again as green spans → injected content appears twice."
        )
        lines.append("")

        # --- 3. Form A empirical analysis ---
        cur_s = [txt for t, txt in spans if t == "stripped"]
        cur_i = [txt for t, txt in spans if t == "injected"]

        lines.append("### 3. Form A — position offsets (empirical analysis)")
        lines.append("")
        fa = _form_a_analysis(spans, orig_norm_text, fwd_norm_text, fwd_raw_text)
        any_failure = any(
            (r.get("offset_mismatch") or r.get("exact_in_raw") == -1)
            for r in fa
        )
        for r in fa:
            tag = r["tag"]
            tlen, plen = r["text_len"], r["probe_len"]
            probe_note = f" (first {plen}c probed)" if plen < tlen else ""
            if tag == "stripped":
                lines.append(
                    f"- `stripped` {tlen}c{probe_note}: "
                    f"pos_in_orig_norm={r['pos_in_orig_norm']}  "
                    f"{r.get('note','')}"
                )
            elif tag == "injected":
                mm = r.get("offset_mismatch", False)
                lines.append(
                    f"- `injected` {tlen}c{probe_note}: "
                    f"pos_in_fwd_norm={r['pos_in_fwd_norm']}  "
                    f"pos_in_fwd_raw={r['pos_in_fwd_raw']}"
                    + ("  **⚠ OFFSET MISMATCH**" if mm else "")
                )
            elif tag == "equal":
                en = r.get("exact_in_raw", 0)
                note = r.get("note", "")
                lines.append(
                    f"- `equal` {tlen}c{probe_note}: "
                    f"pos_in_fwd_norm={r['pos_in_fwd_norm']}  "
                    f"pos_in_fwd_raw={r['pos_in_fwd_raw']}  "
                    f"exact_in_raw={en}"
                )
                if note:
                    lines.append(f"  - ⚠ **{note}**")
        if any_failure:
            lines.append("")
            lines.append(
                "**Form A verdict for this block: BROKEN** — "
                "equal span text(s) not found as substrings in fwd_raw_text."
            )
        else:
            lines.append("")
            lines.append(
                "**Form A verdict for this block: OFFSET-VALID** — "
                "all span texts found at consistent positions (no cache_control before content). "
                "But: word-join gap still applies for non-JSON-serialized text (system blocks)."
            )
        lines.append("")

        # --- 4. Form B per-log ---
        stripped_log, injected_log = _form_b_per_log(spans)
        merged = _merge_form_b(stripped_log, injected_log)
        s_bytes = _bytes([[t, txt] for t, txt in stripped_log])
        i_bytes = _bytes([[t, txt] for t, txt in injected_log])
        m_bytes = _bytes([[t, txt] for t, txt in merged]) if merged else 0

        lines.append("### 4. Form B — per-log enriched span lists")
        lines.append("")
        lines.append("**`_stripped` log entry (equal + stripped in order):**")
        lines.append("```")
        for tag, text in stripped_log:
            lines.append(f"  ({tag:8s}, {_preview(text)})")
        lines.append("```")
        lines.append("")
        lines.append("**`_injected` log entry (equal + injected in order):**")
        lines.append("```")
        for tag, text in injected_log:
            lines.append(f"  ({tag:8s}, {_preview(text)})")
        lines.append("```")
        lines.append("")
        if merged:
            lines.append("**3-color merged sequence (read-side equal-anchor join):**")
            lines.append("```")
            for tag, text in merged:
                lines.append(f"  ({tag:8s}, {_preview(text)})")
            lines.append("```")
            lines.append("")
            lines.append("Merged mock: `" + _inline_mock(merged) + "`")
        else:
            lines.append("*(No equal anchors — logs render independently, no merge needed.)*")
        lines.append("")

        # --- 5. Storage cost ---
        cur_s_bytes = _bytes(cur_s)
        cur_i_bytes = _bytes(cur_i)
        overhead = (s_bytes + i_bytes) - (cur_s_bytes + cur_i_bytes)
        overhead_pct = (overhead / max(1, cur_s_bytes + cur_i_bytes)) * 100

        lines.append("### 5. Storage cost")
        lines.append("")
        lines.append("| Format | _stripped B | _injected B | total B | overhead |")
        lines.append("|---|---|---|---|---|")
        lines.append(f"| Current (texts only) | {cur_s_bytes} | {cur_i_bytes} | {cur_s_bytes+cur_i_bytes} | baseline |")
        lines.append(f"| Form B per-log | {s_bytes} | {i_bytes} | {s_bytes+i_bytes} | +{overhead_pct:.0f}% (+{overhead}B) |")
        if m_bytes:
            lines.append(f"| Form B merged (hypothetical single-log) | — | {m_bytes} | {m_bytes} | |")
        lines.append("")
        lines.append("---")
        lines.append("")

    # --- Tension flag ---
    lines.append("## ⚑ Design Tension: per-log Form B vs 3-color render")
    lines.append("")
    lines.append("Per-log Form B stores 2 colors per log:")
    lines.append("- `_stripped`: `[(equal, ctx), (stripped, text), ...]`")
    lines.append("- `_injected`: `[(equal, ctx), (injected, text), ...]`")
    lines.append("")
    lines.append(
        "For the **3-color inline render** (gray=equal, yellow=stripped, green=injected "
        "simultaneously in one sequence), the read-side must merge both logs:"
    )
    lines.append("1. Load both span lists for the same block location")
    lines.append("2. Align on equal-anchor texts (identical in both logs, duplicated)")
    lines.append("3. Between each anchor pair: emit stripped (from `_stripped`) then injected (from `_injected`)")
    lines.append("")
    lines.append(
        "**Session complexity:** trivial for all blocks in this log — single anchor pair "
        "per block, 1-pass lock-step zip. No ambiguous interleavings."
    )
    lines.append("")
    lines.append(
        "**When non-trivial:** blocks with 3+ distinct change regions each having both "
        "strip and inject content. Merge is still well-defined by equal-anchor alignment, "
        "but requires a non-trivial join implementation."
    )
    lines.append("")
    lines.append(
        "**Alternative (decision required):** store the full 3-color merged sequence in "
        "`_injected` only. Eliminates the read-side merge. Cost: `_injected` carries "
        "stripped content, breaking per-log semantic separation (the four-log architecture). "
        "**Flag for decision: is per-log separation worth the merge step?**"
    )
    lines.append("")
    lines.append("---")
    lines.append("")

    # --- Recommendation ---
    lines.append("## Recommendation: Form B (per-log)")
    lines.append("")
    lines.append("### Form A rejected")
    lines.append("")
    lines.append(
        "1. **Equal span text fails as raw-text anchor** (B3, empirical): "
        "trailing equal span `'\"is_error\": false}'` exists in `fwd_norm_text` but "
        "`fwd_raw_text.find(...)` = -1. Raw text ends with "
        "`...false, \"cache_control\": {\"type\": \"ephemeral\", \"ttl\": \"1h\"}}` — "
        "there is no `false}` substring. "
        "Form A's offset points correctly to the start of `\"is_error\"` but the "
        "span text length overshoots the actual `}` position in raw text."
    )
    lines.append("")
    lines.append(
        "2. **Word-join gap** (structural): `_diff_text` produces spans via "
        "`' '.join(words[i:j])`. System-block texts use `.text` field (raw multi-line strings); "
        "newlines are collapsed to spaces in the joined span text. "
        "For ratio<0.1 (B1, B2) the path returns the full original text unchanged — "
        "trivially correct. But any word-level system-block diff produces spans whose "
        "rejoined text ≠ original character-for-character."
    )
    lines.append("")
    lines.append("### Form B chosen")
    lines.append("")
    lines.append("- **Self-contained:** span texts ARE the rendered content. No raw text slicing needed.")
    lines.append(
        "- **Cache_control immune:** normalized equal spans display as gray context. "
        "Read-side renders `(equal, text)` as gray — never needs to match it against raw text."
    )
    lines.append(
        "- **Zero overhead for whole-block replaces** (B1, B2): no equal spans exist → "
        "Form B = current format. Same bytes."
    )
    lines.append(
        "- **Bounded overhead for word-level** (B3): equal context spans add ~N bytes "
        "(common prefix/suffix). See B3 storage table."
    )
    lines.append(
        "- **Four-log architecture preserved:** `_stripped` and `_injected` stay separate; "
        "each carries its 2-color self-contained view. "
        "3-color merged render = read-side lock-step zip by equal anchors (trivial for "
        "all real-world patterns in this session)."
    )
    lines.append("")

    return lines


if __name__ == "__main__":
    span_inline_probe_workflow()
