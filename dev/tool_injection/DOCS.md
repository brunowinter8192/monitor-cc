# dev/tool_injection/

## Role
Extracts MCP tool schemas for the proxy-side tool-injection schema store, needed to keep `tools[]`
arrays stable and deterministic in every API request — Claude Code's alphabetical/deferred-builtin
tool insertion mid-session would otherwise invalidate the cache. Touch when a plugin's tool set
changes; the produced schema files are what `src/proxy/tool_injection.py` reads at proxy runtime.

## Public Interface
No `__init__.py` in this directory. Entry point is direct invocation: `python3 dev/tool_injection/01_extract_schemas.py`.

## Flow
Loads each configured MCP plugin server in an isolated subprocess (its own venv, bootstrapped from
its own requirements if missing), extracts each tool's name/description/input_schema, and writes one
JSON file per tool.

## Modules

### 01_extract_schemas.py (122 LOC)

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

## State
No persistent state owned by this directory. It writes into `src/proxy/schemas/`, which is owned and read at runtime by `src/proxy/tool_injection.py`, not by this script.
