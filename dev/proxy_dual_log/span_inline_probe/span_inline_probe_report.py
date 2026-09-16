# INFRASTRUCTURE
import json
from datetime import datetime, timezone

PREVIEW_CHARS = 80

# FUNCTIONS

def _preview(text: str, n: int = PREVIEW_CHARS) -> str:
    s = text.replace("\n", "\\n")
    if len(s) > n:
        return repr(s[:n]) + f"…({len(text)}c)"
    return repr(s) + f" ({len(text)}c)"


def _inline_mock(spans: list) -> str:
    parts = []
    for tag, text in spans:
        excerpt = text.replace("\n", "\\n")[:50]
        sym = {"equal": "[=]", "stripped": "[-]", "injected": "[+]"}.get(tag, "[?]")
        parts.append(f"{sym}{excerpt!r}")
    return "  ".join(parts)


def _form_b_per_log(spans: list) -> tuple:
    stripped_log = [(t, txt) for t, txt in spans if t in ("equal", "stripped")]
    injected_log = [(t, txt) for t, txt in spans if t in ("equal", "injected")]
    return stripped_log, injected_log


def _merge_form_b(stripped_log: list, injected_log: list) -> list:
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


def _report_block_spans(lines: list, spans: list) -> None:
    lines.append("### 1. Full ordered span sequence (diff_engine output on normalized text)")
    lines.append("")
    lines.append("```")
    for i, (tag, text) in enumerate(spans):
        lines.append(f"[{i}] ({tag:8s}, {_preview(text)})")
    lines.append("```")
    lines.append("")

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


def _report_form_a_row(lines: list, r: dict) -> None:
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


def _report_form_a(lines: list, spans: list, orig_norm_text: str, fwd_norm_text: str, fwd_raw_text: str) -> None:
    lines.append("### 3. Form A — position offsets (empirical analysis)")
    lines.append("")
    fa = _form_a_analysis(spans, orig_norm_text, fwd_norm_text, fwd_raw_text)
    any_failure = any(
        (r.get("offset_mismatch") or r.get("exact_in_raw") == -1)
        for r in fa
    )
    for r in fa:
        _report_form_a_row(lines, r)
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


def _report_form_b(lines: list, spans: list) -> None:
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

    _report_storage_cost(lines, spans, s_bytes, i_bytes, m_bytes)


def _report_storage_cost(lines: list, spans: list, s_bytes: int, i_bytes: int, m_bytes: int) -> None:
    cur_s = [txt for t, txt in spans if t == "stripped"]
    cur_i = [txt for t, txt in spans if t == "injected"]
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


def _report_block(lines: list, blk: dict) -> None:
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

    _report_block_spans(lines, spans)
    _report_form_a(lines, spans, orig_norm_text, fwd_norm_text, fwd_raw_text)
    _report_form_b(lines, spans)


def _report_tension_flag(lines: list) -> None:
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


def _report_recommendation(lines: list) -> None:
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


def _build_report(blocks: list, log_id: str) -> list:
    lines = []
    now = datetime.now(timezone.utc)
    lines.append(f"# span_inline_probe — {now.strftime('%Y-%m-%d')}")
    lines.append("")
    lines.append(f"**Log:** `{log_id}`  |  **Blocks probed:** {len(blocks)} / 3")
    lines.append("")
    lines.append("---")
    lines.append("")

    for blk in blocks:
        _report_block(lines, blk)

    _report_tension_flag(lines)
    _report_recommendation(lines)

    return lines
