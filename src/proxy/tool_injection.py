# INFRASTRUCTURE
import json
import os
import sys
from pathlib import Path

_SCHEMA_STORE_CACHE = None  # dict: {plugin_name: [schema_dict, ...]}
_ACTIVE_PLUGINS_CACHE = None  # list[str] — last loaded active plugin list
_ACTIVE_PLUGINS_MTIME = None  # float — mtime at last load
_ACTIVE_PLUGINS_PATH = None  # str — path used for last load (per process)

# iterative-dev is always injected regardless of active_plugins.json
_ALWAYS_INJECTED_PLUGIN = "iterative-dev"

# ORCHESTRATOR

# Inject MCP tool schemas into payload["tools"]: iterative-dev always first, active plugins appended.
def inject_mcp_tools(payload: dict, project_path: str) -> dict:
    store = _load_schema_store()
    if not store:
        return payload

    active_plugins = _load_active_plugins(project_path)
    existing_names = {t.get("name") for t in payload.get("tools", [])}

    plugins_to_inject = [_ALWAYS_INJECTED_PLUGIN]
    for p in active_plugins:
        if p != _ALWAYS_INJECTED_PLUGIN and p not in plugins_to_inject:
            plugins_to_inject.append(p)

    to_append = []
    for plugin_name in plugins_to_inject:
        schemas = store.get(plugin_name, [])
        new_schemas = [s for s in schemas if s.get("name") not in existing_names]
        new_schemas_sorted = sorted(new_schemas, key=lambda s: s.get("name", ""))
        to_append.extend(new_schemas_sorted)
        for s in new_schemas_sorted:
            existing_names.add(s.get("name"))

    if not to_append:
        return payload

    modified = dict(payload)
    modified["tools"] = list(payload.get("tools", [])) + to_append
    return modified


# FUNCTIONS

# Read all src/logs/mcp_tool_schemas/<plugin>/*.json into {plugin: [schemas...]}. One-time load per process.
def _load_schema_store() -> dict:
    global _SCHEMA_STORE_CACHE
    if _SCHEMA_STORE_CACHE is not None:
        return _SCHEMA_STORE_CACHE

    store_base = _resolve_schema_store_path()
    if not store_base.exists():
        print(
            f"[tool_injection] WARNING: schema store missing at {store_base} — tool injection disabled. "
            "Run dev/tool_injection/01_extract_schemas.py to populate.",
            file=sys.stderr,
        )
        _SCHEMA_STORE_CACHE = {}
        return _SCHEMA_STORE_CACHE

    store = {}
    for plugin_dir in sorted(store_base.iterdir()):
        if not plugin_dir.is_dir():
            continue
        schemas = []
        for json_file in sorted(plugin_dir.glob("*.json")):
            try:
                schema = json.loads(json_file.read_text(encoding="utf-8"))
                schemas.append(schema)
            except (json.JSONDecodeError, OSError):
                continue
        if schemas:
            store[plugin_dir.name] = schemas

    if not store:
        print(
            f"[tool_injection] WARNING: schema store at {store_base} is empty — tool injection disabled. "
            "Run dev/tool_injection/01_extract_schemas.py to populate.",
            file=sys.stderr,
        )

    _SCHEMA_STORE_CACHE = store
    return _SCHEMA_STORE_CACHE


# Read <project_path>/.claude/active_plugins.json with mtime check. Default: [iterative-dev].
def _load_active_plugins(project_path: str) -> list:
    global _ACTIVE_PLUGINS_CACHE, _ACTIVE_PLUGINS_MTIME, _ACTIVE_PLUGINS_PATH

    if not project_path:
        return [_ALWAYS_INJECTED_PLUGIN]

    plugins_file = os.path.join(project_path, ".claude", "active_plugins.json")
    _ACTIVE_PLUGINS_PATH = plugins_file

    if not os.path.exists(plugins_file):
        _ACTIVE_PLUGINS_CACHE = [_ALWAYS_INJECTED_PLUGIN]
        _ACTIVE_PLUGINS_MTIME = None
        return _ACTIVE_PLUGINS_CACHE

    try:
        mtime = os.path.getmtime(plugins_file)
    except OSError:
        return _ACTIVE_PLUGINS_CACHE if _ACTIVE_PLUGINS_CACHE is not None else [_ALWAYS_INJECTED_PLUGIN]

    if _ACTIVE_PLUGINS_CACHE is not None and _ACTIVE_PLUGINS_MTIME == mtime:
        return _ACTIVE_PLUGINS_CACHE

    try:
        raw = json.loads(Path(plugins_file).read_text(encoding="utf-8"))
        plugins = raw if isinstance(raw, list) else [_ALWAYS_INJECTED_PLUGIN]
    except (json.JSONDecodeError, OSError):
        plugins = [_ALWAYS_INJECTED_PLUGIN]

    if _ALWAYS_INJECTED_PLUGIN not in plugins:
        plugins = [_ALWAYS_INJECTED_PLUGIN] + plugins

    _ACTIVE_PLUGINS_CACHE = plugins
    _ACTIVE_PLUGINS_MTIME = mtime
    return _ACTIVE_PLUGINS_CACHE


# Resolve path to schema store using MONITOR_CC_ROOT env var or module-relative fallback.
def _resolve_schema_store_path() -> Path:
    root = os.environ.get("MONITOR_CC_ROOT")
    if root:
        return Path(root) / "src" / "logs" / "mcp_tool_schemas"
    return Path(__file__).parent.parent.parent / "src" / "logs" / "mcp_tool_schemas"
