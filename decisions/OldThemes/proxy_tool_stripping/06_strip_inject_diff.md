# Strip/Inject Span-Diff — Original↔Forwarded (Step 2+3 Verifikation)

Build step 2026-06-02. Reine dev/-Analyse — keine src/-Änderung, keine Monitor-Änderung.
Verifiziert am frischen Paar `api_requests_opus_monitor_cc_1780442876`.

## Kern-Erkenntnis: Ein Diff, beide Farben

Strip-Highlighting (gelb) und Inject-Highlighting (grün) kommen aus DEMSELBEN Diff:
Original↔Forwarded. Delete-Spans = gestrippt (gelb), Insert-Spans = injiziert (grün).
Block-level-Vergleich (`original_block vs forwarded_block`) hätte nicht gereicht — sys[2]
z.B. **strippt** den CC-Prompt UND **injiziert** die Rules im gleichen Block. Erst der
Text-Span-Diff innerhalb eines ausgerichteten Block-Paares trennt Strip von Inject sauber.

## Alignment-Strategie

- **system:** per Index. Extra-Orig-Index = ganz gestrippt; extra-Fwd-Index = ganz injiziert.
- **tools:** per Name. Nur-in-Orig = Tool komplett gestrippt; Nur-in-Fwd = Tool komplett injiziert;
  In-beiden = Description/Schema span-diffen.
- **messages:** per Index (outer). Within-message (wenn content beides listen): per Block-Position
  (inner). Extra-Orig-Block = gestrippt; Extra-Fwd-Block = injiziert.

## difflib-Granularität

**Wort-Ebene wenn `SequenceMatcher.ratio() >= 0.1`** (echte Teil-Edits, z.B. cache_control-Suffix
an einem 55k-base64-Bild-Block angefügt — ratio ≈ 1.0, nur die letzten Wörter ändern sich).

**Zwei-Span-Voll-Ersetzung wenn `ratio < 0.1`** (ein stripped-Span + ein injected-Span für den
ganzen Block). Begründung: sys[2] hat ratio ≈ 0.0038 (CC-Prompt vs Rules — kein gemeinsamer Text
der inhaltlich relevant wäre). Wort-level würde tausende sinnlose Einzel-Wort-Spans erzeugen.
Unabhängige Verifikation (Opus Spot-Check): ratio 0.0038 bestätigt + Identität von stripped-Text
(CC-Prompt) und injected-Text (Rules) bestätigt.

## Verifikationsergebnisse auf Paar 1780442876 (8 Requests, 2 haiku + 6 opus)

**sys[2] (REPLACED, ratio≈0.0038):**
- stripped: -7471 chars — `\nYou are an interactive agent that helps users with software engineering tasks…`
- injected: +130375 chars — `# Communication\n\nTwo principles for chat with the user: **drive** and **be honest**…`

**sys[3] (REPLACED):**
- stripped: -5511 chars — CC CLAUDE.md/gitStatus block
- injected: +1 char — `"."` (Proxy-Ersatz)

**Haiku sys[2] (REPLACED):** Gleiche Behandlung — Title-Generation-Prompt (-1159c) → `"."` (+1c).

**model (OVERRIDE, jeder opus-Request):** `claude-opus-4-7` → `claude-opus-4-8` sichtbar als Feld-Diff.

**tools:** 4 komplett gestrippt (Agent, AskUserQuestion, ScheduleWakeup, ToolSearch);
5 Descriptions auf "" reduziert (Bash -10665c, Edit -1094c, Read -1782c, Skill -1315c, Write -618c).
Keine injizierten MCP-Tools in dieser Session.

**msg[0] pro Request (3 SR-Blöcke → Platzhalter):**
- block[0]: SR deferred-tools (-599c) → `"."` (+1c)
- block[1]: SR skills (-5777c) → `"."` (+1c)
- block[2]: SR env-context (-373c) → `"\n"` (+1c)
- block[3]: user-text IDENTICAL ✓

**REQ#5+ msg[4] (hook-error-prefix-Strip erkannt):**
- stripped: `"PreToolUse:Read hook error: [python3 …]:` Prefix — korrekt als Strip-Span isoliert
- injected: sauberer PDF-Pfad

**REQ#8 msg[8] block[4] (55k-base64-Bild, ratio≈1.0 → wort-level):**
Vier vorangehende Blöcke IDENTICAL (130359c, 194243c, 204439c, 204439c).
Word-level-Diff isoliert korrekt nur den cache_control-JSON-Suffix als geändert
(`false}` → `false, "cache_control": {"type": "ephemeral", "ttl": "1h"}}`).
Wort-Level trägt hier: ratio ~1.0, einzelne Wortänderung am Ende — kein Block-Replace.

**Span-Counts pro opus-Request:** sys -2/+2 | tools -9/+0 | msgs -3…-9/+3…+9 (wächst mit neuen Turns).

## Tool

`dev/proxy_dual_log/diff_strip_inject.py` — reine Analyse, nur lesend.
Reconstruction: inline der verify_delta.py-Kettenlogik (self-contained, kein Import).
Matching: per request_id; Fallback chain-order per model_family.

## Ausblick

Diese Engine (ratio-Threshold + block-alignment + span-Klassifikation) ist die Grundlage für
grün/gelb im Monitor-Proxy-Pane: strip_vocab.py + proxy_display wissen bereits welche
Modifikationen aufgetreten sind (`modifications[]` im log entry) — der Span-Diff liefert
jetzt die TEXT-Koordinaten für die Färbung. Nächste Iteration: Monitor-Leseseite konsumiert
`_original` als Basis und `_forwarded` für die Overlay-Farben.
