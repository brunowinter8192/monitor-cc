# INFRASTRUCTURE

# FUNCTIONS

def original_log_used(pair_results):
    return any(r["original_attribution"] is not None for r in pair_results)

def _proven_from_bytes_flags(pair_results):
    any_img = any(
        any(m["prev_image_count"] != m["curr_image_count"] for m in r["msg_rows"])
        for r in pair_results
    )
    sys123_stable = all(
        not any(s["changed"] for s in r["sys_rows"] if s["idx"] != 0)
        for r in pair_results
    )
    tools_stable = all(not r["tools_changed"] for r in pair_results)
    recoveries = [(r["req_prev"], r["req_curr"], r["reconciliation"]["recovery_identity_holds"])
                  for r in pair_results]
    return any_img, sys123_stable, tools_stable, recoveries

def _build_proven_from_bytes_lines(any_img, sys123_stable, tools_stable):
    lines = []
    if any_img:
        lines.append(
            "- Image content blocks — both top-level message blocks and images nested inside a "
            "`tool_result` wrapper's own `content` array — are removed (byte-for-byte, not re-encoded, "
            "`content` truncated to `[]` in the tool_result case) from historical messages between some "
            "consecutive requests — see `<-IMG` flagged rows per pair above."
        )
    if sys123_stable:
        lines.append(
            "- `system[1]`, `system[2]`, `system[3]` are byte-identical across all analyzed pairs; "
            "only `system[0]` (per-request billing/entrypoint header) changes every request. "
            "The problem statement's hypothesis that divergence sits in `system[3]`/tools is "
            "REFUTED for this incident — those segments never differ across the analyzed pairs."
        )
    if tools_stable:
        lines.append("- `tools` array is byte-identical across all analyzed pairs — not a factor here.")
    lines.append(
        "- Per pair, the first diverging message index (excluding the constant `system[0]` churn) "
        "is reported above with exact index and char magnitude — see \"Segment Attribution\" per pair."
    )
    return lines

def _gather_original_attribution_rows(pair_results):
    all_orig_rows = []
    for r in pair_results:
        oa = r["original_attribution"]
        if not (oa and oa["available"]):
            continue
        notes_by_idx = {m["idx"]: m["note"] for m in r["msg_rows"]}
        for row in oa["rows"]:
            all_orig_rows.append({**row, "note": notes_by_idx.get(row["idx"], "")})
    return all_orig_rows

def _build_original_attribution_summary_lines(all_orig_rows, pair_results):
    if not all_orig_rows:
        if original_log_used(pair_results):
            return ["- Original-log cross-check was requested but found no matching flow_id entries for the analyzed pairs."]
        return []

    lines = []
    img_rows = [row for row in all_orig_rows if row["note"].startswith("image(s) evicted")]
    other_rows = [row for row in all_orig_rows if not row["note"].startswith("image(s) evicted")]
    img_client = sum(1 for row in img_rows if row["verdict"].startswith("CLIENT-SIDE"))
    img_proxy = sum(1 for row in img_rows if row["verdict"].startswith("PROXY-SIDE"))
    other_client = sum(1 for row in other_rows if row["verdict"].startswith("CLIENT-SIDE"))
    other_proxy = sum(1 for row in other_rows if row["verdict"].startswith("PROXY-SIDE"))
    if img_rows:
        lines.append(
            f"- **Image-eviction rows ({len(img_rows)} cross-checked): {img_client} CLIENT-SIDE, "
            f"{img_proxy} PROXY-SIDE.** " + (
                "ALL image-eviction rows are CLIENT-SIDE — the incoming (original, pre-proxy) payload "
                "already shows the same shrink at the same index; the image eviction happens BEFORE our "
                "proxy ever sees the request. **Fix-vs-document verdict: DOCUMENT — this is upstream/client "
                "behavior, not a proxy bug; do not chase a proxy-side fix for the image eviction.**"
                if img_client == len(img_rows) and img_proxy == 0
                else "Mixed — see per-pair verdicts above, do not generalize a single verdict."
            )
        )
    if other_rows:
        fmt_norm = [row for row in other_rows if row["note"].startswith("format normalization")]
        lines.append(
            f"- **Non-image rows ({len(other_rows)} cross-checked, {len(fmt_norm)} of them "
            f"format-normalization-only): {other_client} CLIENT-SIDE, {other_proxy} PROXY-SIDE.** "
            + (
                "ALL are PROXY-SIDE — the original payload is byte-identical prev->curr at this index "
                "while forwarded differs. Where the note is \"format normalization only\", the identical "
                "original text is our own cache_control-stripping / message-shape normalization "
                "collapsing a single-text-block list to a bare string during forwarding — a benign proxy "
                "transform, unrelated to images and not a factor in the CR/CC collapse (single-digit char "
                "magnitude, see per-pair tables)."
                if other_client == 0 and other_proxy == len(other_rows)
                else "Mixed — see per-pair verdicts above, do not generalize a single verdict."
            )
        )
    return lines

def _build_recoveries_lines(recoveries):
    lines = []
    for rp, rc, holds in recoveries:
        lines.append(
            f"- REQ#{rp}->REQ#{rc}: recovery identity CR[curr]==CR[prev]+CC[prev] "
            f"{'HOLDS' if holds else 'does NOT hold'} (checked from ground-truth CR/CC directly)."
        )
    return lines

def _build_interpretation_lines():
    return [
        "",
        "### Interpretation / hypotheses (not provable from bytes alone)",
        "",
        "- The BP1 cross-session hypothesis (CR=21,023 == cached read of `system[0:2]`) is only "
        "PARTIALLY supported: tiktoken (cl100k_base, an approximation of Claude's real tokenizer) "
        "estimates `system[0:3]` at roughly two-thirds of 21,023 tokens — same order of magnitude, "
        "consistent with cl100k's known undercount on structured content, but not an exact match. "
        "Confirming the exact BP1 byte-identity against another project's session log was out of "
        "scope of the provided data (only this session's logs were read).",
        "- When the recovery identity does NOT hold for a pair where messages are byte-identical up "
        "to some index, cache non-availability is consistent with Anthropic-side cache-write "
        "propagation latency (a large `CC` write may not be immediately readable moments later) — "
        "this is a plausible explanation for requests spaced tens of seconds apart, not something "
        "provable from the sent bytes.",
        "- WHERE the eviction happens (client vs proxy) is settled by the original-vs-forwarded "
        "cross-check above where available. WHY it triggers on this specific turn (a deliberate "
        "size/token-budget threshold vs. some other condition) is not determinable from these logs "
        "alone — only the byte-level EFFECT and its origin side are proven.",
        "",
    ]

def build_findings_summary(pair_results):
    any_img, sys123_stable, tools_stable, recoveries = _proven_from_bytes_flags(pair_results)

    lines = [
        "## Findings Summary",
        "",
        "### Proven from bytes",
        "",
    ]
    lines.extend(_build_proven_from_bytes_lines(any_img, sys123_stable, tools_stable))

    all_orig_rows = _gather_original_attribution_rows(pair_results)
    lines.extend(_build_original_attribution_summary_lines(all_orig_rows, pair_results))
    lines.extend(_build_recoveries_lines(recoveries))
    lines.extend(_build_interpretation_lines())
    return lines
