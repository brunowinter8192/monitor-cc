# INFRASTRUCTURE
import re

PROTECTED_SUBCOMMANDS = {
    "gh-cli": {"get_issue", "list_issues"},
    "rag-cli": {"search"},
    "worker-cli": {"capture", "response"},
    "reddit-cli": {"search_subreddits"},
    "websearch": {"scrape_url_chromium"},
    "linkedin": None,
    "penny-cli": None,
    "duallog": None,
}
KNOWN_CLI_TOOLS = tuple(PROTECTED_SUBCOMMANDS.keys())

_ASSIGN_TOKEN = r'[A-Za-z_][A-Za-z0-9_]*=\S*'
_ASSIGN_PREFIX = rf'(?:{_ASSIGN_TOKEN}\s+)*'
_TOOL_ALT = "|".join(re.escape(t) for t in KNOWN_CLI_TOOLS)
_KNOWN_CLI_RE = re.compile(
    rf'^{_ASSIGN_PREFIX}(?P<tool>{_TOOL_ALT})(?:\s+(?P<sub>[A-Za-z0-9_.-]+))?(?:\s|$)'
)

_CLI_PY_DIR_TOOL = {
    "gh-cli": "gh-cli",
    "rag-cli": "rag-cli",
    "reddit-cli": "reddit-cli",
    "websearch": "websearch",
    "jobscraper": "linkedin",
}
_CLI_DIR_ALT = "|".join(re.escape(d) for d in _CLI_PY_DIR_TOOL)
_CLI_PY_DIR_RE = re.compile(rf'(?:^|[/\s])({_CLI_DIR_ALT})(?=[/\s]|$)')
_INTERPRETER_CLI_RE = re.compile(
    rf'^{_ASSIGN_PREFIX}(?:\S+/)?python3?\s+(?:\S+/)?cli\.py'
    rf'(?:\s+(?P<sub>[A-Za-z0-9_.-]+))?(?:\s|$)'
)


class _InterpreterMatch:
    def __init__(self, tool: str, sub):
        self._groups = {'tool': tool, 'sub': sub}

    def group(self, name: str):
        return self._groups[name]


# FUNCTIONS

def match_known_cli_segment(segment: str):
    return _KNOWN_CLI_RE.match(segment)

def match_interpreter_cli_segment(segment: str, command_context: str):
    match = _INTERPRETER_CLI_RE.match(segment)
    if match is None:
        return None
    dir_matches = list(_CLI_PY_DIR_RE.finditer(command_context))
    if not dir_matches:
        return None
    tool = _CLI_PY_DIR_TOOL[dir_matches[-1].group(1)]
    return _InterpreterMatch(tool, match.group('sub'))

def resolve_cli_segment(segment: str, command_context: str):
    match = match_known_cli_segment(segment)
    if match is not None:
        return match
    return match_interpreter_cli_segment(segment, command_context)

def is_known_cli_segment(segment: str) -> bool:
    return match_known_cli_segment(segment) is not None

def is_protected_segment(match) -> bool:
    if match is None:
        return False
    protected = PROTECTED_SUBCOMMANDS[match.group('tool')]
    if protected is None:
        return True
    return match.group('sub') in protected

def tool_sub_name(tool: str, sub) -> str:
    if sub and not sub.startswith('-'):
        return f"{tool} {sub}"
    return tool
