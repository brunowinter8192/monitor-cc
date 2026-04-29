# Thinking-Audit: proxy-on vs proxy-off Vergleich

## Status Quo (IST)

Bauchgefühl in einer Session 2026-04-28: Thinking wird in proxy-on Sessions häufiger oder länger getriggered als in proxy-off Sessions. Aktuell keine empirischen Daten dazu — kein dev-Script, das pro REQ aus den Session-JSONLs in `~/.claude/projects/` die `type=thinking`-Block-Längen extrahiert und Verteilungs-Statistik (mean/median/p90/p99/% mit thinking>0) liefert.

## Evidenz

Anecdotal only. Keine Messung. Kein A/B-Vergleich.

## Recommendation (SOLL)

**Parked — keine weitere Arbeit geplant.**

Grund: der Proxy wird in jeder Session permanent genutzt (Strip-Logik, Logging, Cache-Display, Worker-Konfiguration etc. hängen alle daran). Ein Vergleich proxy-on vs proxy-off ist akademisch — es gibt keinen Realfall, in dem wir auf den Proxy verzichten würden. Selbst wenn die Vermutung stimmt (Proxy → mehr/längeres Thinking), wäre die Konsequenz nicht "Proxy abschalten" sondern eine Proxy-interne Optimierung, die unabhängig vom Vergleich planbar ist.

Wenn doch mal ein Run interessant wird (z.B. Proxy-Modifikations-Variante A vs B), ist die Implementierung trivial:
- `dev/thinking_audit/audit.py`
- Liest Session-JSONL aus `~/.claude/projects/-Users-brunowinter2000-Documents-ai-Monitor_CC/<session>.jsonl`
- Geht durch Assistant-Turn-Entries, sammelt aus `.message.content[]` alle `type=thinking`-Blöcke, summiert `len(thinking.text)` pro REQ
- Token-Counts aus `.message.usage` (output_tokens; thinking_tokens-Reservation bei adaptive ist in cache_creation_input_tokens enthalten)
- CLI `--session <id>`, `--compare <a> <b>`, Output Markdown mit Aggregat
- Self-contained, eine Datei, keine src/-Änderung

## Offene Fragen

Keine — Topic ist parked.

## Quellen

- Bead Monitor_CC-jwr (geschlossen 2026-04-28, parked statt implementiert)
