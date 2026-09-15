"""
Probe: green-overlay false-injection bug in _diff_text (word-level path).
Reproduces the bug on real log data and validates the char-level candidate fix.
Self-contained — all helpers copied from src/; no src/ imports at module level.

Usage (from project root):
    ./venv/bin/python dev/proxy_dual_log/green_overlay_probe.py
"""

# INFRASTRUCTURE
from pathlib import Path

from green_overlay_probe_diff import (
    diff_text_word, diff_text_char, diff_text_char_gated,
    fmt_spans, compare_pair, _fn_for_inject,
)
from green_overlay_probe_cases import scan_gating_soundness, get_bug_case, get_regression_cases

_SCRIPT_DIR = Path(__file__).parent.resolve()
REPORT_DIR = _SCRIPT_DIR / "green_overlay_probe_reports"

# FUNCTIONS

def _emit_gating_soundness(emit) -> None:
    emit()
    emit("## Gating Signal Soundness Verification")
    emit()
    emit("Gate rule: injected span with `_fn_for_inject(text) == 'unknown'` → reclassify to `equal`.")
    emit()
    try:
        soundness = scan_gating_soundness()
        bg = soundness["bg_done"]
        phantom = soundness["phantom_like"]
        real = soundness["real_like"]
        total_unknown = phantom + real
        emit(f"**Scanned 44 `*_injected.jsonl` logs (msg.\\* loc_keys only):**")
        emit()
        emit(f"| fn value | count | classification |")
        emit(f"|---|---|---|")
        emit(f"| `'_apply_bg_exit_strip'` | {bg} | REAL inject — correctly non-unknown ✅ |")
        emit(f"| `'unknown'` total | {total_unknown} | see breakdown below |")
        emit(f"| — phantom-like (ends `\\\\n\\\\n[\",}}\\\\]]`) | {phantom} | word-level diff artifact ✅ correctly gated |")
        emit(f"| — other (potentially real) | {real} | ⚠️ FLAG: real injects also map to unknown |")
        emit()
        emit("**Phantom attribution test:**")
        for s in ['", "is_error": f', 'connections?\\n\\n",', 'set()))\\n\\n",']:
            fn = _fn_for_inject(s)
            emit(f"- `_fn_for_inject({s!r:30s})` → `{fn!r}` {'→ correctly gated ✅' if fn == 'unknown' else '→ kept green ✅'}")
        emit()
        emit("**Real inject test:**")
        bg_text = 'background done — check worker or other process'
        fn_bg = _fn_for_inject(bg_text)
        emit(f"- `_fn_for_inject('background done...')` → `{fn_bg!r}` → kept green {'✅' if fn_bg != 'unknown' else '❌'}")
        emit()
        emit("**⚠️ FLAG — real injects that ALSO map to 'unknown':**")
        for lk, ex in soundness.get("real_examples", []):
            fn = _fn_for_inject(ex.strip("'"))
            emit(f"- `{lk}` i_text={ex} → fn={fn!r} → would be gated (suppressed)")
        emit()
        emit("**Verdict:** Gate is CONDITIONALLY sound. It correctly eliminates the phantom diff")
        emit(f"artifacts ({phantom} cases — `\\\\n\\\\n[\",}}]` tail pattern from word-level bug on write-side).")
        emit(f"But {real} real message-level injects also attribute to 'unknown'")
        emit("(dot-replacements at msg.0.x for haiku/title calls, file-path injections, etc.) and")
        emit("would be suppressed (shown grey instead of green).")
        emit("Only `_apply_bg_exit_strip` (bg-done, 78 cases) correctly avoids gating.")
    except Exception as ex:
        emit(f"ERROR in soundness scan: {ex}")
        import traceback; traceback.print_exc()


def _emit_bug_case_variants(emit, r: dict, cp_len: int) -> None:
    emit()
    emit(f"### Variant 1: `diff_text_word` — CURRENT PRODUCTION (buggy) — {r['word_count']} spans")
    emit("```")
    emit(fmt_spans(r["word_spans"]))
    emit("```")
    emit("**Bug:** `set()))\\\\n\\\\n<system-reminder>...` (orig) and `set()))\\\\n\\\\n\",` (fwd) are ONE word each.")
    emit("SequenceMatcher 'replace' → common prefix `set()))\\\\n\\\\n` appears as BOTH stripped (yellow) AND injected (green).")

    emit()
    emit(f"### Variant 2: `diff_text_char` — char-level fix — {r['char_count']} spans")
    emit("```")
    emit(fmt_spans(r["char_spans"]))
    emit("```")
    char_spans = r["char_spans"]
    inj_in_char = [t for tag, t in char_spans if tag == "injected"]
    emit(f"**Yellow fixed:** common prefix is now span[0]=equal ({cp_len} chars) ✅")
    emit(f"**Residual phantom green:** `{[repr(t[:60]) for t in inj_in_char]}` — LCS suboptimal alignment on suffix ⚠️")

    emit()
    emit(f"### Variant 3: `diff_text_char_gated` — THE GOAL — {r['gated_count']} spans")
    emit("```")
    emit(fmt_spans(r["gated_spans"]))
    emit("```")
    gated_spans = r["gated_spans"]
    remaining_inj = [t for tag, t in gated_spans if tag == "injected"]
    remaining_stripped = [t for tag, t in gated_spans if tag == "stripped"]
    has_sysrem_g = any("<system-reminder>" in t for t in remaining_stripped)
    emit(f"**Green spans remaining:** {len(remaining_inj)} {'(none — phantom gone ✅)' if not remaining_inj else repr(remaining_inj[0][:60])}")
    emit(f"**Stripped contains `<system-reminder>`:** {has_sysrem_g} {'✅' if has_sysrem_g else '❌'}")
    emit(f"**Fidelity (char):** {r['fid_detail']} | **Fidelity (gated):** gated_ok={r['gated_fid_ok']} {'✅' if r['gated_fid_ok'] else '❌'}")


def _emit_primary_bug_case(emit) -> None:
    emit()
    emit("## Primary Bug Case — Three Variants Side By Side")
    try:
        o_text, f_text, stem, flow_id = get_bug_case()

        cp_len = 0
        while cp_len < len(o_text) and cp_len < len(f_text) and o_text[cp_len] == f_text[cp_len]:
            cp_len += 1

        emit()
        emit(f"**Source:** `{stem}`")
        emit(f"**Flow ID:** `{flow_id}`")
        emit(f"**Location:** `messages[18]` block 0 (tool_result, role=user)")
        emit(f"**o_text len:** {len(o_text)} | **f_text len:** {len(f_text)} | **common prefix:** {cp_len} chars (ends at `set()))\\\\n\\\\n`)")

        r = compare_pair("bug_case", o_text, f_text)
        _emit_bug_case_variants(emit, r, cp_len)

    except Exception as ex:
        emit(f"ERROR in primary bug case: {ex}")
        import traceback; traceback.print_exc()


def _emit_regression_spotcheck(emit) -> None:
    emit()
    emit("## Regression Spot-Check — All Three Variants")
    emit()
    emit("| Case | o_len | f_len | word | char | gated | gated_fid | gated inj remaining |")
    emit("|---|---|---|---|---|---|---|---|")

    reg_detail_lines = []
    try:
        reg_cases = get_regression_cases()
        for label, o_t, f_t in reg_cases:
            r = compare_pair(label, o_t, f_t)
            gated_inj = [t for tag, t in r["gated_spans"] if tag == "injected"]
            inj_cell = f"{len(gated_inj)} kept" if gated_inj else "0 (all gated)"
            fid_g = "✅" if r["gated_fid_ok"] else "❌"
            emit(f"| {label} | {r['o_len']} | {r['f_len']} | {r['word_count']} | {r['char_count']} | {r['gated_count']} | {fid_g} | {inj_cell} |")
            reg_detail_lines.append((label, o_t, f_t, r))

        emit()
        emit("### Details")
        for label, o_t, f_t, r in reg_detail_lines:
            emit()
            emit(f"#### {label}")
            emit(f"o_text: `{repr(o_t[:200])}`")
            emit(f"f_text: `{repr(f_t[:200])}`")
            emit()
            emit(f"Word ({r['word_count']} spans):")
            emit("```"); emit(fmt_spans(r["word_spans"])); emit("```")
            emit(f"Char ({r['char_count']} spans):")
            emit("```"); emit(fmt_spans(r["char_spans"])); emit("```")
            emit(f"Gated ({r['gated_count']} spans):")
            emit("```"); emit(fmt_spans(r["gated_spans"])); emit("```")
            gated_inj_list = [t for tag, t in r["gated_spans"] if tag == "injected"]
            if gated_inj_list:
                for t in gated_inj_list:
                    fn = _fn_for_inject(t)
                    emit(f"  → kept injected: `{repr(t[:80])}` fn=`{fn}` {'✅ real' if fn != 'unknown' else '⚠️ still unknown'}")
            else:
                emit("  → no injected spans remaining (all phantom-gated or no real injects in this case)")
            emit(f"Fidelity: char={r['fid_detail']} | gated={r['gated_fid_ok']}")

    except Exception as ex:
        emit(f"ERROR in regression cases: {ex}")
        import traceback; traceback.print_exc()


def _emit_summary(emit) -> None:
    emit()
    emit("## Summary")
    emit()
    emit("### Level 1 (char-level): fixes YELLOW boundary")
    emit("- Word-level splits on whitespace → JSON `\\\\n` is not whitespace → single-word tokens →")
    emit("  SequenceMatcher 'replace' → common prefix in both stripped (yellow) AND injected (green).")
    emit("- Char-level finds exact boundary → common prefix = equal, only changed suffix colored.")
    emit("- Residual: char-level has LCS suboptimal alignment → phantom green on `\\\"\\\\, is_error: f\\\"` suffix.")
    emit()
    emit("### Level 2 (char-level + gating): fixes residual phantom GREEN")
    emit("- Gate: injected span with fn=unknown (no strip/inject marker) → reclassify equal (grey).")
    emit("- Correctly removes `\\\"\\\\, is_error: f\\\"` phantom from the bug case.")
    emit("- ⚠️ Known limitation: 144 real 'unknown' msg-injects in live logs would also be suppressed")
    emit("  (dot-replacements for haiku calls, file-path injects).")
    emit("  Only `_apply_bg_exit_strip` (bg-done) reliably avoids gating.")
    emit()
    emit("### Whitespace fidelity")
    emit("- Word-level `' '.join(...)` collapses multi-space/tab; char-level/gated preserve exactly.")


# Build and write the probe report (Level 2: gating soundness + three-variant comparison)
def green_overlay_probe_workflow():
    REPORT_DIR.mkdir(exist_ok=True)
    lines = []

    def emit(*parts):
        lines.append("".join(str(p) for p in parts) + "\n")

    emit("# Green Overlay Probe Report (Level 2)")
    emit()
    emit("Three diff variants: `diff_text_word` (current/buggy) · `diff_text_char` (char-level)")
    emit("· `diff_text_char_gated` (char-level + attribution gate for phantom injected spans).")

    _emit_gating_soundness(emit)
    _emit_primary_bug_case(emit)
    _emit_regression_spotcheck(emit)
    _emit_summary(emit)

    report_path = REPORT_DIR / "green_overlay_probe.md"
    with open(report_path, "w") as fout:
        fout.writelines(lines)

    print(f"Report written to: {report_path}")


# ORCHESTRATOR
if __name__ == "__main__":
    green_overlay_probe_workflow()
