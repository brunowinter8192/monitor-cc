# INFRASTRUCTURE
import glob
import json
import os

_STRIP_MOD_MARKER   = "stripped_hook_error_prefix"


# FUNCTIONS

# Scan available proxy logs for stripped_hook_error_prefix; return cross-check result dict
def run_cross_check(buckets: dict, logs_dir: str) -> dict:
    proxy_files = sorted(glob.glob(os.path.join(logs_dir, "api_requests_*.jsonl")))
    first_strip_ts, strip_request_count, strip_item_count = _scan_proxy_logs_for_strip(proxy_files)
    hp_stats = _hook_prefixed_stats(buckets, logs_dir, first_strip_ts)

    return {
        "proxy_files_total":      len(proxy_files),
        "first_strip_ts":         first_strip_ts,
        "strip_request_count":    strip_request_count,
        "strip_item_count":       strip_item_count,
        **hp_stats,
    }


# Find first occurrence of stripped_hook_error_prefix across all available proxy logs
def _scan_proxy_logs_for_strip(proxy_files: list) -> tuple:
    first_strip_ts = None
    strip_request_count  = 0  # unique requests with this modification
    strip_item_count     = 0  # total modification items (one request can strip N messages)
    for pf in proxy_files:
        try:
            with open(pf, encoding="utf-8") as fh:
                for line in fh:
                    if _STRIP_MOD_MARKER not in line:
                        continue
                    entry = json.loads(line)
                    if entry.get("type") == "latency_update":
                        continue
                    mods  = entry.get("modifications", [])
                    items = sum(1 for m in mods if m == _STRIP_MOD_MARKER)
                    if items:
                        strip_request_count += 1
                        strip_item_count    += items
                        ts = entry.get("timestamp", "")
                        if ts and (first_strip_ts is None or ts < first_strip_ts):
                            first_strip_ts = ts
        except (json.JSONDecodeError, OSError):
            pass
    return first_strip_ts, strip_request_count, strip_item_count


# Hook-prefixed entries: timestamp range + referenced proxy files
def _hook_prefixed_stats(buckets: dict, logs_dir: str, first_strip_ts) -> dict:
    hp_entries = buckets.get("hook_prefixed", [])
    hp_ts = sorted(e["ts"] for e in hp_entries)
    hp_proxy_files = set(e.get("proxy_file", "") for e in hp_entries)
    hp_proxy_missing = [pf for pf in hp_proxy_files if pf and not os.path.exists(os.path.join(logs_dir, pf))]
    hp_proxy_present = [pf for pf in hp_proxy_files if pf and os.path.exists(os.path.join(logs_dir, pf))]

    # Determine if all 59 hook_prefixed entries predate the first strip
    all_hp_predate_strip = False
    if hp_ts and first_strip_ts:
        all_hp_predate_strip = hp_ts[-1] < first_strip_ts

    return {
        "hp_ts_earliest":         hp_ts[0]  if hp_ts else None,
        "hp_ts_latest":           hp_ts[-1] if hp_ts else None,
        "hp_proxy_files":         sorted(hp_proxy_files - {""}),
        "hp_proxy_missing":       sorted(hp_proxy_missing),
        "hp_proxy_present":       sorted(hp_proxy_present),
        "all_hp_predate_strip":   all_hp_predate_strip,
    }
