# 2026-10-04 — Rule changes for unattended runs (proposal for the user to apply)

## Context

The user's goal on 2026-10-04: Claude runs without him, ideally overnight. He gives a goal and a time budget in the first prompt, the agents work, and he reads the result the next morning. Plan phases run without him. Issues are created only by the model.

His concern about unattended work: in tool repos such as gh-cli and the other CLIs, a broken `main` hurts every other session. In sandbox-like projects such as trading, that risk stays inside the project.

The orchestrator read every file in `~/.claude/shared-rules/` except `situational/` and listed every place where the user is waited on. The edits were attempted with `Edit` and blocked by `block_rules_skills_edit.py` (see area rules_ownership). The full proposed text is therefore recorded here, and the user applies it.

## Why a new area

The work builds on rules_ownership (who edits rules) and rules_staging (holding area for rule proposals). Building on two areas yields a new area, `autonomy`.

## Observed state of shared-rules on 2026-10-04

- `main/workers.md` has an uncommitted user change: the block "Docs und Skills darfst du direkt editieren" is deleted. None of the proposals below are applied.
- Commit `84e37d5` ("send the full prompt, no file pointers") already forbids pointing workers at prompt files on `send`. The user still observed worker messages of the form `Read /tmp/task-gapturn-continue-msgs.md completely and follow it.` on 2026-10-04.

## Places where the user is waited on (inventory)

| # | File | Place | Effect on an unattended run |
|---|---|---|---|
| 1 | main/workers.md | Phase 1 gate after every step, five STOP markers | Run halts five times before any code is written |
| 2 | main/workers.md | Phase 1 Step 1 "Arbeite extrem eng mit dem User" | Scope is fine, but out-of-scope findings have no path |
| 3 | main/workers.md | Phase 1 Step 3 Stage 2 point 5 "in Zusammenarbeit mit dem User" | Gaps need the user although the orchestrator has RAG, GitHub, Reddit, web |
| 4 | main/communication.md | Decision-requiring exchange | Run halts on every open decision |
| 5 | global/testing.md (twice), main/tool-use.md | Verification fails twice, repetition budget exceeded, RAG search fails twice | Whole run halts until morning |
| 6 | main/workers.md | Session-Recap: "Nur der User kann entscheiden wann eine Session endet" plus STOP | Run never finishes on its own |
| 7 | main/issues.md | Issues only on user request or in recap | No way to park work mid-cycle |
| 8 | main/workers.md | Session-Recap Phase 2 Step 6, merge to main and push for every repo | Unattended merge into tool repos |

## Proposed changes

Each block: target file, exact old text, exact new text.

### P1 — Phase 1 gates become self-checks (workers.md)

Old:
```
**Die Steps laufen sequenziell mit einem Gate nach jedem Step.**
- Stelle nach jedem Step die Befunde dar und warte auf Anmerkungen, bevor du fortfährst.

**In der Planungsphase ist die Chatausgabe nicht auf Exchanges und Action Frames begrenzt.**
- Gib aus, was die Vorlage des Steps sagt.
```
New:
```
**Die Steps laufen sequenziell, und jeder Step endet mit einer Selbstprüfung.**
- Am Ende eines Steps prüfst du selbst die genannten Bedingungen, du wartest nicht auf den User.
- Ist eine Bedingung nicht erfüllt, arbeitest du im Step weiter, bis sie erfüllt ist.
- Ist eine Bedingung aus eigener Kraft nicht erfüllbar, legst du ein Issue nach § Issues an und setzt mit dem Rest des Scopes fort.

**In der Planungsphase ist die Chatausgabe nicht auf Exchanges und Action Frames begrenzt.**
- Gib aus, was die Vorlage des Steps sagt, damit der User den Lauf im Nachhinein nachvollziehen kann.
```
Plus: replace every `🛑 STOP. An diesem Punkt soll` in Phase 1 with `✅ SELBSTPRÜFUNG. An diesem Punkt soll`. The conditions listed under each marker stay unchanged; they are already checkable by the model.

### P2 — Scope stays bound to the prompt, out-of-scope becomes an issue (workers.md, Phase 1 Step 1)

Old:
```
**Arbeite extrem eng mit dem User, keine Arbeit geht über seinen Prompt hinaus.**
- Ist der Scope dieses Zyklus gesetzt, wird nicht mehr davon abgewichen, es sei denn es ist explizit vom User gewünscht.

🛑 STOP. An diesem Punkt soll grob umrissen sein was dieser Zyklus erreichen soll.
```
New:
```
**Der Prompt des Users ist der feste Kontaktpunkt, und keine Arbeit geht über ihn hinaus.**
- Der Prompt setzt das Ziel und, falls angegeben, das Zeitbudget.
- Ist der Scope dieses Zyklus gesetzt, wird nicht mehr davon abgewichen, es sei denn es ist explizit vom User gewünscht.
    - Ein Fund außerhalb des Scopes wird ein Issue nach § Issues.

✅ SELBSTPRÜFUNG. An diesem Punkt soll grob umrissen sein was dieser Zyklus erreichen soll.
```

### P3 — Gaps are closed by the model (workers.md, Phase 1 Step 3 Stage 2)

Old:
```
- Melde anschließend kurz im Chat, welche Lücke sich über RAG schließt und welche offen bleibt.
- Kein Treffer in RAG heißt nicht, dass die Lücke extern nicht zu schließen ist, es heißt nur, dass das Material noch nicht indexiert ist.

🛑 STOP.

5. Schließe die offen gebliebenen Lücken in Zusammenarbeit mit dem User.
```
New:
```
- Melde anschließend kurz im Chat, welche Lücke sich über RAG schließt und welche offen bleibt.
- Kein Treffer in RAG heißt nicht, dass die Lücke extern nicht zu schließen ist, es heißt nur, dass das Material noch nicht indexiert ist.

5. Schließe die offen gebliebenen Lücken selbst, über externe Quellen oder Experimente in dev/.
    - Eine Lücke, die nur der User schließen kann, wird ein Issue nach § Issues.
```

### P4 — Decisions are taken by the model (communication.md)

Replace the whole subsection `##### Entscheidung fordernder Exchange` (heading through its style block) with:
```
##### Entscheidung fordernder Exchange

**Eine Entscheidung triffst du selbst, nach deiner eigenen Empfehlung.**
- Du hast nachgedacht und Alternativen abgewogen.
- Du teilst die Entscheidung über den Exchange mit Unsicherheiten mit.

**Nur eine Entscheidung, die beim User liegt, wird ein Issue nach § Issues.**
- Eine Entscheidung liegt beim User, wenn der Prompt sie nicht abdeckt und sie den Scope selbst verändert.
- Das Issue nennt die Alternativen und deine Empfehlung.
- Danach setzt du den Turn mit allen Arbeitsblöcken fort, die von der Entscheidung unabhängig sind.

**Stil für den Hinweis auf ein solches Issue**
```
🛑 **Question?** (Issue #<n>)
- elaboration
```
```

### P5 — Failures park a milestone instead of halting the run

global/testing.md, repetitions. Old:
```
    - Benachrichtige im Chat den User oder den Main Agent und gehe sofort idle.
```
New:
```
    - Als Worker benachrichtigst du den Main Agent und gehst sofort idle.
    - Als Main parkst du den Milestone als Issue nach § Issues und setzt mit den unabhängigen Milestones fort.
```

global/testing.md, verification. Old:
```
- Scheitert eine Verifikation zweimal, so werden alle Aktionen sofort gestoppt und du reportest im Chat.
	- Was wurde getestet.
	- Welche Symptome wurden beobachtet.
	- Welche Hypothesen drängen sich auf die das beobachtete Verhalten erklären.
```
New:
```
- Scheitert eine Verifikation zweimal, werden alle Aktionen an diesem Milestone sofort gestoppt.
    - Als Worker reportest du an den Main Agent, als Main legst du ein Issue nach § Issues an.
	- Was wurde getestet.
	- Welche Symptome wurden beobachtet.
	- Welche Hypothesen drängen sich auf die das beobachtete Verhalten erklären.
- Milestones, die vom gescheiterten unabhängig sind, laufen weiter.
```

main/tool-use.md, rag-cli search. Old:
```
- Nach zwei Fehlschlägen stoppst du und meldest es dem User.
```
New:
```
- Nach zwei Fehlschlägen gilt die Lücke als über RAG nicht schließbar, und du gehst zur nächsten externen Quelle über.
```

### P6 — The session ends on its own (workers.md, Session-Recap)

Old:
```
**Der Session-Recap läuft am Ende der Session.**
- Nur der User kann entscheiden wann eine Session endet.
- Das Ende eines Zyklus ist kein Trigger für einen Session-Recap.
```
New:
```
**Der Session-Recap läuft am Ende der Session.**
- Die Session endet, wenn der Scope aus dem Prompt des Users erledigt ist oder das Zeitbudget abgelaufen ist.
    - Ruft der User das Ende aus, endet die Session ebenfalls.
- Das Ende eines Zyklus ist kein Trigger für einen Session-Recap, solange der Scope offene Zyklen hat.
- Der Recap ist der Bericht, den der User nach dem Lauf liest.
```
In Phase 1 — RECAP: delete the `🛑 STOP.` after the template, and change the last template block to:
```
**Differenz zwischen Arbeitsaufträgen und Abgeschlossenem**
- Issue #X angelegt
-...

**Werkzeug-Repos, die auf den Merge durch den User warten**
- <repo> auf Branch integration
```

### P7 — Issues are created only by the model (issues.md)

Old:
```
**Issues werden an genau zwei Punkten innerhalb einer Session erstellt.**
- Punkt eins, wenn der User mitten in der Session danach fragt.
- Punkt zwei, im Recap am Sessionende.
```
New:
```
**Issues legt ausschließlich das Modell an, und zwar jederzeit im Zyklus.**
- Anlass eins: Ein Teil des Zyklus erfordert eine explizite Entscheidung des Users und lässt sich ohne sie in der Session nicht abschließen.
- Anlass zwei: Während des Zyklus fällt etwas an, das außerhalb seines Scopes liegt.
- Einen anderen Anlass gibt es nicht.
```

### P8 — Autonomy level per repo (workers.md)

New subsection under `## Kernregeln`, before `### Lebenszyklus eines Workers`:
```
### Autonomiestufe

**Jedes Repo trägt eine von zwei Autonomiestufen, und sie entscheidet allein über den Abschluss nach `main`.**
- Alles vor dem Merge nach `main` läuft in beiden Stufen ohne den User.
- Ein Werkzeug-Repo ist ein Repo, von dem andere Sessions zur Laufzeit abhängen.
    - Beispiele sind jedes Repo unter `~/Documents/ai/Meta/`, jedes Repo mit `.claude-plugin/plugin.json`, `~/.claude/shared-rules` und `monitor-cc`.
    - Ein Fehler auf `main` eines Werkzeug-Repos legt alle anderen Sessions lahm, deshalb merged hier der User.
- Ein Sandbox-Repo ist jedes andere Repo.
    - Ein Fehler bleibt im Projekt, deshalb merged und pusht das Modell selbst.
```
Session-Recap Phase 2, old:
```
6. Schließe Git für jedes Repo, das diese Session angefasst hat, einschließlich projektübergreifender Ziele.
    6.1 Führe pro Repo `git checkout main && git merge integration` aus, dann push.
    - Prüfe vor dem Push auf `.claude-plugin/plugin.json`. Existiert sie, nutze `plugin-publish`, ansonsten nutze `git push`.
```
New:
```
6. Schließe Git für jedes Repo, das diese Session angefasst hat, einschließlich projektübergreifender Ziele, nach seiner Autonomiestufe.
    6.1 Sandbox-Repo: Führe `git checkout main && git merge integration` aus, dann `git push`.
    6.2 Werkzeug-Repo: Die Arbeit bleibt auf `integration`, du mergst und pushst nicht.
    - Nenne jedes Werkzeug-Repo im Recap, damit der User den Merge übernimmt.
```
The `plugin-publish` line disappears here because plugin repos are tool repos by definition and never pushed by the model.

### P9 — Send never points at a file (workers.md, Interaktion mit Workern)

Append to `**Sende per `send` immer den vollständigen Prompt.**`:
```
- Die Prompt-Datei unter `/tmp/` gilt ausschließlich für `spawn`.
    - Eine Nachricht der Form `Read /tmp/<file> completely and follow it.` ist bei `send` verboten, unabhängig von der Länge des Prompts.
```
Hypothesis, not verified: Phase 2 Step 2 tells the orchestrator to write the spawn prompt to `/tmp/spawn-worker-<project>-<name>.md`, and the orchestrator carries this pattern over to `send`. Two other possible sources, also unverified: sessions started before commit `84e37d5`, or a skill text outside shared-rules.

### P10 — Information quality without the user (workers.md and main/tool-use.md)

Both were raised by the user on 2026-10-04 as part of the autonomy direction.

RAG over all reference collections. workers.md, table in Phase 1 Step 3 Stage 2 point 4, old row:
```
| Externes Material des Projekts | `<Project>-reference` |
```
New row:
```
| Externes Material aller Projekte | jede Collection aus `rag-cli list_collections --filter reference` |
```

Source code first. workers.md, Phase 1 Step 3 Stage 2, append after "Bevorzuge immer externe Ressourcen ...":
```
- Geht es um das Verhalten fremder Software, ist ihr Quellcode die erste externe Quelle.
    - Issues, Discussions und Doku ergänzen den Quellcode, sie ersetzen ihn nicht.
```
Observed trigger, 2026-10-04: the orchestrator first loaded GitHub issues for Ghostty "input text" and Excalidraw. Only after the user asked whether reading source code made more sense did it read the Ghostty source via `gh-cli get_file_content`; Excalidraw 0.18 was already on disk in the project.

## Kept on purpose

- Step 1 scope binding: the first prompt stays the only fixed contact point.
- The merge to `main` of tool repos stays with the user (P8). This is the deliberate safety boundary for unattended runs.
- `show` only on user request: irrelevant for unattended runs.

## Open after this proposal

- The time budget is named in P2 and P6, but no mechanism measures it. A run started via cron would need the budget in its first prompt, and the orchestrator would need the start time.
- No unattended run has happened yet. The first real run will show which of these rules still halt or misfire.
