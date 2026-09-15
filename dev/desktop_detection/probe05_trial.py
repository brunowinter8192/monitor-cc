# INFRASTRUCTURE
import json
import secrets
import time
from pathlib import Path
from typing import Dict, List, Tuple

from probe05_bridge import _CG
from probe05_detection import _OWNER, _REQUIRE_NAME, _TOKEN_PREFIX, _WIN_COT, _method_a, _method_b, _on_screen_wids, _owner_pids, _owner_wids_layer0, _spaces_for_wid, _wid_info
from probe05_lifecycle import _cleanup_window, _open_window

_REPORTS_DIR = Path(__file__).parent / "05_reports"

# FUNCTIONS

def _setup_trial(win_type: str, trial_n: int, foreground: bool):
    owner    = _OWNER[win_type]
    req_name = _REQUIRE_NAME[win_type]
    token    = _TOKEN_PREFIX[win_type] + secrets.token_hex(3)
    # CotEditor always opened with 'open -g' (no cold-launch, no focus steal)
    if win_type == _WIN_COT:
        foreground = False
    fg_label = "fg" if foreground else "bg"

    print(f"  [{win_type} trial {trial_n} {fg_label}] token={token}", flush=True)
    return owner, req_name, token, foreground

def _snapshot_before_open(cid: int, owner: str, win_type: str, req_name: bool, space_map: Dict):
    # S1: active space snapshotted STRICTLY before open
    s1_space_id = int(_CG.CGSGetActiveSpace(cid))
    s1_desktop  = space_map.get(s1_space_id, ("?", "?"))[1]

    pids_before = _owner_pids(owner)
    # Ghostty: snapshot before open (CotEditor uses token-name poll instead)
    before = None
    if win_type != _WIN_COT:
        before = _owner_wids_layer0(owner, req_name)

    return s1_space_id, s1_desktop, pids_before, before

def _poll_for_new_window(win_type: str, owner: str, req_name: bool, token: str, before):
    wid_gt     = None
    ma_wid     = None
    ma_name    = None
    ma_agrees  = None
    poll_start = time.monotonic()

    if win_type == _WIN_COT:
        # Token-name poll: CotEditor titles windows with filename — reliable unique key.
        # Avoids snapshot-diff which grabbed session-restored windows (cold-launch issue).
        while time.monotonic() - poll_start < 5.0:
            time.sleep(0.2)
            ma_wid, ma_name = _method_a(owner, token)
            if ma_wid is not None:
                wid_gt    = ma_wid
                ma_agrees = True   # detection IS the token-match; agrees by construction
                break
    else:
        # Ghostty: snapshot-diff poll — detect new WID by owner-list delta
        while time.monotonic() - poll_start < 5.0:
            time.sleep(0.2)
            after = _owner_wids_layer0(owner, req_name)
            delta = after - before
            if delta:
                wid_gt = min(delta)
                break

    poll_elapsed = round(time.monotonic() - poll_start, 2)
    return wid_gt, ma_wid, ma_name, ma_agrees, poll_elapsed

def _measure_signals(
    cid: int, space_map: Dict, win_type: str, owner: str, req_name: bool, token: str,
    wid_gt, s1_space_id, ma_wid, ma_name, ma_agrees,
) -> dict:
    title_observed  = None
    s2_on_screen    = None
    s3_space_id     = None
    s3_desktop      = None
    space_all_agree = None
    mb_wid          = None
    mb_agrees       = None

    if wid_gt is not None:
        time.sleep(0.5)   # let title settle after detection (OSC-2 late-set, tmux title)

        title_observed, _ = _wid_info(wid_gt)

        if win_type != _WIN_COT:
            # For Ghostty: run method_a here (CotEditor: already resolved during poll)
            ma_wid, ma_name = _method_a(owner, token)
            ma_agrees = (ma_wid == wid_gt)

        # Method B — frontmost among owner layer-0 windows
        mb_wid    = _method_b(owner, req_name)
        mb_agrees = (mb_wid == wid_gt)

        # Space signals
        s2_on_screen = wid_gt in _on_screen_wids()
        s3_spaces    = _spaces_for_wid(cid, wid_gt)
        s3_space_id  = s3_spaces[0] if s3_spaces else None
        if s3_space_id is not None:
            s3_desktop = space_map.get(s3_space_id, ("?", "?"))[1]

        s1_s3_agree     = (s1_space_id == s3_space_id) if s3_space_id is not None else False
        space_all_agree = s1_s3_agree and (s2_on_screen is True)

    return {
        "title_observed": title_observed, "ma_wid": ma_wid, "ma_name": ma_name, "ma_agrees": ma_agrees,
        "mb_wid": mb_wid, "mb_agrees": mb_agrees,
        "s2_on_screen": s2_on_screen, "s3_space_id": s3_space_id, "s3_desktop": s3_desktop,
        "space_all_agree": space_all_agree,
    }

def _print_trial_outcome(wid_gt, signals: dict) -> None:
    print(
        f"    gt={wid_gt}  title={repr(signals['title_observed'])}"
        f"  A={'agree' if signals['ma_agrees'] else 'DISAGREE'}"
        f"  B={'agree' if signals['mb_agrees'] else 'DISAGREE'}"
        f"  desktop={signals['s3_desktop']}  space_agree={signals['space_all_agree']}",
        flush=True,
    )

def _assemble_trial_result(
    win_type: str, trial_n: int, foreground: bool, token: str, wid_gt, poll_elapsed,
    s1_space_id, s1_desktop, signals: dict, cleanup_ok: bool,
) -> dict:
    return {
        "type":           win_type,
        "trial":          trial_n,
        "foreground":     foreground,
        "token":          token,
        "gt_wid":         wid_gt,
        "gt_found":       wid_gt is not None,
        "poll_elapsed_s": poll_elapsed,
        "title_observed": signals["title_observed"],
        "method_a": {
            "wid":          signals["ma_wid"],
            "matched_name": signals["ma_name"],
            "agrees":       signals["ma_agrees"],
        },
        "method_b": {
            "wid":    signals["mb_wid"],
            "agrees": signals["mb_agrees"],
        },
        "space": {
            "s1_space_id":  s1_space_id,
            "s1_desktop":   s1_desktop,
            "s2_on_screen": signals["s2_on_screen"],
            "s3_space_id":  signals["s3_space_id"],
            "s3_desktop":   signals["s3_desktop"],
            "all_agree":    signals["space_all_agree"],
        },
        "cleanup_ok": cleanup_ok,
    }

def _write_trial_json(result: dict, win_type: str, trial_n: int, ts: str) -> Path:
    json_path = _REPORTS_DIR / f"trial_{win_type}_{trial_n}_{ts}.json"
    json_path.write_text(json.dumps(result, indent=2), encoding="utf-8")
    return json_path

# Run one trial: open window, detect via ground-truth + methods A/B, measure space signals.
def _run_trial(
    cid: int, space_map: Dict[int, Tuple[str, int]],
    win_type: str, trial_n: int, foreground: bool,
) -> dict:
    ts = time.strftime("%Y%m%d_%H%M%S")
    owner, req_name, token, foreground = _setup_trial(win_type, trial_n, foreground)

    s1_space_id, s1_desktop, pids_before, before = _snapshot_before_open(
        cid, owner, win_type, req_name, space_map)

    _open_window(win_type, token, foreground)

    wid_gt, ma_wid, ma_name, ma_agrees, poll_elapsed = _poll_for_new_window(
        win_type, owner, req_name, token, before)

    signals = _measure_signals(
        cid, space_map, win_type, owner, req_name, token,
        wid_gt, s1_space_id, ma_wid, ma_name, ma_agrees)

    _print_trial_outcome(wid_gt, signals)

    cleanup_ok = _cleanup_window(win_type, token, wid_gt, pids_before)
    time.sleep(1.0)   # stabilize between trials

    result = _assemble_trial_result(
        win_type, trial_n, foreground, token, wid_gt, poll_elapsed,
        s1_space_id, s1_desktop, signals, cleanup_ok)

    json_path = _write_trial_json(result, win_type, trial_n, ts)
    print(f"    -> {json_path.name}", flush=True)

    return result

# Format and print per-trial results as aligned summary table
def _print_summary(results: List[dict]) -> None:
    print("=== Summary Table ===")
    hdr = (
        f"{'type':<16} {'tr':>2} {'fg/bg':>5}  {'gt_wid':>7}"
        f"  {'A_agree':>7}  {'B_agree':>7}  {'desktop':>7}  {'space_agree':>11}"
    )
    print(hdr)
    print("-" * len(hdr))
    for r in results:
        fg_str    = "fg" if r["foreground"] else "bg"
        gt_str    = str(r["gt_wid"]) if r["gt_wid"] is not None else "N/A"
        a_str     = str(r["method_a"]["agrees"])
        b_str     = str(r["method_b"]["agrees"])
        desktop   = r["space"]["s3_desktop"] or r["space"]["s1_desktop"]
        space_str = str(desktop) if desktop is not None else "?"
        sa_str    = str(r["space"]["all_agree"])
        print(
            f"{r['type']:<16} {r['trial']:>2} {fg_str:>5}  {gt_str:>7}"
            f"  {a_str:>7}  {b_str:>7}  {space_str:>7}  {sa_str:>11}"
        )
