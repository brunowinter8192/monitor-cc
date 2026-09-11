# dev/tool_injection/

## Role
Extracts MCP tool schemas for the proxy-side tool-injection schema store, needed to keep `tools[]`
arrays stable and deterministic in every API request — Claude Code's alphabetical/deferred-builtin
tool insertion mid-session would otherwise invalidate the cache. Touch when a plugin's tool set
changes; the produced schema files are what `src/proxy/tool_injection.py` reads at proxy runtime.

## Flow
Loads each configured MCP plugin server in an isolated subprocess (its own venv, bootstrapped from
its own requirements if missing), extracts each tool's name/description/input_schema, and writes one
JSON file per tool.

## Modules

### 01_extract_schemas.py (130 LOC)

**Purpose:** Extracts tool schemas from FastMCP plugin servers (iterative-dev, github-research) and
writes them as `src/proxy/schemas/<plugin>/<tool_name>.json` in Anthropic API tool-schema format.
**Reads:** each plugin's `server.py` (paths outside this project, in a sibling `Meta` checkout — see
Gotchas), loading each in its own venv (bootstrapped from that plugin's `requirements.txt` if
missing).
**Writes:** `src/proxy/schemas/<plugin>/<tool_name>.json` (gitignored, lives under src/logs
conceptually as generated runtime data).
**Called by:** none — manual CLI, re-run whenever plugin tools change.
**Calls out:** the target plugin servers' own Python venvs (subprocess-isolated, not an import
dependency of this repo).

---

## Gotchas
- Plugin server paths are hardcoded to a sibling checkout outside this project (a `Meta` directory
  next to `monitor-cc`) — this script only runs on a machine where that checkout exists at the
  expected location.
- MCP tool name prefixing follows a fixed pattern per plugin (e.g. `iterative-dev` tools become
  `mcp__plugin_iterative-dev_iterative-dev__<tool_name>`) — verified against a real captured proxy
  log at the time this script was written; a plugin naming change would need re-verification.
