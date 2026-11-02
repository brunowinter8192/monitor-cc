# INFRASTRUCTURE
import json
import os
import re
import sys
from typing import NamedTuple
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from src.hooks._bom1_sandbox_bash import (
    COLLECTION, COMMIT_COLLECT, COMMIT_FINDINGS, HEREDOC_END, HEREDOC_OPEN, HELPER_PREFIX, UNSET_PREFIX,
    bash_input_violation,
)
from src.hooks._fire_log import log_fire

_HOOK_NAME = "block_bom1_worker_sandbox"
_PROJECT_ENV = "CLAUDE_PROJECT_DIR"
_SCOPE_RE = re.compile(r"^(?P<root>.*/BOM1-worker)/\.claude/worktrees/(?P<name>[^/]+)(?:/.*)?$")
_EXEMPT_PREFIX = "dev-"
_POLICY_FILE = "allowed_documents.json"
_DOCUMENT_RE = re.compile(r"^[A-Za-z0-9_.-]+\.md$")
_MAX_DOCUMENTS = 5
_SKILL_NAME = "firm-compensation-collection"
_FILE_TOOLS = frozenset({"Read", "Write", "Edit"})
_PLANNING_TOOLS = frozenset({"TodoWrite", "TaskCreate", "TaskUpdate", "TaskList", "TaskGet"})
_BLOCK_EXIT_CODE = 2
_SUBJECT_MAX_CHARS = 1000

_MESSAGE_HEAD = "BLOCKED by the BOM1 worker sandbox: {reason}.\n"
_MESSAGE_FORMS = (
    "Allowed in this worktree ({ticker}), everything else is blocked:\n"
    "  Bash: {unset}rag-cli list_documents {collection} --document '{ticker}_%'\n"
    "  Bash: {unset}rag-cli search \"<query>\" {collection} --document '<DOCUMENT>'\n"
    "  Bash: {unset}rag-cli expand_chunks {collection} <DOCUMENT> <chunk> --before N --after N\n"
    "        <DOCUMENT> is one of: {documents}\n"
    "  Bash: {helper} read {ticker} Metric_Classification\n"
    "  Bash: {helper} read {ticker} Data_Compensation\n"
    "  Bash: {helper} read-reference Data_Compensation\n"
    "  Bash: {helper} write {ticker} Data_Compensation{heredoc_open}\n"
    "        (JSON list of row objects, then a line {heredoc_end})\n"
    "  Bash: git add excels/{ticker}.xlsx excels/{ticker}.md && git commit -m \"{commit_collect}\"\n"
    "  Bash: git add excels/{ticker}.md && git commit -m \"{commit_findings}\"\n"
    "  Read, Write, Edit: excels/{ticker}.md only.  Skill: {skill}.\n"
    "Queries contain no $, backtick, backslash or double quote. One command per Bash call: no cd, pipes, redirects or chaining.\n"
)
_MESSAGE_STOP = (
    "Stop now: do not retry and do not look for another way around this block. "
    "Report to the user what you tried to do and that the sandbox blocked it, then go idle.\n"
)


class SandboxError(Exception):
    pass


class Scope(NamedTuple):
    root: str
    name: str
    worktree: str


class Verdict(NamedTuple):
    reason: object
    payload: object
    documents: object


# ORCHESTRATOR

def block_bom1_worker_sandbox_workflow() -> None:
    scope = resolve_scope()
    if scope is None:
        sys.exit(0)
    verdict = decide(scope)
    if verdict.reason is None:
        sys.exit(0)
    block(verdict, scope)


# FUNCTIONS

def resolve_scope():
    project_dir = os.environ.get(_PROJECT_ENV) or os.getcwd()
    match = _SCOPE_RE.match(os.path.realpath(project_dir))
    if match is None or match.group("name").startswith(_EXEMPT_PREFIX):
        return None
    root, name = match.group("root"), match.group("name")
    return Scope(root, name, f"{root}/.claude/worktrees/{name}")


def decide(scope: Scope) -> Verdict:
    payload, documents = None, None
    try:
        payload = json.loads(sys.stdin.read())
        documents = load_documents(scope)
        reason = payload_violation(payload, scope, documents)
    except SandboxError as error:
        reason = str(error)
    except Exception as error:
        reason = f"internal error ({type(error).__name__}), the sandbox fails closed"
    return Verdict(reason, payload, documents)


def load_documents(scope: Scope) -> list:
    path = os.path.join(scope.root, _POLICY_FILE)
    try:
        with open(path, encoding="utf-8") as policy_file:
            policy = json.load(policy_file)
    except (OSError, ValueError):
        raise SandboxError("the allowed-documents policy file is missing or invalid")
    documents = policy.get(scope.name) if isinstance(policy, dict) else None
    if documents is None:
        raise SandboxError(f"worker name '{scope.name}' is not a ticker in the policy, everything is blocked")
    valid = isinstance(documents, list) and 0 < len(documents) <= _MAX_DOCUMENTS and all(
        isinstance(document, str) and _DOCUMENT_RE.match(document) for document in documents)
    if not valid:
        raise SandboxError(f"the policy entry for '{scope.name}' is invalid")
    return documents


def payload_violation(payload, scope: Scope, documents: list):
    if not isinstance(payload, dict):
        return "the hook payload is not a JSON object"
    if "agent_id" in payload:
        return "tool calls of subagents are not allowed"
    cwd = payload.get("cwd")
    if not isinstance(cwd, str) or os.path.realpath(cwd) != scope.worktree:
        return "the working directory is not the worktree root"
    return tool_violation(payload.get("tool_name"), payload.get("tool_input"), scope, documents)


def tool_violation(tool_name, tool_input, scope: Scope, documents: list):
    if not isinstance(tool_name, str) or not isinstance(tool_input, dict):
        return "the payload has no tool name or tool input"
    if tool_name == "Bash":
        return bash_input_violation(tool_input, scope.name, documents)
    if tool_name in _FILE_TOOLS:
        return own_markdown_violation(tool_name, tool_input, scope)
    if tool_name == "Skill":
        return None if tool_input.get("skill") == _SKILL_NAME else f"only the skill {_SKILL_NAME} is allowed"
    if tool_name in _PLANNING_TOOLS:
        return None
    return f"the tool {tool_name} is not allowed"


def own_markdown_violation(tool_name: str, tool_input: dict, scope: Scope):
    file_path = tool_input.get("file_path")
    if not isinstance(file_path, str) or not file_path:
        return f"{tool_name} without a file path"
    target = os.path.realpath(os.path.join(scope.worktree, file_path))
    own = os.path.join(scope.worktree, "excels", f"{scope.name}.md")
    return None if target == own else f"{tool_name} is only allowed on excels/{scope.name}.md"


def block(verdict: Verdict, scope: Scope) -> None:
    print(build_message(verdict, scope), file=sys.stderr, end="")
    log_block(verdict)
    sys.exit(_BLOCK_EXIT_CODE)


def build_message(verdict: Verdict, scope: Scope) -> str:
    head = _MESSAGE_HEAD.format(reason=verdict.reason)
    if verdict.documents is None:
        return head + _MESSAGE_STOP
    forms = _MESSAGE_FORMS.format(
        ticker=scope.name, unset=UNSET_PREFIX, collection=COLLECTION, documents=", ".join(verdict.documents),
        helper=" ".join(HELPER_PREFIX), heredoc_open=HEREDOC_OPEN, heredoc_end=HEREDOC_END,
        commit_collect=COMMIT_COLLECT.format(ticker=scope.name), commit_findings=COMMIT_FINDINGS.format(ticker=scope.name),
        skill=_SKILL_NAME,
    )
    return head + forms + _MESSAGE_STOP


def log_block(verdict: Verdict) -> None:
    payload = verdict.payload if isinstance(verdict.payload, dict) else {}
    tool_input = payload.get("tool_input")
    subject = json.dumps(tool_input, ensure_ascii=False)[:_SUBJECT_MAX_CHARS] if isinstance(tool_input, dict) else ""
    log_fire(_HOOK_NAME, "block", str(payload.get("tool_name")), subject, reason=str(verdict.reason), session_id=payload.get("session_id"))


if __name__ == "__main__":
    block_bom1_worker_sandbox_workflow()
