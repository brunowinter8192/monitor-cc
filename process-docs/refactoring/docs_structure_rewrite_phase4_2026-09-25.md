# DOCS.md structure rewrite (refactor-scan Phase 4), worker mcdoc-a, 2026-09-25

Scope: DOCS.md of src/, menubar, hooks, core, ccwrap, input, jsonl, format, workers, ram_audit. Rule applied: DOCS.md at module level only; no function, method, class or constant names; Gotchas sections do not exist in the template, so their content moved here. No code was changed.

Stale claims found while rewriting (removed from DOCS.md, verified against code on 2026-09-25):
- `workers/worker_pane.py` and its siblings no longer exist; old DOCS listed them as callers of input, ram_audit and jsonl. Only `worker_tokens_pane.py` remains.
- `core/monitor.py` does not import `src/input` nor `ram_audit`; old DOCS listed it as a caller.
- `workflow.py` is 33 LOC (old DOCS said 39).
- src/DOCS.md carried a duplicated monitor_janitor log-path gotcha (two variants); kept once below.

## src/ (root) gotchas moved out of DOCS.md
- The search-highlight background sentinel embedded by every zebra/hover row loop must be resolved by every renderer that embeds it, otherwise a literal escape code leaks into terminal output.
- The kill-line key in search_bar is Ctrl-U, an unconfirmed guess of Cmd+Backspace's terminal encoding; rebinding after live testing is a one-line change.
- monitor_janitor's log path follows the root resolver in monitor_root: env override if set, else the checkout the module sits in. A manual run from a worktree without the env var writes into that worktree's own src/logs/. The first `ROOT source=...` line in monitor_sweep.log states which source won.
- tmux_launcher restart self-heals only a pane whose spec parent pane is present; an unplaceable pane raises RuntimeError instead of splitting an arbitrary pane. Structural tmux calls run with check=True and raise on failure. The global history-limit lookup returns None when no tmux server exists, and the launch then skips restoring the history limit.
- pane_error_log swallows its own write failures silently: a full disk or permission error never propagates and never kills a pane loop.
- session_finder's project-path encoding must stay byte-identical to how Claude Code encodes project directory names, or the project filter silently matches nothing.
- utils cell-width treats emoji and CJK ranges as width 2; every truncation and padding function depends on it, otherwise ANSI row-fill columns drift one cell per wide character.

## core/
- The subagent-file filter (agent-* prefix) must stay in sync with what session_finder indexes as a subagent file.
- The session start timestamp is the newest main session's first timestamp minus 10 seconds; proxy_display uses it as the historical-replay cutoff.

## ccwrap/
- macOS PTY EOF differs from Linux: reading master_fd after child exit raises OSError(EIO) on Linux but returns b'' on macOS; the io loop handles both.
- The child wait must run before closing master_fd. Closing first sends SIGHUP to the child and masks the real exit code with 129.
- Raw stdin mode and adding stdin to the select list are both skipped when stdin is not a tty; under a non-tty runner the child never receives stdin.
- The SIGWINCH handler is reset to default before master_fd closes to avoid a racing resize on a closed fd.
- Log rotation is mtime-based, matches pairs by stem, but iterates only .bin files; an orphaned .ansi.log from a crash mid-write is never cleaned.
- The carry buffer for split escape sequences holds only 1-2 bytes; a longer sequence split at a 4096-byte read boundary is logged as two fragments.

## input/
- All stdin reads use os.read(fd, 1), never sys.stdin.read: Python's 4096-byte stdin buffer makes select() unreliable for escape-sequence detection.
- Multi-byte UTF-8 keypress: lead byte read, continuation count derived from its bit pattern, then that many further single-byte reads, each gated by a 0.005s select timeout, decoded together.
- Any-event mouse tracking (SGR 1003) captures ALL mouse events from tmux, so native tmux scroll stops working while enabled; panes scroll themselves.
- Mouse read returns (-1,-1,-1), not None, for a release event; callers interested in presses check the first element.
- Failures are tripwires: non-tty stdin, malformed SGR mouse field and a failing pbcopy raise into the pane-loop log; terminal-restore failures go to the pane error log.

## jsonl/
- Claude Code writes one logical API response as several top-level assistant lines (one per content block: thinking, text, tool_use), all sharing the same requestId and usage. The cache-turn extractor dedups per requestId and tracks already-counted content blocks in a seen set; never assume one JSONL line equals one API response.
- A user message beginning with a command-message or command-name marker is a skill invocation and always opens a new turn, the one exception to "same-timestamp messages merge into the current turn".
- Each api call carries the timestamp of the request's LAST assistant entry (response end).

## format/
- Strip highlight wraps each line of a chunk individually because downstream renderers split on newline and apply per-line zebra background.
- Some underscore-prefixed helpers of token_format (compact token count, turn header line, cache call line) are imported by 4+ external callers; treat them as public.
- The cache tracker returns a 5-tuple (visible lines, visible keys, sticky header, viewport start, initial parent count), not a string.
- Inline foreground endings use the soft reset (foreground only) so a caller-injected row background survives; the broken-cache row keeps a full reset since its background must end at the line terminator.
- Sticky-header truncation path rebuilds the header from only the "Turn N" match, dropping a prepended search marker. A turn that is simultaneously a search match, long enough to truncate and the current sticky header loses its highlight; match data and jump still work (hypothesis-level: seen in code reading, not in live use).
- The expanded model line is RED when proxy_forwarded_model and answering_model differ, DIM otherwise, nothing when answering_model is empty. response_rid_map values are full dual-log response entries keyed by request_id.
- Search in panes/token_search reuses token_format's render helpers directly so a search match can never diverge from what is rendered.

## ram_audit/
- Dump has four sections: header (timestamp, pid, RSS), top-30 gc objects by class, top-30 tracemalloc by line, pane module state (containers as len and sizeof, scalars as value).
- tracemalloc only starts when MONITOR_CC_RAM_AUDIT=1 is set at process start; otherwise the section reports "not active" while the other sections still work.
- The dump directory follows the same root resolver as monitor_janitor (worktree-vs-main caveat); the winning source is noted once in /tmp/monitor_cc_error.log.
- RSS uses psutil when installed, else stdlib resource with macOS-bytes vs Linux-KB normalization.

## workers/
- The all-workers list pane (worker_pane and siblings) was DELETED in the 2026-09 panesplit milestone. The user accepted losing the simultaneous overview for two consistent tokens/proxy-shaped windows per worker; the switch header is the only overview. Do not resurrect a stacked multi-worker render; that would be a new design decision.
- The freeze feature (f key, LIVE/FROZEN badge) went with the list pane and was not carried forward; it solved churn across N simultaneous worker blocks.
- Worker switch resets pane state (expand, scroll, search, incremental read position), mirroring worker_proxy_pane. The stats cache is the exception: it covers every listed worker and is never reset.
- The switch header wraps over several rows at the pane's real width (34% window share next to worker-proxy at 66%); one click region per row segment a marker straddles, verified down to width 34 in dev/click_ui/p1_worker_selection_click_probe.py.
- The header line count is cached per render and used to estimate the search-jump scroll target; it is not recomputed at jump time.
- Worker stats are incremental and this is load-bearing: an unconditional full-file read per worker per tick measured about 70ms for 5 typical worker JSONLs and 620ms for one 196MB file, blocking the poll loop; doubled across two panes that is about 280ms/s (see dev/worker_pane_split/). Reintroducing a read from offset 0 reintroduces the cost in both panes.
- Worker context window is a flat 1M tokens since the worker fleet runs only 1M-context models.
- Stats cache entry shape: position, total output, context percent, jsonl path; self-resets when a session's resolved jsonl path changes. Each worker pane process owns its own cache; no sharing.
- Selection file: md5 of the normalized project path in the name, 'global' when absent; falsy worker name removes the file.

## hooks/ (details removed from DOCS.md; hook rule specifics are in each script)
Design and incidents worth keeping:
- Fail-open is mandatory: every hook exits 0 on any parse error or missing field; a hook must never block a legitimate call due to its own failure.
- Hook timeout is 5s (installer constant). Hooks fire for every matching call in every session on the machine (main and workers): keep them fast and narrow.
- Fire-log decision values in use: block (exit 2, reason field), rewrite (exit 0 plus updated input, rewritten field), trace (reason only, no effect on outcome: parse errors, raw-text strip fallback, exempted shlex segments, unknown-size po block, degraded worker-status check, rag repeat-state failures, getcwd failure). A fourth value ui-notice is reserved and unused. Filter with `jq 'select(.decision != "trace")'`.
- PreToolUse exit codes: 0 allow, 2 block (stderr shown to the model), 1 hook error (logged, not a block).
- Stale registered hooks block ALL Bash calls machine-wide: a registered `python3 <path>` whose file no longer exists exits non-zero on every call. Recovery: run the installer from the main repo root in a real terminal (not Claude Code's Bash tool); its stale sweep runs before the add loop. The installer writes absolute paths, so moving the checkout requires re-running it.
- Per-clone setup: `git config core.hooksPath .githooks` once (local config, not committed), otherwise post-merge and post-commit do not auto-run the installer on commits touching src/hooks/.
- The installer gates each script on being committed on main AND present in the working tree; a worktree guard exits 2 when run outside the main repo root.
- Subprocess hooks must resolve plugin CLIs by absolute path: the hook environment has a stripped PATH, and a bare subprocess call raises FileNotFoundError, which the fail-open catch turns into a silent no-fire. The two worker-status guards resolve via shutil.which then a glob over the plugin-cache bin directory (status call has a 3s timeout). Follow this for any new subprocess-invoking hook.
- block_po_read keeps a hand-maintained copy of the poread byte ceiling from src/proxy/inject_poread.py (no shared import, since hooks import only same-directory siblings and run as standalone entry points). Drift in either direction reopens a gap: stale-high wrongly blocks a file poread would refuse, stale-low wrongly allows a partial read of a file poread could export whole. Change both by hand. dev/hook_smoke/test_block_po_read.py pins its own literal copy. Size undeterminable (missing file, OSError, unresolved token) defaults to blocked.
- rewrite_worker_wait supersedes the former pair block_worker_wait_isolated and block_worker_wait_foreground: one updatedInput must carry corrected command and forced background flag together; a merge or precedence dependency across two hooks was rejected (background: process-docs/tool_use_safety/). block_unauthorized_background therefore excludes any command that merely mentions the worker wait form, leaving the rewrite hook as sole decider.
- rewrite_worker_wait blocks (exit 2) only when chaining follows the leading cd (trailing and-and, semicolon, pipe), since rewriting would discard a requested command.
- The two worker-status guards (kill, send) are deliberately duplicated code: this hook family favors small independent scripts. dev/hook_smoke tests import their decision function directly. Double gate: regex name capture plus live status, so a kill right after a worker finishes is never falsely blocked.
- block_path_typo rewrites `.claire/` to `.claude/` and `..<letter>` to `../<letter>`; file name kept for settings matcher continuity though it no longer blocks. Registered on Bash, Read, Write and Edit matchers.
- block_manual_worker_cleanup deliberately does not police git branch -D since worker branches carry no distinguishing prefix.
- block_rag_cli_document_repeat: 10-minute (600s) rolling window keyed by (session_id, "<subcommand>:<collection>"); state file is rewritten in full each call (self-pruning, not append-only). A single one-off --document call always passes.
- block_cd_drift and rewrite_background_sleep both key on the worktree path fragment .claude/worktrees/ and skip when the hook itself runs inside a worktree.
- block_dev_imports_src exempts pytest-shaped files (test_*.py, *_test.py, conftest.py) under a tests/ segment.
- The shell stripper on an unclosed heredoc or quote (deliberate strip error) returns input unchanged and logs a trace; any other exception propagates. It keeps command substitution and backticks active.
- block_cli_chained covers 8 CLIs (gh-cli, rag-cli, worker-cli, reddit-cli, websearch, linkedin, penny-cli, duallog), resolves the bare interpreter form by a known project directory in the command, falling back to the session cwd; three rules: no piping a CLI segment, no redirecting a protected subcommand to a file, no same-call readback of a redirected file. Other chaining is unrestricted.
- Disabled scripts (`*.disabled` in the directory) are not registered and not documented.
- Registration state of block_po_read lives in the machine-local user settings file, which this repo does not track; do not assert it in docs.
