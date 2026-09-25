# INFRASTRUCTURE
import functools
import os
import subprocess
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from src.claude_settings import guard_not_worktree, load_settings, save_settings

_HOOKS_DIR     = Path(__file__).resolve().parent
_REPO_ROOT     = _HOOKS_DIR.parent.parent
_HOOK_TIMEOUT  = 5
_MAIN_BRANCH   = "main"
_EVENT         = "PreToolUse"

_HOOK_SCRIPTS = [
    ("block_dangerous_kill.py",          "Bash"),
    ("rewrite_chained_sleep.py",         "Bash"),
    ("block_cli_chained.py",                     "Bash"),
    ("block_rag_cli_index_isolated.py",          "Bash"),
    ("block_rag_docs_layer.py",                  "Bash"),
    ("block_rag_corpus_read.py",                 "Bash"),
    ("block_unauthorized_background.py",   "Bash"),
    ("block_worker_send_background.py",     "Bash"),
    ("rewrite_worker_wait.py",              "Bash"),
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
    guard_not_worktree(__file__)
    settings = load_settings()
    swept = _sweep_stale_hooks(settings)
    if swept:
        save_settings(settings)
    installable, skipped = decide_entries(_HOOK_SCRIPTS, _script_on_main, _script_in_worktree)
    _report_skipped(skipped)
    installed = _install_scripts(settings, installable)
    if installed:
        save_settings(settings)

# FUNCTIONS

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
                        print(f"Swept stale hook: {event} {cmd}", file=sys.stderr)
                        continue
                new_hooks.append(h)
            if new_hooks:
                new_groups.append({**group, "hooks": new_hooks})
        hooks[event] = new_groups
    return swept

def decide_entries(hook_scripts: list, git_query_fn, tree_query_fn) -> tuple:
    to_install, skipped, cache = [], [], {}
    for entry in hook_scripts:
        script, matcher = entry
        if script not in cache:
            cache[script] = _script_verdict(script, git_query_fn, tree_query_fn)
        install, reason = cache[script]
        if install:
            to_install.append(entry)
        else:
            skipped.append((script, matcher, reason))
    return to_install, skipped

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

def _script_in_worktree(script_filename: str) -> bool:
    return os.path.exists(_HOOKS_DIR / script_filename)

def _report_skipped(skipped: list) -> None:
    seen = set()
    for script, _matcher, reason in skipped:
        if script in seen:
            continue
        seen.add(script)
        print(f"SKIPPED: {reason}", file=sys.stderr)

def _install_scripts(settings: dict, installable: list) -> int:
    hooks = settings.setdefault("hooks", {})
    installed = 0
    for script, matcher in installable:
        installed += _install_script(hooks, script, matcher)
    return installed

def _install_script(hooks: dict, script: str, matcher: str) -> int:
    command = f"python3 {_HOOKS_DIR / script}"
    bucket = hooks.setdefault(_EVENT, [])
    if _already_installed(bucket, command, matcher):
        return 0
    _add_hook(bucket, command, matcher)
    return 1

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

if __name__ == "__main__":
    hook_setup_workflow()
