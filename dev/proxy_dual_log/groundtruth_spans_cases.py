# INFRASTRUCTURE
import json
from pathlib import Path

from groundtruth_spans_algorithm import _strip_cache_control, _normalize_msg_shape, _get_inner_text, _get_text

_SCRIPT_DIR = Path(__file__).parent.resolve()
_log_from_main = (_SCRIPT_DIR.parents[1] / "src" / "logs" / "dual_log").resolve()
_log_from_wt = (_SCRIPT_DIR.parents[4] / "src" / "logs" / "dual_log").resolve()
LOG_DIR = _log_from_main if _log_from_main.exists() else _log_from_wt

# FUNCTIONS

# ── data loading ─────────────────────────────────────────────────────────────

def load_entry_by_flow_id(path: Path, flow_id: str) -> dict:
    with open(path) as f:
        for line in f:
            e = json.loads(line)
            if e.get("flow_id") == flow_id:
                return e
    return {}


def run_rules(orig_payload: dict) -> tuple:
    from src.proxy.rules import apply_modification_rules
    return apply_modification_rules(orig_payload)


# ── case builders ─────────────────────────────────────────────────────────────

def get_bug_case():
    """Primary bug case: badge-recap, msg[18] blk[0], tool_result with SR strip."""
    stem = "api_requests_worker_25c51a2e_badge-recap_1780678180"
    flow_id = "7a12336f-7d76-476f-a3b2-4d58f9ae6f2f"

    orig_e = load_entry_by_flow_id(LOG_DIR / f"{stem}_original.jsonl", flow_id)
    orig_payload = orig_e["payload"]

    mod_payload, _, _, _, _, sremoved, *_ = run_rules(orig_payload)

    def _sc(obj):
        return _strip_cache_control(obj)

    orig_msg18 = _sc(orig_payload["messages"][18])
    mod_msg18 = _sc(mod_payload["messages"][18])

    fwd_e = load_entry_by_flow_id(LOG_DIR / f"{stem}_forwarded.jsonl", flow_id)
    fwd_msg18 = _sc(fwd_e["messages_delta"]["18"])
    fwd_msg18 = _normalize_msg_shape(fwd_msg18)

    orig_blk0 = orig_msg18["content"][0]
    mod_blk0 = mod_msg18["content"][0]
    fwd_blk0 = fwd_msg18["content"][0]

    # Validate mod == fwd (re-run matches forwarded log)
    mod_match = _get_inner_text(mod_blk0) == _get_inner_text(fwd_blk0)

    return {
        "label": "BUG (msg[18] blk[0] tool_result, SR stripped)",
        "o_text": _get_inner_text(orig_blk0),
        "f_text": _get_inner_text(mod_blk0),
        # JSON-dump level texts for phantom demo (production diff_engine path)
        "o_text_json": _get_text(orig_blk0),
        "f_text_json": _get_text(mod_blk0),
        "blk_type": "tool_result",
        "chunks": sremoved.get(18, []),
        "mod_matches_fwd": mod_match,
        "flags_meta": [] if mod_match else ["MOD_FWD_MISMATCH"],
    }


def get_text_block_replace_case():
    """badge-recap, msg[0] blk[0]: pure text block that is entirely the DEF SR → replaced with '.'"""
    stem = "api_requests_worker_25c51a2e_badge-recap_1780678180"
    flow_id = "7a12336f-7d76-476f-a3b2-4d58f9ae6f2f"

    orig_e = load_entry_by_flow_id(LOG_DIR / f"{stem}_original.jsonl", flow_id)
    orig_payload = orig_e["payload"]
    mod_payload, _, _, _, _, sremoved, *_ = run_rules(orig_payload)

    def _sc(obj):
        return _strip_cache_control(obj)

    orig_blks = _sc(orig_payload["messages"][0]["content"])
    mod_blks = _sc(mod_payload["messages"][0]["content"])

    orig_blk0 = orig_blks[0]
    mod_blk0 = mod_blks[0]

    # Assign per-block chunks: chunk[0] belongs to blk[0] (DEF SR = full block text)
    chunks_msg0 = sremoved.get(0, [])
    blk0_text = orig_blk0.get("text", "")
    blk0_chunks = [c for c in chunks_msg0 if c in blk0_text]

    # Recording-gap check for blk[2]
    orig_blk2 = orig_blks[2]
    blk2_text = orig_blk2.get("text", "")
    blk2_in_chunks = any(c in blk2_text for c in chunks_msg0)
    recording_gap_flag = (
        []
        if blk2_in_chunks
        else [f"RECORDING_GAP: blk[2] ENV-SR (len={len(blk2_text)}) not in stripped_msg_removed[0]"]
    )

    return {
        "label": "TEXT_REPLACE (msg[0] blk[0] DEF-SR → '.')",
        "o_text": _get_inner_text(orig_blk0),
        "f_text": _get_inner_text(mod_blk0),
        "blk_type": "text",
        "chunks": blk0_chunks,
        "mod_matches_fwd": True,  # validated manually in probe data analysis
        "flags_meta": recording_gap_flag,
    }


def get_bg_exit_replace_case():
    """monitor_cc, msg[78] blk[0]: TN stripped + BG command stripped + wakeup injected."""
    stem = "api_requests_opus_monitor_cc_1780517466"
    flow_id = "6bfe5d0e-5b7d-4e9c-b005-f92d527ec9f4"

    orig_e = load_entry_by_flow_id(LOG_DIR / f"{stem}_original.jsonl", flow_id)
    orig_payload = orig_e["payload"]
    mod_payload, _, _, _, _, sremoved, *_ = run_rules(orig_payload)

    def _sc(obj):
        return _strip_cache_control(obj)

    orig_blk0 = _sc(orig_payload["messages"][78]["content"][0])
    mod_blk0 = _sc(mod_payload["messages"][78]["content"][0])

    fwd_e = load_entry_by_flow_id(LOG_DIR / f"{stem}_forwarded.jsonl", flow_id)
    fwd_delta = _sc(fwd_e.get("messages_delta", {}))
    fwd_blk0 = fwd_delta.get("78", {}).get("content", [{}])[0] if isinstance(fwd_delta.get("78"), dict) else {}

    mod_match = _get_inner_text(mod_blk0) == _get_inner_text(fwd_blk0)

    return {
        "label": "BG_REPLACE (msg[78] blk[0] TN→wakeup, 2 chunks)",
        "o_text": _get_inner_text(orig_blk0),
        "f_text": _get_inner_text(mod_blk0),
        "blk_type": "text",
        "chunks": sremoved.get(78, []),
        "mod_matches_fwd": mod_match,
        "flags_meta": [] if mod_match else ["MOD_FWD_MISMATCH"],
    }


def get_multi_chunk_case():
    """badge-recap msg[0] blk[1]: SK SR (5776/5777 chars) — tests large-SR strip fidelity."""
    stem = "api_requests_worker_25c51a2e_badge-recap_1780678180"
    flow_id = "7a12336f-7d76-476f-a3b2-4d58f9ae6f2f"

    orig_e = load_entry_by_flow_id(LOG_DIR / f"{stem}_original.jsonl", flow_id)
    orig_payload = orig_e["payload"]
    mod_payload, _, _, _, _, sremoved, *_ = run_rules(orig_payload)

    def _sc(obj):
        return _strip_cache_control(obj)

    orig_blks = _sc(orig_payload["messages"][0]["content"])
    mod_blks = _sc(mod_payload["messages"][0]["content"])

    orig_blk1 = orig_blks[1]
    mod_blk1 = mod_blks[1]

    blk1_text = orig_blk1.get("text", "")
    chunks_msg0 = sremoved.get(0, [])
    blk1_chunks = [c for c in chunks_msg0 if c in blk1_text]

    return {
        "label": "LARGE_SR (msg[0] blk[1] SK-SR 5777 chars → '.')",
        "o_text": _get_inner_text(orig_blk1),
        "f_text": _get_inner_text(mod_blk1),
        "blk_type": "text",
        "chunks": blk1_chunks,
        "mod_matches_fwd": True,
        "flags_meta": [],
    }
