# INFRASTRUCTURE
import glob
import hashlib
import json
import os
import re
from datetime import date, datetime, timezone
from pathlib import Path

_HERE = Path(__file__).parent.resolve()
_REPO_ROOT = _HERE.parents[1]
REPORT_DIR = _HERE / "md"

_HAIKU_RE = re.compile(r"haiku", re.IGNORECASE)

_SKIPPED_LINES = 0


# ORCHESTRATOR

def probe_sys_tool_original_chars_workflow() -> None:
    dual_log_dir = _resolve_dual_log_dir()
    stems = sorted(set(p[:-len("_original.jsonl")] for p in glob.glob(str(dual_log_dir / "*_original.jsonl"))))
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    report_path = REPORT_DIR / f"probe_sys_tool_original_chars_{date.today().isoformat()}.md"
    if not stems:
        report_path.write_text("# probe_sys_tool_original_chars\n\nno sessions found\n", encoding="utf-8")
        print(f"no sessions found; report written to {report_path}")
        return
    lines = [
        "# probe_sys_tool_original_chars",
        "",
        f"Run {datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')} against {len(stems)} sessions "
        f"under `{dual_log_dir}`.",
        "",
    ]
    lines += _measure_whole_tool_coverage(stems)
    lines += _measure_tool_content_stability(stems)
    lines += _measure_system_stability(stems)
    lines += _measure_recording_pattern(stems)
    report_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"report written to {report_path}")
    _report_skipped_lines()


# FUNCTIONS

def _resolve_dual_log_dir() -> Path:
    env_root = os.environ.get("MONITOR_CC_ROOT")
    if env_root:
        return Path(env_root) / "src" / "logs" / "dual_log"
    direct = _REPO_ROOT / "src" / "logs" / "dual_log"
    if direct.exists():
        return direct
    parents = _HERE.parents
    if len(parents) > 4:
        from_worktree = parents[4] / "src" / "logs" / "dual_log"
        if from_worktree.exists():
            return from_worktree
    return direct


def _measure_whole_tool_coverage(stems: list) -> list:
    lines = ["## 1. Whole-stripped tool coverage", ""]
    total_sessions, total_names, total_found = 0, 0, 0
    for stem in stems:
        stripped = Path(f"{stem}_stripped.jsonl")
        if not stripped.exists():
            continue
        whole_names = _whole_stripped_names(stripped)
        if not whole_names:
            continue
        total_sessions += 1
        entry = _last_non_haiku_entry(Path(f"{stem}_original.jsonl"))
        if entry is None:
            lines.append(f"- `{Path(stem).name}`: NO non-haiku request found, {len(whole_names)} names unresolvable")
            continue
        tools = (entry.get("payload") or {}).get("tools", []) or []
        by_name = {t.get("name", "?") for t in tools if isinstance(t, dict)}
        found = whole_names & by_name
        total_names += len(whole_names)
        total_found += len(found)
    lines.append(
        f"**{total_sessions} sessions carry a whole-stripped tool**, "
        f"**{total_found}/{total_names} whole-stripped name-instances found** in their own last "
        f"`_original` request's `tools` list ({total_names - total_found} missing)."
    )
    lines.append("")
    return lines


def _whole_stripped_names(stripped_path: Path) -> set:
    names = set()
    for line in open(stripped_path, encoding="utf-8"):
        line = line.strip()
        if not line:
            continue
        try:
            entry = json.loads(line)
        except json.JSONDecodeError:
            _note_skipped_line()
            continue
        for name, val in (entry.get("tools_delta") or {}).items():
            if isinstance(val, dict) and val.get("whole") is True:
                names.add(name)
    return names


def _note_skipped_line() -> None:
    global _SKIPPED_LINES
    _SKIPPED_LINES += 1


def _last_non_haiku_entry(original_path: Path):
    last = None
    for line in open(original_path, encoding="utf-8"):
        line = line.strip()
        if not line:
            continue
        try:
            entry = json.loads(line)
        except json.JSONDecodeError:
            _note_skipped_line()
            continue
        if _infer_family(entry.get("model", "")) == "haiku":
            continue
        last = entry
    return last


def _infer_family(model: str) -> str:
    if _HAIKU_RE.search(model or ""):
        return "haiku"
    if "sonnet" in (model or "").lower():
        return "sonnet"
    return "opus"


def _measure_tool_content_stability(stems: list) -> list:
    lines = ["## 2. Tool content stability across a session", ""]
    checked, mismatches = 0, 0
    for stem in stems:
        original = Path(f"{stem}_original.jsonl")
        by_name_per_request = []
        for line in open(original, encoding="utf-8"):
            line = line.strip()
            if not line:
                continue
            try:
                entry = json.loads(line)
            except json.JSONDecodeError:
                _note_skipped_line()
                continue
            tools = (entry.get("payload") or {}).get("tools", []) or []
            by_name_per_request.append({t.get("name", "?"): _delta_hash(t) for t in tools if isinstance(t, dict)})
        if len(by_name_per_request) < 2:
            continue
        checked += 1
        last = by_name_per_request[-1]
        for by_name in by_name_per_request[:-1]:
            for name, h in by_name.items():
                if name in last and last[name] != h:
                    mismatches += 1
    lines.append(f"**{checked} sessions checked** (>=2 `_original` requests); **{mismatches} tool-hash mismatches** "
                 f"comparing any earlier request's own tool-by-name content against the last request's.")
    lines.append("")
    return lines


def _delta_hash(element) -> str:
    if isinstance(element, dict):
        element = {k: v for k, v in element.items() if k != "cache_control"}
    return hashlib.md5(json.dumps(element, sort_keys=True).encode("utf-8")).hexdigest()[:10]


def _measure_system_stability(stems: list) -> list:
    lines = ["## 3. System block stability (indices 1-3, family-first vs. family-last)", ""]
    checked, flagged = 0, 0
    for stem in stems:
        original = Path(f"{stem}_original.jsonl")
        entries = []
        for line in open(original, encoding="utf-8"):
            line = line.strip()
            if not line:
                continue
            try:
                entries.append(json.loads(line))
            except json.JSONDecodeError:
                _note_skipped_line()
                continue
        if not entries:
            continue
        family = _infer_family(entries[-1].get("model", ""))
        fam_entries = [e for e in entries if _infer_family(e.get("model", "")) == family]
        if len(fam_entries) < 2:
            continue
        checked += 1
        first_sys = [b for b in (fam_entries[0].get("payload") or {}).get("system", []) or [] if isinstance(b, dict)]
        last_sys = [b for b in (fam_entries[-1].get("payload") or {}).get("system", []) or [] if isinstance(b, dict)]
        first_h = [_delta_hash(b) for b in first_sys]
        last_h = [_delta_hash(b) for b in last_sys]
        mism = [i for i in (1, 2, 3) if i < len(first_h) and i < len(last_h) and first_h[i] != last_h[i]]
        if mism or len(first_h) != len(last_h):
            flagged += 1
    lines.append(f"**{checked} sessions checked** (family with >=2 requests); **{flagged} show a length or "
                 f"content mismatch** at indices 1-3 between the family's first and last request.")
    lines.append("")
    return lines


def _measure_recording_pattern(stems: list) -> list:
    lines = ["## 4. Recording pattern (whole-tool strip / system_delta, rendered family only)", ""]
    multi_line_sessions, non_first_sessions, total = 0, 0, 0
    for stem in stems:
        original = Path(f"{stem}_original.jsonl")
        stripped = Path(f"{stem}_stripped.jsonl")
        last_entry = _last_non_haiku_entry(original)
        if last_entry is None:
            continue
        family = _infer_family(last_entry.get("model", ""))
        carrying = []
        for line in open(stripped, encoding="utf-8"):
            line = line.strip()
            if not line:
                continue
            try:
                entry = json.loads(line)
            except json.JSONDecodeError:
                _note_skipped_line()
                continue
            if _infer_family(entry.get("model", "")) != family:
                continue
            has_whole = any(isinstance(v, dict) and v.get("whole") for v in (entry.get("tools_delta") or {}).values())
            if has_whole or entry.get("system_delta"):
                carrying.append(entry.get("is_first", False))
        if not carrying:
            continue
        total += 1
        if len(carrying) > 1:
            multi_line_sessions += 1
        if not carrying[0]:
            non_first_sessions += 1
    lines.append(f"**{total} sessions** carry a whole-tool-strip or system_delta line for the rendered family; "
                 f"**{multi_line_sessions} have more than one such line**; **{non_first_sessions}** where the "
                 f"FIRST such line is not `is_first=True` (the known sidecar-interleave write-side artifact, "
                 f"see `process-docs/dual_log_cli/`, not a new finding).")
    lines.append("")
    return lines


def _report_skipped_lines() -> None:
    print(f'skipped undecodable lines: {_SKIPPED_LINES}')


def _tool_chars(tool) -> int:
    return len(json.dumps(tool))


if __name__ == "__main__":
    probe_sys_tool_original_chars_workflow()
