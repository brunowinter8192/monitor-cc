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


def _load_config() -> dict:
    """Load proxy_rules.json config, re-reading only when mtime changes."""
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
    """Read a rule file by path relative to shared-rules dir, caching by mtime."""
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


def _load_system2_rules(model_family: str, project_path: str = "") -> str:
    """Concatenate system2 rule files for a given model family (global + model-specific + project)."""
    config = _load_config()
    s2 = config.get("system2_rules", {})
    # Project-level opt-out: exclude_projects patterns suppress all system2 injection
    for pattern in s2.get("exclude_projects", []):
        if pattern and pattern in project_path:
            return ""
    global_files = s2.get("global", {}).get("files", [])
    # Map model family to config key: opus → "opus", sonnet/haiku → "worker"
    model_key = "opus" if model_family == "opus" else "worker"
    model_files = s2.get(model_key, {}).get("files", [])
    # haiku gets no rules (returns empty → system[2] becomes ".")
    if model_family == "haiku":
        return ""
    # Load project-specific files from system2_rules.projects
    project_files = []
    exclusive_files = None
    if project_path:
        for _name, proj in s2.get("projects", {}).items():
            path_contains = proj.get("path_contains", "")
            if path_contains and path_contains in project_path:
                # Exclusive project: skip global+model, load ONLY these files.
                # Optional exclusive_model_families restricts to listed families;
                # other families fall through to empty rules.
                if proj.get("exclusive"):
                    allowed = proj.get("exclusive_model_families")
                    if allowed is not None and model_family not in allowed:
                        return ""
                    exclusive_files = list(proj.get("files", []))
                    break
                project_files.extend(proj.get("files", []))
    if exclusive_files is not None:
        all_files = exclusive_files
    else:
        all_files = global_files + model_files + project_files
    parts = [c for c in (_read_rule_file(f) for f in all_files) if c]
    return "\n\n".join(parts)
