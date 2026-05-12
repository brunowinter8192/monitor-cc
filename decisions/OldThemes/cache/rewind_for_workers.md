# /rewind für Worker — Cache-Behavior

## Frage

Worker sterben am Context-Limit. Anthropic `/rewind` setzt in Main-Session den Conversation-State auf früheren REQ zurück — bei Opus ohne Cache-Rebuild, weil cached prefix im 5-Min-TTL noch existiert. Funktioniert das Feature ähnlich cache-freundlich für Worker?

## Hypothesen

- **V1:** Jeder Worker hat eigene conversation_id → eigener Cache-Scope → `/rewind` im Worker nutzt cached prefix wie Main-Opus → Hebel funktioniert.
- **V2:** Worker und Main teilen Cache-Scope → `/rewind` im Worker referenziert REQ aus anderer Conversation → uncached → Rebuild → kein Hebel.

User-Verdacht: V2 ("die worker teilen sich einen cache pro projekt mit dir [Main] weil du der einzige main in dem projekt bist").

## Verifikations-Test (klein, ungedeckt)

1. Worker spawnen, 5–10 REQs Akkumulation aufbauen.
2. `/rewind` im Worker auf REQ N (z.B. N=3 von 10).
3. Nächste REQ feuern, `cache_read` messen.
4. ≈ prev_REQ_3's prefix → V1. ≈ 0 → V2.
5. Vergleich zu Main-Session-Rewind als Baseline.

## Status

Spec only. Test nicht ausgeführt. Geparkt — kein hoher Druck, weil Worker-Kontext-Management auch ohne `/rewind`-Hebel handhabbar ist (fresh spawn + AGGRESSIVE REUSE).

## Quellen

- Anthropic `/rewind` docs
- worker-cli / `src/spawn/tmux_spawn.sh`
