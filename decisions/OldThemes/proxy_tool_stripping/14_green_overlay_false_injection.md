# Green-Overlay False-Injection — Investigation (2026-06-04)

Status: NOT fixed. Strong hypothesis, final reproduction on exact real input PENDING. Investigation paused (scope-cut at session end).

## Symptom

Proxy pane colors UNCHANGED content green (=injected). Confirmed live: req#169 msg[336] tool_result — `arm64\n\n` rendered green although it is byte-identical in original AND forwarded; only the trailing `<system-reminder>…</system-reminder>` was stripped (yellow). The green should only mark genuinely-injected content; unchanged content must be grey.

## Evidence (write-side, not renderer)

`_injected` dual-log for that block (`messages_delta["336"]["0"]`) stores the span list:
- `["equal", "{\"tool_use_id\": …, \"type\": \"tool_result\", \"content\": …"]`
- `["injected", "arm64\n\n\","]`   ← unchanged `arm64\n\n` mis-tagged injected
- `["equal", "\"is_error\": false}"]`

So the diff engine itself tags `arm64\n\n",` as injected. The renderer is CORRECT: `render_messages.py` / `render_sections.py` set `bg = DIM_GREEN_BG if tag == "injected" else ""` — equal spans stay grey. → bug is in the WRITE side (`diff_engine._diff_text`).

## Root-cause hypothesis (strong, not final-verified)

`_diff_text` (`src/proxy/diff_engine.py`) word-level path: `ow, fw = orig_text.split(), fwd_text.split()` then difflib opcodes, spans rebuilt via `" ".join(...)`.

The diff runs on the SERIALIZED block JSON, where content newlines are escaped as literal `\n` (backslash+n, 2 chars — NOT real whitespace). `str.split()` only breaks on REAL whitespace, so a run like `arm64\n\n",` (no real spaces) stays ONE token. That token differs from the original's corresponding token (`arm64\n\n<system-reminder>…`), so difflib classifies the whole token — including the unchanged `arm64\n\n` — as insert/delete → injected/stripped.

Disconfirmation control: a synthetic `_diff_text` run using REAL newlines did NOT reproduce (real `\n` gets split by `.split()`, so `arm64` lands in an equal span). This points to the literal-escaped-`\n` in the serialized JSON as the trigger.

Note: current `src/proxy/diff_engine.py` and both frozen live-copies (`src/logs/.proxy_live_*/proxy/diff_engine.py`) have IDENTICAL `_diff_text` — not a stale-frozen-copy issue.

## Fix direction (NOT done — eval needed)

Options to evaluate:
- Tokenize so escaped-whitespace runs break at the actual change boundary (char-level, or split that also breaks on literal `\n`).
- Diff the DESERIALIZED content (tool_result.content string with real newlines) instead of the serialized JSON block.
Whitespace-fidelity tradeoff (07_stripped_injected_logs.md § Whitespace-Fidelität) interacts with any tokenization change — revisit there.

## Source refs
- `_diff_text`, `_diff_messages` in `src/proxy/diff_engine.py`
- span render: `_aggregate`-adjacent inline path in `src/proxy_display/render_messages.py` (msg blocks), `src/proxy_display/render_sections.py` (system/tools/fields)
- prior span-model work: `09_inline_span_rendering.md` (Form B equal-anchor spans)
