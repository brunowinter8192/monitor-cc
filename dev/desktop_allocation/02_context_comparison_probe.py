# INFRASTRUCTURE
import argparse
import os
import sys

from probe02_bridge import _CG
from probe02_diagnostics import _collect_context_diagnostics, _collect_tcc_state
from probe02_pipeline import _build_space_map, _collect_detection_result, _collect_raw_windows, _ghostty_pid
from probe02_report import _write_report


# ORCHESTRATOR

def probe_workflow() -> None:
    ap = argparse.ArgumentParser(description='TCC context comparison probe — Monitor_CC Etappe 2')
    ap.add_argument('--tag', choices=['ccbash', 'launchd', 'bundle'], required=True)
    args = ap.parse_args()
    print_probe_tag(args)
    cid          = _CG.CGSMainConnectionID()
    ctx          = _collect_context_diagnostics()
    tcc          = _collect_tcc_state()
    smap, active = _build_space_map(cid)
    ghostty_pid  = _ghostty_pid()
    raw          = _collect_raw_windows(cid)
    det          = _collect_detection_result(cid, raw, ghostty_pid, smap, active)
    path         = _write_report(args.tag, ctx, tcc, det, raw)
    print_probe_report(path)


# FUNCTIONS

def print_probe_tag(args):
    print(f'[probe02] tag={args.tag} pid={os.getpid()} exe={sys.executable}', flush=True)


def print_probe_report(path):
    print(f'[probe02] report → {path}', flush=True)


if __name__ == '__main__':
    probe_workflow()
