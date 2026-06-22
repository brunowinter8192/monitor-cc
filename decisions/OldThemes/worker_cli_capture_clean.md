# worker-cli capture — clean+scope redesign (#25 capture-noise, 2026-06-22)

Two-repo feature: `worker-cli capture` redesigned to return clean, scoped output (iterative-dev plugin)
+ a monitor-cc rewrite hook that strips capture pipe-appendages. Closes the "capture-noise" item of #25.

## Motivation
`worker-cli capture <name>` dumped the raw tmux pane (boot box, footer chrome, `(ctrl+o to expand)`
collapse markers, glyphs, diff hunk bodies) to a file → the orchestrator then `tail`-guessed at it.
Main pain (user): `tail` is FRAGILE — `capture | tail 40` / `80` / `100` never gives certainty of the
full turn and re-stacks the same lines in context. Wanted: capture behaves like `response` (one call,
complete output since the last orchestrator prompt) but sourced from the PANE, not JSONL — because for a
dying/stuck worker the JSONL has no completed turn, only the pane shows the live state.

## Design (decided in chat)
- **Stay with the tmux-pane capture** (NOT JSONL/proxy) — user preference, "sauberer".
- Capture default = clean + scoped to last real `❯` prompt; `--raw` = old raw-pane-to-file escape hatch.
- **Collapse of edit output is DESIRED, not content loss** — for reading a worker the orchestrator only
  needs WHAT it wrote + WHICH files it touched; the full edit content comes from `git diff`. So diff hunk
  bodies are stripped (keep `Update(file)` header + `Added/removed` counter).
- Constraint (hard, user): **no content loss, some noise acceptable** ("lieber etwas Noise als Content-Verlust").
- `history-limit 50000` on worker sessions so a long turn's `❯` anchor never scrolls out of scrollback.

## IST (final, both repos)
- iterative-dev: `worker_capture_clean()` + `_capture_clean.py` (scope+clean filter) + `--raw` dispatch in
  `worker-cli`; history-limit at spawn+revive. See `iterative-dev/decisions/spawn.md` + `src/spawn/DOCS.md`.
- monitor-cc: `rewrite_worker_cli_capture_noise.py` (Hook 32). See `decisions/pipe07_safety_hooks.md`.

## Iteration (process — what was tried, fixed, rejected)
1. **Stage 1 built (pollfix).** _capture_clean.py: scope to last `^❯ <non-empty>` (anchor fix — bare
   bottom input-box `❯` was excluded via `_trim_bottom_widget` + `^❯\s+\S`), clean filter, `--raw`,
   history-limit. Smoke 20/20 green — but on a **hand-built fixture**.
2. **Diff-body bug (caught in Phase-4 live-verify, NOT the fixture).** Running on a REAL pane left diff
   bodies in. Root cause was triple: (a) `_RE_DIFF_LINE = ^\s*[+\-]\s` did not match CC's real format
   `<indent><linenum> [+/-]<content>`; (b) `in_diff` was set False at the `Added` counter, so the body
   that follows arrived un-tracked; (c) `_RE_ADDED = ^Added \d+` never matched the INDENTED counter
   `  ⎿  Added …` (glyph-strip assumes glyph at col 0; the `⎿` counter is indented). The fixture used a
   simplified `+ x` format AND wrong order (body before counter), so it gave false confidence.
   Fix (capclean2): `_RE_DIFF_LINE = ^\s+\d+(?:\s|$)`, `_RE_ADDED = ^⎿\s+Added \d+`, keep `in_diff` True
   after the counter. Fixture rebuilt with real CC format. Verified against two real panes (0 leaks).
3. **`...`-in-diff residual (caught in live-verify after Stage-1 merge).** CC collapses unchanged lines
   mid-diff as `     ...`; that non-numbered line exited `in_diff` early → the body tail after it leaked
   (same class: wrapped continuation lines). Fix: **sticky `in_diff`** — after header+counter, drop by
   default; exit ONLY on a blank line or a new `⏺`-led tool line (checked on the pre-glyph-strip `orig`).
   `...`, numbered body, +/-, wraps all dropped.
4. **Global `_RE_DIFF_EXPLICIT` filter — REJECTED.** capclean2 also added a GLOBAL strip of any
   `^\s+\d+\s+[+-]` line (numbered +/- outside a diff block) to catch 3 orphaned-prose hits. Rejected on
   review: content-loss risk — a legit numbered list `   16 - item` or prose math `   3 + 4` would be
   stripped, violating the hard constraint. Removed; sticky-in_diff alone fixes the real leak. The
   remaining orphaned diff-format prose (worker narration quoting diff text) is **accepted noise** — it is
   real content, kept, not lost.
5. **Stage 2 hook (capturehook).** `rewrite_worker_cli_capture_noise.py` — near-exact mirror of
   `rewrite_worker_cli_response_noise.py`, three differences: anchor `worker-cli capture`; `_NOISE_RE`
   **pipe-only** `(?<!\|)\|(?!\|)` (NOT redirects — `capture X > file` is a legit full-output save, and
   `--raw` is a flag that survives); log_fire name. No grep exception (user: "kein Use-Case für grep auf
   capture"). Live-verified end-to-end: the hook rewrote a real `capture … | tail … | head` command to
   bare capture (fire-logged).

## Verification
- Stage 1: `_capture_clean.py` run on two REAL panes → 0 Update-block diff-body leaks; control re-run on
  the known-leak fixture stays 0; the only "hits" in a live clean capture were orchestrator-prompt-echo +
  worker narration (kept content, not leaks).
- Stage 2: 17/17 smoke + 6 direct-invocation cases (pipe→bare, --raw survives, redirect preserved, quoted
  unchanged, chain preserved, `response` untouched) + 1 live end-to-end fire.

## Key lessons
- **Fixture ≠ reality.** A hand-built fixture using a simplified diff format passed 20/20 while real CC
  output slipped through. Phase-4 live-verify against a REAL captured pane is what caught every diff bug.
  Test fixtures for pane-cleaning MUST use real CC rendering.
- **Noise-removal must never risk content** (the global-filter rejection). Per the hard constraint, an
  accepted-noise residual beats a content-loss filter.
