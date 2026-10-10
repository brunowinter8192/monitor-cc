# INFRASTRUCTURE
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

from dev.pdf_conversion_qa.config import JSON_DIR, PATCH_DIR, ROOT

MINERU_PYTHON = Path.home() / "Documents" / "ai" / "Mineru" / "venv" / "bin" / "python"
PROBE_SCRIPT = ROOT / "detokenizer_probe.py"
OUTPUT_FILE = JSON_DIR / "00_detokenizer_check.json"


# ORCHESTRATOR
def detokenizer_check_workflow() -> None:
    unpatched = run_probe(patched=False)
    patched = run_probe(patched=True)
    OUTPUT_FILE.write_text(json.dumps({"unpatched": unpatched, "patched": patched}, indent=1, ensure_ascii=False))
    print(json.dumps({"unpatched": unpatched, "patched": patched}, ensure_ascii=False))


# FUNCTIONS
def run_probe(patched: bool) -> dict:
    marker = Path(tempfile.mkdtemp()) / "marker.txt"
    env = os.environ.copy()
    if patched:
        env["PYTHONPATH"] = str(PATCH_DIR)
        env["QA_DETOKENIZER_PATCH"] = "1"
        env["QA_PATCH_MARKER"] = str(marker)
    result = subprocess.run([str(MINERU_PYTHON), str(PROBE_SCRIPT)], env=env, capture_output=True, text=True)
    return {
        "exit_code": result.returncode,
        "probe": parse_probe_output(result.stdout),
        "stderr_tail": result.stderr[-400:],
        "marker_pids": marker.read_text().split() if marker.exists() else [],
    }


def parse_probe_output(stdout: str) -> dict:
    lines = [line for line in stdout.splitlines() if line.startswith("{")]
    return json.loads(lines[-1]) if lines else {}


if __name__ == "__main__":
    sys.exit(detokenizer_check_workflow())
