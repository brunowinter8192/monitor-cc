#!/bin/bash

# INFRASTRUCTURE
JANITOR_KEEP=30

# FUNCTIONS
_janitor_cleanup_live_copies() {
    local orphan_count=0 id shim dir_path

    for shim in "$LOG_DIR"/.proxy_addon_live_*.py; do
        [ -f "$shim" ] || continue
        id="${shim##*/.proxy_addon_live_}"
        id="${id%.py}"
        dir_path="$LOG_DIR/.proxy_live_${id}"
        pgrep -f "$shim" >/dev/null 2>&1 && continue
        rm -f "$shim"
        [ -d "$dir_path" ] && rm -rf "$dir_path"
        orphan_count=$((orphan_count + 1))
    done

    for dir_path in "$LOG_DIR"/.proxy_live_*/; do
        [ -d "$dir_path" ] || continue
        id="${dir_path##*/.proxy_live_}"
        id="${id%/}"
        [ -f "$LOG_DIR/.proxy_addon_live_${id}.py" ] && continue
        rm -rf "$dir_path"
        orphan_count=$((orphan_count + 1))
    done

    echo "Janitor: cleaned $orphan_count orphan live-copies"
}

_janitor_cleanup_jsonl_logs() {
    local rotated_dual=0 surviving_ids
    local DUAL_LOG_DIR="$LOG_DIR/dual_log"

    if [ -d "$DUAL_LOG_DIR" ]; then
        _janitor_version_purge_jsonl_logs
        rotated_dual=$((rotated_dual + $(_rotate_original_logs opus)))
        rotated_dual=$((rotated_dual + $(_rotate_original_logs worker)))
        surviving_ids="$(_surviving_log_ids)"
        rotated_dual=$((rotated_dual + $(_delete_unlisted_dual_logs "$surviving_ids")))
    fi

    _remove_legacy_logs
    echo "Janitor: rotated $rotated_dual dual-log files"
}

_janitor_version_purge_jsonl_logs() {
    local purged_stale=0 current_hash saved_hash f
    local version_marker="$DUAL_LOG_DIR/.proxy_version"
    current_hash="$(_compute_proxy_hash)"
    saved_hash="$(cat "$version_marker" 2>/dev/null)"
    if [ "$current_hash" != "$saved_hash" ]; then
        while IFS= read -r f; do
            rm -f "$f"
            purged_stale=$((purged_stale + 1))
        done < <(find "$DUAL_LOG_DIR" -maxdepth 1 -type f -name "api_requests_*.jsonl" -mmin +60 2>/dev/null)
        echo "$current_hash" > "$version_marker"
        echo "Janitor: version change ($purged_stale stale dual-logs purged)"
    fi
}

_compute_proxy_hash() {
    { cat "$SCRIPT_DIR/proxy_addon.py"
      find "$SCRIPT_DIR/proxy" -type f \( -name '*.py' -o -name '*.json' \) | sort \
          | while IFS= read -r f; do cat "$f"; done
    } | if command -v md5 &>/dev/null; then md5; else md5sum | head -c 32; fi
}

_rotate_original_logs() {
    local kind="$1" f count=0
    while IFS= read -r f; do
        [ -f "$f" ] || continue
        rm -f "$f"
        count=$((count + 1))
    done < <(ls -t "$DUAL_LOG_DIR"/api_requests_${kind}_*_original.jsonl 2>/dev/null | tail -n +$((JANITOR_KEEP + 1)))
    echo "$count"
}

_surviving_log_ids() {
    local f stem
    for f in "$DUAL_LOG_DIR"/api_requests_opus_*_original.jsonl \
             "$DUAL_LOG_DIR"/api_requests_worker_*_original.jsonl; do
        [ -f "$f" ] || continue
        stem="$(basename "$f" .jsonl)"
        stem="${stem#api_requests_}"
        echo "${stem%_original}"
    done
}

_delete_unlisted_dual_logs() {
    local surviving_ids="$1" f stem log_id sfx count=0
    for f in "$DUAL_LOG_DIR"/api_requests_*.jsonl; do
        [ -f "$f" ] || continue
        stem="$(basename "$f" .jsonl)"
        stem="${stem#api_requests_}"
        for sfx in original forwarded stripped injected errors response; do stem="${stem%_$sfx}"; done
        log_id="$stem"
        if ! echo "$surviving_ids" | grep -qxF "$log_id"; then
            rm -f "$f"
            count=$((count + 1))
        fi
    done
    echo "$count"
}

_remove_legacy_logs() {
    find "$LOG_DIR" -maxdepth 1 -type f -name 'api_error_payload_*.json' -delete 2>/dev/null
    find "$LOG_DIR" -maxdepth 1 -type f -name 'proxy_errors_*.log' -delete 2>/dev/null
    rm -f "$LOG_DIR/tool_use_errors.jsonl"
}
