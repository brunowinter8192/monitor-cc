# INFRASTRUCTURE
import functools
import glob
import itertools
import json
import os
import re
import shlex
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from src.hooks._fire_log import log_fire

_HOOK_NAME = "ask_rag_storage"
_ROOTS_ENV = "MONITOR_CC_RAG_STORAGE_ROOTS"
_DEFAULT_ROOT_SUFFIXES = (
    "Documents/ai/Meta/ClaudeCode/cli/rag-cli/data/pdf",
    "Documents/ai/Meta/ClaudeCode/cli/rag-cli/data/documents",
)
_GLOB_CAP = 500
_DIR_ENTRY_CAP = 5000
_EXEMPT_RAG_SUBCOMMANDS = ("search", "expand_chunks", "list_documents", "list_collections", "progress")
_STORAGE_RAG_SUBCOMMANDS = ("index", "delete")
_PREFIX_WORDS = (
    "export", "local", "declare", "readonly", "do", "then", "else", "elif", "if", "while",
    "until", "!", "{", "time", "command", "nohup", "exec",
)
_FILESYSTEM_FREE_WORDS = (
    "cd", "unset", "export", "set", "echo", "printf", "true", "false", "sleep", "exit", ":",
    "for", "done", "fi", "esac", "case", "select", "read", "test", "[", "[[",
)
_ENV_ARGUMENT_OPTIONS = ("-u", "-C", "-S")
_SEPARATOR_CHARS = frozenset(";&|()")
_GLOB_CHARS_RE = re.compile(r'[*?\[]')
_ASSIGNMENT_RE = re.compile(r'^([A-Za-z_][A-Za-z0-9_]*)=(.*)$', re.DOTALL)
_OPTION_VALUE_RE = re.compile(r'^-{0,2}[A-Za-z][\w-]*=(.*)$', re.DOTALL)
_VARIABLE_RE = re.compile(r'\$(?:\{([A-Za-z_][A-Za-z0-9_]*)\}|([A-Za-z_][A-Za-z0-9_]*))')
_LINE_CONTINUATION_RE = re.compile(r'\\\n')
_FALLBACK_SEPARATOR_RE = re.compile(r'([;&|()])')


# ORCHESTRATOR

def ask_rag_storage_workflow() -> None:
    payload = _parse_payload()
    if payload is None:
        sys.exit(0)
    reason = _detect_storage_hit(payload)
    if reason is None:
        sys.exit(0)
    _ask(payload, reason)


# FUNCTIONS

def _parse_payload():
    try:
        payload = json.loads(sys.stdin.read())
    except Exception as e:
        log_fire(_HOOK_NAME, "trace", "Bash/Read/Write/Edit/Glob/Grep", "", reason=f"parse error: {type(e).__name__}: {e}")
        return None
    return payload if isinstance(payload, dict) else None


def _detect_storage_hit(payload: dict):
    try:
        return _tool_hit(payload)
    except Exception as e:
        log_fire(_HOOK_NAME, "trace", str(payload.get("tool_name")), _subject(payload),
                 reason=f"detection error, allowed: {type(e).__name__}: {e}",
                 session_id=payload.get("session_id"))
        return None


def _tool_hit(payload: dict):
    tool = payload.get("tool_name")
    tool_input = payload.get("tool_input")
    if not isinstance(tool_input, dict):
        return None
    cwd = _initial_cwd(payload.get("cwd"))
    if tool == "Bash":
        command = tool_input.get("command")
        return _bash_hit(command, cwd) if isinstance(command, str) else None
    if tool in ("Read", "Write", "Edit"):
        return _paths_hit([tool_input.get("file_path")], cwd)
    if tool == "Glob":
        return _paths_hit(_glob_targets(tool_input, cwd), cwd)
    if tool == "Grep":
        return _paths_hit([tool_input.get("path") or cwd], cwd)
    return None


def _initial_cwd(payload_cwd):
    if isinstance(payload_cwd, str) and payload_cwd:
        return os.path.realpath(payload_cwd)
    return os.path.realpath(os.getcwd())


def _glob_targets(tool_input: dict, cwd: str) -> list:
    base = tool_input.get("path") or cwd
    pattern = tool_input.get("pattern")
    if not isinstance(base, str) or not isinstance(pattern, str) or not pattern:
        return [base]
    return [base, pattern if os.path.isabs(pattern) else os.path.join(base, pattern)]


def _paths_hit(paths: list, cwd: str):
    for path in paths:
        if isinstance(path, str) and path:
            reason = _path_hit(path, cwd)
            if reason:
                return reason
    return None


def _bash_hit(command: str, start_cwd: str):
    variables = dict(os.environ)
    cwd = start_cwd
    for segment in _segments(command):
        assignments, words = _split_prefix(segment)
        variables.update(_resolvable_assignments(assignments, variables))
        words = [_expand_variables(word, variables) for word in words]
        reason = _segment_hit(words, cwd)
        if reason:
            return reason
        cwd = _next_cwd(words, cwd)
    return None


def _segments(command: str) -> list:
    segments, current = [], []
    for token in _tokenize(command):
        if _is_separator(token):
            segments.append(current)
            current = []
        else:
            current.append(token)
    segments.append(current)
    return [segment for segment in segments if segment]


def _tokenize(command: str) -> list:
    text = _LINE_CONTINUATION_RE.sub(' ', command).replace('\n', ' ; ')
    lexer = shlex.shlex(text, posix=True, punctuation_chars=True)
    lexer.whitespace_split = True
    lexer.commenters = ''
    try:
        return list(lexer)
    except ValueError as e:
        log_fire(_HOOK_NAME, "trace", "Bash", command, reason=f"shlex fallback: {e}")
        return _fallback_tokens(text)


def _fallback_tokens(text: str) -> list:
    spaced = _FALLBACK_SEPARATOR_RE.sub(r' \1 ', text)
    return [token.strip('\'"') for token in spaced.split()]


def _is_separator(token: str) -> bool:
    return bool(token) and all(char in _SEPARATOR_CHARS for char in token)


def _split_prefix(segment: list) -> tuple:
    assignments, index = [], 0
    while index < len(segment):
        token = segment[index]
        match = _ASSIGNMENT_RE.match(token)
        if match:
            assignments.append((match.group(1), match.group(2)))
        elif token not in _PREFIX_WORDS:
            break
        index += 1
    rest = segment[index:]
    if rest and os.path.basename(rest[0]) == "env":
        env_assignments, rest = _split_env(rest)
        assignments.extend(env_assignments)
    return assignments, rest


def _split_env(words: list) -> tuple:
    assignments, index = [], 1
    while index < len(words):
        token = words[index]
        match = _ASSIGNMENT_RE.match(token)
        if token in _ENV_ARGUMENT_OPTIONS:
            index += 2
        elif token.startswith("-"):
            index += 1
        elif match:
            assignments.append((match.group(1), match.group(2)))
            index += 1
        else:
            break
    return assignments, words[index:]


def _resolvable_assignments(assignments: list, variables: dict) -> dict:
    resolved = {}
    for name, value in assignments:
        if "$(" in value or "`" in value or value.endswith("$"):
            continue
        resolved[name] = _expand_variables(value, {**variables, **resolved})
    return resolved


def _expand_variables(token: str, variables: dict) -> str:
    def replace(match):
        name = match.group(1) or match.group(2)
        return variables.get(name, match.group(0))
    return _VARIABLE_RE.sub(replace, token)


def _segment_hit(words: list, cwd):
    if not words:
        return None
    subcommand = _rag_cli_subcommand(words)
    if subcommand in _EXEMPT_RAG_SUBCOMMANDS:
        return None
    if subcommand in _STORAGE_RAG_SUBCOMMANDS:
        return f"rag-cli {subcommand} changes files in RAG storage"
    if words[0] == "cd":
        return None
    for token in words:
        reason = _token_hit(token, cwd)
        if reason:
            return reason
    return _cwd_hit(words[0], cwd)


def _rag_cli_subcommand(words: list):
    if os.path.basename(words[0]) != "rag-cli":
        return None
    for token in words[1:]:
        if not token.startswith("-"):
            return token
    return None


def _token_hit(token: str, cwd):
    value = _path_value(token)
    if not value:
        return None
    return _path_hit(value, cwd)


def _path_value(token: str) -> str:
    match = _OPTION_VALUE_RE.match(token)
    if match:
        return match.group(1)
    return "" if token.startswith("-") else token


def _path_hit(value: str, cwd):
    expanded = os.path.expanduser(value)
    root_match = _root_text_re().search(expanded)
    if root_match:
        return f"{root_match.group(0)} is named in the call"
    for candidate in _candidates(expanded.split("$")[0], cwd):
        reason = _storage_reason(candidate)
        if reason:
            return reason
    return None


def _candidates(path: str, cwd) -> list:
    if not path:
        return []
    if not os.path.isabs(path):
        if cwd is None:
            return []
        path = os.path.join(cwd, path)
    if _GLOB_CHARS_RE.search(path):
        return list(itertools.islice(glob.iglob(path), _GLOB_CAP))
    return [path]


def _storage_reason(candidate: str):
    real = os.path.realpath(candidate)
    if _inside_roots(real):
        return f"{candidate} resolves into RAG storage ({real})"
    if os.path.isdir(real) and _dir_links_into_roots(real):
        return f"{candidate} is a directory holding symlinks into RAG storage"
    return None


def _cwd_hit(command_word: str, cwd):
    if cwd is None or command_word in _FILESYSTEM_FREE_WORDS:
        return None
    if _inside_roots(cwd) or _dir_links_into_roots(cwd):
        return f"working directory {cwd} is RAG storage or holds symlinks into it"
    return None


def _next_cwd(words: list, cwd):
    if not words or words[0] != "cd":
        return cwd
    target = words[1] if len(words) > 1 else "~"
    if "$" in target or target == "-":
        return None
    expanded = os.path.expanduser(target)
    if not os.path.isabs(expanded):
        if cwd is None:
            return None
        expanded = os.path.join(cwd, expanded)
    return os.path.realpath(expanded) if os.path.isdir(expanded) else cwd


@functools.lru_cache(maxsize=None)
def _roots() -> tuple:
    override = os.environ.get(_ROOTS_ENV)
    if override:
        literal = [root for root in override.split(os.pathsep) if root]
    else:
        home = os.path.expanduser("~")
        literal = [os.path.join(home, suffix) for suffix in _DEFAULT_ROOT_SUFFIXES]
    forms = []
    for root in literal:
        for form in (root, os.path.realpath(root)):
            stripped = form.rstrip(os.sep)
            if stripped not in forms:
                forms.append(stripped)
    return tuple(forms)


@functools.lru_cache(maxsize=None)
def _root_text_re():
    return re.compile("|".join(re.escape(root) + r'(?![\w.\-])' for root in _roots()))


def _inside_roots(real_path: str) -> bool:
    return any(real_path == root or real_path.startswith(root + os.sep) for root in _roots())


@functools.lru_cache(maxsize=None)
def _dir_links_into_roots(directory: str) -> bool:
    try:
        with os.scandir(directory) as entries:
            for entry in itertools.islice(entries, _DIR_ENTRY_CAP):
                if entry.is_symlink() and _inside_roots(os.path.realpath(entry.path)):
                    return True
    except OSError:
        return False
    return False


def _subject(payload: dict) -> str:
    tool_input = payload.get("tool_input")
    if not isinstance(tool_input, dict):
        return ""
    command = tool_input.get("command")
    return command if isinstance(command, str) else json.dumps(tool_input, ensure_ascii=False)


def _ask(payload: dict, reason: str) -> None:
    message = f"RAG storage operation: {reason}. Confirmation required."
    output = {
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "ask",
            "permissionDecisionReason": message,
        },
    }
    log_fire(_HOOK_NAME, "ask", str(payload.get("tool_name")), _subject(payload),
             reason=message, session_id=payload.get("session_id"))
    print(json.dumps(output))
    sys.exit(0)


if __name__ == "__main__":
    ask_rag_storage_workflow()
