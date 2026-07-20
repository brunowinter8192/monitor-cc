# Strip tool_use/tool_result + Cache-BP-Verschiebung

## Idee

Worker sterben am Context-Limit. `tool_use` + `tool_result`-Blöcke sind die voluminösesten Teile im Message-Array. Spekulation (User): Cache-Breakpoint NACH `tool_use`+`tool_result` setzen, AI-thinking/text drauf laufen lassen, in nächster REQ die tool_*-Blöcke aus messages strippen → Context wächst nicht mehr unbegrenzt, thinking/text als Memory bleibt erhalten.

## Hypothese (Opus, unverifiziert)

Würde Cache invalidieren. Cached prefix ist `messages[0..K]` (Bytes bis BP). REQ N enthält `tool_use`+`tool_result` an Index <K → cached. REQ N+1 strippt sie → andere Bytes vor K → Cache-Miss → CC für den ganzen messages-Prefix. `tools`+`system` bleibt cached (separater BP), aber `messages` ist der größte Block. Effekt: 100% messages-Rebuild pro REQ — vermutlich teurer als jetziges Akkumulieren.

## Verifikation nötig (vor Implementation)

- Live-Messung: 2 REQs aufeinander, eine mit normaler Akkumulation, eine mit Strip-and-Move-BP. CR/CC vergleichen.
- Anthropic Doku `PromptCaching*.md` prüfen — gibt es Mechanismen wo BP "verschoben" werden ohne Rebuild?

## Status

Spec only. Verifikations-Messung nicht durchgeführt. Idee geparkt — Hypothese deutet stark auf "teurer als Akkumulation" hin; bevor Implementation lohnt sich erst die kleine Messung.

## Wo (falls reaktiviert)

- `src/proxy/strip_*.py` (Strip-Hook)
- `proxy_rules.json` (BP-Steuerung über `sent_cache_breakpoints`)
- `sources/PromptCaching*.md`
