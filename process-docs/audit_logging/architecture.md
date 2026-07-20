# Audit Logging — Two Persistent Logs (2026-05-24)

**Topic:** build two persistent JSONL logs that capture data CC only exposed transiently
(session-JSONL strings) or in-memory (`warnings_pane`) as of 2026-05-24. Closes the audit
blind spots for (a) silent hook fires and (b) cross-session tool errors.

---

## Original Framing (refuted)

The initial framing was "hook output visibility — Opus doesn't see rewrite-hooks in the
API tool_result". Research on `anthropics/claude-code` surfaced the CC output-channel split:

| Field | Routing |
|---|---|
| `systemMessage` | Terminal/UI display ONLY (CC pane). NEVER in model context. |
| `hookSpecificOutput.additionalContext` | Injected into model context (PreToolUse since CC 2.1.9, CHANGELOG line 2549). |
| `stderr` + exit 2 | Block-error, model sees it. |

Sources: `anthropics/claude-code` issues #41285, #47692, #61109; CHANGELOG lines 929,
2549, 3486; `plugins/plugin-dev/skills/hook-development/SKILL.md` lines 130-220.

That would make the visibility asymmetry technically solvable via the `additionalContext`
field in the rewrite hooks. **User veto 2026-05-24:** explicitly NOT wanted. Rewrite hooks
stay silent — the agent doesn't need context pollution about `git diff dev` being rewritten
to `git diff dev --`. Hook output to the model is only justified on blocks, where the agent
needs to understand WHY it was blocked to retry differently.

The real pain is not visibility-for-the-agent but persistent audit logging as a data
foundation for future analyses.

---

## Reframed Pain — Two Blind Spots

**Blind spot 1: hook fires.**

| Current source | What it sees | What it misses |
|---|---|---|
| CC session JSONLs (`~/.claude/projects/*/*.jsonl`) | Block events (greps `"PreToolUse:<Tool> hook error: ... BLOCKED:"`) | Rewrites (silent `updatedInput`), silent allow-passthroughs, rewrite-FPs of the form "command rewritten into breakage" |

Block hooks are only accidentally auditable — CC serializes their stderr output into the
session transcripts. That's implementation-detail luck, not design. As soon as a hook works
silently (which per user directive is the desired behavior) it is structurally invisible.
`rewrite_chained_sleep.py` was the first hook to demonstrate this — there was no way to
measure whether it rewrote the targeted trivial-sync violations as planned or produced FPs
that went unseen.

**Blind spot 2: tool errors cross-session.**

| Current source | What it sees | What it misses |
|---|---|---|
| Monitor `warnings_pane` | Tool errors of the **current** session, in-memory (proxy-JSONL `is_error: true` blocks) | Everything before session start (cleared on every switch — `src/panes/warnings_pane.py:213,234`), no worker-session aggregation, no cross-session history |

`warnings_pane` extracts, via `_is_tool_error()` (`src/panes/warnings_parse.py:43`),
exactly the right class of events — but persists them nowhere. `tool_errors` is a
module-level list, append-only within a session, cleared on session switch. Zero disk
persistence.

`dev/tool_use_errors/analyze.py` attempted to plug the gap via on-demand parsing of the
proxy JSONLs with a built-in pattern classification (18 failure patterns × 6 hookability
buckets). That was over-engineered: the user directive called for *raw data + ad-hoc grep*,
not *built-in classification*. Patterns change, classification goes stale quickly; a thin
append-only JSONL is the more robust data foundation.

---

## Chosen Architecture — Two Logs

**Log A — Hook Firing Log:** `src/logs/hook_firing.jsonl`

Each hook calls a shared `_fire_log.log_fire()` at its decision point (before `sys.exit(2)`
for blocks, before `print(json.dumps(...))` for rewrites). Schema:

```json
{"ts":"2026-05-24T14:23:11Z","hook":"rewrite_git_ambiguous","decision":"rewrite","tool":"Bash","command":"git diff dev..HEAD","rewritten":"git diff dev..HEAD --","session":"<cc_session_id>"}
{"ts":"2026-05-24T14:23:45Z","hook":"block_chained_sleep","decision":"block","tool":"Bash","command":"sleep 5 && echo foo","reason":"BLOCKED: chained sleep — use separate calls"}
```

`session_id` comes free from the CC stdin payload — cross-reference with session JSONLs
is possible.

Shared module: `src/hooks/_fire_log.py`, parallel to `_shell_strip.py`. Fail-silent
(try/except → drop, hook continues normally). 18 active hooks × ~3 lines of change.
Uniform pattern.

**Log B — Tool Error Log:** `src/logs/tool_errors.jsonl`

Mirrors the `warnings_pane` extraction to disk, but cross-session and cross-worker.
Schema:

```json
{"ts":"2026-05-24T14:30:22Z","session_id":"<id>","worker":"main|<worker-name>","tool_name":"Bash","tool_use_id":"<id>","error_preview":"<truncated error text>","error_full":"<complete text>","proxy_file":"src/logs/api_requests_..._....jsonl","request_id":"<rid>"}
```

Extraction logic is already established in `src/panes/warnings_parse._is_tool_error()` —
checks `type=='tool_result'` AND `is_error is True`. The logic is mirrored into a new
write module (NOT hooked into `warnings_pane.py` itself — `warnings_pane` keeps its
in-memory UI logic, the logging is an orthogonal path).

Writer architecture options considered:
1. **Tail-side daemon:** standalone process tails all proxy JSONLs, writes the error log.
   Decoupled from the Monitor.
2. **Monitor-side hook:** `warnings_pane` (or a sister component) additionally writes each
   newly detected error to disk. Existing UI stays unchanged.
3. **Proxy-side inline:** proxy writes an error-only JSONL in parallel with the regular
   JSONL. Tightest coupling, real-time.

Recommendation was option 2 — minimal new code footprint, the extraction logic already
exists in exactly one place, a write path is attached in parallel.

---

## Script Deletion (resolved 2026-05-24)

Decision after a suitability assessment: BOTH scripts to be deleted once the two logs are
live. One-sentence rationale: the meta-FP problem. Hooks are non-trivial — a script that
analyzes hook fires produces just as many FPs in its own analysis as the hooks themselves.
The script layer adds a second layer of brittle heuristics on top of the first.

| Script | Verdict | When |
|---|---|---|
| `dev/hook_firing/analyze.py` | DELETE | With the log build (same commit) |
| `dev/hook_firing/DOCS.md` | DELETE | Same commit |
| `dev/tool_use_errors/analyze.py` | DELETE | Same commit |
| `dev/tool_use_errors/DOCS.md` | DELETE | Same commit |
| `dev/hook_firing/reports/*` | KEEP | Historical snapshots with concrete dated findings |
| `dev/tool_use_errors/reports/*` | KEEP | Same rationale |
| `dev/sleep_pattern_analysis/` | KEEP | Audit run complete, evidence for `rewrite_chained_sleep.py` design |
| `dev/hook_smoke/` | KEEP + EXTEND | Smoke tests active, new tests for the two logs |

**Knowledge preservation:** the encoded pattern library from both scripts is not lost — the
18 failure-class fingerprints from `tool_use_errors/analyze.py` plus the per-hook FP/TP
heuristics from `hook_firing/analyze.py` are archived as static historical knowledge in a
companion catalog.

## Future Hook-Iteration Workflow (replaces script-driven analysis)

Instead of persistent dev scripts, the workflow for future hook work is human-in-the-loop
on the two logs:

1. **Pick a failure class.** Grep `tool_errors.jsonl` raw, identify a specific class
   (`is_error: true` + pattern XYZ).
2. **Pull a concrete example.** Extract the `tool_use_id` from the log, read the full
   tool-call context from the matching proxy JSONL in `src/logs/api_requests_*.jsonl`
   (what did the agent do before, what was the trigger, what was intended).
3. **Think through the hook reaction.** How would a hook react to this failure class?
   Which tool input would be blocked/rewritten? What side effects?
4. **Build a probe hook.** Implement the pattern as a hook script, tested with synthetic
   inputs in `dev/hook_smoke/`.
5. **Replay against historical data.** Run the probe hook retroactively against the
   existing proxy JSONLs in `src/logs/` — see how often it would have fired, and in what
   share correctly vs incorrectly.
6. **FP-rate assessment.** If the probe's FP rate is too high → back to step 3. If
   acceptable → promote to a real hook, register via `hook_setup.py`.

Live data from step 5 onward uses `hook_firing.jsonl` — the live probe hook writes its
fires there and they are grepped out.

The previous approach (a dev script analyzing pre-aggregated hook fires with built-in
FP/TP heuristics that had to be maintained as code) was explicitly discarded — the
heuristics were not stable enough for persistent code, and the maintenance overhead for
the patterns delivered no better outcome than ad-hoc grep + domain knowledge in the
implementer's head.

## Orphan Awareness

`src/logs/hook_outputs.jsonl` already existed (17MB, 31142 entries, last write 2026-04-19)
— a relic of an older logging framework (schema with `skill-trigger.py` / `bash-hook.sh`
entries, not the current hooks). Grep confirmed: no `src/` module writes to it anymore.
At implementation time: delete the orphan file, or archive it with an unambiguous suffix
(`hook_outputs.jsonl.legacy_2026-04`) to avoid schema collisions with the new
`hook_firing.jsonl`.

---

## Resolved Decisions

| # | Decision | Resolution |
|---|---|---|
| 1 | Log A path | **`src/logs/hook_firing.jsonl`** (directive 2026-05-24: all logs live in `src/logs/`) |
| 4 | Log B path | **`src/logs/tool_errors.jsonl`** (same directive) |

## Pending Design Decisions (at time of writing)

**Log A (hook):**
2. Schema: sketched above (ts/hook/decision/tool/command/reason-or-rewritten/session).
3. Rotation: append-forever (~10MB/year, manageable).

**Log B (tool errors):**
5. Schema: sketched above. Open question whether `error_full` (complete error text) is
   always sensible or whether a cap (e.g. 4KB) makes sense — some tool errors run several
   KB (Python tracebacks, large diffs).
6. Writer architecture: option 2 (monitor-side hook) as the default proposal.
7. Backfill: forward-from-now only (live) OR an initial one-time scan of all existing
   proxy JSONLs to retroactively populate? Backfill costs one-time compute but gives an
   immediate historical data foundation.

---

## Open Questions (at time of writing)

- Should `_fire_log.log_fire()` be a `hook_setup.py`-enforced mandatory import (a lint/hook
  that aborts on missing import)? Or code-review discipline?
- Is a `decision="error"` class needed for hook-internal failures (crashed hook), or is
  fail-silent without an audit entry enough?
- Should the log paths be configurable via env var (for test isolation in
  `dev/hook_smoke/`)? Practical, but adds complexity.
- Tool-error log: worker-vs-main-session attribution — how is `worker_name` resolved from
  the proxy-JSONL path? The existing `warnings_pane` already does this (worker log files
  are in its reads-set), the logic is available.

---

## Sources

- `src/panes/warnings_pane.py` (line 213/234/259: in-memory `tool_errors` without
  persistence)
- `src/panes/warnings_parse.py` (line 43: `_is_tool_error()` extraction logic)
- `src/panes/DOCS.md` (`warnings_pane` architecture)
- `src/hooks/_shell_strip.py` (precedent for the shared-module pattern)
- `src/hooks/rewrite_git_ambiguous.py`, `rewrite_chained_sleep.py` (silent rewrite hooks,
  blind-spot demonstrators)
- `dev/hook_firing/analyze.py` + DOCS.md (block-only audit at time of writing)
- `dev/tool_use_errors/analyze.py` + DOCS.md (pattern classifier at time of writing)
- `anthropics/claude-code`:
  - `plugins/plugin-dev/skills/hook-development/SKILL.md` lines 130-220
    (output-channel doc)
  - `plugins/plugin-dev/skills/hook-development/references/advanced.md` line 358
    (audit-log pattern)
  - CHANGELOG.md lines 929, 2549, 3486 (`additionalContext` field history — refuted path)
  - Issues #41285, #47692, #61109, #61983 (visibility + observability gaps)
