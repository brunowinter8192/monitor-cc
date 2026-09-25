# block_git_add_deps: heredoc false positives (2026-09-25)

## Problem

`block_git_add_deps` matched a git-add pattern and a `venv`/`node_modules` pattern independently anywhere in the command. Its private `_strip_quoted` did not know heredocs. In the fire log (78 entries for this hook) nine blocks between 2026-09-23 and 2026-09-25 were false positives: `python3 - <<'EOF'` edits of DOCS.md, `cat > ... <<'EOF'` process-docs and worker prompt files, `sed -i` plus heredoc.

Observed example 2026-09-25T14:18:01Z: `cat >> process-docs/... <<'EOF'` with `./venv/bin/python` in the body, then `git add -A && git commit` in the same call. The `git add` and the `venv` text were both present, so it blocked. Also observed: the orchestrator's own `cat > /tmp/spawn-worker-....md <<'EOF'` call, blocked because the prompt text named the positives.

## Decision

- Drop `_strip_quoted`; use `_strip_non_shell_active` from `_shell_strip.py` (as 22 other hooks do). It blanks heredoc bodies and quoted strings, position-preserving.
- Split the stripped text into segments at `&&`, `||`, `;`, `|`, newline. Block only when ONE segment contains `git [-C <path>] add ... <target>` where target is a whole token: `venv`, `.venv`, `node_modules`, optional leading `./`, optional trailing `/`.
- The whole-token rule keeps `git add ./venv/bin/python` and `git add src/venv_tools.py` unblocked; `git add -A && ./venv/bin/python -m pytest` passes because the two parts are different segments.

## Consequences

- Trace side effect: the old `unterminated quote: remainder dropped` trace of this hook is gone. An unclosed quote now produces the shared `_shell_strip` trace `raw-text fallback: unclosed single quote` (the raw command is then matched). `test_hook_trace_lines.py` lost `case_unterminated_quote` because `case_strip_raw_fallback` already covers that trace.
- Hypothesis (never observed): quoted targets such as `git add "venv"` or `git add 'venv/'` are blanked by the shared stripper and therefore no longer blocked. The old code also stripped quotes, so this is no regression. Accepted by the user; no quote-preserving pass was added (YAGNI).
- `git add -A` in monitor-cc is safe: the `.gitignore` entry `venv` also matches the worktree `venv` symlink.

## Tests

`dev/hook_smoke/test_block_git_add_deps.py`: 10 PASS cases (the observed fire-log commands, reduced, plus chained and substring forms) and 8 BLOCK cases (`git add venv/`, `venv`, `.venv`, `node_modules/`, `git -C /repo add venv`, `git add -A venv`, `git add README.md venv/`, `cd /repo && git add node_modules`, and a `git add venv/` after a heredoc). Registered in `run_all.py`; full run 25/25 strands.
