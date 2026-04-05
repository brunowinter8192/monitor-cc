#!/usr/bin/env python3
"""Scan a Claude Code session JSONL to find how loaded rules appear in system-reminders.

Purpose: Verify the exact pattern/format of "Contents of" lines in system-reminder
tags within tool_result content blocks. This tells us whether we can reliably parse
loaded rules (CLAUDE.md, .claude/rules/*.md) from the JSONL instead of relying on
the InstructionsLoaded hook (which has known bugs: #33275, #30973, #31017).

Usage:
    python3 dev/display/scan_jsonl_rules.py

Scans the most recent JSONL from the RAG project (not Monitor_CC, to avoid
self-referential noise from this session's own messages).

Output: All unique "Contents of" lines found in system-reminder tags,
with the message type and line number they appear in.
"""

import json
import re
from pathlib import Path

PROJECTS_DIR = Path.home() / '.claude' / 'projects'
TARGET_PROJECT = None  # auto-discover newest project

SYSTEM_REMINDER_PATTERN = re.compile(r'<system-reminder>(.*?)</system-reminder>', re.DOTALL)
CONTENTS_OF_PATTERN = re.compile(r'Contents of ([^\n]+)')


def find_latest_jsonl(project_name: str = None) -> Path:
    if project_name:
        project_dir = PROJECTS_DIR / project_name
    else:
        project_dirs = [d for d in PROJECTS_DIR.iterdir() if d.is_dir() and not d.name.startswith('.')]
        if not project_dirs:
            raise FileNotFoundError(f"No projects found in {PROJECTS_DIR}")
        project_dir = max(project_dirs, key=lambda d: d.stat().st_mtime)
    if not project_dir.exists():
        raise FileNotFoundError(f"Project dir not found: {project_dir}")
    jsonl_files = sorted(project_dir.glob('*.jsonl'), key=lambda x: x.stat().st_mtime, reverse=True)
    if not jsonl_files:
        raise FileNotFoundError(f"No JSONL files in {project_dir}")
    return jsonl_files[0]


def scan_jsonl(filepath: Path) -> None:
    print(f"Scanning: {filepath.name} ({filepath.stat().st_size} bytes)")
    print(f"Project: {filepath.parent.name}")
    print("=" * 80)

    seen_rules = set()
    rule_locations = []

    with open(filepath, 'r', encoding='utf-8') as f:
        for line_num, line in enumerate(f):
            if 'Contents of' not in line:
                continue
            try:
                msg = json.loads(line)
            except json.JSONDecodeError:
                continue

            msg_type = msg.get('type', 'unknown')

            # Search through all content for system-reminder tags
            raw = json.dumps(msg)
            reminders = SYSTEM_REMINDER_PATTERN.findall(raw)

            for reminder in reminders:
                contents_matches = CONTENTS_OF_PATTERN.findall(reminder)
                for match in contents_matches:
                    # Deduplicate
                    if match not in seen_rules:
                        seen_rules.add(match)
                        rule_locations.append({
                            'line': line_num,
                            'msg_type': msg_type,
                            'contents_of': match
                        })

    print(f"\nFound {len(rule_locations)} unique 'Contents of' entries:\n")

    for entry in rule_locations:
        print(f"  Line {entry['line']:>5} [{entry['msg_type']:>10}]: Contents of {entry['contents_of']}")

    print("\n" + "=" * 80)
    print(f"\nParseable rule names:")
    for entry in rule_locations:
        raw = entry['contents_of']
        # Extract: path and scope from "path/to/file.md (scope description):"
        path_match = re.match(r'(.+\.md)\s*\(([^)]+)\)', raw)
        if path_match:
            filepath_str = path_match.group(1).strip()
            scope = path_match.group(2).strip()
            name = Path(filepath_str).stem
            # Determine [P] or [G]
            if 'global' in scope or "user's private" in scope:
                tag = '[G]'
            else:
                tag = '[P]'
            print(f"  {tag} {name}  ←  {filepath_str}  ({scope})")
        else:
            print(f"  [?] {raw}")


if __name__ == '__main__':
    jsonl_path = find_latest_jsonl(TARGET_PROJECT)
    scan_jsonl(jsonl_path)
