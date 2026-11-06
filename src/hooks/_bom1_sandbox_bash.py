# INFRASTRUCTURE
import re

UNSET_PREFIX = "unset PYTHONHOME PYTHONPATH RESOURCEPATH EXECUTABLEPATH ARGVZERO; "
HELPER_PREFIX = [
    "env", "-u", "PYTHONHOME", "-u", "PYTHONPATH", "-u", "RESOURCEPATH", "-u", "EXECUTABLEPATH", "-u", "ARGVZERO",
    "uv", "run", "-q", "--no-project", "--with", "openpyxl", "python", "tools/workbook_io.py",
]
COLLECTION = "bom1-reports"
HEREDOC_OPEN = " <<'ROWS'"
HEREDOC_END = "ROWS"
COMMIT_COLLECT = "feat: collect {ticker} compensation data"
COMMIT_FINDINGS = "docs: record {ticker} findings"
COMMIT_COLLECT_KPI = "feat: collect {ticker} kpi data"
COMMIT_FINDINGS_KPI = "docs: record {ticker} kpi findings"

_MAX_COMMAND_BYTES = 300000
_QUERY_MAX_CHARS = 300
_QUERY_FORBIDDEN = frozenset("$`\\")
_ALLOWED_INPUT_KEYS = frozenset({"command", "description", "timeout"})
_FALSE_ONLY_KEYS = frozenset({"run_in_background", "dangerouslyDisableSandbox"})
_OWN_READ_SHEETS = ("Metric_Classification", "Data_Compensation", "Data_KPI")
_WRITE_SHEETS = ("Data_Compensation", "Data_KPI")
_REFERENCE_SHEETS = ("Data_Compensation", "Data_KPI")
_INTEGER_RE = re.compile(r"^[0-9]{1,4}$")
_EXPAND_FLAGS = ("--before", "--after")
_TOKEN_RE = re.compile(
    r"(?P<bare>[A-Za-z0-9_./%-]+)"
    r"|'(?P<single>[^'\x00-\x1f\x7f]*)'"
    r'|"(?P<double>[^"$`\\\x00-\x1f\x7f]*)"'
)


# FUNCTIONS

def bash_input_violation(tool_input: dict, ticker: str, documents: list):
    unexpected = sorted(set(tool_input) - _ALLOWED_INPUT_KEYS - _FALSE_ONLY_KEYS)
    if unexpected:
        return f"Bash input carries unexpected keys {unexpected}"
    if any(tool_input.get(key) not in (None, False) for key in _FALSE_ONLY_KEYS):
        return "background or sandbox-disabling Bash options are not allowed"
    if "timeout" in tool_input and (isinstance(tool_input["timeout"], bool) or not isinstance(tool_input["timeout"], int)):
        return "the Bash timeout must be an integer"
    return command_violation(tool_input.get("command"), ticker, documents)


def command_violation(command, ticker: str, documents: list):
    if not isinstance(command, str) or not command.strip():
        return "empty or non-text Bash command"
    if len(command.encode("utf-8")) > _MAX_COMMAND_BYTES:
        return "Bash command is too long"
    if "\r" in command or "\x00" in command:
        return "carriage return or NUL in the Bash command"
    head, has_body, reason = split_heredoc(command)
    if reason is not None:
        return reason
    return head_violation(head, has_body, ticker, documents)


def split_heredoc(command: str) -> tuple:
    stripped = command.rstrip("\n")
    if "\n" not in stripped:
        return stripped, False, None
    first_line, _, rest = stripped.partition("\n")
    if not first_line.endswith(HEREDOC_OPEN):
        return None, False, "multi-line Bash commands are only allowed as the write heredoc"
    lines = rest.split("\n")
    if lines[-1] != HEREDOC_END:
        return None, False, f"the heredoc must end with a line {HEREDOC_END} and nothing after it"
    if HEREDOC_END in lines[:-1]:
        return None, False, f"a line {HEREDOC_END} inside the heredoc body would end it early"
    return first_line[:-len(HEREDOC_OPEN)], True, None


def head_violation(head: str, has_body: bool, ticker: str, documents: list):
    segments = head.split(" && ") if head.startswith("git ") else [head]
    if len(segments) > 2:
        return "more than two commands in one Bash call"
    word_lists = []
    for segment in segments:
        words, used_unset = lex_segment(segment)
        if not words:
            return "the Bash command could not be parsed into plain words"
        if used_unset and words[0] != "rag-cli":
            return "the unset prefix is only allowed in front of rag-cli"
        word_lists.append(words)
    return dispatch_violation(word_lists, has_body, ticker, documents)


def lex_segment(segment: str) -> tuple:
    used_unset = segment.startswith(UNSET_PREFIX)
    text = segment[len(UNSET_PREFIX):] if used_unset else segment
    return lex_words(text), used_unset


def lex_words(text: str):
    words, position = [], 0
    while position < len(text):
        match = _TOKEN_RE.match(text, position)
        if match is None:
            return None
        words.append(match.group(match.lastgroup))
        position = match.end()
        if position == len(text):
            break
        if text[position] != " ":
            return None
        position += 1
        if position == len(text):
            return None
    return words


def dispatch_violation(word_lists: list, has_body: bool, ticker: str, documents: list):
    first = word_lists[0]
    if first[0] == "git":
        return git_violation(word_lists, ticker) if not has_body else "a heredoc is only allowed with the write form"
    if len(word_lists) != 1:
        return "chaining with && is only allowed for git add followed by git commit"
    if first[0] == "env":
        return helper_violation(first, has_body, ticker)
    if has_body:
        return "a heredoc is only allowed with the write form"
    if first[0] == "rag-cli":
        return rag_violation(first[1:], ticker, documents)
    return f"command '{first[0]}' is not allowed"


def rag_violation(words: list, ticker: str, documents: list):
    if len(words) == 5 and words[0] == "search" and words[3] == "--document":
        return search_violation(words, documents)
    if len(words) >= 4 and words[0] == "expand_chunks":
        return expand_violation(words, documents)
    if words == ["list_documents", COLLECTION, "--document", f"{ticker}_%"]:
        return None
    return "rag-cli form is not one of the three allowed forms"


def search_violation(words: list, documents: list):
    if words[2] != COLLECTION:
        return f"the collection must be {COLLECTION}"
    if words[4] not in documents:
        return f"document '{words[4]}' is not allowed for this worker"
    return query_violation(words[1])


def query_violation(query: str):
    if not 1 <= len(query) <= _QUERY_MAX_CHARS:
        return f"the query must have 1 to {_QUERY_MAX_CHARS} characters"
    if not query.isprintable() or not query.strip():
        return "the query contains non-printable characters"
    if any(char in _QUERY_FORBIDDEN for char in query):
        return "the query contains $, a backtick or a backslash"
    if query.startswith("-"):
        return "the query must not start with a dash"
    return None


def expand_violation(words: list, documents: list):
    if words[1] != COLLECTION:
        return f"the collection must be {COLLECTION}"
    if words[2] not in documents:
        return f"document '{words[2]}' is not allowed for this worker"
    if not _INTEGER_RE.match(words[3]):
        return "the chunk number must be a plain integer"
    return expand_options_violation(words[4:])


def expand_options_violation(options: list):
    if len(options) % 2 != 0 or len(options) > 2 * len(_EXPAND_FLAGS):
        return "expand_chunks takes only --before N and --after N"
    flags = options[0::2]
    if any(flag not in _EXPAND_FLAGS for flag in flags) or len(set(flags)) != len(flags):
        return "expand_chunks takes each of --before and --after at most once"
    if not all(_INTEGER_RE.match(value) for value in options[1::2]):
        return "--before and --after take plain integers"
    return None


def helper_violation(words: list, has_body: bool, ticker: str):
    if words[:len(HELPER_PREFIX)] != HELPER_PREFIX:
        return "the env/uv form is not the workbook helper form"
    rest = words[len(HELPER_PREFIX):]
    if rest in [["write", ticker, sheet] for sheet in _WRITE_SHEETS]:
        return None if has_body else "the write form needs the JSON heredoc"
    if has_body:
        return "a heredoc is only allowed with the write form"
    reads = [["read", ticker, sheet] for sheet in _OWN_READ_SHEETS] + [["read-reference", sheet] for sheet in _REFERENCE_SHEETS]
    return None if rest in reads else "the workbook helper form is not allowed"


def git_violation(word_lists: list, ticker: str):
    kinds = [git_kind(words, ticker) for words in word_lists]
    if None in kinds:
        return "git is only allowed as git add of your own excels files and git commit with the fixed messages"
    if kinds in (["add"], ["commit"], ["add", "commit"]):
        return None
    return "git commands must be in the order git add, then git commit"


def git_kind(words: list, ticker: str):
    workbook, findings = f"excels/{ticker}.xlsx", f"excels/{ticker}.md"
    if words in (["git", "add", workbook, findings], ["git", "add", findings], ["git", "add", workbook]):
        return "add"
    messages = tuple(template.format(ticker=ticker) for template in (COMMIT_COLLECT, COMMIT_FINDINGS, COMMIT_COLLECT_KPI, COMMIT_FINDINGS_KPI))
    if len(words) == 4 and words[:3] == ["git", "commit", "-m"] and words[3] in messages:
        return "commit"
    return None
