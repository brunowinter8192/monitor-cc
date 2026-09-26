# 2026-09-26 — Rules and skills become user-owned (orchestrator record)

## Context

The user's longer-term direction on 2026-09-26: move towards the agentic part. The plan is a proper
RAG setup, then a concrete case in which an agent or a team of agents gets a goal, a time budget and
every tool it needs, and works on its own. Two RAG questions were raised and parked, not decided:

- Whether to switch from one search returning 12 results to several chained searches with fewer
  results each. Orchestrator recommendation given to the user: decide this by measurement inside the
  agent case, not upfront.
- Extending the rule "search only the own project's reference collection" to the reference
  collections of all projects.

As the first step of that direction the user fixed the ownership of three things he will review
from now on: his canvas, `~/.claude/shared-rules/`, and the skills. Agents no longer edit rules or
skills themselves. An agent writes the proposed change into its process-docs, and the user applies
it. The canvas is explicitly out of scope for agents and for this hook ("braucht dich 0 zu
interessieren").

## Decisions taken with the user

| Question | Decision | Source |
|---|---|---|
| Which paths are protected? | Everything under `~/.claude/shared-rules/` and everything inside any directory named `skills` | User: "alles was in einem verzeichnis skills/ liegt blocken" |
| Existing files only, or new files too? | Both | Orchestrator, following the user's "alles ... blocken" |
| Bash-based writes? | Not covered | Orchestrator: no Bash bypass of this kind was ever observed; the rules already forbid Bash for file work |
| Workers too? | Yes | Hook is registered globally, so every Claude Code session is covered |
| Worktree copies of `skills/`? | Blocked too | Orchestrator: otherwise a worker edits a skill in its worktree and the merge bypasses the user |
| Hook form | Block (exit 2), never rewrite | One unambiguous condition, one consequence; matches the hard-rule criterion in the tool_use_safety area |

## Why a new area

The work builds on two existing areas at once: tool_use_safety (hook mechanics, block-vs-rewrite
principle) and rules_staging (holding area for proposed rule changes). Per the area rule for
work without an issue, that yields a new area, `rules_ownership`.

## Observed fact: Edit hooks fire under acceptEdits (2026-09-26)

The tool_use_safety area holds a 2026-05-22 entry reporting that a PreToolUse hook did not fire for
the Edit tool under `defaultMode: acceptEdits`. The new hook depends on Edit, so this was tested
live before implementation, in the orchestrator session, with `acceptEdits` active:

1. Created `/tmp/edit_probe/dev/probe.py` containing `x = 1`.
2. Issued an `Edit` adding `from src.probe import y`.
3. Result: blocked by `block_dev_imports_src.py` with its stderr message shown to the model; the
   file stayed `x = 1`; the fire log recorded
   `{"ts": "2026-09-26T10:33:03Z", "hook": "block_dev_imports_src", "decision": "block", "tool": "Write/Edit", "command": "/tmp/edit_probe/dev/probe.py", ...}`.

So the 2026-05-22 no-fire observation does not reproduce on this date. It is not corrected in its
own file (author-only editing); this entry is the newer statement.

## Proposed rule change for the user to apply (M2)

The orchestrator rules contain, in the Workers section under "Du editierst keinen Quellcode":

> **Docs und Skills darfst du direkt editieren.**
> - Du darfst Skills und alle Dokumentationsdateien (DOCS.md und process-docs) direkt editieren.

This contradicts the new hook. Proposed replacement:

> **Docs darfst du direkt editieren.**
> - Du darfst alle Dokumentationsdateien (DOCS.md und process-docs) direkt editieren.
>
> **Rules und Skills gehören dem User.**
> - Weder du noch ein Worker editiert Dateien unter shared-rules oder in einem Ordner skills.
> - Eine gewünschte Änderung schreibst du als Vorschlag in deine process-docs-Datei.
> - Der User übernimmt den Vorschlag selbst.

No other rule was found that grants rule or skill edits. This proposal was not applied by the
orchestrator; applying it is the user's step.

## Implementation

Built by a worker on branch `rules-hook` in monitor-cc (hook `block_rules_skills_edit.py`, smoke
test, registration for Edit and Write). The worker's own entry in this area documents the build.
Activation requires the merge to `main`, after which `hook_setup.py` registers the hook in
`~/.claude/settings.json`. Planned live verification after activation: try to Write a new file into
a `skills/` directory and into `~/.claude/shared-rules/`; both must be blocked.
