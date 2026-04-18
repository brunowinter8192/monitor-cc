# Hook Limits (Monitor_CC)

## additionalContext Per-Hook Limit (VERIFIED 2026-04-05)

Live-tested limit: **~10KB (10,000 bytes)** per hook `additionalContext`.

| Test | Bytes | Result |
|------|-------|--------|
| 9,945 | ✅ injected fully |
| 10,081 | ❌ persisted to disk, 2KB preview only |

**GitHub CHANGELOG v2.1.89 claims 50K — this is incorrect or refers to a different mechanism.**

**When exceeded:**
- Claude Code saves full output to `~/.claude/projects/.../tool-results/hook-...-additionalContext.txt`
- Only first 2KB injected as `<persisted-output>` preview
- Silent truncation — no error to the hook script

**Design rules for injection hooks:**
- Each hook's additionalContext MUST stay under 9,500 bytes (safety margin)
- Split large files into multiple hooks, each under the limit
- Multiple hooks with additionalContext merge as separate system-reminders (do NOT overwrite each other)
- Measure: `wc -c < file` or `python3 -c "print(len(open('file').read().encode('utf-8')))"`

## Worker Research Caveat

When dispatching workers to research Claude Code limits/thresholds via GitHub:
- Worker prompt MUST include: "Verify any claimed limits with a LIVE TEST before reporting as fact."
- GitHub source analysis can be wrong (wrong branch, outdated, misread)
- A 30-second live test beats hours of source diving
