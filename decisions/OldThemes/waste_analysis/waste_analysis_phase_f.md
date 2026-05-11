# Waste-Call Analyse + Phase F (Git-Wrapper) — Abgeschlossen 2026-04-22

## Status Quo (IST)

Tool-Use Waste-Tracking läuft live im Monitor (Window 4, waste_pane). Ratio-basiert (input_chars / output_chars ≥ threshold). Threshold per Digit-Key 1-9 einstellbar.

### Umgesetzte Maßnahmen (Bead 6ja, Sessions 2026-04-21 bis 2026-04-22)

1. **Tool-Description Strip (Phase E):** Proxy strippt `tools[*].description` (top-level + `input_schema.properties[*].description`) zu `""`. Pre-strip Originals im JSONL geloggt. Display zeigt `[STRIPPED]` + dim-yellow Expand. Einsparung: ~15.8k chars pro Request (von ~19.7k strippbar, ~80% Reduktion).

2. **sys[3] Strip:** Proxy ersetzt `system[3].text` (claudeMd-Block) durch `"."`. Pre-strip Original geloggt. Display zeigt `[STRIPPED]` + dim-yellow. Einsparung: ~3k chars pro Request.

3. **MCP→CLI Migration:** 4 MCP-Tools (worker_spawn, worker_send, worker_merge, worker_status) zu CLI-Wrappern migriert. MCP-Server + venv gelöscht. Tool-Count im Payload: 11 → 7.

4. **tool-use Skill Consolidation (Phase C):** `tool-usage.md` + `git-commit-workflow.md` + `worker-cli` Skill in einen konsolidierten `tool-use` SKILL.md zusammengeführt. 3 Quell-Dateien gelöscht.

5. **`c` Shorthand (aus qfr):** `worker-cli` und `git-check` akzeptieren `c` als project_path Argument (resolves zu aktuellem Git-Root). Eliminiert wiederholte absolute Pfade.

6. **`worker-cli status --all` (aus qfr):** Snapshot aller aktiven Worker in einem Call statt N einzelne Status-Aufrufe.

## Phase F — Git-Wrapper-Batterie (gmv, gst, gd, gadd, gp)

### Evidenz

Waste-Report `dev/tool_use_analysis/20260422_session_waste_patterns.md` (6 Proxy-JSONLs, 562 tool_use Blöcke):

| Wrapper-Kandidat | Count | Total Waste Input | Bewertung |
|---|---|---|---|
| `gst` (git status + branch) | 3 | 626 chars | Marginal — 3 Aufrufe über 6 Sessions |
| `gl` (git log --oneline) | opportunistisch | — | Kein messbarer Count |
| `gmv`, `gd`, `gadd`, `gp` | 0-1 | <200 chars je | Keine Count-basierte Evidenz |

### Entscheidung

**Closed — kein Handlungsbedarf.** Die großen Hebel (worker-cli c-shorthand, status --all, Tool-Description-Strip, MCP-Removal) sind umgesetzt. Die verbleibenden Git-Wrapper-Kandidaten haben Count=1-3 über 6 Sessions — kein systematischer Waste-Pattern. Falls sich organisch ein Pattern zeigt (z.B. gst taucht in 5+ Sessions als Top-Offender auf), kann in 5 Minuten ein Wrapper gebaut werden.

### Quellen

- `dev/tool_use_analysis/20260422_session_waste_patterns.md` — Aggregierte Waste-Analyse
- `dev/tool_use_analysis/extract_patterns.py` — Script für Pattern-Extraktion
- `dev/ToolsSystemPrompts/_review.md` — Tool-Description Strip-Analyse (Phase B)
