# Launcher model-selection precedence dry run (2026-09-23T09:37:01Z)

**Result: 11/11 checks passed**

Pure argument-parsing simulation of src/claude_proxy_start.sh's full precedence chain
(--model > config file 'main' key > nothing injected, no CLI shortcuts since 2026-09-23)
— never starts the proxy or claude, never touches the real
~/.claude/shared-rules/model_selection.json.

| Case | Resulting CLAUDE_ARGS | Result |
|---|---|---|
| no flag, no config -> byte-identical (nothing injected) | `--extra|val` | PASS |
| explicit --model, no config -> explicit passed through | `--model|claude-custom` | PASS |
| --project alone, no config -> --project extracted, nothing injected | `` | PASS |
| no flag, valid config -> config's main model injected | `--extra|val|--model|claude-opus-5-5` | PASS |
| --project + no other flags, valid config -> --project extracted, config's main model injected (the actual real-world invocation) | `--model|claude-opus-5-5` | PASS |
| --project + other passthrough, valid config -> --project extracted, other flag kept, model appended | `--other-flag|val|--model|claude-opus-5-5` | PASS |
| explicit --model + valid config -> explicit wins, config never consulted | `--model|claude-custom` | PASS |
| missing config file -> nothing injected (falls through to no-injection case) | `--extra|val` | PASS |
| malformed JSON config -> nothing injected, no crash | `--extra|val` | PASS |
| config present but missing 'main' key -> nothing injected | `--extra|val` | PASS |
| config present with empty 'main' value -> nothing injected | `--extra|val` | PASS |
