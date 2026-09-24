#!/bin/bash

WORKTREE_ROOT="$(cd "$(dirname "$0")/../.." && pwd)"

PASS=0
FAIL=0
FAILURES=()
RESULT_ROWS=()

_parse_args() {
    PROJECT=""
    CLAUDE_ARGS=()
    HAS_EXPLICIT_MODEL=""
    while [[ $# -gt 0 ]]; do
        case "$1" in
            --project)
                PROJECT="$2"
                shift 2
                ;;
            --model)
                HAS_EXPLICIT_MODEL=1
                CLAUDE_ARGS+=("$1" "$2")
                shift 2
                ;;
            *)
                CLAUDE_ARGS+=("$1")
                shift
                ;;
        esac
    done
    PROJECT="${PROJECT:-$(pwd)}"
    if [ -z "$HAS_EXPLICIT_MODEL" ] && command -v jq &>/dev/null && [ -f "$MODEL_SELECTION_FILE" ]; then
        CONFIG_MODEL="$(jq -r '.main // empty' "$MODEL_SELECTION_FILE" 2>/dev/null)"
        if [ -n "$CONFIG_MODEL" ]; then
            CLAUDE_ARGS+=("--model" "$CONFIG_MODEL")
        fi
    fi
}

_join() { local IFS='|'; echo "$*"; }

_assert_args() {
    local desc="$1"; shift
    local expected="$1"; shift
    _parse_args "$@"
    local got
    got="$(_join "${CLAUDE_ARGS[@]}")"
    if [ "$got" = "$expected" ]; then
        echo "  [OK  ] $desc"
        PASS=$((PASS + 1))
        RESULT_ROWS+=("| $desc | \`$got\` | PASS |")
    else
        echo "  [FAIL] $desc"
        echo "         expected: $expected"
        echo "         got:      $got"
        FAIL=$((FAIL + 1))
        FAILURES+=("$desc")
        RESULT_ROWS+=("| $desc | \`$got\` (expected \`$expected\`) | FAIL |")
    fi
}

echo "verify_launcher_model_precedence.sh — src/claude_proxy_start.sh full precedence chain"
echo

TMP_DIR="$(mktemp -d)"
trap 'rm -rf "$TMP_DIR"' EXIT

MODEL_SELECTION_FILE="$TMP_DIR/does_not_exist.json"

_assert_args "no flag, no config -> byte-identical (nothing injected)" \
    "--extra|val" \
    --extra val

_assert_args "explicit --model, no config -> explicit passed through" \
    "--model|claude-custom" \
    --model claude-custom

_assert_args "--project alone, no config -> --project extracted, nothing injected" \
    "" \
    --project /some/path

VALID_CONFIG="$TMP_DIR/valid.json"
echo '{"main": "claude-opus-5-5", "worker": "claude-sonnet-5"}' > "$VALID_CONFIG"
MODEL_SELECTION_FILE="$VALID_CONFIG"

_assert_args "no flag, valid config -> config's main model injected" \
    "--extra|val|--model|claude-opus-5-5" \
    --extra val

_assert_args "--project + no other flags, valid config -> --project extracted, config's main model injected (the actual real-world invocation)" \
    "--model|claude-opus-5-5" \
    --project /some/path

_assert_args "--project + other passthrough, valid config -> --project extracted, other flag kept, model appended" \
    "--other-flag|val|--model|claude-opus-5-5" \
    --project /some/path --other-flag val

_assert_args "explicit --model + valid config -> explicit wins, config never consulted" \
    "--model|claude-custom" \
    --model claude-custom

MODEL_SELECTION_FILE="$TMP_DIR/missing.json"
_assert_args "missing config file -> nothing injected (falls through to no-injection case)" \
    "--extra|val" \
    --extra val

MALFORMED_CONFIG="$TMP_DIR/malformed.json"
echo '{not valid json' > "$MALFORMED_CONFIG"
MODEL_SELECTION_FILE="$MALFORMED_CONFIG"
_assert_args "malformed JSON config -> nothing injected, no crash" \
    "--extra|val" \
    --extra val

MISSING_KEY_CONFIG="$TMP_DIR/missing_key.json"
echo '{"worker": "claude-sonnet-5"}' > "$MISSING_KEY_CONFIG"
MODEL_SELECTION_FILE="$MISSING_KEY_CONFIG"
_assert_args "config present but missing 'main' key -> nothing injected" \
    "--extra|val" \
    --extra val

EMPTY_KEY_CONFIG="$TMP_DIR/empty_key.json"
echo '{"main": "", "worker": "claude-sonnet-5"}' > "$EMPTY_KEY_CONFIG"
MODEL_SELECTION_FILE="$EMPTY_KEY_CONFIG"
_assert_args "config present with empty 'main' value -> nothing injected" \
    "--extra|val" \
    --extra val

echo
total=$((PASS + FAIL))
if [ "$FAIL" -gt 0 ]; then
    echo "FAILED: $FAIL/$total assertion(s):"
    for f in "${FAILURES[@]}"; do echo "  - $f"; done
fi
echo "$PASS/$total passed."

MD_DIR="$WORKTREE_ROOT/dev/model_selector/md"
mkdir -p "$MD_DIR"
OUT_PATH="$MD_DIR/verify_launcher_model_precedence.md"

{
    echo "# Launcher model-selection precedence dry run"
    echo
    echo "**Result: $PASS/$total checks passed**"
    echo
    echo "Pure argument-parsing simulation of src/claude_proxy_start.sh's full precedence chain"
    echo "(--model > config file 'main' key > nothing injected, no CLI shortcuts since 2026-09-23)"
    echo "— never starts the proxy or claude, never touches the real"
    echo "~/.claude/shared-rules/model_selection.json."
    echo
    echo "| Case | Resulting CLAUDE_ARGS | Result |"
    echo "|---|---|---|"
    for row in "${RESULT_ROWS[@]}"; do
        echo "$row"
    done
} > "$OUT_PATH"

echo
echo "Report written to: $OUT_PATH"

if [ "$FAIL" -gt 0 ]; then
    exit 1
fi
exit 0
