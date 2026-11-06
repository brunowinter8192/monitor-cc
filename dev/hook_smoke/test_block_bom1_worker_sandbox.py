# INFRASTRUCTURE
import json
import os
import subprocess
import sys
import tempfile
from case_strands import exit_code_runners, function_runners, report_case, run_case_strands
from hook_runner import FIRING_LOG_ENV, REPO_ROOT, run_hook

HOOK = "src/hooks/block_bom1_worker_sandbox.py"
PROJECT_ENV = "CLAUDE_PROJECT_DIR"
ADS = "ADS_RemunerationReport_2024.md"
SAP_DOC = "SAP_RemunerationReport_2024.md"
UNSET = "unset PYTHONHOME PYTHONPATH RESOURCEPATH EXECUTABLEPATH ARGVZERO; "
HELPER = ("env -u PYTHONHOME -u PYTHONPATH -u RESOURCEPATH -u EXECUTABLEPATH -u ARGVZERO "
          "uv run -q --no-project --with openpyxl python tools/workbook_io.py")
POLICY = {
    "SAP": [SAP_DOC, ADS],
    "IFX": ["IFX_RemunerationReport_2025.md", ADS],
    "ALV": ["ALV_AnnualReport_2024.md", ADS],
}
SCENARIOS = {
    "SAP": ("SAP", "good"), "IFX": ("IFX", "good"), "NOPE": ("NOPE", "good"), "DEV": ("dev-sandbox", "good"),
    "NO_POLICY": ("SAP", "none"), "BAD_POLICY": ("SAP", "bad"), "BAD_ENTRY": ("SAP", "badentry"),
    "NO_ENV": ("SAP", "good"), "SUBDIR": ("SAP", "good"), "ROOT": ("SAP", "good"), "OTHER": ("SAP", "good"),
}
ALLOWED_EXIT = 0
BLOCKED_EXIT = 2


# ORCHESTRATOR

def test_block_bom1_worker_sandbox_workflow() -> None:
    sys.exit(run_case_strands(globals(), __file__, _all_runners()))


# FUNCTIONS

def _all_runners() -> dict:
    runners = exit_code_runners(_all_cases(), _run_case)
    runners.update(function_runners([
        _check_block_message_names_allowed_forms,
        _check_block_message_for_unknown_worker_has_no_forms,
        _check_block_is_written_to_the_fire_log,
        _check_allowed_call_writes_no_fire_log,
    ]))
    return runners


def _all_cases() -> list:
    return (_allowed_cases() + _blocked_rag_cases() + _blocked_helper_and_git_cases() + _blocked_command_cases()
            + _blocked_tool_cases() + _blocked_payload_cases() + _scope_cases())


def _ok(desc: str, spec: dict, scenario: str = "SAP") -> tuple:
    return (desc, spec, ALLOWED_EXIT, scenario)


def _no(desc: str, spec: dict, scenario: str = "SAP") -> tuple:
    return (desc, spec, BLOCKED_EXIT, scenario)


def _bash(command, **extra) -> dict:
    return {"tool": "Bash", "input": {"command": command, **extra}}


def _tool(tool: str, **tool_input) -> dict:
    return {"tool": tool, "input": tool_input}


def _write_command(body: str, head: str = None) -> str:
    return (head or f"{HELPER} write SAP Data_Compensation") + " <<'ROWS'\n" + body + "\nROWS"


def _allowed_cases() -> list:
    search = f"rag-cli search \"CEO total remuneration\" bom1-reports --document '{SAP_DOC}'"
    expand = f"rag-cli expand_chunks bom1-reports {SAP_DOC} 10"
    return [
        _ok("list_documents with unset prefix", _bash(UNSET + "rag-cli list_documents bom1-reports --document 'SAP_%'")),
        _ok("list_documents without unset prefix", _bash("rag-cli list_documents bom1-reports --document 'SAP_%'")),
        _ok("full payload shape observed in the 02.11.2026 probe", {
            "tool": "Bash", "input": {"command": "rag-cli list_documents bom1-reports --document 'SAP_%'", "description": "List documents"},
            "extra": {"effort": "low", "hook_event_name": "PreToolUse", "permission_mode": "bypassPermissions", "prompt_id": "p",
                      "scratchpad_dir": "/tmp/s", "tool_use_id": "t", "transcript_path": "/tmp/t.jsonl"}}),
        _ok("search with unset prefix, own document", _bash(UNSET + search)),
        _ok("search, adidas document", _bash(f"rag-cli search \"q\" bom1-reports --document '{ADS}'")),
        _ok("search with single-quoted query and bare document", _bash(f"rag-cli search 'short term incentive' bom1-reports --document {SAP_DOC}")),
        _ok("search query with parentheses percent ampersand apostrophe", _bash(f"rag-cli search \"Total (EUR) 5% R&D CEO's bonus\" bom1-reports --document '{SAP_DOC}'")),
        _ok("search query with non-ASCII characters", _bash(f"rag-cli search \"Gesamtvergütung in €\" bom1-reports --document '{SAP_DOC}'")),
        _ok("expand without options", _bash(UNSET + expand)),
        _ok("expand with before and after", _bash(f"{expand} --before 1 --after 10")),
        _ok("expand with after then before", _bash(f"{expand} --after 4 --before 2")),
        _ok("expand with only after", _bash(f"{expand} --after 3")),
        _ok("expand adidas document", _bash(f"rag-cli expand_chunks bom1-reports {ADS} 3 --before 0 --after 2")),
        _ok("search own IFX document", _bash(f"rag-cli search \"q\" bom1-reports --document 'IFX_RemunerationReport_2025.md'"), "IFX"),
        _ok("helper read Metric_Classification", _bash(f"{HELPER} read SAP Metric_Classification")),
        _ok("helper read own Data_Compensation", _bash(f"{HELPER} read SAP Data_Compensation")),
        _ok("helper read-reference", _bash(f"{HELPER} read-reference Data_Compensation")),
        _ok("helper read own Data_KPI", _bash(f"{HELPER} read SAP Data_KPI")),
        _ok("helper read-reference Data_KPI", _bash(f"{HELPER} read-reference Data_KPI")),
        _ok("helper read own Data_KPI for IFX", _bash(f"{HELPER} read IFX Data_KPI"), "IFX"),
        _ok("helper write Data_KPI heredoc", _bash(_write_command('[{"values": {}, "pages": {}}]', f"{HELPER} write SAP Data_KPI"))),
        _ok("helper write Data_KPI heredoc, body is inert shell text", _bash(_write_command("$(rm -rf /)\n`id`\n; ls\nROWSX", f"{HELPER} write SAP Data_KPI"))),
        _ok("helper write heredoc", _bash(_write_command('[{"ISIN": "x", "Pages": "15, 17"}]'))),
        _ok("helper write heredoc, body is inert shell text", _bash(_write_command("$(rm -rf /)\n`id`\n; ls\n| cat\n> /etc/passwd\nEOF\nROWSX"))),
        _ok("helper write heredoc with trailing newline", _bash(_write_command("[]") + "\n")),
        _ok("git add both files and commit feat", _bash('git add excels/SAP.xlsx excels/SAP.md && git commit -m "feat: collect SAP compensation data"')),
        _ok("git add md and commit docs", _bash('git add excels/SAP.md && git commit -m "docs: record SAP findings"')),
        _ok("git commit message in single quotes", _bash("git commit -m 'docs: record SAP findings'")),
        _ok("git add alone", _bash("git add excels/SAP.xlsx excels/SAP.md")),
        _ok("git commit alone", _bash('git commit -m "feat: collect SAP compensation data"')),
        _ok("git add both files and commit kpi feat", _bash('git add excels/SAP.xlsx excels/SAP.md && git commit -m "feat: collect SAP kpi data"')),
        _ok("git add md and commit kpi docs", _bash('git add excels/SAP.md && git commit -m "docs: record SAP kpi findings"')),
        _ok("git commit kpi message in single quotes", _bash("git commit -m 'docs: record SAP kpi findings'")),
        _ok("git commit kpi feat alone", _bash('git commit -m "feat: collect SAP kpi data"')),
        _ok("git commit kpi for IFX uses the IFX ticker", _bash('git add excels/IFX.md && git commit -m "docs: record IFX kpi findings"'), "IFX"),
        _ok("git commit for IFX uses the IFX ticker", _bash('git add excels/IFX.md && git commit -m "docs: record IFX findings"'), "IFX"),
        _ok("Bash with description timeout and false flags", _bash("rag-cli list_documents bom1-reports --document 'SAP_%'", description="d", timeout=60000, run_in_background=False, dangerouslyDisableSandbox=False)),
        _ok("Read own md absolute", _tool("Read", file_path="@WT@/excels/SAP.md")),
        _ok("Read own md relative", _tool("Read", file_path="excels/SAP.md")),
        _ok("Write own md", _tool("Write", file_path="@WT@/excels/SAP.md", content="x")),
        _ok("Edit own md", _tool("Edit", file_path="@WT@/excels/SAP.md", old_string="a", new_string="b")),
        _ok("Skill firm-compensation-collection", _tool("Skill", skill="firm-compensation-collection")),
        _ok("Skill with args", _tool("Skill", skill="firm-compensation-collection", args="SAP")),
        _ok("Skill firm-kpi-collection", _tool("Skill", skill="firm-kpi-collection")),
        _ok("Skill firm-kpi-collection with args", _tool("Skill", skill="firm-kpi-collection", args="SAP")),
        _ok("TodoWrite", _tool("TodoWrite", todos=[])),
        _ok("TaskCreate", _tool("TaskCreate", subject="x")),
        _ok("TaskUpdate", _tool("TaskUpdate", taskId="1")),
        _ok("TaskList", _tool("TaskList")),
        _ok("TaskGet", _tool("TaskGet", taskId="1")),
    ]


def _blocked_rag_cases() -> list:
    base = f"rag-cli search \"q\" bom1-reports --document '{SAP_DOC}'"
    cases = [
        _no("env var prefix", _bash("FOO=1 " + base)),
        _no("PYTHONUNBUFFERED prefix", _bash("PYTHONUNBUFFERED=1 " + base)),
        _no("command substitution in query", _bash(f"rag-cli search \"$(cat /etc/passwd)\" bom1-reports --document '{SAP_DOC}'")),
        _no("backticks in query", _bash(f"rag-cli search \"`id`\" bom1-reports --document '{SAP_DOC}'")),
        _no("variable in query", _bash(f"rag-cli search \"$HOME\" bom1-reports --document '{SAP_DOC}'")),
        _no("braced variable in query", _bash(f"rag-cli search \"${{HOME}}\" bom1-reports --document '{SAP_DOC}'")),
        _no("backslash in query", _bash(f"rag-cli search \"a\\nb\" bom1-reports --document '{SAP_DOC}'")),
        _no("dollar in single-quoted query", _bash(f"rag-cli search '$HOME' bom1-reports --document '{SAP_DOC}'")),
        _no("variable as document", _bash("rag-cli search \"q\" bom1-reports --document $DOC")),
        _no("variable as collection", _bash(f"rag-cli search \"q\" $COL --document '{SAP_DOC}'")),
        _no("process substitution", _bash(f"rag-cli search \"q\" bom1-reports --document <(echo {SAP_DOC})")),
        _no("pipe to head", _bash(base + " | head -5")),
        _no("pipe to tee", _bash(base + " | tee /tmp/x")),
        _no("redirect to file", _bash(base + " > /tmp/x")),
        _no("append redirect", _bash(base + " >> /tmp/x")),
        _no("stderr merge", _bash(base + " 2>&1")),
        _no("ampersand redirect", _bash(base + " &> /tmp/x")),
        _no("input redirect", _bash(base + " < /tmp/x")),
        _no("semicolon chain", _bash(base + "; ls")),
        _no("and chain", _bash(base + " && ls")),
        _no("or chain", _bash(base + " || true")),
        _no("newline chain", _bash(base + "\nls")),
        _no("backslash continuation", _bash(base + " \\\n  --document 'ALV_AnnualReport_2024.md'")),
        _no("trailing ampersand", _bash(base + " &")),
        _no("glued ampersand command", _bash(base + "&ls")),
        _no("glued ampersand without spaces on list", _bash("rag-cli list_documents bom1-reports --document 'SAP_%'&ls")),
        _no("subshell", _bash("(" + base + ")")),
        _no("brace group", _bash("{ " + base + "; }")),
        _no("quote concatenation in document", _bash(f"rag-cli search \"q\" bom1-reports --document 'SAP_Remuneration'\"Report_2024.md\"")),
        _no("quote concatenation in query", _bash(f"rag-cli search \"a\"'b' bom1-reports --document '{SAP_DOC}'")),
        _no("absolute path to rag-cli", _bash(f"/Users/x/.local/bin/rag-cli search \"q\" bom1-reports --document '{SAP_DOC}'")),
        _no("venv python cli.py", _bash(f"./venv/bin/python cli.py search \"q\" bom1-reports --document '{SAP_DOC}'")),
        _no("python3 cli.py index", _bash("python3 cli.py index --collection bom1-reports")),
        _no("variable interpreter", _bash("PYBIN=$(cat /tmp/p); \"$PYBIN\" \"$CLIPATH\" search")),
        _no("bash -c", _bash(f"bash -c \"rag-cli search 'q' bom1-reports --document '{SAP_DOC}'\"")),
        _no("sh -c", _bash("sh -c 'rag-cli list_collections'")),
        _no("eval", _bash("eval rag-cli list_collections")),
        _no("env rag-cli", _bash("env rag-cli list_collections")),
        _no("command rag-cli", _bash("command rag-cli list_collections")),
        _no("exec rag-cli", _bash("exec rag-cli list_collections")),
        _no("time rag-cli", _bash(f"time {base}")),
        _no("nohup rag-cli", _bash(f"nohup {base}")),
        _no("glob in document", _bash("rag-cli search \"q\" bom1-reports --document SAP_*")),
        _no("percent wildcard in search", _bash("rag-cli search \"q\" bom1-reports --document 'SAP_%'")),
        _no("bare percent document", _bash("rag-cli search \"q\" bom1-reports --document '%'")),
        _no("abbreviated --doc", _bash(f"rag-cli search \"q\" bom1-reports --doc '{SAP_DOC}'")),
        _no("--document= form", _bash(f"rag-cli search \"q\" bom1-reports --document='{SAP_DOC}'")),
        _no("duplicate --document", _bash(base + f" --document '{ADS}'")),
        _no("--exclude", _bash(base + " --exclude 'x'")),
        _no("--filter on search", _bash(base + " --filter x")),
        _no("search without --document", _bash("rag-cli search \"q\" bom1-reports")),
        _no("flag before collection", _bash(f"rag-cli search \"q\" --document '{SAP_DOC}' bom1-reports")),
        _no("collection bom1-docs", _bash(f"rag-cli search \"q\" bom1-docs --document '{SAP_DOC}'")),
        _no("collection bom1-reference", _bash(f"rag-cli search \"q\" bom1-reference --document '{SAP_DOC}'")),
        _no("collection with suffix", _bash(f"rag-cli search \"q\" bom1-reports-x --document '{SAP_DOC}'")),
        _no("collection uppercase", _bash(f"rag-cli search \"q\" BOM1-REPORTS --document '{SAP_DOC}'")),
        _no("document of another firm", _bash("rag-cli search \"q\" bom1-reports --document 'ALV_AnnualReport_2024.md'")),
        _no("annual report not in the policy", _bash("rag-cli search \"q\" bom1-reports --document 'SAP_AnnualReport_2024.md'")),
        _no("document wrong case", _bash("rag-cli search \"q\" bom1-reports --document 'sap_remunerationreport_2024.md'")),
        _no("document path traversal", _bash("rag-cli search \"q\" bom1-reports --document '../x.md'")),
        _no("IFX worker uses SAP document", _bash(f"rag-cli search \"q\" bom1-reports --document '{SAP_DOC}'"), "IFX"),
        _no("empty query", _bash(f"rag-cli search \"\" bom1-reports --document '{SAP_DOC}'")),
        _no("query starting with dash", _bash(f"rag-cli search \"--document x\" bom1-reports --document '{SAP_DOC}'")),
        _no("query longer than 300 characters", _bash(f"rag-cli search \"{'a' * 301}\" bom1-reports --document '{SAP_DOC}'")),
        _no("newline inside query", _bash(f"rag-cli search \"a\nb\" bom1-reports --document '{SAP_DOC}'")),
        _no("tab inside query", _bash(f"rag-cli search \"a\tb\" bom1-reports --document '{SAP_DOC}'")),
        _no("zero-width character in query", _bash(f"rag-cli search \"a​b\" bom1-reports --document '{SAP_DOC}'")),
        _no("expand negative chunk", _bash(f"rag-cli expand_chunks bom1-reports {SAP_DOC} -1")),
        _no("expand non-numeric chunk", _bash(f"rag-cli expand_chunks bom1-reports {SAP_DOC} abc")),
        _no("expand five-digit chunk", _bash(f"rag-cli expand_chunks bom1-reports {SAP_DOC} 12345")),
        _no("expand negative before", _bash(f"rag-cli expand_chunks bom1-reports {SAP_DOC} 1 --before -1")),
        _no("expand before without value", _bash(f"rag-cli expand_chunks bom1-reports {SAP_DOC} 1 --before")),
        _no("expand duplicate after", _bash(f"rag-cli expand_chunks bom1-reports {SAP_DOC} 1 --after 2 --after 3")),
        _no("expand extra flag", _bash(f"rag-cli expand_chunks bom1-reports {SAP_DOC} 1 --force")),
        _no("expand wildcard document", _bash("rag-cli expand_chunks bom1-reports 'SAP_%' 1")),
        _no("expand other document", _bash("rag-cli expand_chunks bom1-reports ALV_AnnualReport_2024.md 1")),
        _no("expand other collection", _bash(f"rag-cli expand_chunks bom1-docs {SAP_DOC} 1")),
        _no("list_documents other ticker", _bash("rag-cli list_documents bom1-reports --document 'ALV_%'")),
        _no("list_documents without filter", _bash("rag-cli list_documents bom1-reports")),
        _no("list_documents adidas pattern", _bash("rag-cli list_documents bom1-reports --document 'ADS_%'")),
        _no("list_documents with exclude", _bash("rag-cli list_documents bom1-reports --document 'SAP_%' --exclude x")),
        _no("list_documents other collection", _bash("rag-cli list_documents bom1-docs --document 'SAP_%'")),
        _no("rag-cli alone", _bash("rag-cli")),
        _no("rag-cli --help", _bash("rag-cli --help")),
        _no("rag-cli search --help", _bash("rag-cli search --help")),
        _no("rag-cli list_collections", _bash("rag-cli list_collections")),
        _no("rag-cli index", _bash("rag-cli index --collection bom1-reports")),
        _no("rag-cli delete", _bash("rag-cli delete --collection bom1-reports")),
        _no("rag-cli update_docs", _bash("rag-cli update_docs .")),
        _no("rag-cli progress", _bash("rag-cli progress bom1-reports")),
        _no("rag-cli status", _bash("rag-cli status")),
        _no("rag-cli server", _bash("rag-cli server status")),
        _no("unset of PATH", _bash("unset PATH; " + base)),
        _no("unset of one variable", _bash("unset PYTHONHOME; " + base)),
        _no("unset prefix with extra variable", _bash("unset PYTHONHOME PYTHONPATH RESOURCEPATH EXECUTABLEPATH ARGVZERO PATH; " + base)),
        _no("unset prefix without space after semicolon", _bash(UNSET.rstrip() + base)),
        _no("unset prefix with double space", _bash(UNSET + " " + base)),
        _no("double unset", _bash(UNSET + "unset X; " + base)),
        _no("unset prefix in front of git", _bash(UNSET + 'git commit -m "feat: collect SAP compensation data"')),
        _no("unset prefix in front of helper", _bash(UNSET + f"{HELPER} read SAP Data_Compensation")),
        _no("unset prefix alone", _bash(UNSET.rstrip())),
        _no("double space in command", _bash(f"rag-cli  list_documents bom1-reports --document 'SAP_%'")),
        _no("tab separator", _bash("rag-cli\tlist_documents bom1-reports --document 'SAP_%'")),
        _no("trailing space", _bash("rag-cli list_documents bom1-reports --document 'SAP_%' ")),
        _no("leading space", _bash(" rag-cli list_documents bom1-reports --document 'SAP_%'")),
        _no("carriage return", _bash("rag-cli list_documents bom1-reports --document 'SAP_%'\r")),
    ]
    return cases


def _blocked_helper_and_git_cases() -> list:
    prefix = HELPER.split(" python ")[0]
    return [
        _no("helper read other ticker", _bash(f"{HELPER} read ALV Data_Compensation")),
        _no("helper read Data_Dictionary", _bash(f"{HELPER} read SAP Data_Dictionary")),
        _no("helper read Data_KPI of another ticker", _bash(f"{HELPER} read ALV Data_KPI")),
        _no("helper read-reference Metric_Classification", _bash(f"{HELPER} read-reference Metric_Classification")),
        _no("helper read-reference Data_Dictionary", _bash(f"{HELPER} read-reference Data_Dictionary")),
        _no("helper read-reference Data_KPI with extra argument", _bash(f"{HELPER} read-reference Data_KPI SAP")),
        _no("helper read-reference Data_KPI with ticker", _bash(f"{HELPER} read-reference SAP Data_KPI")),
        _no("helper read Data_KPI with extra argument", _bash(f"{HELPER} read SAP Data_KPI extra")),
        _no("helper read Data_KPI lowercase", _bash(f"{HELPER} read SAP data_kpi")),
        _no("helper read Data_KPI with heredoc", _bash(_write_command("[]", f"{HELPER} read SAP Data_KPI"))),
        _no("helper read-reference Data_KPI with heredoc", _bash(_write_command("[]", f"{HELPER} read-reference Data_KPI"))),
        _no("helper write Data_KPI without heredoc", _bash(f"{HELPER} write SAP Data_KPI")),
        _no("helper write Data_KPI other ticker", _bash(_write_command("[]", f"{HELPER} write ALV Data_KPI"))),
        _no("helper write Data_KPI ADS", _bash(_write_command("[]", f"{HELPER} write ADS Data_KPI"))),
        _no("helper write Data_Dictionary", _bash(_write_command("[]", f"{HELPER} write SAP Data_Dictionary"))),
        _no("helper write Data_KPI with EOF delimiter", _bash(f"{HELPER} write SAP Data_KPI <<'EOF'\n[]\nEOF")),
        _no("helper write Metric_Classification", _bash(_write_command("[]", f"{HELPER} write SAP Metric_Classification"))),
        _no("helper write other ticker", _bash(_write_command("[]", f"{HELPER} write ALV Data_Compensation"))),
        _no("helper write ADS", _bash(_write_command("[]", f"{HELPER} write ADS Data_Compensation"))),
        _no("helper extra argument", _bash(f"{HELPER} read SAP Data_Compensation extra")),
        _no("helper without env prefix", _bash("uv run -q --no-project --with openpyxl python tools/workbook_io.py read SAP Data_Compensation")),
        _no("helper with extra package", _bash(f"{prefix} --with requests python tools/workbook_io.py read SAP Data_Compensation")),
        _no("helper other script path", _bash(f"{prefix} python tools/other.py read SAP Data_Compensation")),
        _no("helper absolute script path", _bash(f"{prefix} python /tmp/workbook_io.py read SAP Data_Compensation")),
        _no("free python from stdin", _bash(f"{prefix} python -")),
        _no("free python with heredoc", _bash(f"{prefix} python - <<'EOF'\nimport os\nEOF")),
        _no("python -c", _bash("python3 -c 'print(1)'")),
        _no("uv run python -c", _bash("uv run python -c 'import os'")),
        _no("helper write without heredoc", _bash(f"{HELPER} write SAP Data_Compensation")),
        _no("helper read with heredoc", _bash(_write_command("[]", f"{HELPER} read SAP Data_Compensation"))),
        _no("heredoc on a rag command", _bash(_write_command("x", f"rag-cli list_documents bom1-reports --document 'SAP_%'"))),
        _no("heredoc on cat", _bash(_write_command("x", "cat"))),
        _no("heredoc with EOF delimiter", _bash(f"{HELPER} write SAP Data_Compensation <<'EOF'\n[]\nEOF")),
        _no("heredoc with unquoted delimiter", _bash(f"{HELPER} write SAP Data_Compensation <<ROWS\n[]\nROWS")),
        _no("heredoc with dash form", _bash(f"{HELPER} write SAP Data_Compensation <<-'ROWS'\n[]\nROWS")),
        _no("heredoc with double-quoted delimiter", _bash(f"{HELPER} write SAP Data_Compensation <<\"ROWS\"\n[]\nROWS")),
        _no("heredoc body ends early then command runs", _bash(_write_command("[]\nROWS\nrm -rf /\nx"))),
        _no("heredoc terminator followed by a command", _bash(_write_command("[]") + "\nls")),
        _no("heredoc terminator followed by a second terminator", _bash(_write_command("[]") + "\nROWS")),
        _no("heredoc without terminator", _bash(f"{HELPER} write SAP Data_Compensation <<'ROWS'\n[]")),
        _no("heredoc terminator with trailing text", _bash(f"{HELPER} write SAP Data_Compensation <<'ROWS'\n[]\nROWS; ls")),
        _no("heredoc with redirect after the opener", _bash(f"{HELPER} write SAP Data_Compensation <<'ROWS' > /tmp/x\n[]\nROWS")),
        _no("heredoc with pipe after the opener", _bash(f"{HELPER} write SAP Data_Compensation <<'ROWS' | cat\n[]\nROWS")),
        _no("heredoc opener on a later line", _bash(f"ls\n{HELPER} write SAP Data_Compensation <<'ROWS'\n[]\nROWS")),
        _no("heredoc with carriage return in body", _bash(_write_command("[]\r"))),
        _no("heredoc with NUL in body", _bash(_write_command("[]\x00"))),
        _no("heredoc body over the size limit", _bash(_write_command("x" * 300001))),
        _no("git add -A", _bash("git add -A")),
        _no("git add dot", _bash("git add .")),
        _no("git add excels directory", _bash("git add excels/")),
        _no("git add other firm xlsx", _bash("git add excels/ALV.xlsx")),
        _no("git add own xlsx and other md", _bash("git add excels/SAP.xlsx excels/ALV.md")),
        _no("git add own files in swapped order", _bash("git add excels/SAP.md excels/SAP.xlsx")),
        _no("git add the helper", _bash("git add tools/workbook_io.py")),
        _no("git add settings", _bash("git add .claude/settings.json")),
        _no("git add force", _bash("git add -f excels/SAP.md")),
        _no("git commit other message", _bash('git commit -m "other message"')),
        _no("git commit message of another ticker", _bash('git commit -m "feat: collect ALV compensation data"')),
        _no("git commit kpi message of another ticker", _bash('git commit -m "feat: collect ALV kpi data"')),
        _no("git commit kpi message with suffix", _bash('git commit -m "feat: collect SAP kpi data now"')),
        _no("git commit kpi message with swapped type", _bash('git commit -m "docs: collect SAP kpi data"')),
        _no("git commit kpi findings with feat type", _bash('git commit -m "feat: record SAP kpi findings"')),
        _no("git commit kpi message with command substitution", _bash('git commit -m "feat: collect $(id) kpi data"')),
        _no("git commit message with suffix", _bash('git commit -m "feat: collect SAP compensation data now"')),
        _no("git commit amend", _bash('git commit --amend -m "feat: collect SAP compensation data"')),
        _no("git commit -am", _bash('git commit -am "feat: collect SAP compensation data"')),
        _no("git commit no-verify", _bash('git commit --no-verify -m "feat: collect SAP compensation data"')),
        _no("git commit without message", _bash("git commit")),
        _no("git commit allow-empty", _bash('git commit --allow-empty -m "feat: collect SAP compensation data"')),
        _no("git commit message with command substitution", _bash('git commit -m "feat: collect $(id) compensation data"')),
        _no("git status", _bash("git status")),
        _no("git log", _bash("git log")),
        _no("git diff", _bash("git diff")),
        _no("git show", _bash("git show HEAD")),
        _no("git branch", _bash("git branch -a")),
        _no("git checkout", _bash("git checkout main")),
        _no("git push", _bash("git push")),
        _no("git config", _bash("git config user.name x")),
        _no("git -C other repo", _bash("git -C /tmp add excels/SAP.md")),
        _no("git commit before add", _bash('git commit -m "docs: record SAP findings" && git add excels/SAP.md')),
        _no("git add and git add", _bash("git add excels/SAP.md && git add excels/SAP.xlsx")),
        _no("git add then other command", _bash("git add excels/SAP.md && ls")),
        _no("git add semicolon commit", _bash('git add excels/SAP.md; git commit -m "docs: record SAP findings"')),
        _no("three git commands", _bash('git add excels/SAP.md && git commit -m "docs: record SAP findings" && git push')),
        _no("git commit then pipe", _bash('git commit -m "docs: record SAP findings" | cat')),
    ]


def _blocked_command_cases() -> list:
    commands = [
        "ls", "ls excels", "cat excels/ALV.md", "cat /etc/passwd", "cd /tmp", "pwd", "echo hi", "true", "sleep 1",
        "curl http://example.com", "wget http://example.com", "python3 -c 'print(1)'", "python tools/workbook_io.py read SAP Data_Compensation",
        "duallog sessions", "worker-cli list", "worker-cli capture other", "poread /etc/hosts", "sed -n 1p excels/ALV.md",
        "find / -name '*.md'", "grep -r CEO .", "tmux ls", "rm excels/SAP.md", "mv excels/SAP.md /tmp/x", "cp excels/ALV.md /tmp/x",
        "ln -s /etc/passwd excels/SAP.md", "chmod 777 tools/workbook_io.py", "bash", "sh -c ls", "eval ls", "source /tmp/x", "xargs ls",
        "nohup ls", "websearch search_web q", "gh-cli get_issue a b 1", "linkedin get_messages", "cd /tmp && " + UNSET + "rag-cli list_documents bom1-reports --document 'SAP_%'",
        f"{HELPER.split(' python ')[0]} python - <<'EOF'\nimport os\nEOF", "cat <<'EOF'\nx\nEOF", "ls $(pwd)", "ls `pwd`", "echo $HOME", "~/bin/x", "./tools/workbook_io.py",
    ]
    cases = [_no(f"command: {command[:50]!r}", _bash(command)) for command in commands]
    cases += [
        _no("empty command", _bash("")),
        _no("whitespace-only command", _bash("   ")),
        _no("non-string command", _bash(["ls"])),
        _no("missing command", _tool("Bash", description="x")),
        _no("run_in_background true", _bash("rag-cli list_documents bom1-reports --document 'SAP_%'", run_in_background=True)),
        _no("dangerouslyDisableSandbox true", _bash("rag-cli list_documents bom1-reports --document 'SAP_%'", dangerouslyDisableSandbox=True)),
        _no("unknown Bash input key", _bash("rag-cli list_documents bom1-reports --document 'SAP_%'", foo="x")),
        _no("string timeout", _bash("rag-cli list_documents bom1-reports --document 'SAP_%'", timeout="60")),
        _no("boolean timeout", _bash("rag-cli list_documents bom1-reports --document 'SAP_%'", timeout=True)),
        _no("command over the size limit", _bash("a" * 300001)),
    ]
    return cases


def _blocked_tool_cases() -> list:
    other_tools = [
        ("Agent", {"description": "x", "prompt": "y"}), ("Task", {"description": "x", "prompt": "y"}), ("WebFetch", {"url": "http://x"}),
        ("WebSearch", {"query": "x"}), ("Glob", {"pattern": "*"}), ("Grep", {"pattern": "x"}), ("NotebookEdit", {"notebook_path": "x"}),
        ("ToolSearch", {"query": "x"}), ("ExitPlanMode", {}), ("EnterPlanMode", {}), ("BashOutput", {"bash_id": "1"}), ("KillShell", {"shell_id": "1"}),
        ("TaskOutput", {"task_id": "1"}), ("TaskStop", {"task_id": "1"}), ("mcp__postgres__query", {"sql": "select 1"}), ("SlashCommand", {"command": "/x"}),
        ("AskUserQuestion", {"questions": []}), ("", {}), ("read", {"file_path": "excels/SAP.md"}),
    ]
    cases = [_no(f"tool {name or '(empty name)'}", _tool(name, **tool_input)) for name, tool_input in other_tools]
    cases += [
        _no("Skill other name", _tool("Skill", skill="probe-skill")),
        _no("Skill thesis-writing", _tool("Skill", skill="thesis-writing")),
        _no("Skill namespaced name", _tool("Skill", skill="bom1:firm-compensation-collection")),
        _no("Skill namespaced kpi name", _tool("Skill", skill="bom1:firm-kpi-collection")),
        _no("Skill kpi name with suffix", _tool("Skill", skill="firm-kpi-collection-2")),
        _no("Skill kpi name uppercase", _tool("Skill", skill="Firm-KPI-Collection")),
        _no("Skill without name", _tool("Skill")),
    ]
    paths = {
        "other firm md": "@WT@/excels/ALV.md", "other firm md relative": "excels/ALV.md", "own xlsx": "@WT@/excels/SAP.xlsx",
        "reference xlsx": "@WT@/reference/ADS_Reference_Topic4.xlsx", "helper script": "@WT@/tools/workbook_io.py",
        "policy file in worktree": "@WT@/allowed_documents.json", "policy file in root": "@ROOT@/allowed_documents.json",
        "project settings": "@WT@/.claude/settings.json", "git file": "@WT@/.git", "skill file": "@WT@/firm-compensation-collection/SKILL.md",
        "dotdot out of excels": "@WT@/excels/../excels/ALV.md", "dotdot through own md": "@WT@/excels/SAP.md/../ALV.md",
        "other worktree": "@WT@/../ALV/excels/ALV.md", "root excels": "@ROOT@/excels/SAP.md", "etc passwd": "/etc/passwd",
        "home settings": "~/.claude/settings.json", "wrong case": "@WT@/excels/sap.md", "tmp file": "/tmp/x.md", "excels directory": "@WT@/excels",
        "empty path": "", "directory dot": ".",
    }
    for label, path in paths.items():
        cases.append(_no(f"Read {label}", _tool("Read", file_path=path)))
        cases.append(_no(f"Write {label}", _tool("Write", file_path=path, content="x")))
        cases.append(_no(f"Edit {label}", _tool("Edit", file_path=path, old_string="a", new_string="b")))
    cases += [
        _no("Read without file_path", _tool("Read")),
        _no("Write with non-string file_path", _tool("Write", file_path=["x"], content="x")),
        _no("Read via symlinked excels directory", _tool("Read", file_path="@WT@/excels/SAP.md"), "SYMLINK"),
    ]
    return cases


def _blocked_payload_cases() -> list:
    allowed_input = {"command": "rag-cli list_documents bom1-reports --document 'SAP_%'"}
    return [
        _no("subagent call with agent_id", {"tool": "Bash", "input": allowed_input, "extra": {"agent_id": "a1", "agent_type": "general-purpose"}}),
        _no("payload cwd is another directory", {"tool": "Bash", "input": allowed_input, "cwd": "/tmp"}),
        _no("payload cwd is the worktree excels directory", {"tool": "Bash", "input": allowed_input, "cwd": "@WT@/excels"}),
        _no("payload cwd is the project root", {"tool": "Bash", "input": allowed_input, "cwd": "@ROOT@"}),
        _no("payload cwd missing", {"tool": "Bash", "input": allowed_input, "cwd": None}),
        _no("payload cwd not a string", {"tool": "Bash", "input": allowed_input, "cwd": 5}),
        _no("tool_name missing", {"tool": None, "input": allowed_input}),
        _no("tool_name not a string", {"tool": 5, "input": allowed_input}),
        _no("tool_input missing", {"tool": "Bash", "input": None}),
        _no("tool_input is a list", {"tool": "Bash", "input": ["ls"]}),
        _no("payload is a JSON list", {"raw": b"[1, 2]"}),
        _no("payload is a JSON string", {"raw": b'"text"'}),
        _no("payload is garbage", {"raw": b"not json{{{"}),
        _no("payload is empty", {"raw": b""}),
        _no("payload is invalid UTF-8", {"raw": b"\xff\xfe\x00"}),
        _no("worker name not in the policy", {"tool": "Bash", "input": allowed_input}, "NOPE"),
        _no("worker name not in the policy, harmless tool", {"tool": "TodoWrite", "input": {}}, "NOPE"),
        _no("policy file missing", {"tool": "Bash", "input": allowed_input}, "NO_POLICY"),
        _no("policy file is not JSON", {"tool": "Bash", "input": allowed_input}, "BAD_POLICY"),
        _no("policy entry is invalid", {"tool": "Bash", "input": allowed_input}, "BAD_ENTRY"),
        _no("project dir below the worktree root", {"tool": "Bash", "input": allowed_input, "cwd": "@WT@/excels"}, "SUBDIR"),
        _ok("project env missing, session in the worktree, allowed call", {"tool": "Bash", "input": allowed_input}, "NO_ENV"),
        _no("project env missing, session in the worktree, blocked call", {"tool": "Bash", "input": {"command": "ls"}}, "NO_ENV"),
    ]


def _scope_cases() -> list:
    blocked_in_scope = {"tool": "Bash", "input": {"command": "rm -rf /"}}
    return [
        _ok("root session of BOM1-worker is free", blocked_in_scope, "ROOT"),
        _ok("root session is free even with garbage stdin", {"raw": b"not json"}, "ROOT"),
        _ok("root session is free for other tools", {"tool": "Agent", "input": {"prompt": "x"}}, "ROOT"),
        _ok("other project is free", blocked_in_scope, "OTHER"),
        _ok("other project is free with garbage stdin", {"raw": b""}, "OTHER"),
        _ok("dev- worktree is free", blocked_in_scope, "DEV"),
        _ok("dev- worktree is free with garbage stdin", {"raw": b"not json"}, "DEV"),
        _no("ticker worktree blocks the same call", blocked_in_scope, "SAP"),
    ]


def _build_tree(tmp: str, scenario: str) -> tuple:
    name, policy_mode = SCENARIOS.get(scenario, ("SAP", "good"))
    root = os.path.join(os.path.realpath(tmp), "BOM1-worker")
    worktree = os.path.join(root, ".claude", "worktrees", name)
    os.makedirs(os.path.join(worktree, "excels"))
    for md_name in (name, "ALV"):
        with open(os.path.join(worktree, "excels", f"{md_name}.md"), "w", encoding="utf-8") as handle:
            handle.write("x")
    _write_policy(root, policy_mode)
    if scenario == "SYMLINK":
        _replace_excels_with_symlink(worktree, tmp)
    return root, worktree


def _write_policy(root: str, policy_mode: str) -> None:
    contents = {"good": json.dumps(POLICY), "bad": "{not json", "badentry": json.dumps({"SAP": ["SAP_%.md", ADS]})}.get(policy_mode)
    if contents is not None:
        with open(os.path.join(root, "allowed_documents.json"), "w", encoding="utf-8") as handle:
            handle.write(contents)


def _replace_excels_with_symlink(worktree: str, tmp: str) -> None:
    target = os.path.join(os.path.realpath(tmp), "elsewhere")
    os.makedirs(target)
    with open(os.path.join(target, "SAP.md"), "w", encoding="utf-8") as handle:
        handle.write("x")
    os.rename(os.path.join(worktree, "excels"), os.path.join(worktree, "excels_real"))
    os.symlink(target, os.path.join(worktree, "excels"))


def _project_and_cwd(scenario: str, root: str, worktree: str, tmp: str) -> tuple:
    if scenario == "ROOT":
        return root, root
    if scenario == "OTHER":
        other = os.path.join(os.path.realpath(tmp), "other-project")
        os.makedirs(other)
        return other, other
    if scenario == "SUBDIR":
        return os.path.join(worktree, "excels"), os.path.join(worktree, "excels")
    if scenario == "NO_ENV":
        return None, worktree
    return worktree, worktree


def _build_stdin(spec: dict, root: str, worktree: str) -> bytes:
    if "raw" in spec:
        return spec["raw"]
    payload = {"tool_name": spec["tool"], "tool_input": spec["input"], "session_id": "s1", "cwd": spec.get("cwd", "@WT@")}
    payload.update(spec.get("extra", {}))
    text = json.dumps(payload).replace("@WT@", worktree).replace("@ROOT@", root)
    return text.encode("utf-8")


def _run_case(spec: dict, scenario: str) -> int:
    with tempfile.TemporaryDirectory(prefix="bom1_sandbox_") as tmp:
        root, worktree = _build_tree(tmp, scenario)
        project_dir, cwd = _project_and_cwd(scenario, root, worktree, tmp)
        return run_hook(HOOK, _build_stdin(spec, root, worktree), {PROJECT_ENV: project_dir}, cwd=cwd).returncode


def _run_for_stderr(spec: dict, scenario: str) -> str:
    with tempfile.TemporaryDirectory(prefix="bom1_sandbox_") as tmp:
        root, worktree = _build_tree(tmp, scenario)
        project_dir, cwd = _project_and_cwd(scenario, root, worktree, tmp)
        result = run_hook(HOOK, _build_stdin(spec, root, worktree), {PROJECT_ENV: project_dir}, cwd=cwd)
        return result.stderr.decode("utf-8", errors="replace")


def _check_block_message_names_allowed_forms() -> None:
    message = _run_for_stderr(_bash("ls"), "SAP")
    needed = [
        "BLOCKED by the BOM1 worker sandbox", "command 'ls' is not allowed", "Allowed in this worktree (SAP)", SAP_DOC, ADS,
        "rag-cli list_documents bom1-reports --document 'SAP_%'", "rag-cli search", "rag-cli expand_chunks", "tools/workbook_io.py read SAP Metric_Classification",
        "read-reference Data_Compensation", "write SAP Data_Compensation <<'ROWS'", 'git commit -m "feat: collect SAP compensation data"',
        'git commit -m "docs: record SAP findings"', "excels/SAP.md only", "firm-compensation-collection", "Stop now", "Report to the user", "go idle",
        "tools/workbook_io.py read SAP Data_KPI", "read-reference Data_KPI", "write SAP Data_KPI <<'ROWS'", 'git commit -m "feat: collect SAP kpi data"',
        'git commit -m "docs: record SAP kpi findings"', "firm-kpi-collection",
    ]
    missing = [text for text in needed if text not in message]
    report_case("block message names reason, forms, documents and the stop instruction", not missing, f": missing {missing}")


def _check_block_message_for_unknown_worker_has_no_forms() -> None:
    message = _run_for_stderr(_bash("ls"), "NOPE")
    ok = "not a ticker in the policy" in message and "Stop now" in message and "Allowed in this worktree" not in message
    report_case("unknown worker message states the reason and stop, lists no forms", ok, f": {message[:120]!r}")


def _check_block_is_written_to_the_fire_log() -> None:
    with tempfile.TemporaryDirectory(prefix="bom1_sandbox_log_") as tmp:
        log_path = os.path.join(tmp, "fire.jsonl")
        os.makedirs(os.path.join(tmp, "tree"))
        root, worktree = _build_tree(os.path.join(tmp, "tree"), "SAP")
        stdin = _build_stdin(_bash("ls -la"), root, worktree)
        env = dict(os.environ, **{FIRING_LOG_ENV: log_path, PROJECT_ENV: worktree})
        subprocess.run(["python3", str(REPO_ROOT / HOOK)], input=stdin, capture_output=True, env=env, cwd=worktree)
        records = _read_records(log_path)
    ok = len(records) == 1 and records[0]["hook"] == "block_bom1_worker_sandbox" and records[0]["decision"] == "block" \
        and records[0]["session"] == "s1" and records[0]["tool"] == "Bash" and "ls -la" in records[0]["command"]
    report_case("a block writes one fire-log record with hook, tool, session and command", ok, f": {records}")


def _read_records(log_path: str) -> list:
    if not os.path.exists(log_path):
        return []
    with open(log_path, encoding="utf-8") as handle:
        return [json.loads(line) for line in handle]


def _check_allowed_call_writes_no_fire_log() -> None:
    with tempfile.TemporaryDirectory(prefix="bom1_sandbox_log_") as tmp:
        log_path = os.path.join(tmp, "fire.jsonl")
        os.makedirs(os.path.join(tmp, "tree"))
        root, worktree = _build_tree(os.path.join(tmp, "tree"), "SAP")
        stdin = _build_stdin(_bash("rag-cli list_documents bom1-reports --document 'SAP_%'"), root, worktree)
        env = dict(os.environ, **{FIRING_LOG_ENV: log_path, PROJECT_ENV: worktree})
        result = subprocess.run(["python3", str(REPO_ROOT / HOOK)], input=stdin, capture_output=True, env=env, cwd=worktree)
        written = os.path.exists(log_path)
    report_case("an allowed call exits 0, prints nothing and writes no log", result.returncode == 0 and not result.stderr and not result.stdout and not written)


if __name__ == "__main__":
    test_block_bom1_worker_sandbox_workflow()
