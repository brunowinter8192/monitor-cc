# INFRASTRUCTURE
import json
import os
from pathlib import Path

from src.proxy.proxy_error_log import clear_proxy_error, log_proxy_error, log_proxy_error_on_change, proxy_monitor_root

_SCHEMA_STORE_CACHE = None
_ACTIVE_PLUGINS_CACHE = None
_ACTIVE_PLUGINS_MTIME = None
_ACTIVE_PLUGINS_PATH = None

_ALWAYS_INJECTED_PLUGIN = "iterative-dev"
_PLUGINS_SOURCE = "tool_injection.active_plugins"
_EXCLUDE_SOURCE = "tool_injection.exclude_projects"

# ORCHESTRATOR

def inject_mcp_tools(payload: dict, project_path: str) -> dict:
    if _is_project_excluded(project_path):
        return payload
    if not payload.get("tools"):
        return payload
    store = _load_schema_store()
    if not store:
        return payload
    to_append = _collect_schemas_to_append(payload, store, project_path)
    if not to_append:
        return payload
    return _append_tools(payload, to_append)


# FUNCTIONS

def _collect_schemas_to_append(payload: dict, store: dict, project_path: str) -> list:
    active_plugins = _load_active_plugins(project_path)
    existing_names = {t.get("name") for t in payload.get("tools", [])}
    to_append = []
    for plugin_name in _plugins_to_inject(active_plugins):
        to_append.extend(_new_schemas_for_plugin(store, plugin_name, existing_names))
    return to_append


def _plugins_to_inject(active_plugins: list) -> list:
    plugins_to_inject = [_ALWAYS_INJECTED_PLUGIN]
    for p in active_plugins:
        if p != _ALWAYS_INJECTED_PLUGIN and p not in plugins_to_inject:
            plugins_to_inject.append(p)
    return plugins_to_inject


def _new_schemas_for_plugin(store: dict, plugin_name: str, existing_names: set) -> list:
    schemas = store.get(plugin_name, [])
    new_schemas = [s for s in schemas if s.get("name") not in existing_names]
    new_schemas_sorted = sorted(new_schemas, key=lambda s: s.get("name", ""))
    for s in new_schemas_sorted:
        existing_names.add(s.get("name"))
    return new_schemas_sorted


def _append_tools(payload: dict, to_append: list) -> dict:
    modified = dict(payload)
    modified["tools"] = list(payload.get("tools", [])) + to_append
    return modified

def _load_schema_store() -> dict:
    global _SCHEMA_STORE_CACHE
    if _SCHEMA_STORE_CACHE is not None:
        return _SCHEMA_STORE_CACHE

    store_base = _resolve_schema_store_path()
    if not store_base.exists():
        log_proxy_error(
            "tool_injection.schema_store",
            f"schema store missing at {store_base}, tool injection disabled. "
            "Run dev/tool_injection/01_extract_schemas.py to populate.",
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
            except (json.JSONDecodeError, OSError) as e:
                log_proxy_error_on_change(f"tool_injection.schema_file {json_file}", e)
                continue
        if schemas:
            store[plugin_dir.name] = schemas

    if not store:
        log_proxy_error(
            "tool_injection.schema_store",
            f"schema store at {store_base} is empty, tool injection disabled. "
            "Run dev/tool_injection/01_extract_schemas.py to populate.",
        )

    _SCHEMA_STORE_CACHE = store
    return _SCHEMA_STORE_CACHE


def _load_active_plugins(project_path: str) -> list:
    global _ACTIVE_PLUGINS_CACHE, _ACTIVE_PLUGINS_MTIME, _ACTIVE_PLUGINS_PATH

    if not project_path:
        log_proxy_error_on_change(_PLUGINS_SOURCE, "project path is empty, default plugin list")
        return [_ALWAYS_INJECTED_PLUGIN]

    plugins_file = os.path.join(project_path, ".claude", "active_plugins.json")
    _ACTIVE_PLUGINS_PATH = plugins_file

    if not os.path.exists(plugins_file):
        log_proxy_error_on_change(_PLUGINS_SOURCE, f"active_plugins.json missing, default plugin list: {plugins_file}")
        _ACTIVE_PLUGINS_CACHE = [_ALWAYS_INJECTED_PLUGIN]
        _ACTIVE_PLUGINS_MTIME = None
        return _ACTIVE_PLUGINS_CACHE

    try:
        mtime = os.path.getmtime(plugins_file)
    except OSError as e:
        log_proxy_error_on_change(_PLUGINS_SOURCE, e)
        return _ACTIVE_PLUGINS_CACHE if _ACTIVE_PLUGINS_CACHE is not None else [_ALWAYS_INJECTED_PLUGIN]

    if _ACTIVE_PLUGINS_CACHE is not None and _ACTIVE_PLUGINS_MTIME == mtime:
        return _ACTIVE_PLUGINS_CACHE

    plugins = _read_plugins_file(plugins_file)

    if _ALWAYS_INJECTED_PLUGIN not in plugins:
        plugins = [_ALWAYS_INJECTED_PLUGIN] + plugins

    _ACTIVE_PLUGINS_CACHE = plugins
    _ACTIVE_PLUGINS_MTIME = mtime
    return _ACTIVE_PLUGINS_CACHE


def _read_plugins_file(plugins_file: str) -> list:
    try:
        raw = json.loads(Path(plugins_file).read_text(encoding="utf-8"))
        if isinstance(raw, dict):
            plugins = raw.get("plugins", [_ALWAYS_INJECTED_PLUGIN])
            if not isinstance(plugins, list):
                log_proxy_error_on_change(_PLUGINS_SOURCE, f"active_plugins.json 'plugins' is not a list, default plugin list: {plugins_file}")
                plugins = [_ALWAYS_INJECTED_PLUGIN]
            else:
                clear_proxy_error(_PLUGINS_SOURCE)
        elif isinstance(raw, list):
            plugins = raw
            clear_proxy_error(_PLUGINS_SOURCE)
        else:
            log_proxy_error_on_change(_PLUGINS_SOURCE, f"active_plugins.json has an unexpected shape, default plugin list: {plugins_file}")
            plugins = [_ALWAYS_INJECTED_PLUGIN]
    except (json.JSONDecodeError, OSError) as e:
        log_proxy_error_on_change(_PLUGINS_SOURCE, e)
        plugins = [_ALWAYS_INJECTED_PLUGIN]
    return plugins


def _resolve_schema_store_path() -> Path:
    return proxy_monitor_root() / "src" / "proxy" / "schemas"


def _is_project_excluded(project_path: str) -> bool:
    if not project_path:
        return False
    config_path = Path.home() / ".claude" / "shared-rules" / "proxy_rules.json"
    if not config_path.exists():
        log_proxy_error_on_change(_EXCLUDE_SOURCE, f"proxy_rules.json missing, no project excluded: {config_path}")
        return False
    try:
        config = json.loads(config_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as e:
        log_proxy_error_on_change(_EXCLUDE_SOURCE, e)
        return False
    exclude_list = config.get("tool_injection", {}).get("exclude_projects", [])
    if not isinstance(exclude_list, list):
        log_proxy_error_on_change(_EXCLUDE_SOURCE, "exclude_projects is not a list, no project excluded")
        return False
    clear_proxy_error(_EXCLUDE_SOURCE)
    for pattern in exclude_list:
        if pattern and isinstance(pattern, str) and pattern in project_path:
            return True
    return False
