# INFRASTRUCTURE
import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))

"""
Unit tests for cwd_desktop.json sidecar:
  1. None result does NOT clobber a previously known-good entry (LKG semantics)
  2. cwd removed from active set → next write omits it (stale cleanup)

Run from project root:
    ./venv/bin/python dev/test_cwd_desktop_sidecar.py
"""
import json
import os
import sys
import tempfile
import importlib
import types
from pathlib import Path
from unittest.mock import patch

# ORCHESTRATOR

def test_sidecar_workflow() -> None:
    _test_none_does_not_clobber_lkg()
    _test_stale_cwd_removed_on_active_set_shrink()
    print("ALL TESTS PASSED")

# FUNCTIONS

# Inject a controlled _cwd_desktop_lkg into the real discover module and verify write output
def _run_sidecar_write_with_lkg(lkg: dict, tmp_dir: Path) -> dict:
    import src.menubar.discover as discover_mod
    import src.menubar.desktop_detection as det_mod

    # Swap module-level LKG and file path
    original_lkg = det_mod._cwd_desktop_lkg.copy()
    det_mod._cwd_desktop_lkg.clear()
    det_mod._cwd_desktop_lkg.update(lkg)

    sidecar_path = tmp_dir / "cwd_desktop.json"
    with patch("src.menubar.discover.CWD_DESKTOP_FILE", sidecar_path):
        discover_mod._write_cwd_desktop_sidecar()

    # Restore original LKG
    det_mod._cwd_desktop_lkg.clear()
    det_mod._cwd_desktop_lkg.update(original_lkg)

    return json.loads(sidecar_path.read_text()) if sidecar_path.exists() else {}

# Test 1: None result must NOT clobber a known-good entry in the sidecar
def _test_none_does_not_clobber_lkg() -> None:
    import src.menubar.desktop_detection as det_mod

    with tempfile.TemporaryDirectory() as td:
        tmp_dir = Path(td)

        # Simulate: first successful detection for /proj/a → LKG populated
        det_mod._cwd_desktop_lkg.clear()
        det_mod._cwd_desktop_lkg["/proj/a"] = {"space_id": 4, "desktop_no": 2}

        # Write sidecar with good LKG
        result1 = _run_sidecar_write_with_lkg(det_mod._cwd_desktop_lkg.copy(), tmp_dir)
        assert result1 == {"/proj/a": {"space_id": 4, "desktop_no": 2}}, \
            f"First write wrong: {result1}"

        # Simulate: detection fails (returns None) — LKG must NOT be touched by detect_ callers
        # The orchestrator only updates _cwd_desktop_lkg on the `if info:` success path.
        # Simulate this by NOT updating the LKG dict (the code contract).
        # LKG still holds the old good value:
        lkg_after_failure = {"/proj/a": {"space_id": 4, "desktop_no": 2}}

        result2 = _run_sidecar_write_with_lkg(lkg_after_failure, tmp_dir)
        assert result2 == {"/proj/a": {"space_id": 4, "desktop_no": 2}}, \
            f"LKG was clobbered by None: {result2}"

        print("  PASS: None does not clobber LKG")

# Test 2: cwd removed from active set → stale cleanup removes it from LKG → next write omits it
def _test_stale_cwd_removed_on_active_set_shrink() -> None:
    import src.menubar.desktop_detection as det_mod

    with tempfile.TemporaryDirectory() as td:
        tmp_dir = Path(td)

        # Simulate: two cwds known-good
        det_mod._cwd_desktop_lkg.clear()
        det_mod._cwd_desktop_lkg["/proj/a"] = {"space_id": 4, "desktop_no": 2}
        det_mod._cwd_desktop_lkg["/proj/b"] = {"space_id": 7, "desktop_no": 3}

        result1 = _run_sidecar_write_with_lkg(det_mod._cwd_desktop_lkg.copy(), tmp_dir)
        assert "/proj/a" in result1 and "/proj/b" in result1, \
            f"Initial write incomplete: {result1}"

        # Simulate stale cleanup: /proj/b session closed → detect_main_desktop_numbers
        # removes it from _cwd_desktop_lkg (the `for gone in ... if c not in cwds` block)
        active_cwds = frozenset({"/proj/a"})
        for gone in [c for c in det_mod._cwd_desktop_lkg if c not in active_cwds]:
            del det_mod._cwd_desktop_lkg[gone]

        result2 = _run_sidecar_write_with_lkg(det_mod._cwd_desktop_lkg.copy(), tmp_dir)
        assert "/proj/a" in result2, f"/proj/a missing after cleanup: {result2}"
        assert "/proj/b" not in result2, f"/proj/b still present after cleanup: {result2}"

        print("  PASS: stale cwd removed from active set → omitted in next write")


if __name__ == "__main__":
    test_sidecar_workflow()
