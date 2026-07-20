# Parallel Bash + Sleep-Timer — Empirical Investigation (2026-05-25)

**Status:** Hook NOT implemented. Investigation produced an empirical finding that made the proposed hook redundant. Document preserved as a decision record.

**Outcome:** the strict canonical timer form in workers-1.md + the existing `block_unauthorized_background.py` are sufficient. No new hook needed.

---

## Triggering Evidence

RAG session 2026-05-25 ~20:46. Opus dispatched two separate Bash tool_use blocks in ONE assistant response:

```
Block 1 (foreground): worker-cli send eval-sweep2 "<Go Phase B prompt>"
Block 2 (run_in_background=true): sleep 480 && echo "8min check eval-sweep2 Phase B"
```

Observed behavior: the first block ran through, the second block came back with exit 143 (SIGTERM). Opus interpreted the exit-143 return as "timer started" and went idle — actually no timer was active, no wake-up came. A pure observability gap.

First impression: "two parallel Bash tool_uses → the CC dispatcher kills the second with SIGTERM, regardless of BG or FG." Planned hook: detect when ≥2 Bash + ≥1 timer-form appear, block with a clear stderr.

---

## Deeper Investigation — What Actually Happened

User question in the session: "was the problem maybe actually that the sleeps were foregrounded?"

The `hook_firing.jsonl` entry from exactly this timestamp:

```json
{"ts": "2026-05-25T19:02:50Z", "hook": "block_unauthorized_background",
 "decision": "rewrite", "tool": "Bash",
 "command": "sleep 480 && echo \"8min check eval-sweep2 Phase B\"",
 "rewritten": "run_in_background: true → false"}
```

The timer command did NOT match the strict canonical regex `^\s*sleep\s+\d+(?:\.\d+)?\s*&&\s*echo\s+done\s*$` because the typical echo pattern used `echo "<descriptive text>"` — not the literal `echo done`. So `block_unauthorized_background.py` silently rewrote the timer from background to foreground.

That means the actual situation at dispatch time was: two FOREGROUND Bash tool_uses in the same response. Not "BG-timer + FG-Bash" as originally assumed.

---

## Rules Inconsistency Discovered

Three rule files had three different canonical forms:

| File | Line | Form |
|---|---|---|
| `workers-1.md` | 331 | `sleep N && echo 'check'` (quoted descriptive text) |
| `workers-2.md` | 68 | `sleep 600 && echo done` (literal `done`) |
| `tool-use.md` | 162 | `sleep N && echo done` (literal `done`) |

The hook `block_unauthorized_background._CANONICAL` only strictly matched forms 2/3. Opus drifted to form 1's pattern and beyond, to even more descriptive echoes. Result: every timer got silently rewritten to FG.

**Fix:** `workers-1.md:331` aligned to the strict canonical `echo done` literal. All three rule files are now consistent. User directive: "just always keep the error sources and variables to a minimum."

---

## Empirical Test — CC Dispatcher BG vs FG Behavior

Before building the hook, the open question was: is the parallel-Bash SIGTERM a generic mechanism, or does it only apply to FG+FG?

Test setup (with `block_parallel_bash_timer` temporarily removed from settings.json):

```python
# Bash 1 (foreground)
echo "FG test marker" && date +%H:%M:%S.%N

# Bash 2 (background, strict canonical)
sleep 5 && echo done   # run_in_background=true
```

Both dispatched in the same assistant response.

**Result:**

```
Bash 1: "FG test marker\n22:08:18.257674000"           — exit 0, returned immediately
Bash 2: "Command running in background with ID: blbwa5clw" — bg_id assigned, NO SIGTERM
```

The BG timer survived. After 5s it wrote its `done` to the bg-output file. No exit 143.

**Conclusion:** CC's dispatcher does distinguish BG from FG. The SIGTERM collision only happens on FG+FG in the same response. BG+FG is safe. So the original damage was NOT the parallel-tool_use mechanism in general — it was specifically that the non-canonical timer had been silently rewritten to FG by `block_unauthorized_background`, which produced FG+FG.

---

## Why No Hook

The planned `block_parallel_bash_timer.py` would have fired whenever ≥2 Bash + ≥1 strict-canonical timer appeared in one response. But exactly this pattern is empirically SAFE — BG+FG works. The hook would have produced a false positive on a demonstrably harmless constellation.

The existing protection chain is sufficient:

1. **Rule** (workers-1, workers-2, tool-use now consistent): the timer is always the literal `sleep N && echo done`
2. **block_unauthorized_background**: rewrites every non-canonical background call to foreground — a loud signal (a visible exit 143 if it collides with another FG Bash) that the rule was violated
3. **tool-use Rule 6**: "one Bash tool_use block per assistant response" — general discipline

Discipline + the existing rewrite hook covers the damage class. An additional hook that blocks the canonical case would be a classic "much too broad" — exactly what the user flagged about false positives in this session.

---

## What We Kept

- **The workers-1.md:331 strict-canonical update** — the most productive change of this session. Eliminates the drift pattern at the source.
- **This investigation record** as a decision record: why the hook was NOT built, what the empirical evidence was.
- **`block_unauthorized_background.py` unchanged** — does its job correctly, was never the problem.

## What We Discarded

- `src/hooks/block_parallel_bash_timer.py` — deleted (was briefly committed, then discarded)
- `dev/hook_smoke/test_block_parallel_bash_timer.py` — deleted
- The hook registration in `hook_setup.py` — removed
- Entries in `src/hooks/DOCS.md` and `dev/hook_smoke/DOCS.md` — removed

## Lesson for Future Hook Proposals

Before building any hook: empirically verify that the damage pattern actually occurs AND that the planned detection region exactly coincides with the damage region. If the existing protection chain already covers the real problem — silence is better than a redundant hook that can produce false positives.
