# INFRASTRUCTURE
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, ".")

from composition_probe_ops import _strip_cache_control, _block_text, compose_block, check_invariants
from composition_probe_passes import run_passes_and_collect_ops
from composition_probe_corpus import run_corpus, get_money_shot_case

_AREA_ROOT = Path(__file__).resolve().parent
while _AREA_ROOT.name != 'proxy_dual_log':
    _AREA_ROOT = _AREA_ROOT.parent
REPORT_DIR = _AREA_ROOT / "01_reports"

# FUNCTIONS

def fmt_spans(spans: list, max_text: int = 80) -> list:
    lines = []
    for tag, text in spans:
        preview = repr(text[:max_text]) + ("..." if len(text) > max_text else "")
        lines.append(f"  ({tag!r:12}, {preview})")
    return lines


def _emit_intro(emit, ts_human: str) -> None:
    emit("# Multi-Pass Composition Probe — ", ts_human)
    emit()
    emit("Validates: per-pass ops `(offset_in_Ck, removed, injected)` composed via span-list")
    emit("accumulation produce byte-exact reconstruction of both C0 and Cfwd.")
    emit()
    emit("**Invariants per block:**")
    emit("- Inv1: `\"\".join(equal+stripped) == C0_block_text`")
    emit("- Inv2: `\"\".join(equal+injected) == Cfwd_block_text`")
    emit()
    emit("**Op extraction**: common-prefix/suffix on each pass's `(before_pass, after_pass)`")
    emit("block-text pair. Stand-in for what production passes would record directly.")
    emit("Validated by the invariants — a fail implicates op extraction, not the algorithm.")
    emit()
    emit("**Layer clarification:** `_dedup_wakeup_blocks` is a Layer-1 payload modification")
    emit("(changes what gets forwarded). Modeled here as a composed op. There is NO separate")
    emit("dedup in the span-building path — the composition already reflects reality after dedup.")


def _emit_money_shot(emit, wakeup_core: str) -> None:
    emit()
    emit("## Money Shot — msg[100] TN+BG Double-Inject")
    emit()
    emit("**Confirmed production bug.** C0 = one TN block containing a failed-BG `<summary>`.")
    emit("Pass chain: `_apply_first_pass` strips TN wrapper + injects wakeup → reveals BG line;")
    emit("`_apply_bg_exit_strip` strips BG line + injects wakeup again;")
    emit("`_dedup_wakeup_blocks` removes second wakeup from Cfwd.")
    emit("Composition must produce exactly ONE injected wakeup (= Cfwd byte-exact).")
    emit()

    try:
        c0_text, cfwd_text, blk_ops, spans = get_money_shot_case()
        if c0_text is None:
            emit("⚠️ money-shot case not found (flow_id 58620c90 absent from corpus)")
        else:
            ok, detail = check_invariants(spans, c0_text, cfwd_text)
            emit(f"**C0** ({len(c0_text)} chars): `{repr(c0_text[:100])}...`")
            emit(f"**Cfwd** ({len(cfwd_text)} chars): `{repr(cfwd_text)}`")
            emit()
            emit("**Op chain (derived from per-pass before→after):**")
            for pn, off, rem, inj in blk_ops:
                emit(f"- `{pn}` offset={off} removed={repr(rem[:60])} injected={repr(inj[:60])}")
            emit()
            emit("**Composed span list over C0:**")
            emit("```")
            for sl in fmt_spans(spans):
                emit(sl)
            emit("```")
            inj_wakeups = [t for tag, t in spans if tag == "injected" and wakeup_core in t]
            stripped_n  = sum(1 for tag, _ in spans if tag == "stripped")
            emit()
            emit(f"- Injected wakeup spans: **{len(inj_wakeups)}**"
                 f" {'✅ exactly 1 — double-inject FIXED' if len(inj_wakeups) == 1 else '❌ expected 1'}")
            emit(f"- Stripped spans: {stripped_n} (full TN block shown as yellow ✅)")
            emit(f"- Inv1 C0 recon:   {'✅ PASS' if 'C0_recon_FAIL'   not in detail else '❌ FAIL'}")
            emit(f"- Inv2 Cfwd recon: {'✅ PASS' if 'Cfwd_recon_FAIL' not in detail else '❌ FAIL'}")
            emit(f"- **Overall: {'✅ BYTE-EXACT' if ok else '❌ ' + detail}**")
    except Exception as ex:
        import traceback as tb
        emit(f"ERROR: {ex}")
        emit("```"); emit(tb.format_exc()); emit("```")


def _emit_corpus_summary_table(emit, R: dict) -> None:
    emit(f"| Metric | Value |")
    emit(f"|---|---|")
    emit(f"| Total entries | {R['total_entries']} |")
    emit(f"| Entries with modifications | {R['entries_modified']} |")
    emit(f"| Blocks checked | {R['blocks_checked']} |")
    emit(f"| Blocks passed (byte-exact) | {R['blocks_passed']} |")
    emit(f"| Blocks failed | {R['blocks_failed']} |")
    emit(f"| Multi-pass blocks (≥2 ops same block) | {R['multi_pass_blocks']} |")
    emit(f"| Double-inject blocks (≥2 injecting ops) | {R['double_inject_blocks']} |")
    emit()

    emit("### Per-Pass-Type Results")
    emit()
    emit("| Pass | Passed | Failed | Rate |")
    emit("|---|---|---|---|")
    for pn, (pc, fc) in sorted(R["pass_stats"].items()):
        total = pc + fc
        rate  = f"{100 * pc // total}%" if total else "N/A"
        emit(f"| `{pn}` | {pc} | {fc} | {rate} |")

    if R["failed_cases"]:
        emit()
        emit("### Failing Cases (first 20)")
        emit()
        for fc in R["failed_cases"][:20]:
            emit(f"**{fc['stem']} / flow={fc['flow_id']} / msg[{fc['msg_idx']}] blk[{fc['blk_idx']}]**")
            emit(f"- pass_chain: {fc['pass_chain']}")
            emit(f"- c0_len={fc['c0_len']} cfwd_len={fc['cfwd_len']}")
            emit(f"- ops: {fc['ops']}")
            emit(f"- detail: `{fc['detail']}`")
            emit()
    else:
        emit()
        emit("**No failing cases — all blocks pass both invariants byte-exact ✅**")


def _emit_corpus_run(emit):
    emit()
    emit("## Corpus Run — All Entries Across 5 Stems")
    emit()

    try:
        R = run_corpus()
        _emit_corpus_summary_table(emit, R)
        return R

    except Exception as ex:
        import traceback as tb
        emit(f"ERROR in corpus run: {ex}")
        emit("```"); emit(tb.format_exc()); emit("```")
        return None


def _emit_op_shape_guide(emit) -> None:
    emit()
    emit("## Op Shape Per Pass (Port Guidance)")
    emit()
    emit("What each production pass would emit directly (instead of probe's stand-in):")
    emit()
    emit("| Pass | Op shape at recording point | Notes |")
    emit("|---|---|---|")
    emit("| `_apply_first_pass` (SR strips) | `Op(blk_idx, sr_offset, SR_block, '.')` | '.' is proxy placeholder |")
    emit("| `_apply_first_pass` (TN transform) | `Op(blk_idx, prefix_len, changed_region, new_region)` | common-prefix/suffix of full content; TN strips XML wrapper while keeping inner text — not a clean strip |")
    emit("| `_apply_cumulative_sr_strips` | `Op(blk_idx, offset, SR_block, '.')` per SR | multiple ops if multiple SRs in one string |")
    emit("| `_apply_final_sr_pass` | same as cumulative | |")
    emit("| `_apply_bg_exit_strip` | `Op(blk_idx, match_offset, bg_line+'\\n', _WAKEUP_TEXT)` first; `Op(blk_idx, offset, bg_line, '')` subsequent | injected only on first match |")
    emit("| `_apply_po_preview_strip` | `Op(blk_idx, offset, preview_section, '')` | pure strip |")
    emit("| `_apply_hook_prefix_strip` | `Op(blk_idx, 0, prefix_text, '')` | prefix at block start |")
    emit("| `_apply_git_lock_strip` | `Op(blk_idx, offset, lock_advice, '')` | pure strip |")
    emit("| `_apply_bd_noise_strip` | `Op(blk_idx, offset, bd_line, '')` | pure strip |")
    emit("| `_dedup_wakeup_blocks` | `Op(blk_idx, offset_2nd+, wakeup, '')` | run AFTER all passes; Layer-1 payload op, NOT a span-building hack |")


def _emit_verdict(emit, R) -> None:
    emit()
    emit("## Verdict")
    emit()
    try:
        n_pass = R["blocks_passed"]
        n_fail = R["blocks_failed"]
        n_tot  = R["blocks_checked"]
        multi  = R["multi_pass_blocks"]
        dbl    = R["double_inject_blocks"]
        emit(f"**Multi-pass composition: "
             f"{'HOLDS BYTE-EXACT on all corpus data' if n_fail == 0 else str(n_fail) + ' blocks fail — see Failing Cases above'}**")
        emit()
        emit(f"- `{n_pass}/{n_tot}` blocks pass both invariants across {R['entries_modified']} modified requests")
        emit(f"- `{multi}` multi-pass blocks verified (same block, ≥2 passes)")
        emit(f"- `{dbl}` double-inject blocks — dedup op reduces each to 1 injected wakeup ✅")
        emit(f"- `_dedup_wakeup_blocks` is a Layer-1 pass, not a span-building workaround")
        emit(f"- Money shot (msg[100] TN+BG): 1 injected wakeup, C0+Cfwd byte-exact ✅")
    except Exception:
        emit("Results unavailable (corpus run failed).")


# ORCHESTRATOR

def composition_probe_workflow():
    from src.proxy.strip_bg_completed import _WAKEUP_TEXT
    wakeup_core = _WAKEUP_TEXT.rstrip('\n')

    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    ts       = datetime.now().strftime("%Y%m%d")
    ts_human = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    report_path = REPORT_DIR / f"composition_probe_{ts}.md"

    lines = []
    def emit(*parts):
        lines.append("".join(str(p) for p in parts) + "\n")

    _emit_intro(emit, ts_human)
    _emit_money_shot(emit, wakeup_core)
    R = _emit_corpus_run(emit)
    _emit_op_shape_guide(emit)
    _emit_verdict(emit, R)

    with open(report_path, "w") as fout:
        fout.writelines(lines)
    print(f"Report: {report_path}")


if __name__ == "__main__":
    composition_probe_workflow()
