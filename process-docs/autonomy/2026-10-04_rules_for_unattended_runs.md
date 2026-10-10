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
**Die Steps laufen sequenziell, Step 1 und Step 2 enden mit einem STOP, ab Step 3 endet jeder Abschnitt mit einer SELBSTPRÜFUNG.**
- Bei einem STOP wartest du auf Anmerkungen des Users, bevor du fortfährst.

**Eine SELBSTPRÜFUNG ist eine Liste kritischer Fragen an dich.**
- Jeder Punkt unter einer SELBSTPRÜFUNG ist eine Frage.
- Du beantwortest jede Frage gedanklich, bevor du weitergehst.
- Kannst du eine Frage nicht beantworten, spawnst du einen frischen Worker.
    - Du übergibst ihm die vollständige Problematik, inklusive deiner Zweifel.
- Gibt dir der Worker einen neuen Anstoß, mit dem du die Frage beantworten kannst, gehst du weiter.
- Gibt er dir keinen, legst du ein Issue nach § Issues an.

**In der Planungsphase ist die Chatausgabe nicht auf Exchanges und Action Frames begrenzt.**
- Gib aus, was die Vorlage des Steps sagt, damit der User den Lauf im Nachhinein nachvollziehen kann.
```
### P1a — Step 3 Stage 1: STOP becomes SELBSTPRÜFUNG (workers.md, end of "Stage 1 durchsuche die DOCS.md über RAG und lies relevante Module")

Old:
```
🛑 STOP. An diesem Punkt soll:
                    - Grob umrissen sein welches Ziel der Zyklus erreichen soll.
                    - Der bisherige Prozess im Projekt klar sein, und wie er mit dem was der Zyklus erreichen soll zusammenhängt.
                    - Der Code vollständig erschlossen sein, sofern er einen Einfluss auf das was der Zyklus erreichen soll hat.

#### Stage 2 Lücken identifizieren.
```
New:
```
✅ SELBSTPRÜFUNG
                    - Ist der Code vollständig erschlossen, sofern er Einfluss auf das Ziel des Zyklus hat?

#### Stage 2 Lücken identifizieren.
```

### P1b — Step 3 Stage 2: STOPs become one SELBSTPRÜFUNG (workers.md, end of "Stage 2 Lücken identifizieren", just before `---` and Phase 2)

This block replaces the numbered list of Stage 2 down to the end of Phase 1. It also contains P3 and the table row of P10; both are done once this block is applied. The explanatory text of Stage 2 above the list ("Eine Lücke ist ein Informationserfordernis." through "das ist IMMER möglich.") stays unchanged.

Old (from `1. Benenne gedanklich die Lücken.` down to the line before `---`):
````
1. Benenne gedanklich die Lücken.
2. Benenne gedanklich externe Quellen, um die Lücke zu schließen, zum Beispiel:
    - Papers, Bücher.
    - GitHub.
    - Reddit, Stack Overflow.
    - Websites, Dokumentationen.
3. Schreibe in den Chat die Lücken in folgendem Format.

```
Gap 1 — <gap in one line> — gh
- Suchbegriff

Gap 2 — <gap in one line> — web
- Suchbegriff

Gap 3 — <gap in one line> — reddit
- Suchbegriff 
```

4. Prüfe jede Lücke gegen das, was bereits in RAG indexiert ist.

| Inhalt | Collection |
|---|---|
| GitHub Issues | `github_issues` |
| Reddit-Posts | `reddit-cli-posts` |
| Externes Material des Projekts | `<Project>-reference` |

- Melde anschließend kurz im Chat, welche Lücke sich über RAG schließt und welche offen bleibt.
- Kein Treffer in RAG heißt nicht, dass die Lücke extern nicht zu schließen ist, es heißt nur, dass das Material noch nicht indexiert ist.

🛑 STOP.

5. Schließe die offen gebliebenen Lücken in Zusammenarbeit mit dem User.

🛑 STOP. An diesem Punkt soll:
                    - Grob umrissen sein welches Ziel der Zyklus erreichen soll.
                    - Der bisherige Prozess im Projekt klar sein, und wie er mit dem was der Zyklus erreichen soll zusammenhängt.
                    - Der Code vollständig erschlossen sein, sofern er einen Einfluss auf das was der Zyklus erreichen soll hat.
                    - Alle Lücken, die das Erreichen des Ziels des Zyklus erschweren oder verhindern, geschlossen sein.
````
New:
````
1. Benenne gedanklich die Lücken.
2. Prüfe jede Lücke gegen das, was bereits in RAG indexiert ist.

| Inhalt | Collection |
|---|---|
| GitHub Issues | `github_issues` |
| Reddit-Posts | `reddit-cli-posts` |
| Externes Material aller Projekte | jede Collection aus `rag-cli list_collections --filter reference` |

- Melde anschließend kurz im Chat, welche Lücke sich über RAG schließt und welche offen bleibt.
- Kein Treffer in RAG heißt nicht, dass die Lücke extern nicht zu schließen ist, es heißt nur, dass das Material noch nicht indexiert ist.

3. Spawne einen frischen Worker und übergib ihm deinen kompletten Kenntnisstand.
    - Dazu gehören das Ziel des Zyklus, der bisherige Prozess, der erschlossene Code und das Ergebnis der RAG-Prüfung.
    - Frage ihn, welche Lücken er identifiziert.
    - Gib ihm erst im Anschluss deine eigenen Lücken und frage ihn, was er davon hält.
4. Hake die Lücken des Workers gegen deine eigenen ab.
    - Eine neue Lücke des Workers prüfst du wie in 2 gegen RAG.
    - Eine reale Lücke ist jede, die nach Abgleich und RAG-Prüfung offen bleibt.
5. Benenne gedanklich externe Quellen, um jede reale Lücke zu schließen, zum Beispiel:
    - Papers, Bücher.
    - GitHub.
    - Reddit, Stack Overflow.
    - Websites, Dokumentationen.
6. Schreibe alle realen Lücken kurz in den Chat, in folgendem Format.

```
Gap 1 — <gap in one line> — gh
- Suchbegriff

Gap 2 — <gap in one line> — web
- Suchbegriff

Gap 3 — <gap in one line> — reddit
- Suchbegriff 

Gap 4 — <gap in one line> — literature
- Titel oder Suchbegriff
```

7. Aktiviere nur die Skills, die du für die offenen Lücken wirklich brauchst.
    - Maßgeblich ist die Quelle, die du in 6 an jede Lücke geschrieben hast.
    - Für `web`: Aktiviere den Skill websearch:websearch-web-research.
    - Für `reddit`: Aktiviere den Skill reddit-cli:reddit-cli-search.
    - Für `gh`: Aktiviere den Skill gh-cli:gh-cli-search.
    
8. Schließe die Lücken selbst, über Web, Reddit, GitHub oder Experimente in dev/.

**Eine Lücke, die sich nur über Papers oder Bücher schließen lässt, ist eine Literaturlücke.**
- Mit PDFs und Büchern kannst du nicht selbst arbeiten.
- Halte jede Literaturlücke in deiner process-docs-Datei fest.
- Lege für jede Literaturlücke ein Issue an.
    - Eine Literaturlücke löst der User.

✅ SELBSTPRÜFUNG
                    - Ist jede reale Lücke geschlossen oder als Literaturlücke in den process-docs und einem Issue festgehalten?
````

Step 1 and Step 2 STOPs stay unchanged.
Each self-check asks only what its own stage produced. Goal and process history are settled with the user at the STOPs of Step 1 and Step 2; the old STOP markers repeated them cumulatively, which made sense while the user re-confirmed everything at each gate, but not for a self-check.
Revision 2026-10-04, after user feedback: a first draft defined the self-check as "comparing a condition against evidence". The user rejected it: "Bedingung" and "Beleg" are unexplained words, and the points under the marker already say what to check. He defined it himself: the points are critical questions to the model; an unanswerable question goes to a fresh worker with the full problem; a new impulse from the worker means continue, none means issue. Step 1 and Step 2 keep their STOP; the rename applies from Step 3 on.

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

🛑 STOP. An diesem Punkt soll grob umrissen sein was dieser Zyklus erreichen soll.
```

### P3 — Gaps are closed by the model (workers.md, Phase 1 Step 3 Stage 2)

Merged into P1b. Skip this block if P1b is applied; it stays here only as the original proposal.

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

### P6 — Recap runs autonomously after every cycle (workers.md, whole section `## Session-Recap` to the end of the file)

Revision 2026-10-04: the user decided the recap runs autonomously after every cycle, not once at the end of the session. This block replaces the earlier P6 draft and also contains the git step of P8.

Old (from `## Session-Recap` to the end of workers.md):
````
## Session-Recap

**Der Session-Recap läuft am Ende der Session.**
- Nur der User kann entscheiden wann eine Session endet.
- Das Ende eines Zyklus ist kein Trigger für einen Session-Recap.

### Phase 1 — RECAP 🔍

1. Gehe gedanklich alle Issues durch, die in der Session bearbeitet wurden.
2. Gehe gedanklich alle Arbeitsaufträge des Users durch, die in dieser Session aufkamen.
3. Gehe gedanklich durch was tatsächlich ausgeführt und abgeschlossen wurde.
4. Präsentiere den Recap in der folgenden Form:

```
**Issues die in der Session bearbeitet wurden**
- Issue X (kann geschlossen werden)
- Issue Y (bleibt offen)
- ...

**Arbeitsaufträge in dieser Session**
- Arbeitsauftrag X
- ...

**Tatsächlich ausgeführt und abgeschlossen in dieser Session**
- ausgeführt und abgeschlossen X
- ...

**Differenz zwischen Arbeitsaufträgen und Abgeschlossenem**
- Vorschlag für neue Issue X
-...
```

🛑 STOP.

### Phase 2 — IMPROVE+CLOSE 🛠️

1. Aktualisiere alle DOCS.md, bei denen du unsicher bist ob sie formal korrekt und auf dem neuesten Stand sind.
2. Schreibe für alles tatsächlich Ausgeführte und Abgeschlossene process-docs, sofern nicht schon von Workern erledigt.
3. Erstelle Issues für die Differenz zwischen Arbeitsaufträgen und Abgeschlossenem.
4. Aktualisiere die Issue-Bodys bearbeiteter Issues bzw. schließe Issues wenn abgeschlossen.
5. Synchronisiere die Docs nach RAG mit `[ -f .rag-docs.json ] && rag-cli update_docs .`.
6. Schließe Git für jedes Repo, das diese Session angefasst hat, einschließlich projektübergreifender Ziele.
    6.1 Führe pro Repo `git checkout main && git merge integration` aus, dann push.
    - Prüfe vor dem Push auf `.claude-plugin/plugin.json`. Existiert sie, nutze `plugin-publish`, ansonsten nutze `git push`.
````
New:
````
## Zyklus-Recap

**Der Zyklus-Recap läuft autonom am Ende jedes Zyklus.**
- Ein Zyklus endet, sobald Phase 2 Step 7 für alle Milestones abgeschlossen ist.
- Du wartest an keiner Stelle des Recaps auf den User.
- Der Recap ist der Bericht, den der User nach dem Lauf liest.

### Phase 1 — RECAP 🔍

1. Gehe gedanklich alle Issues durch, die im Zyklus bearbeitet wurden.
2. Gehe gedanklich alle Arbeitsaufträge des Users durch, die zum Zyklus gehören.
3. Gehe gedanklich durch was tatsächlich ausgeführt und abgeschlossen wurde.
4. Präsentiere den Recap in der folgenden Form:

```
**Issues die im Zyklus bearbeitet wurden**
- Issue X (geschlossen)
- Issue Y (bleibt offen)
- ...

**Arbeitsaufträge in diesem Zyklus**
- Arbeitsauftrag X
- ...

**Tatsächlich ausgeführt und abgeschlossen in diesem Zyklus**
- ausgeführt und abgeschlossen X
- ...

**Differenz zwischen Arbeitsaufträgen und Abgeschlossenem**
- Issue #X angelegt
-...

**Werkzeug-Repos, die auf den Merge durch den User warten**
- <repo> auf Branch integration
```

### Phase 2 — IMPROVE+CLOSE 🛠️

1. Aktualisiere alle DOCS.md, bei denen du unsicher bist ob sie formal korrekt und auf dem neuesten Stand sind.
2. Schreibe für alles tatsächlich Ausgeführte und Abgeschlossene process-docs, sofern nicht schon von Workern erledigt.
3. Lege Issues für die Differenz zwischen Arbeitsaufträgen und Abgeschlossenem an.
4. Aktualisiere die Issue-Bodys bearbeiteter Issues bzw. schließe Issues wenn abgeschlossen.
5. Synchronisiere die Docs nach RAG mit `[ -f .rag-docs.json ] && rag-cli update_docs .`.
6. Schließe Git für jedes Repo, das dieser Zyklus angefasst hat, einschließlich projektübergreifender Ziele, nach seiner Autonomiestufe.
    6.1 Sandbox-Repo: Führe `git checkout main && git merge integration` aus, dann `git push`.
    6.2 Werkzeug-Repo: Die Arbeit bleibt auf `integration`, du mergst und pushst nicht.
````
The `plugin-publish` line disappears because plugin repos are tool repos by definition and never pushed by the model. Tool repos waiting for the user are named in the recap template.

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
The git step of the recap that uses the autonomy level is part of P6.

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

## Review format the user can work with (2026-10-04)

The Old/New blocks above were not usable for the user: he could not see where in workers.md a block belongs or what the file looks like afterwards ("so kann ich nicht arbeiten"). What works instead:

- A complete target file (`/tmp/rules-review/workers-soll.md`), built by a script that applies every replacement with an exact-count assertion to a copy of the live file. The user can replace the rule file with it as a whole.
- A rendered full-file diff as HTML (`/tmp/rules-review/workers-diff.html`, renderer `render_diff.py` in the same folder, `difflib` line opcodes): every line of the file, removed lines on red background, added lines on green, opened in the browser via `open`.
- Markdown was the user's first wish, but `show` opens `.md` in CotEditor, which renders raw text without background colour; HTML is the only format here that shows red/green highlighting.

Diff base used: the last commit of shared-rules (`git show HEAD:main/workers.md`), so the user's own uncommitted edits of P1, P1a, P1b appear as changes too. While applying P1b the user removed the explanatory text of Step 3 Stage 2 ("Eine Lücke ist ein Informationserfordernis." through "das ist IMMER möglich."); the target file keeps that removal, and the source-code sentence of P10 moved under the gap-closing step.

## Proposal stored as patches, viewed with patchview (system date 2026-10-10)

The system clock showed 2026-10-04 at session start and 2026-10-10 later in the same session; dates in this file follow the clock at the time of writing.

- The proposal now lives as plain `diff -u` patches against the live rule files: `dev/autonomy/patch/workers.md.patch` and `dev/autonomy/patch/tool-use.md.patch`. The P-blocks above are the history of how the text came about; where they differ from the patches, the patches are authoritative.
- `patchview <patch>` (iterative-dev `bin/`, symlinked into `~/.local/bin`; area patchview in iterative-dev) applies the patch to the live file read-only and renders the whole target file, removed lines on red, added on green, no +/- signs so copied text is clean. A patch that no longer matches fails with `STALE PATCH`.
- Observed stale case: the user deleted the block "Sende per `send` immer den vollständigen Prompt." from workers.md while the patch was being created; patchview refused hunk 2 (P9). P9 was dropped from the proposal because the block it extended no longer exists.
- workers.md patch also contains a new recap step: rule or skill change proposals are justified by one observed misbehaviour traced to a rule or skill text, or by a user work order touching a rule or skill; they consist of a patch in `dev/<area>/patch/`, process-docs and an issue.
- tool-use.md patch adds a `patchview` section: run it only when the user asks to see a proposal, because it always opens the browser.
- The user was disrupted by windows opening unasked (browser opened three times during verification). Verification of a page happens without a window: `python3 <iterative-dev>/src/patchview/__main__.py <patch>` prints the page path and opens nothing.

## Outcome (system date 2026-10-10)

The user applied the proposal himself, largely but with his own wording:
- Applied: Phase 1 STOP only after Step 1 and Step 2, SELBSTPRÜFUNG from Step 3 on, gap search with RAG first then a fresh worker, skill activation per needed source, literature gaps as issues, the recap step for rule and skill proposals, issues for the difference, the `patchview` section in main/tool-use.md.
- Rejected: the autonomy levels (Werkzeug-Repo / Sandbox-Repo). The user called them nonsense. The recap git step now reads only "Schließe Git für jedes Repo, das dieser Zyklus berührt hat." without saying whether to merge to main or push.
- Kept by the user: the heading and trigger of the recap still say "Session-Recap ... am Ende der Session", "Nur der User kann entscheiden wann eine Session endet", "Das Ende eines Zyklus ist kein Trigger", while the body speaks of the cycle. This contradicts his statement in this session that the recap runs autonomously after every cycle; it was reported to him, not changed.
- The patches in `dev/autonomy/patch/` were removed after application; git history holds them.
