# INFRASTRUCTURE
import argparse
import os
import sys
from datetime import datetime
from typing import Dict, List

from probe03_bridge import _CG
from probe03_diagnostics import _collect_context_diagnostics, _collect_tcc_state
from probe03_ghostty_detail import _collect_ghostty_as_window_properties, _collect_ghostty_windows_detailed
from probe03_report import _write_report
from probe03_windows import _collect_full_cgwindow_data, _ghostty_pid


# ORCHESTRATOR

def probe_workflow() -> None:
    ap = argparse.ArgumentParser(description='CGWindow field availability probe — Monitor_CC probe03')
    ap.add_argument('--tag', choices=['ccbash', 'launchd', 'bundle'], required=True)
    args = ap.parse_args()
    print_probe_tag(args)

    cid         = _CG.CGSMainConnectionID()
    ctx         = _collect_context_diagnostics()
    tcc         = _collect_tcc_state()
    ghostty_pid = _ghostty_pid()

    all_keys, field_summary, raw_ptr = _collect_full_cgwindow_data(cid, ghostty_pid)

    ghostty_detail = collect_ghostty_detail(cid, ghostty_pid, raw_ptr)

    as_props = _collect_ghostty_as_window_properties()

    payload = {
        'tag':                       args.tag,
        'timestamp':                 datetime.now().isoformat(),
        'context_diagnostics':       ctx,
        'tcc_state':                 tcc,
        'ghostty_pid':               ghostty_pid,
        'all_field_keys_observed':   all_keys,
        'field_availability_summary': field_summary,
        'ghostty_windows_detailed':  ghostty_detail,
        'ghostty_as_window_properties': as_props,
    }

    path = _write_report(payload)
    print_probe_report(path)


# FUNCTIONS

def print_probe_tag(args):
    print(f'[probe03] tag={args.tag} pid={os.getpid()} exe={sys.executable}', flush=True)


def collect_ghostty_detail(cid, ghostty_pid, raw_ptr):
    ghostty_detail: List[Dict] = []
    if ghostty_pid:
        ghostty_detail = _collect_ghostty_windows_detailed(cid, ghostty_pid, raw_ptr)
    return ghostty_detail


def print_probe_report(path):
    print(f'[probe03] report → {path}', flush=True)


if __name__ == '__main__':
    probe_workflow()
