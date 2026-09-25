#!/usr/bin/env python3
# INFRASTRUCTURE
import argparse
import subprocess
from pathlib import Path

from PIL import Image

PANE_TARGETS = [
    ("0.0", "main"),
    ("0.1", "tokens"),
    ("1.0", "proxy"),
    ("1.1", "metadata"),
    ("2.0", "rules"),
    ("2.1", "hooks"),
    ("3.0", "workers"),
    ("3.1", "worker-proxy"),
    ("3.2", "worker-metadata"),
    ("4.0", "warnings"),
]

OUTPUT_PATH = Path("/tmp/monitor_cc_screenshot.png")
PANE_TXT_TEMPLATE = "/tmp/monitor_pane_{n}.txt"
PANE_PNG_TEMPLATE = "/tmp/monitor_pane_{n}.png"

PANE_LAYOUT = [
    (0.00, 0.0,  0.70, 0.2),
    (0.70, 0.0,  0.30, 0.2),
    (0.00, 0.2,  0.70, 0.2),
    (0.70, 0.2,  0.30, 0.2),
    (0.00, 0.4,  0.50, 0.2),
    (0.50, 0.4,  0.50, 0.2),
    (0.00, 0.6,  0.34, 0.2),
    (0.34, 0.6,  0.33, 0.2),
    (0.67, 0.6,  0.33, 0.2),
    (0.00, 0.8,  1.00, 0.2),
]

COMBINED_WIDTH = 3200
COMBINED_HEIGHT = 2500


# ORCHESTRATOR

def main() -> None:
    parser = argparse.ArgumentParser(description="Screenshot all 10 Monitor_CC tmux panes (5 windows).")
    parser.add_argument("--session", default=None, help="tmux session name (default: auto-detect monitor_cc_*)")
    args = parser.parse_args()

    session = compute_session(args)

    png_paths = []
    process_pane_targets(session, png_paths)

    combined = compose_layout(png_paths)
    combined.save(str(OUTPUT_PATH))

    print(str(OUTPUT_PATH))


# FUNCTIONS

def compute_session(args):
    return args.session if args.session else detect_session()


def detect_session() -> str:
    output = run(["tmux", "ls"])
    for line in output.splitlines():
        name = line.split(":")[0]
        if name.startswith("monitor_cc_"):
            return name
    raise RuntimeError("No monitor_cc_* session found. Is the monitor running?")


def run(cmd: list[str]) -> str:
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(f"Command failed: {' '.join(cmd)}\n{result.stderr}")
    return result.stdout.strip()


def process_pane_targets(session, png_paths):
    for idx, (pane, _label) in enumerate(PANE_TARGETS):
        txt_path = capture_pane_text(session, pane, idx)
        columns = get_pane_width(session, pane)
        png_path = render_pane_png(txt_path, idx, columns)
        png_paths.append(png_path)


def capture_pane_text(session: str, pane: str, idx: int) -> str:
    txt_path = PANE_TXT_TEMPLATE.format(n=idx)
    content = run(["tmux", "capture-pane", "-p", "-e", "-t", f"{session}:{pane}"])
    Path(txt_path).write_text(content, encoding="utf-8")
    return txt_path


def get_pane_width(session: str, pane: str) -> str:
    return run(["tmux", "display", "-p", "-t", f"{session}:{pane}", "#{pane_width}"])


def render_pane_png(txt_path: str, idx: int, columns: str) -> str:
    png_path = PANE_PNG_TEMPLATE.format(n=idx)
    run([
        "termshot",
        "--raw-read", txt_path,
        "--filename", png_path,
        "--columns", columns,
    ])
    return png_path


def compose_layout(png_paths: list[str]) -> Image.Image:
    combined = Image.new("RGB", (COMBINED_WIDTH, COMBINED_HEIGHT), color=(30, 30, 30))
    for idx, png_path in enumerate(png_paths):
        pane_img = Image.open(png_path)
        x_frac, y_frac, w_frac, h_frac = PANE_LAYOUT[idx]
        slot_w = int(COMBINED_WIDTH * w_frac)
        slot_h = int(COMBINED_HEIGHT * h_frac)
        slot_x = int(COMBINED_WIDTH * x_frac)
        slot_y = int(COMBINED_HEIGHT * y_frac)
        pane_img = pane_img.resize((slot_w, slot_h), Image.LANCZOS)
        combined.paste(pane_img, (slot_x, slot_y))
    return combined


if __name__ == "__main__":
    main()
