# RAG Helpfulness Evaluation

## Status quo

Hard rule in `~/.claude/shared-rules/opus/workers-1.md` § "RAG-First on Code Exploration": RAG-cli search before any explicit `ls`/`grep`/`Read` chain when exploring unfamiliar code territory. Rationale: DOCS.md + decisions/ + CLAUDE.md are indexed — RAG gives architecture-level context in one call that would take 5-10 tool calls to reconstruct manually.

Bauchgefühl aus production sessions: wertvoll für Status-quo/decisions/DOCS-Fragen ("warum ist X so", "wo steht Y"). Weniger wertvoll wenn die Dateiposition bereits bekannt (dann `Read` direkt billiger). Noch unklar: wie gut deckt RAG Fragen ab, bei denen mehrere Konzepte kombiniert werden müssen oder bei denen der Suchbegriff nicht klar im Index-Text steht.

## Beobachtungen aus production sessions

**Queries oft zu spezifisch.** Beobachtetes Muster: Opus formuliert queries die wie "bead-comments lesen" wirken — sehr nah am unmittelbaren task-kontext, wenig semantische Variation. Beispiel: statt "NSPanel cursor rects non-key window" eher "enableCursorRects NonactivatingPanel". Das trifft Dokumente mit exakt dieser Phrase, lässt aber thematisch verwandte Chunks durch.

**Single-query-topics lassen viel durchrutschen.** Ein einziger query pro topic deckt nur einen semantischen Winkel ab. Bei mehrstufigen Sachverhalten (z.B. "warum feuert cursorUpdate_ nicht") gibt es oft keinen Chunk der alle relevanten Aspekte enthält — die Antwort setzt mehrere Chunks voraus die unterschiedliche queries triggern würden. Wenn Opus nur einen query abfeuert, bleibt Recall niedrig.

**Queries wirken wie bead-comments-lesen.** Queries spiegeln oft den aktuellen Erkenntnisstand statt offene Fragen zu stellen. Das führt zu confirmation-bias im Retrieval: gefunden wird was man schon weiß, nicht was noch fehlt. Nützlichere Query-Strategie wäre "was weiß der Index über X dass ich noch nicht weiß?" — aber das lässt sich schlecht als query formulieren.

**Konsequenz:** RAG-First ist für decisions/DOCS/architecture-Fragen klar wertvoll. Für bug-diagnosis und investigative Fragen ist der Mehrwert fraglicher — dort dominiert direktes `grep` / `Read` weil die relevante Information in code-Zeilen steckt, nicht in prose.

## Eval-Plan

**Schritt 1 — Datenextraktion aus Proxy-Logs**

Quelle: `src/logs/api_requests_*.jsonl` — enthalten alle rag-cli tool-calls der Opus-Sessions als JSON payloads. Extrahieren via dev/-script:

- Alle `rag-cli search_hybrid` / `search` / `search_keyword` Aufrufe
- Pro Aufruf: query-text, collection, top-k, session-timestamp
- Aggregieren nach topic (session-cluster): wieviele queries pro topic, welche collections, top-k Verteilung
- Signal: wieviele topics wurden mit single-query abgehandelt vs mehrfach reformuliert

**Schritt 2 — Eval-Methodologie**

Drei Bewertungsdimensionen pro query-result:

| Dimension | Messung | Signal |
|---|---|---|
| Hit-rate | Kam brauchbares im top-k zurück? | Ja/Nein per query |
| Follow-up-rate | Musste Opus nachhaken (gleicher topic, weiterer query)? | Count follow-up queries per topic |
| Recall-proxy | Wurde das relevante Dokument gefunden das hätte gefunden werden müssen? | Requires ground-truth — manuell für Sample |

Für automatische Auswertung: hit-rate + follow-up-rate aus Proxy-Logs ableitbar. Recall-proxy erfordert manuelle Annotation eines Samples (10-20 topics).

Output: report-MD mit per-session query-Inventar + Bewertung pro query (Brauchbar / Zu-eng / Zu-breit / Miss).

**Schritt 3 — Klassifizierung WIN-RAG vs WIN-Direct vs Tie**

Nach Annotation: pro topic entscheiden ob RAG oder direktes `Read`/`grep` die effizientere Strategie gewesen wäre:

- **WIN-RAG:** RAG lieferte im ersten query ausreichende Antwort; direkter Ansatz hätte 3+ tool calls gekostet
- **WIN-Direct:** Dateiposition war bekannt oder einfach inferierbar; RAG kostete zusätzliche query-round ohne Mehrwert
- **Tie:** Beides wäre vergleichbar gewesen

Ziel: Regelverfeinerung "RAG-First wenn ..., direct wenn ..." mit empirischer Basis statt Bauchgefühl.

## Trade-off Kern

**Specificity vs noise.** Spezifische queries haben hohe Precision (was zurückkommt ist relevant) aber niedrigen Recall (was fehlt wird nicht bemerkt). Breite queries erhöhen Recall auf Kosten von Noise im result-set. Mit reranker mitigierbar, aber nur wenn gute Chunks im retrieval-set sind.

**Single-query vs reformulation rounds.** 2-3 komplementäre queries pro topic (z.B. eine technische + eine konzeptuelle + eine problem-orientierte) erhöhen Recall erheblich. Kosten: 2-3x mehr tool calls für retrieval. Netto oft billiger als eine Runde `Read`-drilling, teurer als ein direktes `grep` wenn die Antwort in einer bekannten Datei steht.

**Bekannte Dateiposition als switch.** Der stärkste Prädiktor für "direct beats RAG" ist ob Opus bereits weiß welche Datei betroffen ist. Wenn ja: `Read` + `grep` direkt. Wenn nein (architecture-Frage, cross-cutting concern, "wo steht X überhaupt"): RAG-First bleibt die richtige Wahl.

## Open questions

- Welche Sample-Größe ist ausreichend für statistisch belastbare Aussagen? Schätzung: 30-50 topics aus ~10 sessions.
- Welche Topics nehmen? Repräsentativ über query-Typen (architecture / bug-diagnosis / lookup) oder gezielt die schwachen Klassen?
- Wie scoren ohne ground-truth? Proxy-Signal: follow-up-query-rate als Recall-Proxy (hohe follow-up-rate = erster query war zu eng). Limitation: Opus reformuliert nicht immer explizit.
- Muss als dev/-script orchestriert werden (nicht ad-hoc) um reproduzierbar zu sein. Output: report-MD mit per-session Inventar.
- Ist die RAG-First-Regel für workers genauso sinnvoll wie für Opus? Workers haben engeren task-scope — möglicherweise dominiert dort "bekannte Dateiposition" stärker.

## Sources

- `src/logs/api_requests_*.jsonl` — Proxy-Log Datenquelle für rag-cli Aufruf-Extraktion
- `~/.claude/shared-rules/opus/workers-1.md` § RAG-First on Code Exploration — aktuelle Hard Rule
