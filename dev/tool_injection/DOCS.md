# dev/tool_injection/

## Role
Extracts MCP tool schemas for the proxy-side tool-injection schema store, keeping the tool arrays of API requests stable and deterministic. Touch when a plugin's tool set changes; `src/proxy/` reads the produced schema files at runtime.

## Public Interface
No `__init__.py`. Entry point: `python3 dev/tool_injection/01_extract_schemas.py`. `ToolsSystemPrompts/` is a captured reference corpus, not a script.

## Flow
Loads each configured MCP plugin server in an isolated subprocess with its own venv, extracts each tool's name, description and input schema, and writes one JSON file per tool.

## Modules

### 01_extract_schemas.py (141 LOC)

**Purpose:** Extracts tool schemas from the configured FastMCP plugin servers into the proxy schema store in Anthropic API format.
**Reads:** each plugin's server file in a sibling checkout outside this project, loaded in its own venv.
**Writes:** one JSON file per tool in the proxy schema store under `src/proxy/` (gitignored generated data).
**Called by:** none; manual CLI, re-run when plugin tools change.
**Calls out:** the plugin servers' own venvs, subprocess-isolated.

---

## Sub-directories

- `ToolsSystemPrompts/`: captured reference corpus, no `.py` modules. See its own `DOCS.md`.

## State
None owned. Output goes to the proxy schema store under `src/proxy/`, owned and read at runtime by the proxy tool-injection module.
