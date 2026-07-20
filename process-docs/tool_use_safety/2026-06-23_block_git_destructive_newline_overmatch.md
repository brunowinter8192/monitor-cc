# block_git_destructive — Newline Over-Match FP (2026-06-23)

Same over-match class as the proxy bg_launch_ack strip (`message_strip_fp_nuke/`) — a matcher reaching beyond its intended unit. Here in a safety HOOK, not the proxy strip.

## Symptom
During session recap, `block_git_destructive` blocked a completely SAFE multi-line Bash command with reason `git push -f` — no force-push present. The command chained `git checkout main && git merge dev && (git push || git push -u origin main)` and then, two lines later, `[ -f .rag-docs.json ] && rag-cli update_docs .`.

## Root cause — confirmed (fire-log + source read)
`src/hooks/block_git_destructive.py`, pattern `\bgit\b[^|;&]*\bpush\b[^|;&]*\s-f\b`.
- `[^|;&]*` excludes the shell separators `|`, `;`, `&` (to stop bridging across `cmd1 ; cmd2`) but NOT the newline `\n`.
- In a multi-line command the connector spans line breaks freely. `_strip_quoted` removes the quoted `$'...'` blobs + `echo "..."` content, leaving `...git push -u origin main)\necho \n[ -f .rag-docs.json ...`.
- The ` -f ` that matched is the bash file-existence test in `[ -f .rag-docs.json ]`, two lines below an unrelated `git push`. The `broad-find` worker name (initially suspected) was NOT the trigger — its `-f` is `d-f` with no leading whitespace.

Evidence: fire-log `src/logs/hook_firing.jsonl`, event ts `2026-06-23T00:23:06Z`, reason `git push -f`, full command recorded.

## Fix — committed `d6112c8` on dev
`[^|;&]` → `[^|;&\n]` in all five `_PATTERNS` + `_GIT_CONFIG_RE`. Confines every match to a single physical line. Mirrors the precedent fix in `block_manual_worker_cleanup.py` (`[^;&|\n]*`). Conservative: only narrows, never broadens — single-line force-push (`git push -f`, `git push --force`) stays caught. Only theoretical loss: a force-push split across a backslash-newline continuation (rare; hook is fail-open anyway).

## Verification
New smoke `dev/hook_smoke/test_block_git_destructive.py` — 21 cases (2 FP-regression multi-line ALLOW, 13 BLOCK TP, 6 ALLOW incl. quoted-`--force`-in-commit-message FP). 21/21 PASS.

## Open question (separate scope — NOT fixed here)
`_strip_quoted` does not strip heredoc bodies. A `cat << 'EOF' ... git commit --amend ... EOF` doc-text triggered a `--amend` block on `2026-06-20` (fire-log). Heredoc-aware stripping is a larger, separate change — left open.

## Cross-link — same over-match class, different surfaces
- proxy strip, substring-anywhere → anchored `startswith`: `decisions/OldThemes/message_strip_fp_nuke/bg_launch_ack_anchor.md`
- proxy strip, plan-mode branch: `decisions/OldThemes/message_strip_fp_nuke/plan_mode_branch.md`
- safety hook, substring spans newlines → bounded to single line: this file
