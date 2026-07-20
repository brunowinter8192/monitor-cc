# A1 — Hook Design Principle: Use-Case-Specificity Over Generality (2026-05-28)

**Status:** Design-Prinzip, etabliert nach Spillover-Incident in dieser Session.

## Prinzip

Hooks MÜSSEN extrem use-case-spezifisch geschrieben werden, NIEMALS allgemein. Generic Hooks erzeugen Spillover-Bugs die zur Build-Zeit nicht abschätzbar sind — was heute ein "korrekt geblocktes Anti-Pattern" ist, kann in zwei Wochen einen legitimen Workflow blockieren weil sich die Tool-Surface erweitert hat.

Konkret bedeutet das:

1. **Pattern-Match auf die exakte Anti-Pattern-Signatur**, nicht auf einen umliegenden Kontext. Wenn z.B. ein Hook `sleep N` im Background blockieren soll, dann matche nur auf `run_in_background=true + sleep + numerischer Argument`. NICHT auf "background + irgendwas".

2. **Erlaubte-Liste vor Verbots-Liste.** Wenn klar ist welche Patterns OK sind, explizit whitelist. Wenn klar ist nur welche NICHT OK sind, schmal-spezifisch blocken und alles andere durchlassen.

3. **Kein Tool-Class-weites Wrappen.** Ein Hook der ALLE Bash-Calls intercepted und transformiert ist per Definition zu allgemein. Hooks müssen auf der Granularität einzelner Befehl-Pattern operieren, nicht auf der Tool-Klasse.

4. **Spillover-Test vor Aktivierung.** Bevor ein neuer Hook in die Production-Pipeline geht: schreibt der Author min. 3 Beispiele auf wo der Hook NICHT feuern soll, und verifiziert dass jedes davon durchgeht.

## Trigger-Incident (2026-05-28)

Während der Refactor-Skill-Phase-2-Scans hat Opus mehrere Python-Subprocess-Aufrufe gemacht (`python3 /tmp/refactor_funclen.py`, `python3 /tmp/refactor_state.py`, etc.) — alle als FOREGROUND-Tool-Calls (kein `run_in_background=true` gesetzt). Die Skripte sind pure AST-Walks, Laufzeit <2s pro Aufruf.

Mehrere dieser Calls wurden vom Hook `block_unauthorized_background` (oder einem verwandten) auto-rewritten in Background-Execution. Symptome:
- Tool-Result zeigte "Command was manually backgrounded by user with ID: ..." obwohl Opus nicht `run_in_background=true` gesetzt hatte
- Output der Skripte kam nicht direkt zurück, sondern in /private/tmp/.../tasks/<id>.output
- Python-Subprocess-Prozesse hingen nach Bash-Tool-Return weiterhin in der Prozess-Tabelle (PIDs 49345, 56850, 56852, 63997, 63999 wurden manuell mit `kill` aufgeräumt)
- Drei Refactor-Subscans (scripts-in-lib, dev-tooling-gap) konnten nicht durchlaufen weil der Output strukturell nicht zurück kam

Per User-Feedback: "es gibt bei hooks so schnell so krasse spill overs und ich kann vorher nie abschätzen was wir in 2 wochen für prozesse haben und ob bestehende hooks sie blockierne."

## Konsequenzen / TODOs

1. **Audit bestehender Hooks in `src/hooks/`** auf Über-Generalität. Welche Hooks würden 3+ legitime Workflows in den nächsten Wochen blockieren?

2. **Konkret zu reviewen — `block_unauthorized_background`:** das Pattern-Matching ist zu breit, fängt Foreground-Calls. Entweder schärfer auf "background-marker + non-canonical-sleep" einschränken oder als Klassen-Hook deaktivieren und Use-Case-spezifisch ersetzen.

3. **Konkret zu reviewen — `block_broad_grep` etc.:** alle "block_*"-Hooks gegen den 3-Beispiele-Spillover-Test laufen lassen.

4. **Neuer Hook-Design-Standard in iterative-dev Plugin:** vor jedem neuen Hook MUSS der Author die 3-Whitelist-Beispiele dokumentieren. CI-Check optional.

## Cross-Reference

Dieses Prinzip ist plugin-übergreifend relevant (iterative-dev, Monitor_CC src/hooks, andere Projekt-Hook-Sammlungen). Sollte ggf. als geteilte Regel in `~/.claude/shared-rules/` materialisieren, wenn das Prinzip in mehreren Projekten unabhängig verifiziert wurde.

## Quellen

- Session 2026-05-28: Refactor-Skill-Phase-2 Spillover-Beobachtung (siehe Session-Log)
- User-Statement: "hooks in zukunft nur noch extrem use case spezifisch und niemals allgemein"
- Project hooks: `src/hooks/block_unauthorized_background.py`, `src/hooks/block_broad_grep.py`, weitere `block_*.py` siehe `src/hooks/DOCS.md`
