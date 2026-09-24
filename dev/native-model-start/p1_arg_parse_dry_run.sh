#!/bin/bash

WORKTREE_ROOT="$(cd "$(dirname "$0")/../.." && pwd)"

PASS=0
FAIL=0
FAILURES=()
RESULT_ROWS=()

_parse_args() {
    PROJECT=""
    CLAUDE_ARGS=()
    SHORTCUT_MODEL=""
    HAS_EXPLICIT_MODEL=""
    while [[ $# -gt 0 ]]; do
        case "$1" in
            --project)
                PROJECT="$2"
                shift 2
                ;;
            --fable)
                SHORTCUT_MODEL="claude-fable-5"
                shift
                ;;
            --opus)
                SHORTCUT_MODEL="claude-opus-5"
                shift
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
    if [ -z "$HAS_EXPLICIT_MODEL" ] && [ -n "$SHORTCUT_MODEL" ]; then
        CLAUDE_ARGS+=("--model" "$SHORTCUT_MODEL")
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

echo "p1_arg_parse_dry_run.sh — src/claude_proxy_start.sh --fable/--opus/--model precedence"
echo

_assert_args "no flag at all -> byte-identical (nothing injected)" \
    "--extra|val" \
    --extra val

_assert_args "--fable alone -> --model claude-fable-5 appended" \
    "--model|claude-fable-5" \
    --fable

_assert_args "--opus alone -> --model claude-opus-5 appended" \
    "--model|claude-opus-5" \
    --opus

_assert_args "--fable with explicit --model X (shortcut BEFORE explicit) -> explicit wins" \
    "--model|claude-custom" \
    --fable --model claude-custom

_assert_args "--model X --fable (explicit BEFORE shortcut) -> explicit still wins regardless of position" \
    "--model|claude-custom" \
    --model claude-custom --fable

_assert_args "--fable --opus (both shortcuts, no explicit) -> last one wins" \
    "--model|claude-opus-5" \
    --fable --opus

_assert_args "--opus --fable (both shortcuts, reverse order) -> last one wins" \
    "--model|claude-fable-5" \
    --opus --fable

_assert_args "mixed: --project + --fable + other passthrough args -> --project extracted, rest untouched, model appended" \
    "--other-flag|val|--model|claude-fable-5" \
    --project /some/path --fable --other-flag val

echo
total=$((PASS + FAIL))
if [ "$FAIL" -gt 0 ]; then
    echo "FAILED: $FAIL/$total assertion(s):"
    for f in "${FAILURES[@]}"; do echo "  - $f"; done
fi
echo "$PASS/$total passed."

MD_DIR="$WORKTREE_ROOT/dev/native-model-start/md"
mkdir -p "$MD_DIR"
STAMP="$(date -u +%Y%m%d_%H%M%S)"
OUT_PATH="$MD_DIR/p1_arg_parse_dry_run_${STAMP}.md"

{
    echo "# P1 — arg-parse dry run ($(date -u +%Y-%m-%dT%H:%M:%SZ))"
    echo
    echo "**Result: $PASS/$total checks passed**"
    echo
    echo "Pure argument-parsing simulation of src/claude_proxy_start.sh's --fable/--opus/--model"
    echo "precedence logic — never starts the proxy or claude."
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
