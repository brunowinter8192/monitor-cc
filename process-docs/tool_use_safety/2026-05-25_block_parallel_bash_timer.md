# Parallel Bash + Sleep-Timer — Empirical Investigation (2026-05-25)

**Status:** Hook NOT implemented. Investigation produced an empirical finding that made the proposed hook redundant. Document preserved as decision record.

**Outcome:** strict canonical timer form in workers-1.md + existing `block_unauthorized_background.py` are sufficient. No new hook needed.

---

## Triggering Evidence

RAG-Session 2026-05-25 ~20:46. Opus dispatched in EINER Assistant-Response zwei getrennte Bash-tool_use-Blocks:

```
Block 1 (foreground): worker-cli send eval-sweep2 "<Go Phase B prompt>"
Block 2 (run_in_background=true): sleep 480 && echo "8min check eval-sweep2 Phase B"
```

Beobachtetes Verhalten: erster Block lief durch, zweiter Block kam mit Exit 143 (SIGTERM) zurück. Opus interpretierte die exit-143-Return als "Timer gestartet" und ging in Idle — tatsächlich war kein Timer aktiv, kein Wake-Up kam. Reine Observability-Lücke.

Erster Eindruck: "two parallel Bash tool_uses → CC dispatcher killt den zweiten mit SIGTERM, egal ob BG oder FG". Geplanter Hook: erkennen wenn ≥2 Bash + ≥1 Timer-Form, blocken mit klarer Stderr.

---

## Tieferes Investigation — Was Wirklich Passierte

User-Frage in der Session: "war dann das problem vllt doch das die sleeps foregrounded wurden?"

`hook_firing.jsonl` Eintrag aus genau diesem Zeitstempel:

```json
{"ts": "2026-05-25T19:02:50Z", "hook": "block_unauthorized_background",
 "decision": "rewrite", "tool": "Bash",
 "command": "sleep 480 && echo \"8min check eval-sweep2 Phase B\"",
 "rewritten": "run_in_background: true → false"}
```

Der Timer-Command matched NICHT die strikte canonical Regex `^\s*sleep\s+\d+(?:\.\d+)?\s*&&\s*echo\s+done\s*$` weil mein typisches Echo-Pattern `echo "<descriptive text>"` benutzt — nicht das literale `echo done`. `block_unauthorized_background.py` rewriter den Timer also silent von Background zu Foreground.

Damit war die tatsächliche Lage zum Dispatch-Zeitpunkt: zwei FOREGROUND-Bash-tool_uses in derselben Response. Nicht "BG-Timer + FG-Bash" wie ursprünglich gedacht.

---

## Rules-Inconsistency Discovered

Drei Rule-Dateien hatten drei verschiedene canonical-Forms:

| Datei | Zeile | Form |
|---|---|---|
| `workers-1.md` | 331 | `sleep N && echo 'check'` (gequoteter deskriptiver Text) |
| `workers-2.md` | 68 | `sleep 600 && echo done` (literal `done`) |
| `tool-use.md` | 162 | `sleep N && echo done` (literal `done`) |

Der Hook `block_unauthorized_background._CANONICAL` matched nur Form 2/3 strikt. Opus drifted zu Form 1's Pattern und darüber hinaus zu noch deskriptiveren Echos. Resultat: jeder Timer wurde silently rewritten zu FG.

**Fix:** `workers-1.md:331` auf strict canonical `echo done` literal angeglichen. Alle drei Rule-Dateien jetzt konsistent. User-Direktive: "einfach die fehlerquellen und variablem immer klein halten."

---

## Empirical Test — CC Dispatcher BG vs FG Behavior

Vor Hook-Bau die offene Frage: ist die parallel-Bash-SIGTERM ein generischer Mechanismus oder gilt sie nur für FG+FG?

Test-Setup (mit temporär entferntem block_parallel_bash_timer aus settings.json):

```python
# Bash 1 (foreground)
echo "FG test marker" && date +%H:%M:%S.%N

# Bash 2 (background, strict canonical)
sleep 5 && echo done   # run_in_background=true
```

Beide in derselben Assistant-Response dispatched.

**Resultat:**

```
Bash 1: "FG test marker\n22:08:18.257674000"           — exit 0, returned sofort
Bash 2: "Command running in background with ID: blbwa5clw" — bg_id assigned, NO SIGTERM
```

Der BG-Timer überlebte. Nach 5s schrieb er sein `done` in die bg-output Datei. Kein exit 143.

**Schlussfolgerung:** CC's Dispatcher unterscheidet sehr wohl BG von FG. Die SIGTERM-Kollision passiert nur bei FG+FG in derselben Response. BG+FG ist sicher. Der ursprüngliche Schaden war also NICHT die parallel-tool_use Mechanik generell — es war konkret dass der nicht-canonical Timer von block_unauthorized_background silent zu FG umgeschrieben worden war, wodurch FG+FG entstand.

---

## Why No Hook

Die geplante `block_parallel_bash_timer.py` hätte gefeuert wenn ≥2 Bash + ≥1 strict canonical Timer in einer Response stehen. Aber genau dieses Pattern ist empirisch SICHER — BG+FG funktioniert. Der Hook würde einen False-Positive auf eine nachweislich harmlose Konstellation produzieren.

Die existierende Schutzkette reicht:

1. **Rule** (workers-1, workers-2, tool-use jetzt konsistent): Timer ist immer `sleep N && echo done` literal
2. **block_unauthorized_background**: rewriter jeden non-canonical Background-Call zu Foreground — das ist ein lautes Signal (visible exit 143 wenn er gegen anderen FG-Bash kollidiert) dass die Rule verletzt wurde
3. **tool-use Rule 6**: "one Bash tool_use BLOCK per assistant response" — generelle Disziplin

Discipline + bestehender Rewrite-Hook deckt die Damage-Klasse ab. Ein zusätzlicher Hook der den canonical Fall blockiert wäre ein klassisches "viel zu breit" — genau das was in dieser Session der User über False-Positives anmerkte.

---

## Was Wir Behalten

- **workers-1.md:331 strict-canonical Update** — produktivste Änderung dieser Session. Eliminiert das Drift-Pattern an der Quelle.
- **Diese Investigation-Aufzeichnung** als Decision-Record: warum der Hook NICHT gebaut wurde, was die empirische Evidence war.
- **`block_unauthorized_background.py` unverändert** — macht den Job richtig, war nie das Problem.

## Was Wir Verworfen

- `src/hooks/block_parallel_bash_timer.py` — gelöscht (war kurz committet, dann verworfen)
- `dev/hook_smoke/test_block_parallel_bash_timer.py` — gelöscht
- Hook-Registrierung in `hook_setup.py` — entfernt
- Einträge in `src/hooks/DOCS.md` und `dev/hook_smoke/DOCS.md` — entfernt

## Lehre für künftige Hook-Vorschläge

Vor jedem Hook-Bau: empirisch verifizieren dass das Damage-Pattern tatsächlich auftritt UND dass die geplante Detection-Region exakt mit der Damage-Region zusammenfällt. Wenn die existierende Schutzkette das echte Problem schon abdeckt — Schweigen ist besser als ein redundanter Hook der False-Positives erzeugen kann.
