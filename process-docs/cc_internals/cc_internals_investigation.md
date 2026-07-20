# CC Source Code Investigation — Tracker

## Hintergrund

2026-04-28: Research-Worker hat in 2 Passes über GH-Issues + Source-Leak-Repos + binäre Extraktion (v2.1.121) 12+ undokumentierte Env-Vars gefunden, den Watchdog-Mechanismus aufgedeckt, 429/529-Handling und Fast-Mode-Cooldown reverse-engineered. Output: `dev/cc_source_research/20260428_env_var_inventory_v2.1.121.md` (205 LOC, 67 confirmed env vars in 5 Kategorien + 8 Dead-Code-Fragmente).

Erkenntnis: CC-Binary + Leak-Repos sind eine reichhaltige, weitgehend unausgeschöpfte Quelle. Investigations-Thread mit vielen Sub-Fragen, pro Sub-Frage ein Worker-Pass.

## Status der Sub-Fragen

### Erledigt

1. **Vollständige Env-Var-Inventur (v2.1.121)** — `dev/cc_source_research/20260428_env_var_inventory_v2.1.121.md`. Latency-Subset Recommendations für `settings.json:env` dokumentiert (`CLAUDE_STREAM_IDLE_TIMEOUT_MS=300000`, `CLAUDE_ENABLE_STREAM_WATCHDOG=1`, `CLAUDE_ENABLE_BYTE_WATCHDOG=1`, `CLAUDE_SLOW_FIRST_BYTE_MS=8000`). 6 Open Questions im MD.

### Offen (priorisiert)

**Hoch — direkte Latency-Hebel:**

2. **CC-Verhalten gegenüber mitmproxy** — HTTPS_PROXY env-reads, TLS/Cert-Validation, Anti-MitM/Cert-Pinning, Header-Diffs, Stream/SSE-Health-Probes. Erster Worker-Versuch im April: Context-Limit erreicht ohne Task-Start. Frischer Worker pro Sub-Frage nötig.
3. **Cache-Control-Logik** — wie entscheidet CC welche Messages cached werden, ephemeral vs persistent, Cache-Key-Composition. Komplementär zu Latency-Track.
4. **Background-Task / async-agent Delivery** — `<task-notification>`-Injection-Mechanismus (v2.1.121 verwendet TN, NICHT mehr `[SYSTEM NOTIFICATION]` SR), Race-Conditions, Buffer-Größen. Hinweis: `CLAUDE_ASYNC_AGENT_STALL_TIMEOUT_MS` deutet separaten Pfad an.

**Mittel — Architecture/Behavior:**

5. Model-Selection-Routing (`--fallback-model`, `FALLBACK_FOR_ALL_PRIMARY_MODELS`, fast-mode-cooldown-state-machine).
6. Context-Compaction-Logik (Pruning-Heuristiken bei vollem Window).
7. Tool-Definition-Loading (deferred tools, ToolSearch, Skill activation, Lazy-Load).
8. Telemetry-Pipeline (`tengu_*`-Events, Endpoints, blockierbar?).

**Niedrig — exploratory:**

9. Hidden Features / Codenames (`02-hidden-features-and-codenames.md` aus Decompile-Repo).
10. Plan-Mode-Interna (SR-Templates, Übergangs-Logik).
11. Hooks-System (Lifecycle-Phasen, Race-Conditions).

## Lehre — Worker-Reuse für Recherche

cc-perf-research Worker hatte Sub-1 + 2 vorherige GH-Recherche-Passes erledigt → Context aufgebraucht beim Sub-2-Start. **Recherche-Sub-Fragen sind individuell context-heavy** (Binary-Extract + GH-Suche): max 1–2 pro Worker-Lifetime. Frischer Worker pro Sub-Frage planen.

## Approach (wenn reaktiviert)

- Pro Sub-Frage ein Worker-Pass mit github-search Skill aktiv.
- Output als markdown-Section unter `dev/cc_source_research/`.
- Findings mit konkretem Fix-Bedarf → eigener Bead.
- Findings nur als Wissen → Investigation-Doc.
- Wiederverwendete Quellen (Decompile-Repos, Binary-Versionen, NPM-Tarballs) → `sources/sources.md`.

## Out of Scope

- Anthropic API Server-side Internals (kein Source verfügbar).
- Modell-Internals.
- Ad-hoc Bugfixing aus Findings → eigener Bead, nicht hier.

## Cross-Project Spillover

Worker schrieb tool-wishlist nach `/Users/brunowinter2000/Documents/ai/Meta/ClaudeCode/MCP/github/decisions/OldThemes/research_tool_wishlist_20260428.md`. Reibungspunkte: npm-Binary-Extract-Kette (9 calls, 205MB), Comment-Pagination-Blindheit auf #26224 (30/90), Versions-Awareness fehlt in Repo-Search (post-leak vs pre-leak Vars).

## Quellen

- GH Issues #49500, #33949, #26224.
- Decompile-Repos (alanisme, thepono1 INSIGHTS).
- Binary-Strings v2.1.121 (lokal extrahiert in `/tmp/package/claude` zum Investigation-Zeitpunkt).
