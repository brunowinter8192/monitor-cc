# INFRASTRUCTURE
import json
import os
import sys
from pathlib import Path

_SETTINGS_FILE = Path("~/.claude/settings.json").expanduser()
_HOOKS_DIR     = Path(__file__).resolve().parent
_HOOK_TIMEOUT  = 5

# Hook scripts to install: (script_filename, PreToolUse matcher)
# block_path_typo registers under Bash + Read + Write + Edit — the same hook script
# inspects tool_name internally to pick the right field (command vs file_path).
_HOOK_SCRIPTS = [
    ("block_dangerous_kill.py",          "Bash"),
    ("block_polling_loop.py",            "Bash"),
    ("block_log_read.py",                "Bash"),
    ("block_busywait_loop.py",           "Bash"),
    ("rewrite_chained_sleep.py",         "Bash"),
    ("rewrite_rag_cli_search_noise.py",          "Bash"),
    ("rewrite_worker_cli_response_noise.py",     "Bash"),
    ("rewrite_worker_cli_capture_noise.py",      "Bash"),
    ("rewrite_searxng_scrape_noise.py",  "Bash"),
    ("block_unauthorized_background.py",   "Bash"),
    ("block_worker_send_background.py",     "Bash"),
    ("rewrite_background_sleep.py",        "Bash"),
    ("rewrite_reddit_index_background.py", "Bash"),
    ("rewrite_pipe_background.py",         "Bash"),
    ("block_search_subreddits_limit.py", "Bash"),
    ("block_gh_cli_chained.py",          "Bash"),
    ("block_broad_grep.py",              "Bash"),
    ("block_git_destructive.py",         "Bash"),
    ("rewrite_bd_invalid_repo.py",       "Bash"),
    ("block_venv_no_redirect.py",        "Bash"),
    ("block_cd_drift.py",                "Bash"),
    ("block_path_typo.py",               "Bash"),
    ("block_path_typo.py",               "Read"),
    ("block_path_typo.py",               "Write"),
    ("block_path_typo.py",               "Edit"),
    ("block_noop_edit.py",               "Edit"),
    ("block_read_directory.py",          "Read"),
    ("block_read_oversize.py",           "Read"),
    ("block_worker_spawn_opus.py",       "Bash"),
    ("block_worker_spawn_placement.py",  "Bash"),
    ("block_worker_kill_while_working.py", "Bash"),
    ("block_bd_cli_worker.py",           "Bash"),
    ("block_git_add_deps.py",            "Bash"),
    ("block_dev_imports_src.py",         "Write"),
    ("block_dev_imports_src.py",         "Edit"),
    ("block_except_pass.py",             "Write"),
    ("block_except_pass.py",             "Edit"),
    ("block_manual_worker_cleanup.py",   "Bash"),
]
_HOOK_ENTRIES = [(f"python3 {_HOOKS_DIR / s}", m) for s, m in _HOOK_SCRIPTS]

# ORCHESTRATOR

# Install PreToolUse safety hooks into ~/.claude/settings.json; idempotent; supports mixed matchers (Bash/Edit/Read)
def hook_setup_workflow() -> None:
    _guard_not_worktree()
    settings = _load_settings()
    swept = _sweep_stale_hooks(settings)
    if swept:
        _save_settings(settings)
    hooks = settings.setdefault("hooks", {})
    pre = hooks.setdefault("PreToolUse", [])
    installed = 0
    for command, matcher in _HOOK_ENTRIES:
        if not _already_installed(pre, command, matcher):
            _add_hook(pre, command, matcher)
            installed += 1
    if installed:
        _save_settings(settings)

# FUNCTIONS

# Refuse to run if this script is executing from inside a worktree path
def _guard_not_worktree() -> None:
    parts = Path(__file__).resolve().parts
    for i in range(len(parts) - 1):
        if parts[i] == '.claude' and parts[i + 1] == 'worktrees':
            print(
                f"ERROR: This script must be run from the main repo root, not from a worktree at "
                f"{Path(__file__).resolve()}.\n"
                "Wechsel in den Main-Repo-Root und rufe das Skript dort auf.",
                file=sys.stderr,
            )
            sys.exit(2)

# Remove hook entries whose python3 script path no longer exists; drop now-empty groups
def _sweep_stale_hooks(settings: dict) -> int:
    hooks = settings.get("hooks", {})
    swept = 0
    for event, groups in list(hooks.items()):
        new_groups = []
        for group in groups:
            new_hooks = []
            for h in group.get("hooks", []):
                cmd = h.get("command", "")
                if cmd.startswith("python3 "):
                    tokens = cmd.split()
                    if len(tokens) >= 2 and not os.path.exists(tokens[1]):
                        swept += 1
                        continue
                new_hooks.append(h)
            if new_hooks:
                new_groups.append({**group, "hooks": new_hooks})
        hooks[event] = new_groups
    return swept

# True if a hook entry with the given (command, matcher) pair already exists under PreToolUse
def _already_installed(pre_tool_use: list, command: str, matcher: str) -> bool:
    for group in pre_tool_use:
        if group.get("matcher") != matcher:
            continue
        for h in group.get("hooks", []):
            if h.get("command") == command:
                return True
    return False

# Append a new matcher group to the PreToolUse list with the given matcher
def _add_hook(pre_tool_use: list, command: str, matcher: str) -> None:
    pre_tool_use.append({
        "matcher": matcher,
        "hooks": [{"type": "command", "command": command, "timeout": _HOOK_TIMEOUT}],
    })

# Read settings.json; return empty dict if absent; exit on parse error
def _load_settings() -> dict:
    try:
        return json.loads(_SETTINGS_FILE.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return {}
    except json.JSONDecodeError as e:
        print(f"ERROR: cannot parse {_SETTINGS_FILE}: {e}", file=sys.stderr)
        sys.exit(1)

# Atomically write settings back via temp file
def _save_settings(settings: dict) -> None:
    tmp = _SETTINGS_FILE.with_suffix(".tmp")
    tmp.write_text(json.dumps(settings, indent=2), encoding="utf-8")
    os.replace(tmp, _SETTINGS_FILE)


if __name__ == "__main__":
    hook_setup_workflow()
