# INFRASTRUCTURE
import functools
import json
import os
import subprocess
import sys
from pathlib import Path

_SETTINGS_FILE = Path("~/.claude/settings.json").expanduser()
_HOOKS_DIR     = Path(__file__).resolve().parent
_REPO_ROOT     = _HOOKS_DIR.parent.parent
_HOOK_TIMEOUT  = 5
_MAIN_BRANCH   = "main"
_DEFAULT_EVENT = "PreToolUse"

_HOOK_SCRIPTS = [
    ("block_dangerous_kill.py",          "Bash"),
    ("rewrite_chained_sleep.py",         "Bash"),
    ("block_cli_chained.py",                     "Bash"),
    ("block_rag_cli_index_isolated.py",          "Bash"),
    ("block_rag_docs_layer.py",                  "Bash"),
    ("block_rag_corpus_read.py",                 "Bash"),
    ("block_unauthorized_background.py",   "Bash"),
    ("block_worker_send_background.py",     "Bash"),
    ("block_busywait_loop.py",              "Bash"),
    ("rewrite_background_sleep.py",        "Bash"),
    ("block_search_subreddits_limit.py", "Bash"),
    ("block_gh_cli_local_path.py",       "Bash"),
    ("block_broad_grep.py",              "Bash"),
    ("block_broad_find.py",              "Bash"),
    ("block_git_destructive.py",         "Bash"),
    ("block_venv_no_redirect.py",        "Bash"),
    ("block_cd_drift.py",                "Bash"),
    ("block_path_typo.py",               "Bash"),
    ("block_path_typo.py",               "Read"),
    ("block_path_typo.py",               "Write"),
    ("block_path_typo.py",               "Edit"),
    ("block_noop_edit.py",               "Edit"),
    ("block_read_directory.py",          "Read"),
    ("block_worker_spawn_placement.py",  "Bash"),
    ("block_worker_kill_while_working.py", "Bash"),
    ("block_worker_send_while_working.py", "Bash"),
    ("block_git_add_deps.py",            "Bash"),
    ("block_dev_imports_src.py",         "Write"),
    ("block_dev_imports_src.py",         "Edit"),
    ("block_except_pass.py",             "Write"),
    ("block_except_pass.py",             "Edit"),
    ("block_manual_worker_cleanup.py",   "Bash"),
    ("block_po_read.py",                 "Bash"),
    ("block_pipe_scraper_isolated.py",   "Bash"),
    ("block_rag_cli_document_repeat.py", "Bash"),
]

# ORCHESTRATOR

def hook_setup_workflow() -> None:
    _guard_not_worktree()
    settings = _load_settings()
    swept = _sweep_stale_hooks(settings)
    if swept:
        _save_settings(settings)
    installable, skipped = decide_entries(_HOOK_SCRIPTS, _script_on_main, _script_in_worktree)
    _report_skipped(skipped)
    hooks = settings.setdefault("hooks", {})
    installed = 0
    for entry in installable:
        script, matcher, event = _unpack_entry(entry)
        command = f"python3 {_HOOKS_DIR / script}"
        bucket = hooks.setdefault(event, [])
        if not _already_installed(bucket, command, matcher):
            _add_hook(bucket, command, matcher)
            installed += 1
    if installed:
        _save_settings(settings)

# FUNCTIONS

def decide_entries(hook_scripts: list, git_query_fn, tree_query_fn) -> tuple:
    to_install, skipped, cache = [], [], {}
    for entry in hook_scripts:
        script, matcher, _event = _unpack_entry(entry)
        if script not in cache:
            cache[script] = _script_verdict(script, git_query_fn, tree_query_fn)
        install, reason = cache[script]
        if install:
            to_install.append(entry)
        else:
            skipped.append((script, matcher, reason))
    return to_install, skipped


def _unpack_entry(entry) -> tuple:
    script, matcher = entry[0], entry[1]
    event = entry[2] if len(entry) > 2 else _DEFAULT_EVENT
    return script, matcher, event

def _script_verdict(script: str, git_query_fn, tree_query_fn) -> tuple:
    present = git_query_fn(script)
    if present is False:
        return False, (
            f"{script} is not committed on '{_MAIN_BRANCH}' — not registered "
            f"(would become a dead absolute path once the tree leaves this branch)")
    if present is None:
        return False, (
            f"{script}: could not verify '{_MAIN_BRANCH}'-branch presence (git query failed) "
            f"— not registered (fail-safe: unverifiable presence is treated as absent)")
    if not tree_query_fn(script):
        return False, (
            f"{script} is committed on '{_MAIN_BRANCH}' but missing from the current working tree "
            f"— not registered (would be a dead absolute path immediately)")
    return True, None

def _report_skipped(skipped: list) -> None:
    seen = set()
    for script, _matcher, reason in skipped:
        if script in seen:
            continue
        seen.add(script)
        print(f"SKIPPED: {reason}", file=sys.stderr)

@functools.lru_cache(maxsize=None)
def _main_branch_resolves() -> bool:
    try:
        result = subprocess.run(
            ['git', '-C', str(_REPO_ROOT), 'rev-parse', '--verify', '--quiet', _MAIN_BRANCH],
            capture_output=True, timeout=5,
        )
        return result.returncode == 0
    except Exception:
        return False

def _script_on_main(script_filename: str):
    if not _main_branch_resolves():
        return None
    try:
        result = subprocess.run(
            ['git', '-C', str(_REPO_ROOT), 'cat-file', '-e',
             f'{_MAIN_BRANCH}:src/hooks/{script_filename}'],
            capture_output=True, timeout=5,
        )
        return result.returncode == 0
    except Exception:
        return None

def _script_in_worktree(script_filename: str) -> bool:
    return os.path.exists(_HOOKS_DIR / script_filename)

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

def _already_installed(pre_tool_use: list, command: str, matcher: str) -> bool:
    for group in pre_tool_use:
        if group.get("matcher") != matcher:
            continue
        for h in group.get("hooks", []):
            if h.get("command") == command:
                return True
    return False

def _add_hook(pre_tool_use: list, command: str, matcher: str) -> None:
    pre_tool_use.append({
        "matcher": matcher,
        "hooks": [{"type": "command", "command": command, "timeout": _HOOK_TIMEOUT}],
    })

def _load_settings() -> dict:
    try:
        return json.loads(_SETTINGS_FILE.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return {}
    except json.JSONDecodeError as e:
        print(f"ERROR: cannot parse {_SETTINGS_FILE}: {e}", file=sys.stderr)
        sys.exit(1)

def _save_settings(settings: dict) -> None:
    tmp = _SETTINGS_FILE.with_suffix(".tmp")
    tmp.write_text(json.dumps(settings, indent=2), encoding="utf-8")
    os.replace(tmp, _SETTINGS_FILE)


if __name__ == "__main__":
    hook_setup_workflow()
