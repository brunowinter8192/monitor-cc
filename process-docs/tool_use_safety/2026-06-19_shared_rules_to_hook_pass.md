# shared-rules → Hook Migration Pass (2026-06-19)

## Context

Session work sat in `~/.claude/shared-rules/` (a leanness overhaul of the opus/worker rules). Part of it: checking the fine-grained tool-mechanics rules in `opus/` against the existing hook system. Premise (from the user): fine-grained "never use tool X like this" rules cost EVERY session context; hooks only fire on misbehavior and are therefore the complete replacement for such rules. Meta-rules (worker flow, phases, dispatch/review/recap/successor) stay — no hook can express those.

Ties into the damage principle from the hook-principle-block-vs-allow entry in this area: hooks only block on **damage** (irreversible action OR context flood). Friction/sanity without damage → let it through.

## Block-vs-Rewrite Refinement (Output-vs-Sanity)

Worked out as a lever during the session, aligns with the damage principle:

- **Output the agent reasons further from** (grep/gh-cli/rag/reads) → MUST **block**. A silent rewrite produces output that doesn't match the call → the agent concludes "something's broken here" and debugs in the wrong direction. That's damage (reasoning corruption).
- **Pure sanity** (sleeps, fore/background) → block-vs-rewrite doesn't matter; the agent doesn't consume the result. A silent rewrite is friction-free.
- **The cut criterion is independent of this:** a rule is cuttable when a hook (existing OR to be built) covers the critical case — not "because the hook teaches".

## What Got Cut from shared-rules/opus (Against EXISTING Hooks)

| Cut | Coverage |
|---|---|
| `workers-1` timer-form hook explanation (the form stayed) | `block_unauthorized_background` (silent rewrite bg→fg) |
| `workers-2` post-spawn "no thinking" + proxy backup note | proxy-side `thinking` override |
| `workers-2` "max ONE background task" | removed with no replacement (user directive: sanity, out) |
| `workers-2` "no manual cat on timer files" | removed with no replacement / part of the sleep antipattern (Hook 3) |
| `workers-1` "NEVER Opus" | `block_worker_spawn_opus` (block + teach message) |

`workers-2` capture-sed filter (line 98): cut first → restored → finally OUT. Capture IS load-bearing in the successor flow (Opus reads the dying worker's pane), BUT the real fix is a **capture-noise rewrite hook** (planned): deliver `worker-cli capture` natively clean like `response` (trailer out, content stays — no block, capture is output the agent reasons further from). Until that hook exists, it relies on Opus applying capture correctly; a bit of token noise per capture is tolerable. Rule out, hook is the target.

## What Stays as a Rule (and Why)

- **Timer form `sleep N && echo done`** — stays a rule, not because a rewrite doesn't teach, but because the worker sleep is needed in ~95% of sessions. Hooks are for what hits every few sessions; a 95% pattern is allowed to be a rule.
- **Kill-discipline meta** (when to kill / when NOT to — mid-work, blocker, low-context) — judgment, stays. Only the *how* (raw tmux chains, pre-kill status) went out → to hooks.

## Hooks to Be Built

The kill-discipline rules (`workers-3:60/62/44`, `tool-use:33`) were cut on the basis of these hooks still to be built:

1. **`block_manual_worker_cleanup`** — block raw `tmux kill-session worker-*` / `git worktree remove .claude/worktrees/...` / `git branch -D <worker-branch>` → "use worker-cli kill". Damage class: irreversible (partial state). Tight: only `worker-*` / `.claude/worktrees/`.
2. **kill-while-working guard** — intercept `worker-cli kill <name>`, block on status `working`, **fail-OPEN** on an unknown status. BLOCKED by a status bug (see below).
3. **Sleep-strip allowlist** — extend the `rewrite_chained_sleep` allowlist (currently only `echo`/`true`) with read-only-fast commands (grep/cat/ls/wc/head/tail/find, git status|log|diff|show, rag-cli search, worker-cli status|list|response) → strip the appended `sleep`.
4. **capture-noise** — clean `worker-cli capture` output like `response` (successor flow).

**Status bug (blocker for Hook 2):** `worker-cli status` shows a worker as `working` AFTER it died at the context limit (a false `working`). A fail-closed kill guard would choke on that → Hook 2 fail-open OR fix the status detection.

## FP Warning (from Existing Evidence)

The hook-principle-block-vs-allow entry in this area documents: `block_chained_sleep` was, with **45% FP**, the biggest false-alarm generator (legitimate `launchctl … ; cmd` and `rag-cli … && sleep ; cmd` chains). Direct consequence for **Hook 3**: don't block, only strip; keep the allowlist tight; and NEVER strip a legitimate wait (`start-server ; sleep 2 ; curl` — started async → the sleep stays). Only strip when the previous command is provably read-only-fast and nothing async was started.

## Global Pass (Same Session)

`global/tool-use.md` also went through — finding: ALL hookable hard rules are already covered by EXISTING hooks (global was the source these hooks were built from). **No new hooks.** Cut (against verified source):

| Cut | Covering Hook |
|---|---|
| §3 Grep scope (whole section) | `block_broad_grep` |
| §13 Path typo (.claire / ..letter) | `block_path_typo` (silent rewrite) |
| §14 Background-Bash deliberate | `block_unauthorized_background` |
| §16 cd-drift | `block_cd_drift` |
| §4 venv-no-redirect line | `block_venv_no_redirect` |
| Read "directories" | `block_read_directory` |
| Read "256KB limit" | `block_read_oversize` |
| Edit "noop edit" | `block_noop_edit` |
| Git safety: amend/force-push/skip-hooks/empty/config | `block_git_destructive` |

`global/tool-use.md`: −176 lines. Kept: judgment/workflow (§1 heredoc, §5 stop-after-2, §6 one-bash-block [a parallel-block via hook is impossible, see the parallel-tooluse-block-impossible entry in this area], §7/§8/§9/§11/§15, soft rules, tool reference) — no hook catches these. `global/documentation.md` untouched (pure doc convention). The "Read 25k-token line" stayed (the hook only checks bytes/256KB, not tokens).

## Sources

- The hook-principle-block-vs-allow entry in this area (damage principle + FP evidence)
- The hook-API-auto-rewrite-works entry in this area (silent rewrite via updatedInput works)
- `src/hooks/` (block_unauthorized_background, block_dangerous_kill, block_worker_spawn_opus, rewrite_chained_sleep as pattern references)
