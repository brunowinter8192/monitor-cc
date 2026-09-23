# Models tab — cycle + I/O verification — 2026-09-23T11:37:03

## 1. Model cycle logic (5 values)
claude-opus-5 -> claude-opus-5-5
claude-opus-5-5 -> claude-fable-5
claude-fable-5 -> claude-fable-5-1
claude-fable-5-1 -> claude-sonnet-5
claude-sonnet-5 -> claude-opus-5
Last value wraps to first: True
Unrecognized current value starts cycle at first choice: 'claude-opus-5'

## 2. Effort cycle logic
low -> medium
medium -> high
high -> low
Last value wraps to first: True
Unrecognized current value starts cycle at first choice: 'low'

## 3. max_tokens cycle logic
32000 -> 64000
64000 -> 128000
128000 -> 32000
Last value wraps to first: True
Unrecognized current value starts cycle at first choice: 32000

## 4. Thinking toggle logic (2 states)
off -> on: {'type': 'adaptive', 'display': 'summarized'}
on -> off: {'type': 'disabled'}
Toggling twice returns to the original state: True
_thinking_is_enabled reads True for the on-state, False for the off-state

## 5. model_selection.json atomic write
Written file contents: {'main': 'claude-fable-5', 'worker': 'claude-opus-5'}
No leftover .tmp file: True

## 6. model_selection.json read-back + fallback
Valid file -> ('claude-fable-5', 'claude-opus-5')
Missing file -> ('claude-opus-5-5', 'claude-sonnet-5') (expected default pair, no raise)
Malformed file -> ('claude-opus-5-5', 'claude-sonnet-5') (expected default pair, no raise)
Unrecognized-but-valid value file -> ('claude-hand-edited-9000', 'claude-opus-5') (expected preserved verbatim)
Apply without cycling round-trips unchanged -> ('claude-hand-edited-9000', 'claude-opus-5')

## 7. proxy_rules.json serializer format fidelity
Unmodified round-trip byte-identical to fixture: True

## 8. proxy_rules.json read-modify-write
Full-file output matches expected read-modify-write exactly: True
Foreign top-level section ('future_section') byte-preserved: True
Untouched model entry ('claude-fable-5') byte-preserved: True
Second untouched model entry ('claude-untouched-9') byte-preserved: True
Touched main entry (claude-opus-5) updated, thinking now disabled: {'thinking': {'type': 'disabled'}, 'effort': 'medium', 'max_tokens': 128000}
Missing worker entry (claude-sonnet-5) created with established shape: {'thinking': {'type': 'adaptive', 'display': 'summarized'}, 'effort': 'low', 'max_tokens': 32000}
No leftover .tmp file: True

## 9. proxy_rules.json malformed-file fallback
Write from malformed file did not raise; result parses as valid JSON: True
Fresh model_params created for both selected models, thinking states applied: ['claude-opus-5', 'claude-sonnet-5']

RESULT: PASS — model/effort/max_tokens cycles step + wrap correctly; the thinking toggle flips between exactly the on (adaptive/summarized) and off (disabled) states; model_selection.json write is atomic with exact 2-key schema, read-back correct for valid/missing/malformed files, unrecognized values preserved verbatim; proxy_rules.json serializer reproduces the real on-disk convention byte-for-byte, Apply's read-modify-write touches only the two selected models' effort/max_tokens/thinking (foreign sections/keys/models byte-identical, missing entries created with the established thinking-block shape, malformed file degrades to a fresh minimal file without raising).
