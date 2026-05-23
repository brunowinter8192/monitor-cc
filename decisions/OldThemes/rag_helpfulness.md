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

## Phase B — Auto-Metrics Run (2026-05-20)

### Implementation

`dev/tool_use_analysis/rag_query_audit.py` (350 LOC, commit `36b2c54`) — extracts all `rag-cli search_hybrid/search/search_keyword` calls from proxy logs, clusters per session via greedy chain-link (token-Jaccard ≥ 0.20, stopwords excluded), computes auto-metrics, writes report-MD mit manual annotation columns left as `_`.

Auto-metrics: `query_count`, `follow_up` (bool: count > 1), `result_chars`, `chunk_count` (per query, from tool_result content), `top_k`, `collection`, `truncated` (CC 5k/5k split signature).

Manual columns für Review: `hit_quality` (Brauchbar / Zu-eng / Zu-breit / Miss) per query, `classification` (WIN-RAG / WIN-Direct / Tie) per topic.

CLI: `--jaccard T` (default 0.20) — User kann bei Review mit anderen Thresholds re-runnen.

### Run-Output Snapshot

Report: `dev/tool_use_analysis/20260520_rag_query_audit.md`.

| Metric | Value |
|---|---|
| Sessions analyzed | 15 (10 mit rag-cli usage, 5 mit 0 calls) |
| Total events | 2957 |
| Unique rag-cli calls | 44 |
| Unique topics (jaccard ≥ 0.20) | 36 |
| Single-query topics | 31 |
| Multi-query (follow-up) topics | 5 |
| Calls in follow-up rounds | 13 / 44 (29%) |
| Misses (chunk_count = 0) | 8 |
| Truncated results | 1 |
| Calls ohne tool_result | 13 (data gap — vermutlich Bash compound calls verlieren tool_use_id pairing) |
| Collections | Monitor_CC-meta (30), Monitor_CC-features (12), RAG-meta (2) |

Sampling-Bias: alle 44 calls sind `search_hybrid`. `search_keyword` / `search_dense` wurde nie genutzt. RAG-Multi-Model nicht.

### Was direkt sichtbar (vor Manual-Annotation)

- Spitzenreiter Follow-up: **T024** mit 4 queries (cursor rects/edges) — wahrscheinlichstes "RAG couldn't find" Signal
- **T028** (DOCS pattern audit, 3 queries, alle 0 chunks) — strong WIN-Direct candidate
- Echte Misses (kleine result_chars + 0 chunks): T001, T002, T013, T015, T020, T028 (3 queries)

### Was noch offen

- Manual annotation der `hit_quality` + `classification` Spalten in `20260520_rag_query_audit.md` — Folge-Session
- Daraus Regelverfeinerung "RAG-First wenn X, direct wenn Y" in `workers-1.md` § RAG-First on Code Exploration
- Daten-Gap-Investigation: 13/44 (30%) calls ohne tool_result — bei Re-Run prüfen ob Extractor Bug (Bash compound mit mehreren rag-cli's) oder echtes "result missing in log"

## Sources

- `src/logs/api_requests_opus_monitor_cc_*.jsonl` — Proxy-Log Datenquelle für rag-cli Aufruf-Extraktion
- `dev/tool_use_analysis/rag_query_audit.py` — extraction + clustering + metrics + report writer
- `dev/tool_use_analysis/20260520_rag_query_audit.md` — run-output (auto-metrics + leere manual columns)
- `~/.claude/shared-rules/opus/workers-1.md` § RAG-First on Code Exploration — aktuelle Hard Rule
- Bead `Monitor_CC-3d7y` — tracker (offen für manual annotation)

## Session 2026-05-23 — Tool Inventory + Use-Case Audit

### CLI-Tool-Inventur (post-reduction)

`rag-cli` auf 9 Subcommands reduziert (war 11). `search` (pure semantic) und `search_keyword` (BM25) entfernt — in 44 Calls über 15 Sessions nie genutzt.

| Subcommand | Purpose |
|---|---|
| `search_hybrid` | Dense + sparse Fusion; default für alle Queries |
| `list_collections` | Collections auflisten mit `--filter` |
| `list_documents` | Dokumente in Collection auflisten (`--filter`, `--document`) |
| `progress` | Indexierungs-Fortschritt |
| `read_document` | Chunk-Kontext lesen (`--before N`, `--after N`) |
| `delete` | Collection oder Dokument löschen |
| `status` | Server-Health (Embedding/Reranker/Splade) |
| `update_docs` | Re-Indexierung aus `.rag-docs.json` |
| `server` | Server-Presets verwalten (start/stop/restart/list/status) |
| ~~`search`~~ | REMOVED — pure semantic, 0/44 Calls |
| ~~`search_keyword`~~ | REMOVED — BM25-only, 0/44 Calls |

### Standard-Use-Case-Profil

Befunde aus Phase-B-Auswertung (44 Calls, 15 Sessions, 36 Topics):

- **100 % hybrid** — alle 44 Calls `search_hybrid`; Removal von `search`/`search_keyword` datengetrieben
- **86 % single-query** (31/36 Topics) — Opus reformuliert selten; Recall-Lücken durch fehlende Follow-ups
- **14 % multi-query** (5/36 Topics, 13 der 44 Calls) — Follow-up-Rate als Recall-Proxy-Signal
- **8 echte Misses** (chunk_count = 0): T001, T002, T013, T015, T020, T028
- **Collection-Split:** Monitor_CC-meta 30 Calls (68 %), Monitor_CC-features 12 Calls (27 %), RAG-meta 2 Calls (5 %)
- **13 Calls ohne tool_result** (29 %) — Data-Gap, wahrscheinlich Bash-compound-ID-Mismatch im Extractor

### Collection-Inhalts-Mapping

| Collection | Inhalt | Usage (44 Calls) |
|---|---|---|
| `Monitor_CC-meta` | decisions/, DOCS.md-Dateien, CLAUDE.md, sources/sources.md | 30 (68 %) |
| `Monitor_CC-features` | decisions/OldThemes/ | 12 (27 %) |
| `Monitor_reference` | 337 Chunks Anthropic API Docs (s.u.) | 0 (0 %) |

### Reference-Collection als Hebel

`Monitor_reference` enthält 337 Chunks Anthropic API Docs: AdaptiveThinking, PromptCaching, ExtendedThinking, ContextEditing, ProgToolCalling, Citations, Files, ContextWindow, Compaction, FastMode, FineGrained, Effort, Msgs, PDF_support u.a. In keinem der 44 Calls je befragt — 0 % Nutzungsrate.

Use-Case-Beispiele für Misses die dort Treffer hätten ergeben können: T001/T002 (Prompt-Caching-Verhalten → `PromptCaching`-Chunks vorhanden), T015/T020 (Context-Window-Verhalten → `ContextWindow`/`Compaction`-Chunks). Die Collection ist indexiert und bereit — fehlend ist die Rule, sie aktiv bei API-Docs-Fragen zu befragen.

### Naming-Drift

`Monitor_reference` weicht vom Konsistenz-Pattern ab: `RAG_reference`, `searxng_reference` → korrekte Form wäre `Monitor_CC_reference`. `_CC` beim initialen Reindex weggelassen. Fix: beim nächsten Reindex Collection umbenennen → `Monitor_CC_reference`.

### Best-prod-Config (aus RAG-Projekt-Eval)

| Parameter | Wert | Evidenz |
|---|---|---|
| Fusion | CC α=0.8 | +3 pp Snippet Recall vs RRF — `decisions/retrieval03_fusion.md (RAG)` |
| Reranking | False (default off) | Technische Docs: −8.5 pp NDCG@3; Doc Recall +4 pp, Snippet −1 pp + ~2 s Latenz — trade-off rejected — `decisions/retrieval04_reranking.md (RAG)` |
| HYBRID_CANDIDATES | 50 dense + 50 sparse | — |
| top-k Default | 12 | Korrigiert von "20 (10–50 valid)" in shared-rule |

### Pending (Folge-Session)

- **Manual Annotation** — 36 Topics in `dev/tool_use_analysis/20260520_rag_query_audit.md`; `hit_quality` + `classification` Spalten ausfüllen → Regelverfeinerung "RAG-First wenn X, direct wenn Y"
- **Audit-Script Bug-Fix** — 13/44 Calls (29 %) ohne tool_result in `dev/tool_use_analysis/rag_query_audit.py` klären (Bash-compound-ID-Mismatch?)
- **Replay-Probe der 8 Misses** — dieselben Queries gegen `Monitor_reference` feuern; prüfen ob Anthropic-Docs-Chunks die Lücken schließen
- **Collection Rename** — `Monitor_reference` → `Monitor_CC_reference` beim nächsten Reindex
