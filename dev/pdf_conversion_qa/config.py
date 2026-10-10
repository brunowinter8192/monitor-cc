# INFRASTRUCTURE
import os
from pathlib import Path

ROOT = Path(__file__).parent
REPO_ROOT = ROOT.parent.parent

JSON_DIR = ROOT / "json"
CSV_DIR = ROOT / "csv"
MD_DIR = ROOT / "md"
SAMPLES_DIR = ROOT / "samples"
RUNS_DIR = ROOT / "runs"
TRACES_DIR = ROOT / "traces"
TESSDATA_DIR = ROOT / "tessdata"
PATCH_DIR = ROOT / "patch"
VENV_PYTHON = ROOT / "venv" / "bin" / "python"

PDF_ROOT = Path.home() / "Documents" / "ai" / "Meta" / "ClaudeCode" / "cli" / "rag-cli" / "data" / "pdf"
WISE_DIR = PDF_ROOT / "wise2627"
TRADING_DIR = PDF_ROOT / "Trading"

MINERU_BIN = Path.home() / "Documents" / "ai" / "Mineru" / "venv" / "bin" / "mineru"
MINERU_LOCK_FILE = Path.home() / ".mineru-locks" / "mineru.flock"

MANIFEST_FILE = JSON_DIR / "01_build_sample.json"
RUN_RESULTS_FILE = JSON_DIR / "03_run_candidate.jsonl"
WHOLE_RESULTS_FILE = JSON_DIR / "06_run_whole_docs.jsonl"

WATCHDOG_PROC_GB = float(os.environ.get("WATCHDOG_PROC_GB", "30"))
WATCHDOG_FLOOR_GB = float(os.environ.get("WATCHDOG_FLOOR_GB", "5"))
SAMPLE_INTERVAL_S = 1.0
FOOTPRINT_TIMEOUT_S = 8

MINERU_ENV = {
    "MINERU_INTRA_OP_NUM_THREADS": "10",
    "MINERU_VIRTUAL_VRAM_SIZE": "24",
    "MINERU_TASK_RESULT_TIMEOUT_SECONDS": "14400",
    "MINERU_PDF_RENDER_THREADS": "1",
}

MINERU_CANDIDATES = {
    "C1": {"backend": "vlm-auto-engine", "formula": "true", "patch": False},
    "C2": {"backend": "vlm-auto-engine", "formula": "true", "patch": True},
    "C3": {"backend": "pipeline", "formula": "false", "patch": False},
}
CHEAP_CANDIDATES = ("C4a", "C4b", "C5a", "C5b")

WINDOW_TIMEOUT_BASE_S = 600
WINDOW_TIMEOUT_PER_PAGE_S = 60
WHOLE_TIMEOUT_S = 10800
