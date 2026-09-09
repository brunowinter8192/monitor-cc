# INFRASTRUCTURE
import importlib
import json
import sys
import tempfile
from datetime import datetime
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT))

REPORT_PATH = REPO_ROOT / "dev" / "model_selector" / "md" / "verify_model_cycle_and_io.md"

# A minimal fixture mirroring proxy_rules.json's real on-disk convention, confirmed by a manual
# byte-diff against the live file at implementation time: every section is byte-identical to
# plain json.dumps(indent=2), EXCEPT model_params, whose per-model entries render as one compact
# single-line JSON object each. Used both to pin that convention as a regression check and as the
# base fixture for the read-modify-write tests below.
_FIXTURE_RAW = '''{
  "system2_rules": {
    "global": {
      "files": [
        "global/documentation.md"
      ]
    }
  },
  "tool_injection": {
    "exclude_projects": []
  },
  "model_params": {
    "claude-opus-5": {"thinking": {"type": "adaptive", "display": "summarized"}, "effort": "low", "max_tokens": 64000},
    "claude-fable-5": {"thinking": {"type": "adaptive", "display": "summarized"}, "effort": "medium", "max_tokens": 64000},
    "claude-untouched-9": {"thinking": {"type": "adaptive", "display": "summarized"}, "effort": "high", "max_tokens": 32000}
  },
  "pyright_diagnostics_strip": {
    "enabled": true
  },
  "future_section": {
    "some_future_key": "some_future_value"
  }
}
'''

# ORCHESTRATOR

# Verify cycle-order correctness for all 3 cycle kinds (model/effort/max_tokens), atomic-write +
# read-back/fallback correctness for model_selection.json, and the proxy_rules.json read-modify-
# write (format fidelity, foreign-content preservation, missing-entry creation, malformed-file
# fallback) — all against temp paths, never the real ~/.claude/shared-rules/.
def verify_model_cycle_and_io_workflow() -> None:
    ms = _load_model_selection_module()
    lines = [f"# Models tab — cycle + I/O verification — {datetime.now().isoformat(timespec='seconds')}", ""]

    _verify_model_cycle(ms, lines)
    _verify_effort_cycle(ms, lines)
    _verify_max_tokens_cycle(ms, lines)

    with tempfile.TemporaryDirectory() as tmp:
        _verify_model_selection_write(ms, lines, tmp)
        _verify_model_selection_readback(ms, lines, tmp)
        _verify_proxy_rules_format_fidelity(ms, lines)
        _verify_proxy_rules_read_modify_write(ms, lines, tmp)
        _verify_proxy_rules_malformed_fallback(ms, lines, tmp)

    lines.append("")
    lines.append("RESULT: PASS — model/effort/max_tokens cycles step + wrap correctly; "
                "model_selection.json write is atomic with exact 2-key schema, read-back correct "
                "for valid/missing/malformed files, unrecognized values preserved verbatim; "
                "proxy_rules.json serializer reproduces the real on-disk convention byte-for-byte, "
                "Apply's read-modify-write touches only the two selected models' effort/max_tokens "
                "(foreign sections/keys/models byte-identical, missing entries created with the "
                "established thinking-block shape, malformed file degrades to a fresh minimal file "
                "without raising).")

    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("\n".join(lines))

# FUNCTIONS

# Load the real src.menubar.model_selection module via importlib (dev/ probes must not
# write a literal 'from src.' / 'import src.' statement; a dynamic import_module call is not
# that statement and is needed here anyway — model_selection.py has a package-relative import
# that only resolves when loaded as part of the src.menubar package). (2026-09, menubar
# milestone A: every symbol this script touches — the cycle constants/functions and the
# model_selection.json/proxy_rules.json load/write functions — moved out of model_controller.py
# into this pure persistence module; re-pointed here rather than re-exported from
# model_controller.py, which no longer calls any of them directly.)
def _load_model_selection_module():
    module_name = '.'.join(['src', 'menubar', 'model_selection'])
    return importlib.import_module(module_name)

# Section 1: the 4-value model cycle (all 4 values step correctly, wraps, unrecognized -> first)
def _verify_model_cycle(ms, lines) -> None:
    lines.append("## 1. Model cycle logic (4 values)")
    choices = ms._MODEL_CHOICES
    assert len(choices) == 4, f"expected 4 model choices, got {len(choices)}: {choices}"
    for start in choices:
        nxt = ms._next_model(start)
        expected = choices[(choices.index(start) + 1) % len(choices)]
        assert nxt == expected, f"{start} -> {nxt}, expected {expected}"
        lines.append(f"{start} -> {nxt}")
    fourth_wraps = ms._next_model(choices[-1]) == choices[0]
    assert fourth_wraps
    lines.append(f"Fourth value wraps to first: {fourth_wraps}")
    unknown_next = ms._next_model("some-unrecognized-id")
    assert unknown_next == choices[0]
    lines.append(f"Unrecognized current value starts cycle at first choice: {unknown_next!r}")

# Section 2: the effort cycle (low -> medium -> high -> wraps; 'max' deliberately absent)
def _verify_effort_cycle(ms, lines) -> None:
    lines.append("")
    lines.append("## 2. Effort cycle logic")
    choices = ms._EFFORT_CHOICES
    assert choices == ("low", "medium", "high"), f"unexpected effort choices: {choices}"
    assert "max" not in choices, "'max' must stay excluded — valid only on specific Opus models"
    for start in choices:
        nxt = ms._next_effort(start)
        expected = choices[(choices.index(start) + 1) % len(choices)]
        assert nxt == expected, f"{start} -> {nxt}, expected {expected}"
        lines.append(f"{start} -> {nxt}")
    wraps = ms._next_effort(choices[-1]) == choices[0]
    assert wraps
    lines.append(f"Last value wraps to first: {wraps}")
    unknown_next = ms._next_effort("some-unrecognized-effort")
    assert unknown_next == choices[0]
    lines.append(f"Unrecognized current value starts cycle at first choice: {unknown_next!r}")

# Section 3: the max_tokens cycle (32000 -> 64000 -> 128000 -> wraps)
def _verify_max_tokens_cycle(ms, lines) -> None:
    lines.append("")
    lines.append("## 3. max_tokens cycle logic")
    choices = ms._MAXTOK_CHOICES
    assert choices == (32000, 64000, 128000), f"unexpected max_tokens choices: {choices}"
    for start in choices:
        nxt = ms._next_max_tokens(start)
        expected = choices[(choices.index(start) + 1) % len(choices)]
        assert nxt == expected, f"{start} -> {nxt}, expected {expected}"
        lines.append(f"{start} -> {nxt}")
    wraps = ms._next_max_tokens(choices[-1]) == choices[0]
    assert wraps
    lines.append(f"Last value wraps to first: {wraps}")
    unknown_next = ms._next_max_tokens(999)
    assert unknown_next == choices[0]
    lines.append(f"Unrecognized current value starts cycle at first choice: {unknown_next!r}")

# Section 4: model_selection.json atomic write — unchanged behavior for existing callers
def _verify_model_selection_write(ms, lines, tmp) -> None:
    lines.append("")
    lines.append("## 4. model_selection.json atomic write")
    tmp_path = Path(tmp) / "model_selection.json"
    ms._write_model_selection("claude-fable-5", "claude-opus-5", path=tmp_path)
    raw = json.loads(tmp_path.read_text())
    lines.append(f"Written file contents: {raw}")
    assert set(raw.keys()) == {"main", "worker"}, f"unexpected keys: {raw.keys()}"
    assert raw["main"] == "claude-fable-5" and raw["worker"] == "claude-opus-5"
    tmp_leftover = tmp_path.with_name(tmp_path.name + ".tmp")
    assert not tmp_leftover.exists(), "tempfile not cleaned up by os.replace"
    lines.append(f"No leftover .tmp file: {not tmp_leftover.exists()}")

# Section 5: model_selection.json read-back + fallback — unchanged behavior for existing callers
def _verify_model_selection_readback(ms, lines, tmp) -> None:
    lines.append("")
    lines.append("## 5. model_selection.json read-back + fallback")
    tmp_path = Path(tmp) / "model_selection.json"
    main, worker = ms._load_model_selection(path=tmp_path)
    lines.append(f"Valid file -> {(main, worker)}")
    assert (main, worker) == ("claude-fable-5", "claude-opus-5")

    missing_path = Path(tmp) / "does_not_exist.json"
    main, worker = ms._load_model_selection(path=missing_path)
    lines.append(f"Missing file -> {(main, worker)} (expected default pair, no raise)")
    assert (main, worker) == (ms._DEFAULT_MAIN, ms._DEFAULT_WORKER)

    malformed_path = Path(tmp) / "malformed.json"
    malformed_path.write_text("{not valid json", encoding="utf-8")
    main, worker = ms._load_model_selection(path=malformed_path)
    lines.append(f"Malformed file -> {(main, worker)} (expected default pair, no raise)")
    assert (main, worker) == (ms._DEFAULT_MAIN, ms._DEFAULT_WORKER)

    # Correction from review (milestone 2): an unrecognized-but-valid on-disk value must be
    # preserved verbatim on display, NOT silently replaced by the default.
    odd_path = Path(tmp) / "odd_value.json"
    odd_path.write_text(json.dumps({"main": "claude-hand-edited-9000", "worker": "claude-opus-5"}),
                        encoding="utf-8")
    main, worker = ms._load_model_selection(path=odd_path)
    lines.append(f"Unrecognized-but-valid value file -> {(main, worker)} (expected preserved verbatim)")
    assert main == "claude-hand-edited-9000", f"unrecognized value was replaced: {main!r}"
    assert worker == "claude-opus-5"

    ms._write_model_selection(main, worker, path=odd_path)
    main2, worker2 = ms._load_model_selection(path=odd_path)
    lines.append(f"Apply without cycling round-trips unchanged -> {(main2, worker2)}")
    assert (main2, worker2) == ("claude-hand-edited-9000", "claude-opus-5")

# Section 6: the custom proxy_rules.json serializer reproduces the real file's own convention
# byte-for-byte on an unmodified round-trip — the mechanism the read-modify-write below relies on.
def _verify_proxy_rules_format_fidelity(ms, lines) -> None:
    lines.append("")
    lines.append("## 6. proxy_rules.json serializer format fidelity")
    config = json.loads(_FIXTURE_RAW)
    roundtrip = ms._dumps_proxy_rules(config)
    identical = roundtrip == _FIXTURE_RAW
    lines.append(f"Unmodified round-trip byte-identical to fixture: {identical}")
    assert identical, "serializer does not reproduce the established on-disk convention"

# Section 7: Apply's read-modify-write — foreign sections/keys/models byte-preserved, missing
# per-model entry created with the established thinking-block shape, touched entries updated.
def _verify_proxy_rules_read_modify_write(ms, lines, tmp) -> None:
    lines.append("")
    lines.append("## 7. proxy_rules.json read-modify-write")
    path = Path(tmp) / "proxy_rules.json"
    path.write_text(_FIXTURE_RAW, encoding="utf-8")

    # main = claude-opus-5 (existing entry, gets new effort/max_tokens)
    # worker = claude-sonnet-5 (NOT in the fixture — must be created)
    ms._write_proxy_rules_model_params(
        "claude-opus-5", "medium", 128000,
        "claude-sonnet-5", "low", 32000,
        path=path)

    written_raw = path.read_text(encoding="utf-8")
    written = json.loads(written_raw)

    expected_config = json.loads(_FIXTURE_RAW)
    expected_config["model_params"]["claude-opus-5"]["effort"] = "medium"
    expected_config["model_params"]["claude-opus-5"]["max_tokens"] = 128000
    expected_config["model_params"]["claude-sonnet-5"] = {
        "thinking": dict(ms._DEFAULT_THINKING), "effort": "low", "max_tokens": 32000}
    expected_raw = ms._dumps_proxy_rules(expected_config)

    exact_match = written_raw == expected_raw
    lines.append(f"Full-file output matches expected read-modify-write exactly: {exact_match}")
    assert exact_match

    # Foreign top-level section untouched
    assert written["future_section"] == {"some_future_key": "some_future_value"}
    lines.append("Foreign top-level section ('future_section') byte-preserved: True")

    # Untouched model entry (claude-fable-5) and its thinking block untouched
    assert written["model_params"]["claude-fable-5"] == \
        {"thinking": {"type": "adaptive", "display": "summarized"}, "effort": "medium", "max_tokens": 64000}
    lines.append("Untouched model entry ('claude-fable-5') byte-preserved: True")

    # Third, also-untouched model entry, proving the preservation isn't just "the other of two"
    assert written["model_params"]["claude-untouched-9"] == \
        {"thinking": {"type": "adaptive", "display": "summarized"}, "effort": "high", "max_tokens": 32000}
    lines.append("Second untouched model entry ('claude-untouched-9') byte-preserved: True")

    # Touched entry (main): effort/max_tokens updated, thinking block untouched
    opus_entry = written["model_params"]["claude-opus-5"]
    assert opus_entry == {"thinking": {"type": "adaptive", "display": "summarized"},
                          "effort": "medium", "max_tokens": 128000}
    lines.append(f"Touched main entry (claude-opus-5) updated, thinking block unchanged: {opus_entry}")

    # Missing entry (worker) created with the established thinking-block shape
    sonnet_entry = written["model_params"]["claude-sonnet-5"]
    assert sonnet_entry == {"thinking": {"type": "adaptive", "display": "summarized"},
                            "effort": "low", "max_tokens": 32000}
    lines.append(f"Missing worker entry (claude-sonnet-5) created with established shape: {sonnet_entry}")

    tmp_leftover = path.with_name(path.name + ".tmp")
    assert not tmp_leftover.exists(), "tempfile not cleaned up by os.replace"
    lines.append(f"No leftover .tmp file: {not tmp_leftover.exists()}")

# Section 8: a malformed proxy_rules.json degrades to a fresh minimal file, never raises
def _verify_proxy_rules_malformed_fallback(ms, lines, tmp) -> None:
    lines.append("")
    lines.append("## 8. proxy_rules.json malformed-file fallback")
    path = Path(tmp) / "proxy_rules_malformed.json"
    path.write_text("{not valid json", encoding="utf-8")

    ms._write_proxy_rules_model_params(
        "claude-opus-5", "high", 64000,
        "claude-sonnet-5", "high", 64000,
        path=path)

    written = json.loads(path.read_text(encoding="utf-8"))   # must parse — no raise from the write
    lines.append(f"Write from malformed file did not raise; result parses as valid JSON: True")
    assert written["model_params"]["claude-opus-5"]["effort"] == "high"
    assert written["model_params"]["claude-sonnet-5"]["max_tokens"] == 64000
    lines.append(f"Fresh model_params created for both selected models: "
                f"{list(written['model_params'].keys())}")


if __name__ == "__main__":
    verify_model_cycle_and_io_workflow()
