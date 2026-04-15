#!/usr/bin/env python3
"""Capture all 10 tmux panes of a running Monitor_CC session (5 windows) and combine into a single PNG."""

import argparse
import subprocess
from pathlib import Path

from PIL import Image

# --- INFRASTRUCTURE ---

# (window.pane, label) for each of the 10 panes across 5 windows:
#   Window 0 "main":    0.0=MAIN,    0.1=TOKENS
#   Window 1 "proxy":   1.0=PROXY,   1.1=METADATA
#   Window 2 "rules":   2.0=RULES,   2.1=HOOKS
#   Window 3 "workers": 3.0=WORKERS, 3.1=WORKER-PROXY, 3.2=WORKER-METADATA
#   Window 4 "debug":   4.0=WARNINGS
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

# Layout ratios: (x_start, y_start, width, height) as fractions of combined image
# 5 rows, one per window — each row occupies 20% of total height
PANE_LAYOUT = [
    # Row 0: Window 0 "main"    — main (70%) | tokens (30%)
    (0.00, 0.0,  0.70, 0.2),   # 0: main
    (0.70, 0.0,  0.30, 0.2),   # 1: tokens
    # Row 1: Window 1 "proxy"   — proxy (70%) | metadata (30%)
    (0.00, 0.2,  0.70, 0.2),   # 2: proxy
    (0.70, 0.2,  0.30, 0.2),   # 3: metadata
    # Row 2: Window 2 "rules"   — rules (50%) | hooks (50%)
    (0.00, 0.4,  0.50, 0.2),   # 4: rules
    (0.50, 0.4,  0.50, 0.2),   # 5: hooks
    # Row 3: Window 3 "workers" — workers (34%) | worker-proxy (33%) | worker-metadata (33%)
    (0.00, 0.6,  0.34, 0.2),   # 6: workers
    (0.34, 0.6,  0.33, 0.2),   # 7: worker-proxy
    (0.67, 0.6,  0.33, 0.2),   # 8: worker-metadata
    # Row 4: Window 4 "debug"   — warnings (100%)
    (0.00, 0.8,  1.00, 0.2),   # 9: warnings
]

COMBINED_WIDTH = 3200
COMBINED_HEIGHT = 2500


def run(cmd: list[str]) -> str:
    """Run subprocess, raise on failure, return stdout."""
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(f"Command failed: {' '.join(cmd)}\n{result.stderr}")
    return result.stdout.strip()


# --- FUNCTIONS ---

def detect_session() -> str:
    """Auto-detect running monitor_cc_* session from tmux ls."""
    output = run(["tmux", "ls"])
    for line in output.splitlines():
        name = line.split(":")[0]
        if name.startswith("monitor_cc_"):
            return name
    raise RuntimeError("No monitor_cc_* session found. Is the monitor running?")


def get_pane_width(session: str, pane: str) -> str:
    """Return pane width as string for termshot --columns. pane is 'window.pane' e.g. '0.0'."""
    return run(["tmux", "display", "-p", "-t", f"{session}:{pane}", "#{pane_width}"])


def capture_pane_text(session: str, pane: str, idx: int) -> str:
    """Capture pane content including ANSI escapes to temp file, return path. pane is 'window.pane' e.g. '0.0'."""
    txt_path = PANE_TXT_TEMPLATE.format(n=idx)
    content = run(["tmux", "capture-pane", "-p", "-e", "-t", f"{session}:{pane}"])
    Path(txt_path).write_text(content, encoding="utf-8")
    return txt_path


def render_pane_png(txt_path: str, idx: int, columns: str) -> str:
    """Render ANSI text file to PNG via termshot, return output path."""
    png_path = PANE_PNG_TEMPLATE.format(n=idx)
    run([
        "termshot",
        "--raw-read", txt_path,
        "--filename", png_path,
        "--columns", columns,
    ])
    return png_path


def compose_layout(png_paths: list[str]) -> Image.Image:
    """Load 10 pane PNGs and compose into combined layout image."""
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


# --- ORCHESTRATOR ---

def main() -> None:
    parser = argparse.ArgumentParser(description="Screenshot all 10 Monitor_CC tmux panes (5 windows).")
    parser.add_argument("--session", default=None, help="tmux session name (default: auto-detect monitor_cc_*)")
    args = parser.parse_args()

    session = args.session if args.session else detect_session()

    png_paths = []
    for idx, (pane, _label) in enumerate(PANE_TARGETS):
        txt_path = capture_pane_text(session, pane, idx)
        columns = get_pane_width(session, pane)
        png_path = render_pane_png(txt_path, idx, columns)
        png_paths.append(png_path)

    combined = compose_layout(png_paths)
    combined.save(str(OUTPUT_PATH))

    print(str(OUTPUT_PATH))


if __name__ == "__main__":
    main()
