# INFRASTRUCTURE
import json
import os
import sys
from pathlib import Path

_src_dir = os.path.join(os.environ.get("MONITOR_CC_ROOT", str(Path(__file__).parent.parent.parent)), "src")
sys.path.insert(0, _src_dir)

_SHARED_RULES_DIR = Path.home() / ".claude" / "shared-rules"
_PROXY_RULES_CONFIG = _SHARED_RULES_DIR / "proxy_rules.json"
_file_cache: dict = {}
_config_cache: list = [None]

# FUNCTIONS


def _load_config() -> dict:
    try:
        mtime = _PROXY_RULES_CONFIG.stat().st_mtime
        cached = _config_cache[0]
        if cached is not None and cached[0] == mtime:
            return cached[1]
        with open(_PROXY_RULES_CONFIG, encoding="utf-8") as f:
            config = json.load(f)
        _config_cache[0] = (mtime, config)
        return config
    except Exception:
        return {}


def _read_rule_file(rel_path: str) -> str:
    path = _SHARED_RULES_DIR / rel_path
    try:
        mtime = path.stat().st_mtime
        cached = _file_cache.get(rel_path)
        if cached is not None and cached[0] == mtime:
            return cached[1]
        content = path.read_text(encoding="utf-8")
        _file_cache[rel_path] = (mtime, content)
        return content
    except Exception:
        return ""


def _resolve_project_rule_files(s2: dict, project_path: str, model_family: str) -> tuple:
    project_files = []
    exclusive_files = None
    if not project_path:
        return project_files, exclusive_files, False
    for _name, proj in s2.get("projects", {}).items():
        path_contains = proj.get("path_contains", "")
        if path_contains and path_contains in project_path:
            if proj.get("exclusive"):
                allowed = proj.get("exclusive_model_families")
                if allowed is not None and model_family not in allowed:
                    return [], None, True
                exclusive_files = list(proj.get("files", []))
                break
            project_files.extend(proj.get("files", []))
    return project_files, exclusive_files, False


def _load_system2_rules(model_family: str, project_path: str = "", worker_context: str = "") -> str:
    config = _load_config()
    s2 = config.get("system2_rules", {})
    for pattern in s2.get("exclude_projects", []):
        if pattern and pattern in project_path:
            return ""
    if model_family == "haiku":
        return ""
    global_files = s2.get("global", {}).get("files", [])
    role_key = "worker" if (worker_context or "").startswith("worker:") else "main"
    role_files = s2.get(role_key, {}).get("files", [])
    project_files, exclusive_files, empty_due_to_family = _resolve_project_rule_files(s2, project_path, model_family)
    if empty_due_to_family:
        return ""
    if exclusive_files is not None:
        all_files = exclusive_files
    else:
        all_files = global_files + role_files + project_files
    parts = [c for c in (_read_rule_file(f) for f in all_files) if c]
    return "\n\n".join(parts)
