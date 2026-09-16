# INFRASTRUCTURE
import json
import re
from pathlib import Path

from green_overlay_probe_diff import _get_text, _strip_cache_control, _normalize_msg_shape, _fn_for_inject

_AREA_ROOT = Path(__file__).resolve().parent
while _AREA_ROOT.name != 'proxy_dual_log':
    _AREA_ROOT = _AREA_ROOT.parent
_PROJECT_ROOT = _AREA_ROOT.parent.parent


def _main_checkout_root(project_root: Path) -> Path:
    parts = project_root.parts
    if len(parts) >= 3 and parts[-3] == '.claude' and parts[-2] == 'worktrees':
        return Path(*parts[:-3])
    return project_root


_log_from_main = (_PROJECT_ROOT / "src" / "logs" / "dual_log").resolve()
_log_from_wt   = (_main_checkout_root(_PROJECT_ROOT) / "src" / "logs" / "dual_log").resolve()
LOG_DIR  = _log_from_main if _log_from_main.exists() else _log_from_wt

# FUNCTIONS

def scan_gating_soundness() -> dict:
    _phantom_re = re.compile(r'\\n\\n[",}\]]')
    inj_logs = sorted(LOG_DIR.glob("*_injected.jsonl"))
    counts = {"phantom_like": 0, "real_like": 0, "bg_done": 0}
    real_examples = []
    for logf in inj_logs:
        with open(logf) as f:
            for line in f:
                entry = json.loads(line)
                fn_map = entry.get("fn_map", {})
                for lk, fn in fn_map.items():
                    if not lk.startswith("msg."):
                        continue
                    if fn == "_apply_bg_exit_strip":
                        counts["bg_done"] += 1
                        continue
                    if fn != "unknown":
                        continue
                    midx, bidx = lk.split(".")[1], lk.split(".")[2]
                    md = entry.get("messages_delta", {})
                    i_spans = md.get(midx, {}).get(bidx, [])
                    i_text = " ".join(t for tag, t in i_spans if tag == "injected" and t) if i_spans else ""
                    if _phantom_re.search(i_text) or (len(i_text) > 5 and i_text.strip().endswith('}')):
                        counts["phantom_like"] += 1
                    else:
                        counts["real_like"] += 1
                        if len(real_examples) < 5:
                            real_examples.append((lk, repr(i_text[:80])))
    counts["real_examples"] = real_examples
    return counts


def load_entry_by_flow_id(path: Path, flow_id: str) -> dict:
    with open(path) as f:
        for line in f:
            e = json.loads(line)
            if e.get("flow_id") == flow_id:
                return e
    return {}


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


def _get_msg_blk_texts(stem: str, fid: str, midx: int, bidx: int):
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


def get_regression_cases() -> list:
    stem  = "api_requests_worker_25c51a2e_badge-recap_1780678180"
    cases = []

    with open(LOG_DIR / f"{stem}_stripped.jsonl") as f:
        slines = f.readlines()
    fid_r1 = json.loads(slines[3])["flow_id"]
    o1, f1 = _get_msg_blk_texts(stem, fid_r1, 2, 0)
    if o1 and f1 and o1 != f1:
        cases.append(("R1: msg[2] blk[0] partial replace (ratio=0.76)", o1, f1))

    fid_r2 = json.loads(slines[4])["flow_id"]
    o2, f2 = _get_msg_blk_texts(stem, fid_r2, 4, 0)
    if o2 and f2 and o2 != f2:
        cases.append(("R2: msg[4] blk[0] tiny edit large block (ratio=0.99)", o2, f2))

    fid_r3 = json.loads(slines[21])["flow_id"]
    o3, f3 = _get_msg_blk_texts(stem, fid_r3, 38, 0)
    if o3 and f3 and o3 != f3:
        cases.append(("R3: msg[38] blk[0] system-reminder strip (ratio=0.95)", o3, f3))

    o_ws = 'key1:  value1\n\nkey2:\tvalue2\nkey3:   value3'
    f_ws = 'key1:  value1\n\nkey2:\tvalue2_changed\nkey3:   value3'
    cases.append(("R4: synthetic multi-space/tab whitespace-collapse test", o_ws, f_ws))

    return cases
