# 2026-11-02 — BOM1 worker sandbox hook: project-level allow-list, built and tested, not yet live

## Context and decisions (user, 02.11.2026)

- Seminar project BOM1: one Claude Code worker per DAX firm (39 firms) collects CEO compensation data from one firm's reports plus an adidas reference. The user's main concern is leakage: a worker must see only its own firm and adidas.
- The first decision that morning was "no sandboxing, exact instructions suffice". The user reversed it the same day and asked for technical enforcement behind the skill. The skill stays as instruction, the hook is the guardrail.
- Decisions that shaped the design:
  - The orchestrator that spawns the workers runs in the project BOM1-worker.
  - The hook is registered project-level in `BOM1-worker/.claude/settings.json` only, not in `hook_setup.py` and not in `~/.claude/settings.json`. The user commits that file after the merge to monitor-cc main.
  - It acts only in worker worktrees `.../BOM1-worker/.claude/worktrees/<name>`. The user's own root session stays free. Worktree names starting with `dev-` are out of scope.
  - Worker name = ticker exactly. A name that is not a ticker in the policy blocks everything.
  - Allowed documents per ticker come from a file in the BOM1-worker main checkout (area data_collection in the BOM1 project holds that file, the helper and their tests).
  - A fixed workbook helper replaces free python. cd, pipes, redirects and command substitution are blocked. Fail closed inside scope.
  - Block message names the allowed forms and tells the worker to stop and report.
  - Phase order of the skill (adidas reference only in phase 3) stays a skill rule, the hook does not gate it.
  - Enforce from the first pilot, no shadow mode.

## What exists (all committed on branch `sandbox-gaps` of monitor-cc)

| File | Role |
|---|---|
| `src/hooks/block_bom1_worker_sandbox.py` | Entry point: scope, policy, tool dispatch, block message, fire-log record |
| `src/hooks/_bom1_sandbox_bash.py` | Library: strict lexer and slot grammars for one Bash call |
| `dev/hook_smoke/test_block_bom1_worker_sandbox.py` | 388 parallel strands, one temp BOM1-worker tree per case |
| `dev/hook_smoke/run_all.py` | Suite registered |

Run: `python3 dev/hook_smoke/test_block_bom1_worker_sandbox.py` from the repo root. Result 02.11.2026: 388/388.

## Facts observed on 02.11.2026 that the design rests on

Probe run by the user in a throwaway project with a project-level `"*"` hook that logged every payload (kit and log reading are documented in area data_collection of the BOM1 project).

- A project-level `.claude/settings.json` that is committed reaches the worker worktree and its hook fires for Read, Bash, Skill and Agent, and for the subagent's Bash.
- Payload keys: `cwd, effort, hook_event_name, permission_mode, prompt_id, scratchpad_dir, session_id, tool_input, tool_name, tool_use_id, transcript_path`; subagent calls add `agent_id` and `agent_type`, same `session_id`.
- `permission_mode` was `bypassPermissions`. Exit 2 blocked anyway and the worker obeyed the message.
- `tool_input` keys: Bash `command, description`; Read `file_path`; Skill `skill` (value `probe-skill`); Agent `description, prompt`.
- `CLAUDE_PROJECT_DIR` in the hook environment was the worktree in realpath form (`/private/tmp/...` although the project was created under `/tmp`). Payload `cwd` was the worktree on every call.
- `cd /tmp && pwd` printed `/tmp` inside the call, the next call ran in the worktree again ("Shell cwd was reset"). So the payload cwd never drifts for a worker.
- The worker had no Glob and no Grep tool.
- A spawn into an untrusted root hung at the trust prompt and no hook fired before trust. Trust of a project root covers its worktrees.
- Hook PATH contained the plugin-cache bins in this run. The 20.06.2026 finding (stripped PATH) is therefore not reliable either way. The hook uses no subprocess and stdlib only, so it does not depend on PATH.
- Code reading, same day: `worker-cli spawn` takes the project from `PROXY_PROJECT_PATH` (the orchestrator session's project), else from the cwd. It copies only `<project>/.claude/settings.local.json` into the worktree, never `settings.json`; `settings.json` arrives through the checkout of `git worktree add -b <name>` from the project's current HEAD. Workers run with `--permission-mode bypassPermissions`. The worker name is only constrained by git branch and tmux session rules.
- rag-cli (`cli.py`, `db.py`): argparse accepts abbreviations (`--doc`) and `--document=X`; `--document` with `%` is a LIKE match; `expand_chunks` matches its document positional exactly and clamps `--before`/`--after` to 10.

## Design and why

**Allow-list by full match, not a deny-list.** The deny-list hooks in this area were bypassed repeatedly by new carriers: env prefix, `$(...)`, backticks, bare `&` without spaces, `/tmp` file indirection, `venv/python cli.py`, quote concatenation. For a leakage guard the hook therefore lexes the whole command with a strict regex and matches the words against fixed slot grammars. It does not use `shlex` and not `_shell_strip`.
- Tokens are separated by single spaces. A bare token is `[A-Za-z0-9_./%-]+`, which excludes every shell metacharacter, glob, `~` and `=`. A quoted token is `'...'`, or `"..."` without `$`, backtick, backslash or `"`.
- Anything ambiguous simply fails to lex: `rag-cli search "q" bom1-reports --document 'SAP_Rem'"uneration..."` (adjacent quotes) blocks because the second quote is not preceded by a space.
- Double quotes need the exclusion of `$` and backtick because bash evaluates `$(...)` inside them, while the shell-strip blanks them (recorded in the area, 02.08.2026).
- The first word must be exactly `rag-cli`, `env`, `git` or `unset`. That closes absolute paths, interpreter forms, `bash -c`, `eval`, `time`, `nohup`.

**Allowed Bash forms** (`U` = `unset PYTHONHOME PYTHONPATH RESOURCEPATH EXECUTABLEPATH ARGVZERO; `, optional and only in front of `rag-cli`; `H` = `env -u PYTHONHOME -u PYTHONPATH -u RESOURCEPATH -u EXECUTABLEPATH -u ARGVZERO uv run -q --no-project --with openpyxl python tools/workbook_io.py`):
- `[U]rag-cli list_documents bom1-reports --document '<T>_%'`
- `[U]rag-cli search "<query>" bom1-reports --document '<DOC>'`
- `[U]rag-cli expand_chunks bom1-reports <DOC> <chunk> [--before N] [--after N]`
- `H read <T> Metric_Classification`, `H read <T> Data_Compensation`, `H read-reference Data_Compensation`
- `H write <T> Data_Compensation <<'ROWS'` + JSON + `ROWS`
- `git add excels/<T>.xlsx excels/<T>.md && git commit -m "feat: collect <T> compensation data"` and `git add excels/<T>.md && git commit -m "docs: record <T> findings"`; `git add` alone and `git commit` alone with the same exact messages.
- `<DOC>` must be in the policy entry of the ticker. Query: 1 to 300 printable characters, no `$`, backtick, backslash, not starting with a dash. Bash input keys: only `command`, `description`, `timeout`; `run_in_background` and `dangerouslyDisableSandbox` only if false.

**Other tools.** Read, Write, Edit only on `excels/<T>.md`; Skill only `firm-compensation-collection`; `TodoWrite` and `TaskCreate/TaskUpdate/TaskList/TaskGet` pass (side-effect free, a block would stop a worker that only plans); everything else blocks, including Agent, Glob, Grep, WebFetch, WebSearch, MCP. Reason for Read of the own md: Claude Code requires a Read before a Write on an existing file.
- The own-file comparison is `realpath(target) == <worktree>/excels/<T>.md` (lexical on the right side). With a symlinked `excels/` the target resolves elsewhere and blocks (test scenario SYMLINK). Comparing realpath with realpath would have accepted it.

**The one heredoc exception.** `write` takes JSON on stdin. A single-quoted JSON argument breaks on apostrophes in cell text, so the user approved a heredoc. Rules: opener exactly ` <<'ROWS'` on the first line, last line exactly `ROWS`, and no earlier body line equal to `ROWS`. Example blocked: body `[]`, then a line `ROWS`, then `rm -rf /`, then a second `ROWS` at the end. Bash ends the heredoc at the first `ROWS` and runs the rest as commands, so the hook rejects any early terminator line. Body content is otherwise inert (a test pushes `$(rm -rf /)`, backticks, `| cat` and `> /etc/passwd` through as body text and expects exit 0).

**Scope and fail-closed order.**
1. `realpath(CLAUDE_PROJECT_DIR)` (fallback: hook cwd) is matched against `.../BOM1-worker/.claude/worktrees/<name>[/...]`. No match, or name starting with `dev-`: exit 0 without reading stdin. The root session is free even on garbage stdin.
2. In scope: read stdin, parse, load `allowed_documents.json` from the main checkout root (the part before `/.claude/worktrees/`), then check. A payload with `agent_id`, a payload `cwd` that is not the worktree root, a missing or invalid policy, a name not in the policy: block.
3. Any unexpected exception after step 1 blocks with "internal error ... fails closed".

**Block message.** Reason, then the allowed forms with the worker's ticker and its document names filled in, then: "Stop now: do not retry and do not look for another way around this block. Report to the user what you tried to do and that the sandbox blocked it, then go idle." For an unknown worker name there are no forms, only reason and stop. Lesson behind it: area entry of 28.08.2026 (a block that only forbids invites a workaround; here a workaround would be a leak).

**Log.** Only blocks are written to the fire log (hook, tool, session, subject up to 1000 characters). Allowed calls stay silent. Fire-log records from a worktree do not land in the main checkout log; the hook runs from the main checkout path in production.

## Findings during the build

- **Fail-open hole found by a test.** First run: 386/387. The case "payload is invalid UTF-8" exited 1. `sys.stdin.read()` sat in the orchestrator outside the guarded section and raised `UnicodeDecodeError`; exit 1 is a non-blocking error in Claude Code, so the call would have gone through. Fix: stdin is read inside the `try` of `decide`. Rule for successors: after the scope match, nothing may run outside the catch-all. Import errors at module load are still not covered (exit 1); only tests and the registration order protect against them.
- **Misleading exit 2.** An ad-hoc check called the hook by a relative path while setting the subprocess cwd to a temp tree. Python could not open the file and exited 2, the same code as a block, so every command looked "blocked". Looking at the first stderr line (a python path instead of "BLOCKED by the BOM1 worker sandbox") exposed it. Check the reason text, not only the exit code. The same mechanism is the machine-wide outage of 02.08.2026 if the registered script path dies.
- A test helper named `case_functions` was collected by the prefix scan for cases; renamed. Not a hook issue.
- The repo's post-commit githook runs `hook_setup.py` after a commit under `src/hooks/`; from a worktree its guard refuses (expected). The new hook is not in `_HOOK_SCRIPTS`, so `hook_setup.py` never registers it, also after the merge.

## Tested bypass shapes (all block, reason checked for the key ones)

Env prefix (`FOO=1 rag-cli ...`), `$(...)`, backticks, `$VAR`/`${VAR}` in query and as document, process substitution, pipes, all redirect forms, `;`, `&&`, `||`, newline, backslash continuation, trailing and glued `&`, subshell, brace group, quote concatenation, absolute `rag-cli` path, `./venv/bin/python cli.py`, `bash -c`, `eval`, `env rag-cli`, `time`/`nohup`, glob and `%` in `--document` of a search, `--doc`, `--document=X`, duplicate `--document`, `--exclude`, other collections (`bom1-docs`, `bom1-reference`), other firm's document, `unset` variants, free python (`python -`, heredoc with other delimiters, early terminator, text after terminator), git `-A`, `.`, other files, swapped file order, amend, `-am`, `--no-verify`, commit message of another ticker, `git status/log/diff/show/branch/push`, 40+ plain commands, 19 other tools, other skills, 60 path variants for Read/Write/Edit, payload anomalies, unknown worker, missing policy, broken policy.

## Not verified and open (02.11.2026)

- No live run with a real worker and the final hook yet. The first pilot worker is the verification; the user wants enforcement from the first pilot.
- Names of the planning tools are guessed from Claude Code naming (`TodoWrite`, `TaskCreate`, `TaskUpdate`, `TaskList`, `TaskGet`), not observed. A worker that uses another planning tool is blocked and stops.
- The global hooks of `~/.claude/settings.json` still run in worker sessions. The allowed forms were not replayed through all of them; only the project hook was tested.
- Unmeasured: hook timeout behaviour, hook precedence against other hooks' `ask` or `updatedInput` (the global hooks do not use them for these commands), `session_id` across compact or resume.
- Persisted output: no Read of tool-result files is allowed (not observed in this workflow). The helper output of the reference is 2.2 KB. If a result is ever persisted, the worker stops and reports.
- Order for going live: merge monitor-cc to main (script must exist at the main path), merge allowed-documents policy and helper into the BOM1-worker main checkout, edit the skill, then commit `BOM1-worker/.claude/settings.json`. A settings file pointing to a missing script path exits 2 and blocks every BOM1-worker session, including the user's own.
- After that file lands, any BOM1-worker worktree not named `dev-...` and not a ticker is fully blocked (this includes the worktree `sandbox-gaps` the work was done in).
- Exact content prepared for the user to commit:

```json
{
  "hooks": {
    "PreToolUse": [
      {
        "matcher": "*",
        "hooks": [
          {
            "type": "command",
            "command": "/opt/homebrew/bin/python3 /Users/brunowinter2000/Documents/ai/monitor-cc/src/hooks/block_bom1_worker_sandbox.py",
            "timeout": 5
          }
        ]
      }
    ]
  }
}
```
