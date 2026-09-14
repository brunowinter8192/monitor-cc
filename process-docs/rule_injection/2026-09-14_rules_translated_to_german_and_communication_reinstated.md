# 2026-09-14 — Injected rule files translated to German; communication.md put back in the list

Main session entry. Continues this area.

## What the user asked for

Two things, mid-session. First, keep an English copy of every injected rule file. Second, translate
the injected files themselves into German, so the user can read them without working through
English. The stated purpose was reading comprehension, not a behavior change.

## What was done

`~/.claude/shared-rules/` (the GlobalRules repo) holds the rule files. The English originals were
copied to `situational/global/`, `situational/main/`, `situational/worker/` — subfolders rather
than a flat copy, because `global/tool-use.md` and `main/tool-use.md` share a filename and would
have overwritten each other. Note that `situational/` is gitignored in that repo, so those copies
exist on disk only; the English versions remain recoverable from git history regardless.

All nine injected files were then translated in place: five under `global/`, three under `main/`,
one under `worker/`. Prose was translated; paths, CLI commands, filenames, table keys, fenced code
blocks, the position-indicator strings and the chat templates (`🤔 uncertainties i had`,
`🛑 Question?`, `elaboration`) were left verbatim, because those are emitted literally and
translating them would have changed behavior rather than readability. Rule *content* is unchanged —
`documentation.md` still mandates English for all documentation artifacts, it just says so in
German now.

## communication.md was not being injected at all

`proxy_rules.json` under `system2_rules.main.files` listed only `main/tool-use.md` and
`main/workers.md`. `main/communication.md` sat on disk unreferenced, so the proxy never read it.
This area already holds an entry explaining why: it was removed deliberately, as an experiment to
see how a main session behaves without the communication rules. The user ended that experiment this
session, and the entry was put back at the head of the `main` list, before `tool-use.md`.

Practical consequence observed first-hand: the session had drifted into long spec-style prose and
the user said he could not follow it. Reading the file manually fixed the output immediately, which
is what surfaced the missing list entry in the first place.

## How the injection reads the files

`src/proxy/rules_config.py` in monitor-cc is the reader. `_read_rule_file` caches per file keyed on
the file's `mtime`, and `_load_config` does the same for `proxy_rules.json`. A content edit changes
the mtime, so the cache entry is discarded and the next read picks the new text up. No proxy
restart and no session restart is involved. Only paths listed in `proxy_rules.json` are read at
all — the folder listing is not the source of truth, and a new file in `global/` or `main/` stays
invisible until it is added to the JSON. Role decides the set: `global` + `main` for a main session,
`global` + `worker` for a worker, nothing at all for haiku.

As of 2026-09-14 the JSON list and the three folders are congruent — five, three and one file, with
no folder file missing from the list. That congruence is maintained by hand, not enforced.

## Unresolved contradiction, worth a measurement

`src/proxy/rules.py:apply_modification_rules` calls `_load_system2_rules` and rewrites the payload's
system block on **every** request, which reads as "a rule edit lands on the next request of the same
session". Another entry in this area states the opposite: that the assembled rule block is frozen
after a session's first request per model family, so only the next *session* sees the change. Both
claims cannot hold. Nothing was measured here to settle it, and no attempt was made to edit the
other entry. The clean test is a marker line added to an injected file mid-session, then checking
whether the same session's next request carries it — the dual-log `_original`/`_forwarded` pair
under `src/logs/dual_log/` makes that directly observable.
