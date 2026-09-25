# INFRASTRUCTURE
import sys
from pathlib import Path
from unittest.mock import patch

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT))

from AppKit import NSApplication

from dev.session_launcher.test_env import isolate_home

REPORT_PATH = REPO_ROOT / "dev" / "model_selector" / "md" / "verify_apply_flash_layout.md"


# ORCHESTRATOR

def verify_apply_flash_layout_workflow() -> None:
    isolate_home()
    NSApplication.sharedApplication()
    lines = compute_lines()
    lines = update_lines(lines)
    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    run_write_text(lines)
    print("\n".join(lines))
    print("PASS")


# FUNCTIONS

def compute_lines():
    return ["# Apply flash layout verification", ""]


def update_lines(lines):
    lines += _check_flash_and_revert()
    return lines


def _check_flash_and_revert() -> list:
    from src.menubar import model_controller
    from src.menubar.panel import _make_tab_nspanel
    panel, stack, _header = _make_tab_nspanel('Models')
    buttons = model_controller._ModelRowButtons()
    buttons.build(stack, 400, None)
    controller = model_controller.ModelController.__new__(model_controller.ModelController)
    controller._buttons = buttons
    logged = []
    initial_w = _layout_width(stack, buttons.apply)
    with patch.object(model_controller, 'log_menubar', lambda area, msg: logged.append(msg)), \
         patch.object(model_controller.threading, 'Timer') as timer:
        controller._show_apply_success()
        flash_title = str(buttons.apply.title())
        flash_w = _layout_width(stack, buttons.apply)
        controller._revert_apply_button()
        revert_title = str(buttons.apply.title())
        revert_w = _layout_width(stack, buttons.apply)
    assert logged == [], logged
    assert timer.call_args[0][0] == model_controller._APPLY_SUCCESS_DURATION
    assert flash_title == 'Applied successfully', flash_title
    assert flash_w > initial_w, (initial_w, flash_w)
    assert revert_title == 'Apply', revert_title
    assert revert_w == initial_w, (initial_w, revert_w)
    return [f"- initial width {initial_w}", f"- flash title {flash_title!r} width {flash_w}",
            f"- revert title {revert_title!r} width {revert_w}", "- no log_menubar failure lines"]


def _layout_width(stack, btn) -> float:
    stack.layoutSubtreeIfNeeded()
    return btn.frame().size.width


def run_write_text(lines):
    REPORT_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")


if __name__ == "__main__":
    verify_apply_flash_layout_workflow()
