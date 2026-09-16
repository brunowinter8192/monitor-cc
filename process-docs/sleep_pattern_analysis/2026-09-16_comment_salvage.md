## Salvage from dev/sleep_pattern_analysis/analyze.py

```
"""Sleep pattern analyzer for block_chained_sleep hook events.

Walks ~/.claude/projects/*/*.jsonl for the last 30 days, correlates each
block_chained_sleep event to its trigger Bash command via tool_use_id, parses
every `sleep N` in that command for context (cmd_before, cmd_after, chain_op,
in_loop, is_canonical), and produces a classification report.

Usage (from project root):
    ./venv/bin/python dev/sleep_pattern_analysis/analyze.py [--since YYYY-MM-DD] [--out PATH]
"""
```

## Salvage from dev/sleep_pattern_analysis/classify.py

```
"""Token classification rules for sleep-pattern analysis."""
```

```
# Mixed tokens: safe for some subcommands, load-bearing for others
```

```
# Append trivial/load-bearing/mixed/unclassifiable classification tables
```

## Salvage from dev/sleep_pattern_analysis/sleep_events.py

```
# Pass 1: build tool_use_id → command map + uuid → entry map
```

```
# Pass 2: find block events for target hook
```

```
# Resolve trigger command: exact tool_use_id first, then parent fallback
```

## Salvage from dev/sleep_pattern_analysis/sleep_parsing.py

```
# Pre-detect heredoc spans: list of (start, end) byte ranges that are heredoc bodies
```

```
# Flag sleeps that land inside a heredoc body (hook FP — regex scanner too broad)
```

```
# chain_op and cmd_before
```

```
# If nothing between last operator and sleep, cmd_before is the segment
# ending at the operator (e.g. "cmd2\n sleep" → cmd_before = "cmd2")
```

```
# cmd_after: first token after the operator following sleep
```

```
"""Return list of (start, end) for heredoc body regions in cmd."""
```

```
# Strip variable assignments (VAR=val ...)
```

```
# strip subshell prefixes
```
(trailing comment on `first = first.lstrip("$(")          # strip subshell prefixes`)

```
# normalize paths to basename
```
(trailing comment on `first = os.path.basename(first)  # normalize paths to basename`)

## Salvage from dev/sleep_pattern_analysis/sleep_report.py

```
# From classify.py: token classification + add_classification()
```

```
# Classification
```

```
# cmd_before histogram — shell sleeps only
```

```
# pick up to 3 unique snippets
```

```
# cmd_after histogram
```

```
# In-loop vs naked
```

```
# Duration distribution
```

## Salvage from dev/sleep_pattern_analysis/DOCS.md

```
## Gotchas
- All cross-file imports here are bare top-level module imports (`from sleep_events import ...`,
  `from classify import ...`), not `dev.sleep_pattern_analysis.x` — this works when invoked as
  `./venv/bin/python dev/sleep_pattern_analysis/analyze.py` from anywhere, since Python adds the
  executed script's own directory to `sys.path[0]`; no `cd` into this directory is required.
- Heredoc body spans are detected and excluded from histograms — `block_chained_sleep.py`'s own regex
  scanner sees `sleep` tokens inside heredoc strings, which would otherwise inflate the counts.
- `cmd_before = (empty)` means sleep is the first command in the chain (sleep-first pattern, not
  strippable — the sleep itself is the timing intent).
```

## Notes for successor

- 5 files, 21 comments + 3 docstrings, matching the measured state exactly. Per-file true comment counts (excluding the 3 section markers and excluding string literals that merely start with `#`/`##`/`###` as Markdown content inside `lines.append(...)` calls, which are report body text, not comments): analyze.py 0, classify.py 2, sleep_events.py 3, sleep_parsing.py 9 (incl. a 2-line comment and 2 trailing inline comments), sleep_report.py 7. Docstrings: analyze.py module docstring, classify.py module docstring, sleep_parsing.py's `_heredoc_spans` function docstring.
- Watch out: several lines matching `grep "#"` in `sleep_report.py` and `classify.py` are NOT comments — they are Markdown heading strings inside list literals, e.g. `"### Candidate trivial-sync tokens (safe to strip)"` and `"# Sleep Pattern Audit — block_chained_sleep"`. These are report output content and must never be touched. A naive grep-and-strip approach would have corrupted the generated report; only comments that are actual Python syntax (a `#` starting a comment token, not inside a string) were removed.
- No load-bearing docstring: grepped `__doc__` across the directory — zero hits. `analyze.py`'s `argparse.ArgumentParser(description=...)` uses its own literal string `"Analyze block_chained_sleep events"`, not `__doc__`. All 3 docstrings were deleted outright, nothing moved to an INFRASTRUCTURE constant.
- Behavior-unchanged proof: `analyze.py` is the only script with a `__main__` block; `sleep_events.py`, `sleep_parsing.py`, `sleep_report.py`, `classify.py` are pure library modules with no entry point, exercised only via `analyze.py`'s import graph. Ran `python3 dev/sleep_pattern_analysis/analyze.py --since 2026-01-01 --out /tmp/<...>.md` once before comment/docstring removal and once after, diffed the two output report files byte-for-byte after normalizing the `Generated: <timestamp>` line — identical. Also diffed stdout (the printed output path) after normalizing the path itself — identical structure.
- `analyze.py --out` default is `dev/sleep_pattern_analysis/01_reports/sleep_audit_2026-05-24.md`, which does not exist in the tracked tree (the tracked report lives under `dev/sleep_pattern_analysis/md/sleep_audit_2026-05-24.md`, per the now-removed DOCS.md Gotchas note above). Verification runs used an explicit `--out /tmp/...` path to avoid creating `01_reports/` at all; no cleanup of a `01_reports/` directory was needed this time.
- DOCS.md rewrite: the `## Gotchas` section has no home in the new fixed format (Role / Public Interface / Flow / Modules / State), so it moved here in full. The new `## State` section notes that `sleep_report.py` and `classify.py` both mutate the same caller-supplied `lines` list in place — that coupling was previously described only informally ("mutates the `lines` list ... same pattern classify.py already used") inside the old Modules prose; it is now stated once under `State` instead of twice under `Modules`.
