# dev/sleep_pattern_analysis/

## Role

Empirical analysis of `block_chained_sleep` hook firing events — classifies the `cmd_before`
token (command that immediately precedes `sleep N` in a blocked Bash chain) as trivial-sync
(safe to strip) vs load-bearing (keep) vs mixed/unclear. Produces the data needed to design
`rewrite_chained_sleep.py`: a hook that rewrites violations instead of blocking them.

Touch this suite when: re-auditing hook events after rule or hook changes; expanding the
trivial/load-bearing token sets; adding per-subcommand inspection logic for mixed tokens.

## Modules

### analyze.py (361 LOC)

**Purpose:** Orchestrates the full audit — walks `~/.claude/projects/*/*.jsonl`, resolves
each BLOCKED event to its triggering Bash command, extracts per-sleep context records,
produces the markdown report.

**Reads:** `~/.claude/projects/*/*.jsonl` — two passes per file:
  1. Builds `tool_use_id → command` map + `uuid → entry` map
  2. Finds `BLOCKED` lines for `block_chained_sleep`, resolves command via tool_use_id

**Writes:** `--out` path (default `md/sleep_audit_<date>.md`).

**Called by:** CLI only.

**Calls out:** `classify.add_classification()` for the classification section.

---

### classify.py (92 LOC)

**Purpose:** Token classification rules — constant sets (`_TRIVIAL`, `_LOADBEAR`, `_MIXED_NOTES`)
and reasons prose, plus `add_classification()` which appends the four-section classification
table to an in-progress report line list.

**Reads:** nothing (pure constants + logic).

**Writes:** mutates the `lines` list passed in by `analyze._build_report()`.

**Called by:** `analyze._build_report()`.

**Calls out:** nothing.

---

## Output

`md/sleep_audit_<YYYY-MM-DD>.md` — sections:
1. Summary header (event count, sleep count, heredoc FP exclusions, date range)
2. cmd_before histogram (top 25 tokens, count, %, 3 example snippets each)
3. cmd_after histogram (top 15 tokens)
4. In-loop / Naked / Canonical breakdown
5. Sleep duration distribution (1s / 2–5s / 6–15s / 16–60s / 60s+)
6. Classification — trivial-sync / load-bearing / mixed / unclassifiable tail

## Usage

```bash
# From dev/sleep_pattern_analysis/ (required: classify.py must be on sys.path)
cd dev/sleep_pattern_analysis
../../venv/bin/python analyze.py --since 2020-01-01 \
  --out md/sleep_audit_$(date +%Y-%m-%d).md

# Or from project root:
cd dev/sleep_pattern_analysis && \
  /path/to/venv/bin/python analyze.py [--since YYYY-MM-DD] [--out PATH]
```

## CLI Flags

| Flag | Default | Description |
|---|---|---|
| `--since YYYY-MM-DD` | 30 days ago | Earliest event timestamp to include. Pass `2020-01-01` for all-time. |
| `--out PATH` | `md/sleep_audit_2026-05-24.md` | Report output path. |

## Notes

- Must be run from `dev/sleep_pattern_analysis/` so `import classify` resolves. The project
  venv Python is required (stdlib only, but `./venv/bin/python` is the project convention).
- Heredoc body spans are detected and excluded from histograms (hook false positives — the
  regex scanner in `block_chained_sleep.py` sees `sleep` tokens inside heredoc strings).
- `cmd_before = (empty)` means sleep is the FIRST command in the chain (sleep-first pattern,
  not strippable — the sleep IS the timing intent).
