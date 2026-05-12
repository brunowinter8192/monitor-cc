# Worker Thinking-Visibility + Anti-Circling

## Problem

Sonnet-Worker verbraten bei komplexen Refactor-Tasks große Teile ihres Thinking-Budgets (REQ #11 im searxng dev-refactor-Worker am 2026-05-06: 42–43k von 64k Thinking-Tokens, ~67% des Caps, ~11min). Thinking-Inhalt ist komplett opaque — nur Signature (~191k chars) sichtbar, nicht das Reasoning. Damit nicht beurteilbar, ob das Modell produktiv arbeitet oder im Kreis denkt.

User-Constraint: Budget runterstellen ist keine Option (Reasoning-Tiefe behalten). Prompt-level "don't circle" wirkt unzuverlässig. Aktive Prävention von Circling braucht erst Visibility.

## Status Quo (verifiziert 2026-05-06)

- Worker-Spawn sendet `thinking: {type: 'adaptive', display: 'omitted'}` in raw_payload (verifiziert in `src/logs/api_requests_worker_51bdcc16_dev-refactor_1778024004.jsonl` REQ #1).
- Folge: Session-JSONL hat `thinking-block.thinking = ""` (leer), nur Signature gefüllt.
- Sonnet 4-6 würde API-default `summarized` liefern, CC-Harness überschreibt explizit auf `omitted` (GH Issue #49268, faster TTFB).
- `showThinkingSummaries: true` in `~/.claude/settings.json` reicht NICHT — steuert nur Ctrl+O Transcript-Renderer, nicht API-Request.

## Hebel — `--thinking-display summarized`

Hidden CLI-Flag setzt API-Param explizit. Verifiziert in GH Issue #49268 Comments #3, #5, #7: vorher `thinking: ""`, nachher populierte Reasoning-Summary von 200–500 Wörtern. Cost-Aufschlag praktisch null (Signature-Bytes identisch, Summary selbst ~hunderte bis wenige tausend Tokens, sub-1% des Reasoning-Budgets).

Implementation: `~/.claude/plugins/cache/brunowinter-plugins/iterative-dev/<version>/src/spawn/tmux_spawn.sh` hängt Flag an `claude`-Aufruf für jeden gespawnten Worker.

## Empfohlene Reihenfolge (nicht ausgeführt)

1. **Phase A — iterative-dev:** `--thinking-display summarized` in `tmux_spawn.sh`.
2. **Phase B — Monitor_CC:** Token-Pane Expanded-REQ-View aktuell `[N] thinking text: 0c sig:Xc`. Mit Visibility wird `text: Yc` non-zero. Render-Erweiterung: expandable Summary-Block, visuelle Hervorhebung bei Summary-Length nahe Budget-Cap, optional pro-REQ thinking-tokens-Counter im Header.
3. **Phase C — Empirische Beobachtung:** ein paar Worker-Sessions mit Summary-Visibility laufen, Patterns dokumentieren.
4. **Phase D — Anti-Circling-Strategie** auf Basis der Phase-C-Daten.

## Mögliche Anti-Circling-Hebel (zu evaluieren nach Visibility)

1. Pattern-Detection auf Summaries — bei wiederholten Reasoning-Themen Badge in Token-Pane.
2. Per-Worker Thinking-Token-Quota tracken, Alarm bei N% des Cumulativen.
3. Prompt-Engineering — "wenn Thinking-Block >X Tokens, breche ab" (Wirksamkeit unklar).
4. Budget-Adaption pro Task-Typ — komplexes Refactor=max, mechanisches Edit=high/medium (selektiv, nicht globaler Budget-Cut).

## Status

Spec only. Phase A–D nicht ausgeführt. Geparkt.

## Quellen

- GH `anthropics/claude-code` Issue #49268 — Thinking summaries missing on Opus 4.7, API-Mechanik + CLI-Flag-Workaround.
- GH `anthropics/claude-code` Issue #49322 — Opus 4.7 thinking summaries not rendered in VS Code extension.
- Direkte Verifizierung: `src/logs/api_requests_worker_51bdcc16_dev-refactor_1778024004.jsonl` + Session-JSONL `~/.claude/projects/-Users-brunowinter2000-Documents-ai-Meta-ClaudeCode-MCP-searxng--claude-worktrees-dev-refactor/07b733ef-f2c8-4d7d-9098-eaaa40931925.jsonl`.
