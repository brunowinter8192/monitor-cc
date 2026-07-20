# Block Polling Loop — Hook Design Rationale (2026-05-25)

**Topic:** a new hook `block_polling_loop.py` that prevents the canonical polling-loop
anti-pattern where a worker makes repeated short Bash calls to poll an
asynchronously-started background process.

---

## Triggering Evidence

RAG worker `mode-topk-sweep` session 2026-05-24 22:26–~23:00:
- The worker started a sweep process in the shell background via a `cmd ... &` suffix
  (NOT via CC's `run_in_background=true` flag — so our `block_unauthorized_background`
  hook couldn't catch it)
- Captured the PID, then ran **371 sequential polls** in the pattern:
  ```
  ps -p <PID> > /dev/null 2>&1 && echo "still running" || echo "done"; \
  wc -l /tmp/cross_sweep_output.log; tail -N /tmp/cross_sweep_output.log
  ```
- All polls had `bg=False` (the CC flag), a 2-5 second cadence, tail-N monotonically
  incrementing from 18 → 36+
- Per poll: ~2000 chars of log content as a tool result + thinking tokens between
  calls to assess "is the process still there?"
- Estimated token consumption for the poll loop alone: 30-40k. With a 200k window
  there was no budget left for the report write at the end

The worker had several clean alternatives available:
1. **Foreground with `timeout=900000`** — the Bash tool supports 10-15 min timeouts
2. **Background + `wait $PID`** — a bash-native block until the process ends
3. **Background + ONE long `sleep`** instead of 371 small polls

The worker used none of them — it chose the naive default strategy "I'll check more
often whether it's done." A pure worker-discipline gap, not enforced by any hook.

Existing hooks stayed blind: `block_unauthorized_background` only sees the CC flag,
not shell-`&`; all other hooks target different anti-patterns.

---

## Three Attack Surfaces Considered

### A) Single-Call Signature (chosen — implement now)

Pattern-match on the smoking-gun fingerprint in a single Bash command:
- `ps -p <num>` (process-existence check)
- COMBINED with `tail -<num>` (log read with a concrete N)
- BOTH in the same tool_input.command

A PreToolUse hook catches this on the VERY FIRST poll, before the loop even starts.
Stateless, single-call, fail-open. Follows the established pattern family of
`block_dangerous_kill` / `block_broad_grep`.

**Strengths:**
- Stateless — no cross-session/cross-call state files needed
- Catches the loop on the first attempt (before wasted polls)
- Trivial to implement (~50 LOC analogous to block_dangerous_kill)
- A clearly defined failure class — no fuzzy heuristic

**Weaknesses:**
- Catches only this one polling form. Other variants would slip through:
  - `while sleep 1; do tail -n 3 /tmp/log; done` (shell loop)
  - `for i in $(seq 1 100); do sleep 5; check; done` (counter loop)
  - Repeated `tail -N` without a `ps -p` check (pure log polling)
  - Polling via Python/jq pipelines shaped differently

**When to extend:** once `hook_firing.jsonl` shows that other polling patterns
occur in reality (no fire of this hook, but the anti-pattern empirically visible in
session JSONLs), attack surface B or C would get built. Until then: this one
hook + a worker-discipline rule note in `~/.claude/shared-rules/worker/worker-rules.md`.

### B) Cross-Call Repetition Detection (deferred)

A per-session state file of the last N Bash commands with timestamp + command hash.
On every incoming call: check "have the last 3+ commands had ≥80% similarity
within the last 30s?" → block.

**Strengths:** catches EVERY polling variant regardless of the concrete mechanism.

**Weaknesses:**
- Substantial state overhead (file I/O per call, hashing, threshold tuning,
  race conditions between parallel sessions)
- False-positive risk: legitimate use cases like live-tailing a build log
  while verbose output is streaming would get blocked
- More implementation complexity than the other hooks in the set
- Threshold tuning needs empirical data not yet available

### C) Session-JSONL Frequency Analysis (deferred)

The hook opens `$transcript_path` from the CC stdin payload, parses the last 10
tool_use entries, checks for repetition. A variant of B but without its own
state file.

**Strengths:** no own state persistence needed — uses CC's session JSONL, which
already exists.

**Weaknesses:**
- Session JSONLs are MB-sized files, parsing on every Bash call isn't cheap
- Pattern matching between commands would need to be cleanly defined
- Same false-positive class as B

---

## Chosen Architecture — Attack Surface A

**Module:** `src/hooks/block_polling_loop.py`

**Pattern family:** block-with-stderr (exit 2). Follows block_dangerous_kill as
a template — a similar "smoking-gun single-call signature" class.

**Detection regex (combined check):**
- `_PS_P_CHECK = re.compile(r'\bps\s+-p\s+\d+')`
- `_TAIL_N_FILE = re.compile(r'\btail\s+-\d+\s+\S+')`
- Block IFF both match in the same (post-quote-stripped) command

Both patterns must be present — otherwise a false positive on a legitimate
single use (`ps -p <PID>` alone is a normal check, `tail -50 file.log` alone is a
normal read).

**Quote-stripping:** via `_shell_strip._strip_non_shell_active` analogous to the
other pattern-match hooks — prevents false positives when the pattern sits in a
heredoc body or a quoted string as example text.

**Stderr message (one-liner per user directive 2026-05-24):**
```
polling loop antipattern — use `wait $PID` then single `tail file` instead of repeated polls
```

**Logging:** calls `_fire_log.log_fire("block_polling_loop", "block", "Bash", command, reason=<msg>, session_id=<id>)` analogous to all other block hooks, before `sys.exit(2)`.

**Registration:** the `hook_setup.py` `_HOOK_SCRIPTS` list, `("block_polling_loop.py", "Bash")`.

**Smoke test:** `dev/hook_smoke/test_block_polling_loop.py` with a positive case (the
exact cross_sweep pattern) + negative cases (only `ps -p` alone, only `tail -N`
alone, both in a heredoc body, both in a quoted string).

---

## Open Question (Post-Implementation, Data-Driven)

After 2 weeks of live data in `hook_firing.jsonl`:
- How often did the hook fire?
- Were there polling variants that show up in the log file but do NOT match
  this pattern (cross-checked via grep over raw session JSONLs)?
- If yes → re-eval whether attack surface B or C is worth building

That decision would then be made with concrete data, not hypothetically.

---

## 2026-06-22 — Live FP (Frequency Version) + Fix: Pipe-Fed Tail Has No Target

**Context:** the single-call approach (A) described above did not become the final form — the implementation running at the time was the frequency-based variant (decision 2026-05-29, documented in the hook_fp_audit area): `_extract_target` reads `ps -p <N>` → `pid:N` OR `tail -<N> <file>` → `file:path`, counts per (session,target) in a 30s window, blocks from the 3rd hit on.

**FP discovered (session: CC version bump 149→176):** the command `cd … && plugin-publish 2>&1 | tail -25` (+ appended `echo`/`grep`) was blocked with "polling loop — ≥3 checks …". Pure output truncation, not a poll.

**Evidence:**
- `src/logs/hook_firing.jsonl`: two blocks 2026-06-22 15:58:56 (`block_manual_worker_cleanup`, same chain) + 15:59:13 (`block_polling_loop`).
- `src/logs/polling_state.jsonl`: extracted target = `file:echo;` — the hook took the string `echo;` for a "polled file".

**Mechanism (verified):** `_TAIL_N_FILE = r'\btail\s+-\d+\s+(\S+)'` grabs the token AFTER `tail -25`. For a pipe-fed tail (`… | tail -25`) there is NO file argument — tail reads stdin — so `(\S+)` (across the line break) catches the next chained command `echo;`. The habitual style `cmd | tail -N` directly followed by `echo "…"` ⇒ the same pseudo-target `file:echo;` occurred 3× in the 30s window (a merge command + 2 plugin-publish attempts) ⇒ threshold 3 breached. Real FP: a pipe-fed tail has no file to poll.

**Fix direction (user green-lit 2026-06-22):** a pipe-fed `tail -N` (preceded by `|`, reads stdin) delivers NO poll target. Whitelist `cmd | tail -N` (+ chained commands, even repeated). A real `tail -N <file>` (no pipe) stays recognized as a watch-loop target; the `ps -p` path unaffected.

**Implementation (committed `48e1504`, worker `pollfix`):** a two-condition discriminator —
- **C1** `_TAIL_N_FILE = r'\btail\s+-\d+[^\S\n]+(\S+)'`: whitespace before the file arg restricted to space/tab (no newline) → the next-line command is no longer caught as a file.
- **C2** in `_extract_target`: if `stripped[:m.start()].rstrip()` ends in a single `|` (not `||`) → `return None` (pipe-fed, reads stdin).
- C1 catches the newline variant (`| tail -N\necho`), C2 the same-line variant (`| tail -N ; echo`). Real `tail -N <file>` (no pipe before it) + the `ps -p` path unaffected.
- Smoke `dev/hook_smoke/test_block_polling_loop.py`: +group `_run_group_pipe_fed_tail` (5 cases), **20/20 green**. Current-state docs (`src/hooks/DOCS.md` + `dev/hook_smoke/DOCS.md`) updated accordingly.
- **Accepted non-case:** `cmd | tail -N <file>` (pipe-fed WITH a file arg — tail then reads the file, not stdin) also gets whitelisted by C2. Not a real-world written poll pattern; deliberately no extra logic.

**Relation to a data-dependent re-eval item** (documented in the audit_logging area): this FP is exactly one data point on the FP side of that re-eval. The FN side (other polling variants slipping through) stayed open.

---

## 2026-06-22 — Live FN Closed: Long/Offset Tail Forms (Log Polling)

**Live FN discovered:** a Docling/RAG-conversion worker polled a growing log endlessly with `tail -n +58 /tmp/docling-reference_index.log | head -30`, the offset monotonically increasing (+58, +88, +118 …) on the same file. The hook did NOT catch it — verified: 3 identical-file reads all `exit 0`, NO target extracted.

**Root cause:** `_TAIL_N_FILE = r'\btail\s+-\d+…'` only matched the BSD short form `tail -<N>`. The GNU long/offset forms (`-n N`, `-n +N`, `-nN`, `-n+N`, `--lines=N`, `--lines N`) didn't match → no file target → the frequency counter never fired. Exactly the documented gap (the design weakness "pure log polling" + the DOCS note "`tail -n N` long form not detected"). The trigger condition for extending it (per the design doc: "once hook_firing shows other forms occur in reality") was met.

**Fix (committed `db789ad`, worker `polllong`):** `_TAIL_N_FILE` → `_TAIL_FILE`, an alternation across all forms; the number/offset is consumed INSIDE the flag arm (`-n[^\S\n]*\+?\d+` etc.), `(\S+)` always catches the file → **file-keyed, offset-agnostic** (+58/+88/+118 = the same fingerprint → the 3rd read blocks). The pipe-fed exception (C2 from the FP fix) stays. FP-safe: `tail -network` / `--lines-processed` need a digit after the flag → no match. Smoke 20→35 (the worker's exact form blocks on #3; appended `-n30`/`-n+58`; pipe-fed still no-target). Current-state docs updated (caveat removed). Live-verified against the worker's exact form.

**Data-dependent re-eval, FN side:** this closes the **tail-form part** of the FN side. Residual risk remains: form-foreign polls (sed windowing, python/jq tail, dd loops) — the fully form-agnostic variant (attack surface C, session-JSONL frequency analysis) stayed deferred (harder + FP-prone). Pragmatically: realistic tail forms covered, exotic ones remain residual risk. Meta-point (a user question): worker rule violations ("go idle, don't poll") are only structurally fixable by the hook, not the rule.

---

## Sources

- Forensics of the `mode-topk-sweep` worker session (RAG project, 2026-05-24):
  - `~/.claude/projects/-Users-brunowinter2000-Documents-ai-Meta-ClaudeCode-MCP-RAG--claude-worktrees-mode-topk-sweep/530a3eda-df84-4537-ac7c-9201412dd658.jsonl`
  - 371 polls with an identical pattern, all bg=False, monotonically incrementing tail-N
- `src/hooks/block_dangerous_kill.py` (template for the single-call signature hook)
- `src/hooks/_shell_strip.py` (quote-stripping module)
- `src/hooks/_fire_log.py` (logging module)
