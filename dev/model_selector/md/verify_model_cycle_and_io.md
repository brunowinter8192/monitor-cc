# Models tab: cycle and I/O verification

8/8 strands passed

## PASS _strand_model_cycle

## 1. Model cycle logic (5 values)
claude-opus-5 -> claude-opus-5-5
claude-opus-5-5 -> claude-fable-5
claude-fable-5 -> claude-fable-5-1
claude-fable-5-1 -> claude-sonnet-5
claude-sonnet-5 -> claude-opus-5
Last value wraps to first: True
Unrecognized current value starts cycle at first choice: 'claude-opus-5'

## PASS _strand_effort_cycle


## 2. Effort cycle logic
low -> medium
medium -> high
high -> low
Last value wraps to first: True
Unrecognized current value starts cycle at first choice: 'low'

## PASS _strand_max_tokens_cycle


## 3. max_tokens cycle logic
32000 -> 64000
64000 -> 128000
128000 -> 32000
Last value wraps to first: True
Unrecognized current value starts cycle at first choice: 32000

## PASS _strand_thinking_cycle


## 4. Thinking toggle logic (2 states)
off -> on: {'type': 'adaptive', 'display': 'summarized'}
on -> off: {'type': 'disabled'}
Toggling twice returns to the original state: True
_thinking_is_enabled reads True for the on-state, False for the off-state

## PASS _strand_model_selection_io


## 5. model_selection.json atomic write
Written file contents: {'main': 'claude-fable-5', 'worker': 'claude-opus-5'}
No leftover .tmp file: True

## 6. model_selection.json read-back + fallback
Valid file -> ('claude-fable-5', 'claude-opus-5')
Missing file -> ('claude-opus-5-5', 'claude-sonnet-5') (expected default pair, no raise)
Malformed file -> ('claude-opus-5-5', 'claude-sonnet-5') (expected default pair, no raise)
Unrecognized-but-valid value file -> ('claude-hand-edited-9000', 'claude-opus-5') (expected preserved verbatim)
Apply without cycling round-trips unchanged -> ('claude-hand-edited-9000', 'claude-opus-5')

## PASS _strand_proxy_rules_format_fidelity


## 7. proxy_rules.json serializer format fidelity
Unmodified round-trip byte-identical to fixture: True

## PASS _strand_proxy_rules_read_modify_write


## 8. proxy_rules.json read-modify-write
Full-file output matches expected read-modify-write exactly: True
Foreign top-level section ('future_section') byte-preserved: True
Untouched model entry ('claude-fable-5') byte-preserved: True
Second untouched model entry ('claude-untouched-9') byte-preserved: True
Touched main entry (claude-opus-5) updated, thinking now disabled: {'thinking': {'type': 'disabled'}, 'effort': 'medium', 'max_tokens': 128000}
Missing worker entry (claude-sonnet-5) created with established shape: {'thinking': {'type': 'adaptive', 'display': 'summarized'}, 'effort': 'low', 'max_tokens': 32000}
No leftover .tmp file: True

## PASS _strand_proxy_rules_malformed_fallback


## 9. proxy_rules.json malformed file is never overwritten
Write from malformed file raised JSONDecodeError: True
Malformed file left byte-identical on disk: True
No leftover .tmp file: True
