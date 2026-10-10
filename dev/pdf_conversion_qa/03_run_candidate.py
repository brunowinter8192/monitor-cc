# INFRASTRUCTURE
import argparse
import json
import platform
import subprocess
import sys

from dev.pdf_conversion_qa.candidates import run_window
from dev.pdf_conversion_qa.config import JSON_DIR, MANIFEST_FILE, RUN_RESULTS_FILE

ENVIRONMENT_FILE = JSON_DIR / "03_environment.json"
MINERU_PIP = "/Users/brunowinter2000/Documents/ai/Mineru/venv/bin/pip"
PIP_PACKAGES = ("mineru", "mlx-vlm", "mlx", "transformers", "torch", "mineru_vl_utils", "pypdfium2")


# ORCHESTRATOR
def run_candidate_workflow() -> None:
    args = parse_args()
    windows = load_windows()
    existing = load_results()
    write_environment()
    selected = select_windows(args.select, windows, existing, args.candidate)
    for window in selected:
        if already_done(existing, args.candidate, window["window_id"], args.rep) and not args.redo:
            continue
        row = run_window(args.candidate, window, args.rep, "windows")
        append_result(row)
        print(f"{row['candidate']} {row['window_id']} rep{row['rep']} {row['status']} {row['wall_s']}s peak={row['peak_footprint_gb']}GB {row['failure_reason'] or ''}", flush=True)


# FUNCTIONS
def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--candidate", required=True, choices=["C1", "C2", "C3", "C4a", "C4b", "C5a", "C5b"])
    parser.add_argument("--select", default="all")
    parser.add_argument("--rep", type=int, default=1)
    parser.add_argument("--redo", action="store_true")
    return parser.parse_args()


def load_windows() -> list[dict]:
    return json.loads(MANIFEST_FILE.read_text())["windows"]


def load_results() -> list[dict]:
    if not RUN_RESULTS_FILE.exists():
        return []
    return [json.loads(line) for line in RUN_RESULTS_FILE.read_text().splitlines() if line.strip()]


def already_done(existing: list[dict], candidate: str, window_id: str, rep: int) -> bool:
    return any(r["candidate"] == candidate and r["window_id"] == window_id and r["rep"] == rep for r in existing)


def select_windows(selector: str, windows: list[dict], existing: list[dict], candidate: str) -> list[dict]:
    if selector == "all":
        return windows
    if selector == "panel":
        return [w for w in windows if w["panel"]]
    if selector == "calibration":
        return [w for w in windows if w["window_id"].startswith("TelekomPib")]
    if selector.startswith("failed-of:"):
        source = selector.split(":", 1)[1]
        failed = {r["window_id"] for r in existing if r["candidate"] == source and r["rep"] == 1 and r["status"] == "fail"}
        return [w for w in windows if w["window_id"] in failed]
    if selector.startswith("ids:"):
        wanted = set(selector.split(":", 1)[1].split(","))
        return [w for w in windows if w["window_id"] in wanted]
    raise SystemExit(f"unknown selector: {selector}")


def append_result(row: dict) -> None:
    RUN_RESULTS_FILE.parent.mkdir(parents=True, exist_ok=True)
    with RUN_RESULTS_FILE.open("a") as handle:
        handle.write(json.dumps(row, ensure_ascii=False) + "\n")


def write_environment() -> None:
    listing = subprocess.run([MINERU_PIP, "list"], capture_output=True, text=True).stdout.splitlines()
    pins = [line for line in listing if line.split(" ")[0].lower().replace("_", "-") in {p.replace("_", "-") for p in PIP_PACKAGES}]
    ENVIRONMENT_FILE.write_text(json.dumps({
        "machine": platform.platform(),
        "mac_ver": platform.mac_ver()[0],
        "chip": subprocess.run(["sysctl", "-n", "machdep.cpu.brand_string"], capture_output=True, text=True).stdout.strip(),
        "mineru_venv_packages": pins,
    }, indent=1))


if __name__ == "__main__":
    sys.exit(run_candidate_workflow())
