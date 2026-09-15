# INFRASTRUCTURE
import json
import os
import re
import sys
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _shell_strip import _strip_non_shell_active
from _fire_log import log_fire

_REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_REPO_ROOT))
from src.constants import BASH_FILE_MODIFICATION_FORMS

_FORM_BY_LABEL = {f["label"]: f for f in BASH_FILE_MODIFICATION_FORMS}

_ALWAYS_BLOCK_LABELS = {"sed -i", "perl -pi/-ni", "gawk -i inplace", "python open() mode r+"}
_ALWAYS_ALLOW_LABELS = {"python open() mode x", "appending redirect >>", "tee -a", "python open() mode a"}
_NEEDS_STAT_LABELS = {
    "truncating redirect >", "force-clobber redirect >|", "read-write redirect <>",
    "tee (truncating)", "python open() mode w",
}
assert _ALWAYS_BLOCK_LABELS | _ALWAYS_ALLOW_LABELS | _NEEDS_STAT_LABELS == set(_FORM_BY_LABEL)

_PYTHON_BODY_LABELS = ("python open() mode r+", "python open() mode w")
_SHELL_EDIT_LABELS = ("sed -i", "perl -pi/-ni", "gawk -i inplace")
_SHELL_STAT_LABELS = ("truncating redirect >", "force-clobber redirect >|", "read-write redirect <>", "tee (truncating)")

_PY_C_RE = re.compile(r"""python3?\s+-c\s+(["'])((?:\\.|(?!\1).)*)\1""", re.DOTALL)
_PY_HD_OPEN_RE = re.compile(r"python3?\s*(?:-\s*)?<<\s*'(\w+)'")

_CANONICAL_DELIM = "LINEEDIT"
_CANONICAL_MARKERS = (
    re.compile(r'path\s*=\s*[\'"]'),
    re.compile(r"edits\s*=\s*\["),
    re.compile(r"\.lstrip\(\)\[:len\(fp\)\]"),
    re.compile(r"sorted\(edits,\s*reverse=True\)"),
    re.compile(r"open\(path,\s*encoding="),
    re.compile(r'open\(path,\s*[\'"]w[\'"],\s*encoding='),
)

_TOKEN_PREFIX_RE = re.compile(r"^\w+=(.*)$")

_NEXT_TOKEN_RE = re.compile(r"([^\s;&|)`]+)")
_TEE_LEADING_FLAGS_RE = re.compile(r"^\s*(?:-\S+\s+)*([^\s;&|)`]+)")

_BLOCK_MSG_TEMPLATE = (
    "BLOCKED: this command would modify the content of an existing file (__PATH__) without "
    "using the canonical line-numbered edit form. Only this form is accepted for changing what "
    "is already on disk -- appending to the end and creating a brand-new file are unaffected by "
    "this rule.\n\n"
    "Issue exactly this shape, one call per file, every edit in the same 'edits' list, in any order:\n\n"
    "python3 - <<'LINEEDIT'\n"
    "path = \"__PATH__\"\n"
    "edits = [\n"
    '    (START, END, "FIRST-LINE-PREFIX", """NEW TEXT FOR THIS RANGE"""),\n'
    "]\n"
    'with open(path, encoding="utf-8") as f:\n'
    '    lines = f.read().split("\\n")\n'
    "for start, end, fp, new in sorted(edits, reverse=True):\n"
    "    got = lines[start - 1].lstrip()[:len(fp)]\n"
    "    if got != fp:\n"
    '        raise SystemExit(f"fingerprint mismatch at line {start}: expected {fp!r}, got {got!r}")\n'
    '    lines[start - 1:end] = new.split("\\n")\n'
    'with open(path, "w", encoding="utf-8") as f:\n'
    '    f.write("\\n".join(lines))\n'
    "LINEEDIT\n\n"
    "START/END are the 1-indexed first/last line of the range you're changing (START == END for "
    "a single line). FIRST-LINE-PREFIX is the first 8-15 characters of line START's own text, "
    "with leading whitespace stripped -- read straight off the file you already have; if that "
    "line is shorter than that, use the whole (shorter) line. The replacement text goes inside "
    "the triple quotes verbatim -- real newlines, no backslash-n, no escaping needed -- except "
    "it must not itself contain three consecutive double-quote characters.\n"
)


# ORCHESTRATOR

def block_non_canonical_edit_workflow() -> None:
    command, session_id, cwd = _parse_command()
    if command is None:
        sys.exit(0)
    try:
        verdict, reason = _decide(command, cwd)
    except Exception as e:
        print(f"[block_non_canonical_edit] internal error, failing open: {type(e).__name__}: {e}", file=sys.stderr)
        sys.exit(0)
    if verdict == "block":
        print(reason, file=sys.stderr, end="")
        log_fire("block_non_canonical_edit", "block", "Bash", command, reason=reason, session_id=session_id)
        sys.exit(2)
    sys.exit(0)


# FUNCTIONS

def _parse_command():
    try:
        payload = json.loads(sys.stdin.read())
        cmd = payload.get("tool_input", {}).get("command")
        return (cmd if isinstance(cmd, str) else None), payload.get("session_id"), payload.get("cwd")
    except Exception:
        return None, None, None


def _decide(command: str, cwd) -> tuple:
    invocations = _find_python_invocations(command)
    for start, end, kind, delim, body in invocations:
        if kind == "heredoc" and delim == _CANONICAL_DELIM and _is_canonical_linedit(body):
            continue
        verdict = _python_body_verdict(body, cwd)
        if verdict is not None:
            return verdict
    blanked = _blank_spans(command, invocations)
    stripped = _strip_non_shell_active(blanked)
    verdict = _shell_level_verdict(stripped, cwd)
    if verdict is not None:
        return verdict
    return "allow", None


def _find_python_invocations(command: str) -> list:
    spans = []
    for m in _PY_C_RE.finditer(command):
        spans.append((m.start(), m.end(), "c", None, m.group(2)))
    for m in _PY_HD_OPEN_RE.finditer(command):
        delim = m.group(1)
        body_re = re.compile(r"<<\s*'" + re.escape(delim) + r"'\r?\n(.*?)\r?\n" + re.escape(delim) + r"\b", re.DOTALL)
        bm = body_re.search(command, m.start())
        if bm:
            spans.append((bm.start(), bm.end(), "heredoc", delim, bm.group(1)))
    spans.sort(key=lambda s: s[0])
    return spans


def _is_canonical_linedit(body: str) -> bool:
    return all(marker.search(body) for marker in _CANONICAL_MARKERS)


def _blank_spans(command: str, spans: list) -> str:
    blanked = command
    for start, end, *_ in spans:
        blanked = blanked[:start] + (" " * (end - start)) + blanked[end:]
    return blanked


def _python_body_verdict(body: str, cwd):
    for label in _PYTHON_BODY_LABELS:
        pattern = _FORM_BY_LABEL[label]["pattern"]
        m = pattern.search(body)
        if not m:
            continue
        path = _resolve_python_open_path(body, m, cwd)
        if label in _ALWAYS_BLOCK_LABELS:
            return "block", _build_block_message(path or "<the file you are editing>")
        if path is None or not os.path.exists(path):
            continue
        return "block", _build_block_message(path)
    return None


def _resolve_python_open_path(body: str, match, cwd):
    call_text = match.group(0)
    m = re.search(r"open\(\s*['\"]([^'\"]+)['\"]", call_text)
    if m:
        return _resolve_target_path(m.group(1), cwd)
    m = re.search(r"open\(\s*([A-Za-z_]\w*)", call_text)
    if not m:
        return None
    var = m.group(1)
    m2 = re.search(r"\b" + re.escape(var) + r"\s*=\s*['\"]([^'\"]+)['\"]", body)
    if not m2:
        return None
    return _resolve_target_path(m2.group(1), cwd)


def _shell_level_verdict(stripped: str, cwd):
    for label in _SHELL_EDIT_LABELS:
        pattern = _FORM_BY_LABEL[label]["pattern"]
        if pattern.search(stripped):
            target = _resolve_sed_like_target(stripped, label, cwd)
            return "block", _build_block_message(target or "<the file you are editing>")
    tee_append_hit = bool(_FORM_BY_LABEL["tee -a"]["pattern"].search(stripped))
    for label in _SHELL_STAT_LABELS:
        if label == "tee (truncating)" and tee_append_hit:
            continue
        pattern = _FORM_BY_LABEL[label]["pattern"]
        m = pattern.search(stripped)
        if not m:
            continue
        path = _resolve_redirect_target(stripped, label, m, cwd)
        if path is None:
            continue
        if not os.path.exists(path):
            continue
        return "block", _build_block_message(path)
    return None


def _resolve_redirect_target(stripped: str, label: str, match, cwd):
    tail = stripped[match.end():]
    if label == "tee (truncating)":
        tm = _TEE_LEADING_FLAGS_RE.match(tail)
    else:
        tm = _NEXT_TOKEN_RE.match(tail)
    if not tm:
        return None
    return _resolve_target_path(tm.group(1).rstrip(");,"), cwd)


def _resolve_sed_like_target(stripped: str, label: str, cwd):
    pattern = _FORM_BY_LABEL[label]["pattern"]
    m = pattern.search(stripped)
    if not m:
        return None
    tail = stripped[m.end():]
    seg_end = re.search(r"[;&|\n]", tail)
    seg = tail[:seg_end.start()] if seg_end else tail
    tokens = [t for t in seg.split() if t and not t.startswith("-")]
    if not tokens:
        return None
    return _resolve_target_path(tokens[-1].strip("'\""), cwd)


def _resolve_target_path(token: str, cwd):
    prefix_match = _TOKEN_PREFIX_RE.match(token)
    path = prefix_match.group(1) if prefix_match else token
    path = path.strip("'\"")
    if not path or "$" in path or path.startswith("`"):
        return None
    path = os.path.expanduser(path)
    if not os.path.isabs(path):
        base = cwd if isinstance(cwd, str) and cwd else os.getcwd()
        path = os.path.join(base, path)
    return path


def _build_block_message(path: str) -> str:
    return _BLOCK_MSG_TEMPLATE.replace("__PATH__", path)


if __name__ == "__main__":
    block_non_canonical_edit_workflow()
