# Silent-Rewrite Hooks Are Intentionally Invisible in the Proxy Pane, 2026-07-21

## Decision

The monitor proxy pane does NOT surface PreToolUse silent-rewrite transformations. Considered and rejected as of 2026-07-21 — kept as a deliberate anti-goal so it is not re-proposed.

## Context

The rewrite hooks (`rewrite_worker_cli_response_noise`, `rewrite_worker_cli_capture_noise`, `rewrite_gh_cli_read_noise`) strip a truncating pipe (`| tail`/`| head`/`| grep`) from a command via PreToolUse `updatedInput`, so the full output is always returned. This produces an apparent mismatch in the pane:

- The `tool_use` block the pane renders is the MODEL-emitted command, frozen at generation time — it still shows the `| tail`. `updatedInput` changes what the Bash tool EXECUTES; it does not rewrite the already-emitted assistant tool_use block.
- The `tool_result` is the output of the EXECUTED (post-hook, rewritten) command — i.e. the full, untruncated result.

So the pane shows: command with `| tail` (pre-hook) → result full/untruncated (post-hook). Functionally correct end-to-end; only visually asymmetric.

## Where the post-hook command lives

Only in `src/logs/hook_firing.jsonl` — the rewrite hooks log both `command` (original) and `rewritten` (executed) there. The post-hook command is NOT in the API request payload the proxy pane renders; the pane's tool_use is always the model's pre-hook block.

## Why not surfaced

Surfacing the executed command (or annotating "→ rewritten to X") would require a new data path: the pane reading `hook_firing.jsonl` and correlating each rewrite entry to a tool_use block by command-text + timestamp + session. The hook is the invisible middle transform between two endpoints that both render correctly; exposing the middle only adds confusion for a purely cosmetic gap. Not worth the correlation machinery.
