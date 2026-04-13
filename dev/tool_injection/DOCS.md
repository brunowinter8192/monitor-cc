# dev/tool_injection/

Extracts and manages MCP tool schemas for proxy-side tool injection.

## Purpose

Proxy needs stable, deterministic `tools[]` arrays in every API request to prevent cache invalidation caused by Claude Code's alphabetical tool insertion mid-session (ToolSearch / deferred-builtin lifecycle). These scripts provide the schema store that `src/proxy/tool_injection.py` reads at runtime.

## 01_extract_schemas.py

**Purpose:** Extract tool schemas from FastMCP plugin servers and write them as JSON files to `src/logs/mcp_tool_schemas/`.

**Input:**
- `/Users/brunowinter2000/Documents/ai/Meta/blank/server.py` — iterative-dev server (24 tools)
- `/Users/brunowinter2000/Documents/ai/Meta/ClaudeCode/MCP/github/server.py` — github-research server (20 tools)

Each server is loaded in an isolated subprocess using its own Python venv. If the venv doesn't exist, the script bootstraps it from `requirements.txt`.

**Output:** `src/logs/mcp_tool_schemas/<plugin>/<tool_name>.json` — one JSON file per tool, Anthropic API format:
```json
{
  "name": "mcp__plugin_<plugin>_<server>__<tool>",
  "description": "...",
  "input_schema": { ... }
}
```

**MCP prefix pattern** (verified against `src/logs/api_requests_opus_monitor_cc_1776092124.jsonl`):
- `iterative-dev` → `mcp__plugin_iterative-dev_iterative-dev__<tool_name>`
- `github-research` → `mcp__plugin_github-research_github__<tool_name>`

**Usage:**
```bash
./venv/bin/python dev/tool_injection/01_extract_schemas.py
```

Re-run whenever plugin tools change. Output is gitignored (lives in `src/logs/`).

## Stage 2 context

See `src/proxy/tool_injection.py` for how the schema store is loaded and injected into API requests at proxy time. The proxy reads from `src/logs/mcp_tool_schemas/` on first request (cached), then appends iterative-dev tools unconditionally and active plugin tools in activation order.
