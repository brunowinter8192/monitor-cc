#!/bin/bash

PASS=0
FAIL=0
FAILURES=()
SCRIPT_DIR=""
DUAL_LOG_DIR=""
TMPDIR_ROOT=""

_compute_proxy_hash() {
    { cat "$SCRIPT_DIR/proxy_addon.py"
      find "$SCRIPT_DIR/proxy" -type f \( -name '*.py' -o -name '*.json' \) | sort \
          | while IFS= read -r f; do cat "$f"; done
    } | if command -v md5 &>/dev/null; then md5; else md5sum | head -c 32; fi
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

_assert() {
    local desc="$1" result="$2" expected="$3"
    if [ "$result" = "$expected" ]; then
        echo "  [OK  ] $desc"
        PASS=$((PASS + 1))
    else
        echo "  [FAIL] $desc"
        echo "         expected: $expected"
        echo "         got:      $result"
        FAIL=$((FAIL + 1))
        FAILURES+=("$desc")
    fi
}

_fexists() { [ -f "$1" ] && echo exists || echo gone; }

_make_stale() {
    touch "$1"
    local old_ts
    old_ts="$(date -v-2H +%Y%m%d%H%M.%S 2>/dev/null || date -d '2 hours ago' +%Y%m%d%H%M.%S)"
    touch -t "$old_ts" "$1"
}

_setup() {
    TMPDIR_ROOT="$(mktemp -d)"
    SCRIPT_DIR="$TMPDIR_ROOT/src"
    DUAL_LOG_DIR="$TMPDIR_ROOT/dual_log"
    mkdir -p "$SCRIPT_DIR/proxy" "$DUAL_LOG_DIR"
    printf 'print("proxy_addon")\n' > "$SCRIPT_DIR/proxy_addon.py"
    printf '# proxy init\n'         > "$SCRIPT_DIR/proxy/__init__.py"
    printf '{"schema":1}\n'         > "$SCRIPT_DIR/proxy/schema.json"
}

_teardown() { rm -rf "$TMPDIR_ROOT"; }

echo "test_version_purge.sh"
echo

echo "(a) version change purges stale (>60min) logs"
_setup
echo "oldhash" > "$DUAL_LOG_DIR/.proxy_version"
_make_stale "$DUAL_LOG_DIR/api_requests_opus_proj_111_original.jsonl"
_make_stale "$DUAL_LOG_DIR/api_requests_opus_proj_111_forwarded.jsonl"
_janitor_version_purge_jsonl_logs
_assert "stale original deleted"            "$(_fexists "$DUAL_LOG_DIR/api_requests_opus_proj_111_original.jsonl")"  "gone"
_assert "stale forwarded deleted"           "$(_fexists "$DUAL_LOG_DIR/api_requests_opus_proj_111_forwarded.jsonl")" "gone"
_assert "marker updated to current hash"    "$(cat "$DUAL_LOG_DIR/.proxy_version")" "$(_compute_proxy_hash)"
_teardown

echo

echo "(b) same version — no purge"
_setup
echo "$(_compute_proxy_hash)" > "$DUAL_LOG_DIR/.proxy_version"
_make_stale "$DUAL_LOG_DIR/api_requests_opus_proj_222_original.jsonl"
_janitor_version_purge_jsonl_logs
_assert "stale file kept (same version)"    "$(_fexists "$DUAL_LOG_DIR/api_requests_opus_proj_222_original.jsonl")" "exists"
_teardown

echo

echo "(c) fresh logs survive version-change purge"
_setup
echo "oldhash" > "$DUAL_LOG_DIR/.proxy_version"
touch "$DUAL_LOG_DIR/api_requests_opus_proj_333_original.jsonl"
_make_stale "$DUAL_LOG_DIR/api_requests_opus_proj_333_forwarded.jsonl"
_janitor_version_purge_jsonl_logs
_assert "fresh original kept"               "$(_fexists "$DUAL_LOG_DIR/api_requests_opus_proj_333_original.jsonl")"  "exists"
_assert "stale forwarded deleted"           "$(_fexists "$DUAL_LOG_DIR/api_requests_opus_proj_333_forwarded.jsonl")" "gone"
_teardown

echo

echo "(d) absent marker → first-run cleanup"
_setup
_make_stale "$DUAL_LOG_DIR/api_requests_opus_proj_444_original.jsonl"
_janitor_version_purge_jsonl_logs
_assert "stale file deleted (first run)"    "$(_fexists "$DUAL_LOG_DIR/api_requests_opus_proj_444_original.jsonl")" "gone"
_assert "marker created"                    "$(_fexists "$DUAL_LOG_DIR/.proxy_version")"                             "exists"
_teardown

echo
total=$((PASS + FAIL))
if [ "$FAIL" -gt 0 ]; then
    echo "FAILED: $FAIL/$total assertion(s):"
    for f in "${FAILURES[@]}"; do echo "  - $f"; done
    exit 1
fi
echo "All $total assertions passed."
