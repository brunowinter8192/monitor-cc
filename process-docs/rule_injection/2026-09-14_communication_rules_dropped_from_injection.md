# 2026-09-14 — communication.md taken out of the injected main rules

Main session entry. The user asked to see how a session behaves without the communication rules,
without losing the file itself.

## What changed

`proxy_rules.json` in the GlobalRules repo (`~/.claude/shared-rules/`) lists, under
`system2_rules.main.files`, the rule files the proxy injects into a main session's system block.
One entry was removed:

- Before: `["main/communication.md", "main/tool-use.md", "main/workers.md"]`
- After: `["main/tool-use.md", "main/workers.md"]`

`main/communication.md` itself was not touched and stays on disk at 4562 bytes. The `global` and
`worker` lists were not touched. The reader, `src/proxy/rules_config.py` in monitor-cc, needed no
change — it reads the list at request time.

## When it takes effect

Not in the session that made the change. `_load_config` re-reads the JSON when its mtime changes,
so the proxy does pick the edit up without a restart, but the assembled rule block is frozen after
the first request of a session per model family. The first session started after this change is the
first one that runs without the communication rules.

## What the session loses

The file carries the turn anatomy, meaning the Exchange and Action frame formats, the German
conversation language, the one-claim-per-sentence ceiling, and the three Exchange kinds
(plain, uncertainty-informing, decision-demanding). Without it a main session falls back to
ordinary assistant prose. This was the point of the change — the user wanted to compare — but it
is worth stating so a later reader does not mistake the absence for a regression.

## A side effect of committing, worth knowing for this repo

`gcommit` stages every tracked modification plus untracked files. The GlobalRules working tree held
two uncommitted edits at the time — a rewrite of the persisted-output section in `global/tool-use.md`
to point at `poread`, and a loosening of the Exchange format in `main/communication.md` itself —
and both were swept into the same commit as the one-line JSON change. Neither was authored in this
session and neither was intended to be part of it. The commit message names only the JSON change,
so the commit's own message understates what it contains. Check `git status` in
`~/.claude/shared-rules/` before committing there; it accumulates edits between sessions more
readily than a project repo does.
