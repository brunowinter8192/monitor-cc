# 2026-05-20 — `pkill -f` Recurrence Mid-Implementation

Continuation of the session-findings entry in this area. During implementation prep of the `pkill -f`-block hook itself (same session), the antipattern reproduced — concrete evidence that structural prevention is needed because discipline doesn't scale.

## Incident

During an ongoing cursor-edges investigation:

- A foreground probe `dev/cursor_edges/probe.py` was running in background Bash, meant to be killed before the next worker send
- Opus called: `pkill -f "cursor_edges/probe.py"`
- The pattern matched the Python interpreter process AND additionally the `claude.exe` worker process `worker-Monitor_CC-cursor-fix`, because its command line contains the worker prompt content, which referenced `"cursor_edges/probe.py"` as a substring multiple times
- Worker `cursor-fix` SIGTERM'd, exited at 72% context
- Lost context budget: 72% remaining capacity + the already-built cursor-edges mental model
- Recovery: kill-cleanup via `worker-cli kill cursor-fix`, fresh-spawn `leaf-rects` as a replacement

`worker-cli list` output right after the incident:
```
cursor-edges: exited 66%
cursor-probe: unknown
cursor-fix: exited 72%
```

## The Correct Kill Pattern Would Have Been

```bash
pkill -f "venv/bin/python3 dev/cursor_edges/probe.py"
```

Anchoring on the interpreter path makes the pattern unambiguous — claude.exe doesn't match that, because `venv/bin/python3` doesn't appear in its command line. But: even this more precise pattern is fragile. The hook blocks the `pkill -f` call regardless of pattern tightness, because cmdline-substring matching is unsafe for any pattern once worker prompts can contain arbitrary text snippets.

## Convergence with the 2026-05-12 Finding

Both incidents, six days apart, identical pattern:

- `pkill -f <substring>` aiming to kill a Python/tool process
- the cmdline substring additionally matches a claude.exe worker whose prompt contains that substring as text
- worker SIGTERM, context loss
- recovery via fresh-spawn

From the session-findings entry, 2026-05-12:

> "Critical: the pattern fired directly after self-explaining the antipattern. Discipline wasn't enough — structural prevention needed."

Today, identical: after the 2026-05-12 finding, the hook design was already documented + tracked as a TODO. Opus knew the risk and reproduced the antipattern anyway. The discipline layer is demonstrably insufficient.

## Known Allowed Kill Paths (Unchanged Since 2026-05-12)

| Pattern | Allowed? | Rationale |
|---|---|---|
| `worker-cli kill <name>` | yes | the wrapper knows the worker name → tmux session name → exact-kill |
| `kill <numeric_pid>` | yes | direct PID reference, no substring matching |
| `kill -SIGNAL <pid>` | yes | same direct-PID logic |
| `pkill -x <exact_name>` | yes | exact-match flag, no substring |
| `launchctl bootout`, `kickstart` | yes | service-specific via label |
| `pkill -f <substring>` | **no** | substring match on cmdline, hits a worker with the substring in its prompt |
| `ps … \| grep … \| kill …` | **no** | same substring problem |

## Implementation Status

- Dispatch: worker `safety-hooks` builds `src/hooks/block_dangerous_kill.py` + `src/hooks/hook_setup.py` + `src/hooks/DOCS.md` + the safety-hooks current-state doc
- Registration: global in `~/.claude/settings.json` with an absolute path (no plugin)
- First live verification: after the setup run, attempt a `pkill -f` call, expect exit 2 + a stderr alternative

If the hook works after this incident, both historical incidents (05-12 + 05-20) are what triggered the structural correction that prevents all future reproductions.

## Sources

- The session-findings entry in this area — the initial quantification (267 calls in 6 days), the hook-design proposal, allow/block nuance
- anthropics/claude-code `plugins/security-guidance/hooks/security_reminder_hook.py` — a PreToolUse reference pattern (matcher, stdin-JSON format, exit codes)
- `~/.claude/plugins/cache/brunowinter-plugins/iterative-dev/1.0.0/Hooks_Reference/AntrophicDocs.md` — hooks reference (settings.json structure, matcher semantics, exit-code semantics)
