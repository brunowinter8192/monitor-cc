# 2026-09-14 — Where a hard rule ends and the agent's decision begins

## The question this settles

The persisted-output threshold made the boundary concrete. Claude Code persists any Bash result over
roughly 30,000 characters to a file and hands the agent a path plus a preview. That threshold is not
only a size limit, it is a prompt: do you actually need this output in full? For a whole-file read the
honest answer is yes, for a grep over a log it is no. The agent cannot be trusted to answer it
consistently, and a hard rule that answers it for every case answers it wrong for some of them.

Stated by the user on this date, after the poread route was built:

- A hard, event-based rule is right exactly when there is no doubt that one condition implies one
  consequence. That is the hook shape: the event fires, the outcome follows, and no judgment sits in
  between.
- As soon as false positives are possible, or as soon as the rule's action does not necessarily produce
  the intended consequence, the agent decides instead.
- In that second case the project does not stay neutral. It builds the instrument it wants used and
  writes a bias toward using it into the rules.

## How the two halves looked in practice

The hook half is `src/hooks/block_po_read.py`. A path under `/.claude/` ending in `.txt` that a shell
read tool touches is a persisted-output export, without ambiguity, and reading it partially is always
wrong. One condition, one consequence, no judgment: the hook blocks and names the route.

The decision half is poread. Nothing about a persisted output tells the proxy whether the content is
worth the context it will occupy for the rest of the session. A measurement over six recorded sessions
found eleven persisted outputs: four were a worker reading project files in full because it had been
told to, three were command output that should have been narrowed at the source instead, and the rest
sat in between. No rule expressible over the path or the size separates those. So poread exists, it is
the one route that works, and the bias in `shared-rules/global/tool-use.md` says to read in doubt.

## What the bias instrument is, concretely

A bias is not a preference sentence. It is a tool that makes the wanted behavior the cheap one, plus a
rule line that names the tool and tilts the default. Before poread existed, reading a persisted output
in full was impossible, so every agent that tried it failed and moved on with fragments. The rule that
said to read it in full was not a bias, it was an instruction nobody could follow.

## The failure this replaced

The earlier rule text told the agent the export MUST be read via the Read tool. That is the shape of a
hard rule applied to a case that does not qualify: it names a consequence the agent cannot always
produce. Observed twice on this date, once in a main session without the Read tool available and once
in a worker session, both times ending in the same loop — every attempt to read the export produced a
new export of the same size.
