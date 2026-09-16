## Salvage from dev/tool_injection/01_extract_schemas.py

```
# Verified against src/logs/api_requests_opus_monitor_cc_1776092124.jsonl
```

```
# Server definitions: (plugin_name, server_path, server_project_dir, venv_dir)
# venv_dir: which Python venv to use for extraction subprocess
```

```
# Inline helper: executed in each server's subprocess — prints JSON array of schemas to stdout
```

```
    """Extract MCP tool schemas from both plugin servers and write JSON files."""
```

```
# Ensure server venv exists with required packages; returns path to venv python3.
```

```
# Invoke server extraction in a clean subprocess. Returns list of Anthropic-format schema dicts.
```

```
# Write each schema as a separate JSON file; returns count of files written.
```

## Salvage from dev/tool_injection/DOCS.md

Nothing cut — the pre-existing `## Role`, `## Flow`, and `## Modules` sections already fit the required format. The pre-existing `## Gotchas` section has no home in the new fixed format and moved here in full:

```
## Gotchas
- Plugin server paths are hardcoded to a sibling checkout outside this project (a `Meta` directory
  next to `monitor-cc`) — this script only runs on a machine where that checkout exists at the
  expected location.
- MCP tool name prefixing follows a fixed pattern per plugin (e.g. `iterative-dev` tools become
  `mcp__plugin_iterative-dev_iterative-dev__<tool_name>`) — verified against a real captured proxy
  log at the time this script was written; a plugin naming change would need re-verification.
```

## Notes for successor

- 1 file, 7 comments + 1 docstring — matches the measured state exactly. Note the docstring is NOT a module docstring — this file has none — it is a **function** docstring, on `extract_schemas_workflow()` (the ORCHESTRATOR function itself), one line: `"""Extract MCP tool schemas from both plugin servers and write JSON files."""`. Easy to miss if only checking for a module-level triple-quoted string at the top of the file.
- No load-bearing docstring: grepped `__doc__` — zero hits, no `argparse` in this file at all. Docstring deleted outright.
- **Not run**: this script bootstraps real Python venvs via `pip install` (network-dependent), loads real MCP plugin server code from a hardcoded sibling checkout outside this project (`~/Documents/ai/Meta/...`, may not even exist on another machine), and — if it runs to completion — overwrites the real production tool-injection schema cache at `src/proxy/schemas/<plugin>/*.json`, which `src/proxy/tool_injection.py` reads at proxy runtime. None of this is sandboxed or safe to trigger as a side effect of a comment-stripping milestone. Classified as unsafe to run.
- Verification: token-skeleton diff (see `dev/bead_tracker/smoke.py`'s salvage notes, same session, same method) — `tokenize` output with `COMMENT` tokens and the one function-docstring's exact `ast`-located span stripped, plus structural tokens (`NL`/`NEWLINE`/`INDENT`/`DEDENT`/`ENCODING`/`ENDMARKER`) dropped. Before/after token sequences are byte-identical.
