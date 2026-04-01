#!/usr/bin/env python3
"""Capture all 6 tmux panes of a running Monitor_CC session (4 windows) and combine into a single PNG."""

import argparse
import subprocess
from pathlib import Path

from PIL import Image

# --- INFRASTRUCTURE ---

# (window.pane, label) for each of the 6 panes across 4 windows:
#   Window 0 "main":    0.0=main,     0.1=tokens
#   Window 1 "rules":   1.0=rules,    1.1=hooks
#   Window 2 "workers": 2.0=workers (incl. subagents below)
#   Window 3 "debug":   3.0=warnings
PANE_TARGETS = [
    ("0.0", "main"),
    ("0.1", "tokens"),
    ("1.0", "rules"),
    ("1.1", "hooks"),
    ("2.0", "workers"),
    ("3.0", "warnings"),
]

OUTPUT_PATH = Path("/tmp/monitor_cc_screenshot.png")
PANE_TXT_TEMPLATE = "/tmp/monitor_pane_{n}.txt"
PANE_PNG_TEMPLATE = "/tmp/monitor_pane_{n}.png"

# Layout ratios: (x_start, y_start, width, height) as fractions of combined image
PANE_LAYOUT = [
    # Row 1: Window 0 (main+tokens) | Window 1 (rules+hooks)
    (0.0,  0.0,  0.25, 0.5),   # 0: main
    (0.25, 0.0,  0.25, 0.5),   # 1: tokens
    (0.5,  0.0,  0.25, 0.5),   # 2: rules
    (0.75, 0.0,  0.25, 0.5),   # 3: hooks
    # Row 2: Window 2 (workers+subagents) | Window 3 (warnings)
    (0.0,  0.5,  0.5,  0.5),   # 4: workers (incl. subagents)
    (0.5,  0.5,  0.5,  0.5),   # 5: warnings
]

COMBINED_WIDTH = 3200
COMBINED_HEIGHT = 2000


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
    """Load 6 pane PNGs and compose into combined layout image."""
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
    parser = argparse.ArgumentParser(description="Screenshot all 6 Monitor_CC tmux panes.")
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
