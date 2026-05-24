# Sleep Pattern Audit — 2026-05-24

**Topic:** Empirical analysis of `block_chained_sleep` firing patterns to inform
`rewrite_chained_sleep.py` design.

**Script:** `dev/sleep_pattern_analysis/analyze.py` + `classify.py`
**Report:** `dev/sleep_pattern_analysis/01_reports/sleep_audit_2026-05-24.md`
**Data:** `~/.claude/projects/*/*.jsonl`, all-time (no date filter; actual range: 2026-05-20–2026-05-24)

---

## Methodology

Two-pass JSONL scan per file:
1. Build `tool_use_id → Bash command` map from assistant messages with `type=tool_use`.
2. Find user messages with `BLOCKED` + `block_chained_sleep`; resolve triggering command
   via `tool_use_id`, falling back to `parentUuid` lookup.

Per command: detect heredoc body spans (to exclude regex false positives), then for each
`sleep N` match: extract `cmd_before` (first token of the segment before the sleep),
`cmd_after` (first token after), `chain_op`, `in_loop`, `is_canonical` (whole command is
exactly `sleep N && echo done`).

Histograms built on shell-level sleeps only (heredoc-body sleeps excluded).

---

## Key Numbers

| Metric | Value |
|---|---|
| Blocked events (all-time) | 50 |
| Sleep occurrences parsed | 54 |
| Inside heredoc body (excluded FP) | 8 |
| Shell-level sleeps (histograms) | 46 |
| Actual date range | 2026-05-20 – 2026-05-24 |
| Canonical (`sleep N && echo done` standalone) | 0 (0%) |
| In-loop (`while`/`for`/`until`) | 4 (8.7%) |
| Sleep-first / no cmd_before | 5 (10.9%) |
| Duration ≤ 5s | 38 (82.6%) |

The 0% canonical count is significant: no blocked event was a well-formed
standalone `sleep N && echo done`. All 50 were genuine violations.

---

## cmd_before Token Distribution

Full histogram in the report. Top tokens:

| Rank | Token | Count | % | Classification |
|---|---|---|---|---|
| 1 | `echo` | 12 | 26.1% | Trivial-sync |
| 2 | `(empty)` | 5 | 10.9% | Sleep-first (not strippable) |
| 3 | `launchctl` | 5 | 10.9% | Load-bearing |
| 4 | `kill` | 4 | 8.7% | Load-bearing |
| 5 | `true` | 2 | 4.3% | Trivial-sync |
| 6 | `rag-cli` | 2 | 4.3% | Mixed |
| 7 | `bd` | 2 | 4.3% | Mixed |
| 8 | `#` | 2 | 4.3% | Unclassifiable |
| 9 | `pkill` | 2 | 4.3% | Load-bearing |
| 10 | `tmux` | 2 | 4.3% | Load-bearing |

---

## Trivial-Sync Candidates (safe to strip sleep)

**`echo`** (12 events, 26.1% of all violations):
- Dominant pattern: Opus chains a progress echo with a sleep before the next action.
  e.g. `... push 2>&1 | tail -3; echo "=== restart ==="; sleep 2; launchctl ...`
- `echo` returns synchronously with no side effects. Sleep adds no value here.
- A rewrite hook stripping `sleep N` when `cmd_before=echo` would eliminate the largest
  single violation class.

**`true`** (2 events, 4.3%):
- Pattern: `launchctl bootout ... 2>&1 || true; sleep 1; echo "prod killed"`
- The `|| true` guard catches launchctl failures silently. The sleep after is stalling
  for no reason — launchctl has not been called in the segment just before sleep.
- Safe to strip `sleep N` when `cmd_before=true`.

Combined trivial-sync coverage: **14 / 46 = 30.4%** of shell-level sleeps.

---

## Load-Bearing Tokens (do NOT strip)

**`launchctl`** (5 events, 10.9%):
- Pattern: `launchctl kickstart ... && sleep 2; pgrep -f "workflow.py"` or
  `launchctl bootout ...; sleep 1; launchctl bootstrap ...`
- `kickstart`/`bootout` are async. The daemon reaches running state after the command
  returns. Sleep is the settling time before the pgrep verification.
- Stripping would cause pgrep to miss the daemon or see stale state.

**`kill`** (4 events, 8.7%):
- Pattern: `kill <PID> 2>&1; sleep 2; rag-cli status` or
  `worker-cli kill X && ... && kill 60586 2>&1; sleep 2; rag-cli status`
- Signal delivery and process reaping is async. Checking immediately after kill sees
  the process still alive.

**`pkill`** (2 events, 4.3%) — same reason as `kill`.

**`tmux`** (2 events, 4.3%):
- Pattern: sleep after tmux commands that mutate session state.
- Some tmux ops propagate asynchronously (pipe-pane, new-session, send-keys).

---

## Mixed Tokens (per-subcommand inspection required)

**`rag-cli`** (2 events):
- `rag-cli server restart embedding-0.6b; sleep 3; rag-cli server status` — LOAD-BEARING
  (server restart spawns a new process)
- `rag-cli search_hybrid ...` — sync read, sleep would be strippable
- A rewrite hook would need to inspect the subcommand: `restart|start` → keep, else strip.

**`bd`** (2 events):
- `bd dolt start; sleep 2; bd list -s open` — LOAD-BEARING (Dolt server spawn)
- `bd label list ...; sleep N; ...` — trivial (sync read)
- Subcommand: `dolt start` → keep, else strip.

**`worker-cli`** (1 event):
- `worker-cli kill X; sleep 1; ...` — LOAD-BEARING (kill is async)
- `worker-cli status X; sleep N; ...` — trivial (sync read)
- Subcommand: `kill|spawn` → keep, else strip.

---

## `(empty)` Pattern — Sleep-First Chains

5 events (10.9%) have `cmd_before=(empty)`, meaning sleep is the FIRST command in the chain:
- `sleep 15 && rag-cli server list` — check server status in 15s
- `sleep 6 && bd comments add ...` — post a comment after 6s
- `sleep 3 && cat /tmp/...` — read a log after 3s

These are "manual timer + action" patterns. The sleep IS the intent (not strippable). A
rewrite hook must NOT strip when `cmd_before=(empty)` and sleep is the chain leader.

---

## Heredoc False Positives

8 of 54 sleep occurrences were inside heredoc bodies. The hook's regex scanner sees these
as real sleeps and fires — but the triggered Bash command is valid (the heredoc body is
string data, not executed shell). The analysis correctly excludes these from histograms.

This is a known hook limitation. No action in this audit.

---

## Recommendation for `rewrite_chained_sleep.py` Design

Rewrite-hook decision tree (per `sleep N` occurrence in a blocked command):

1. `cmd_before in _TRIVIAL` (`echo`, `true`, `git`, `ls`, `cat`, etc.) → **STRIP** sleep
2. `cmd_before in _LOADBEAR` (`kill`, `pkill`, `launchctl`, `tmux`, etc.) → **ALLOW** (pass through)
3. `cmd_before in _MIXED`:
   - inspect subcommand: `restart|start|kill|spawn|bootout|kickstart` → ALLOW
   - else → STRIP
4. `cmd_before == (empty)` (sleep-first chain) → **ALLOW** (timer intent)
5. Unclassifiable tail (`#`, `cmd`, `delay`, `cd`, etc.) → **BLOCK** (preserve current behavior)

Expected impact: trivial-sync tokens (`echo` + `true`) cover 30.4% of violations and can
be auto-rewritten. Load-bearing tokens (23.9%) correctly pass through. The remaining 45.7%
(mixed + unclassifiable + sleep-first) need either per-subcommand logic or remain blocked.

Do NOT implement the hook here — this audit is input to Opus + user design review.
