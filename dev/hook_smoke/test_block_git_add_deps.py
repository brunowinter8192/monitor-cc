# INFRASTRUCTURE
import json
import sys
from case_strands import exit_code_runners, run_case_strands
from hook_runner import run_hook

HOOK = "src/hooks/block_git_add_deps.py"

CASES = [

    ("FP 09-23 python heredoc after git checkout PASS",
     "git checkout -- dev/box_status_bar/md/report.md && python3 - <<'EOF'\np=\"src/DOCS.md\"; s=open(p).read()\na=s.index(\"### boxStatusBar.ts (117 LOC)\")\nopen(p,\"w\").write(s)\nEOF\nkill $(lsof -tiTCP:4460 -sTCP:LISTEN) 2>/dev/null; rm -f /tmp/x", 0),
    ("FP 09-24 sed -i then cat heredoc mentioning git add venv PASS",
     "W=/tmp/wt; cd $W\nsed -i '' 's/a/b/' dev/skill_picker/DOCS.md\ncat > process-docs/x.md <<'EOF'\n# note\n\nThe hook blocks git add venv/ wrongly. Worker's ./venv/bin/python fails.\nEOF\ngit -C $W add -A && git -C $W commit -m \"docs: x\"", 0),
    ("FP 09-25 python heredoc then cat heredoc with ln -s venv PASS",
     "B=$(cat /tmp/base_dir); rm -rf $B/base0\npython3 - <<'EOF'\ns=open(\"/tmp/snap.sh\").read()\ns=s.replace(\"ln -s $W/venv $B/curtree_$label/venv\\n\",\"\")\nopen(\"/tmp/snap.sh\",\"w\").write(s)\nEOF\nmkdir $B/base0; git archive 7bb68ff | tar -x -C $B/base0", 0),
    ("FP 09-25 worker cat >> heredoc with ./venv/bin/python then git add -A commit PASS",
     "M=/tmp/m; cd $M; cat >> process-docs/a/note.md <<'EOF'\n## Other fixes\n\n- Run with ./venv/bin/python and don't stage venv/ manually.\nEOF\ngit -C $M add -A && git -C $M commit -m \"docs: note\"", 0),
    ("FP 09-25 orchestrator prompt file heredoc naming positives PASS",
     "cat > /tmp/spawn-worker.md <<'EOF'\n# task\n\nReal positives: git add of venv/, .venv, node_modules/, also in the git -C <path> add form.\nEOF", 0),
    ("FP git add -A chained with venv python in another command PASS",
     "git add -A && ./venv/bin/python -m pytest", 0),
    ("FP quoted commit message naming git add venv PASS",
     "git commit -m 'stop git add venv/ from being blocked'", 0),
    ("git add -A alone PASS",
     "git add -A", 0),
    ("git add regular file PASS",
     "git add src/hooks/block_git_add_deps.py", 0),
    ("git add path containing venv as substring PASS",
     "git add src/venv_tools.py", 0),

    ("git add venv/ BLOCK",
     "git add venv/", 2),
    ("git add venv without slash BLOCK",
     "git add venv", 2),
    ("git add .venv BLOCK",
     "git add .venv", 2),
    ("git add node_modules/ BLOCK",
     "git add node_modules/", 2),
    ("git -C path add venv BLOCK",
     "git -C /repo add venv", 2),
    ("git add -A venv BLOCK",
     "git add -A venv", 2),
    ("git add file and venv/ BLOCK",
     "git add README.md venv/", 2),
    ("chained cd then git add node_modules BLOCK",
     "cd /repo && git add node_modules", 2),
    ("git add venv/ after heredoc in same call BLOCK",
     "cat > /tmp/a.md <<'EOF'\nnote\nEOF\ngit add venv/", 2),
]


# ORCHESTRATOR

def test_block_git_add_deps_workflow() -> None:
    sys.exit(run_case_strands(globals(), __file__, exit_code_runners(CASES, _run_hook)))


# FUNCTIONS

def _run_hook(command: str) -> int:
    payload = json.dumps({
        "tool_name": "Bash",
        "tool_input": {"command": command},
    })
    result = run_hook(HOOK, payload.encode())
    return result.returncode


if __name__ == "__main__":
    test_block_git_add_deps_workflow()
