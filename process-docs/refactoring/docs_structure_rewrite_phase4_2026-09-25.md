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

## menubar/ (Gotchas and State detail removed from DOCS.md)
Process and lifecycle:
- The singleton lock must exit 0 on failure: launchd KeepAlive=true only respawns on a non-zero exit.
- The installed menubar is a FROZEN py2app bundle in ~/Applications. Restart or kill re-launches the same bundle and does NOT pick up edited src/menubar/*.py; any code change needs `./venv/bin/python setup_py2app.py py2app` to reach production. The bundle MUST be built from the main checkout: the repo root comes from the plist's PROJECT_ROOT, which the build script fills with the build directory.
- The kill action runs `launchctl bootout`, which removes the plist from the launchd domain; KeepAlive no longer respawns until a manual `launchctl bootstrap` or login (RunAtLoad=true).
- LSUIElement=1 must be set (environ setdefault) before app.run(), otherwise the Dock icon appears.
- launchd default PATH lacks Homebrew: the plist's EnvironmentVariables/PATH must prepend /opt/homebrew/bin or tmux/lsof lookups in proc_cache fail silently.
- launchd runs under the ascii locale: every subprocess.run(text=True) in this package must carry encoding='utf-8', errors='replace', else non-ASCII CC output (emoji, umlauts) raises UnicodeDecodeError.
- hook_setup in menubar refuses to run from a worktree path; hooks must be installed from the main checkout or the registered path dies when the worktree is removed.
- Code signing: the desktop detection needs Screen Recording (TCC) permission for window-name visibility, and Launch needs PostEvent permission; both grants survive rebuilds only while the bundle stays signed with the `monitor-cc Code Signing` identity (not the ad-hoc fallback).

Threading and caches:
- Discovery runs exclusively on the discovery-worker thread because the module caches in proc_cache, ghostty and desktop_detection are single-writer. The one cross-thread read (ghostty cwd-to-tty lookup from the focus path on the main thread) MUST go through proc_cache's snapshot accessor; direct iteration raises "dictionary changed size during iteration".
- ghostty's batch refresh early-return branch (no new ttys) must still set the last-refresh timestamp, or the 10s TTL guard never re-arms and two `ps -A` calls run every discovery cycle.
- proc_cache's bg-task open-paths and holder-pids dicts are REASSIGNED on every refresh, unlike the CC process cache (mutated in place). A `from .proc_cache import <dict>` in another module binds the import-time object and goes stale after the first refresh; bg_task_orphans reads through the snapshot accessor for this reason; any new consumer must do the same.
- The active-background check is handle-based (lsof open-write-handle), not file-size-based: a task output file can be non-zero seconds after start while the task runs for minutes.
- The abort action must resolve each killed PID's own .output file (lsof on fds 1 and 2) BEFORE sending SIGTERM: the handle disappears when the process exits.
- Orphan reaper: bg_task_orphans self-throttles to once per 10s independent of the 1.5s discovery cadence, reconfirms each candidate with a fresh lsof immediately before a kill (the 10s-old cache is not trusted), walks ancestry up to 5 hops, dedups orphan_detected log lines per pid.
- Tick architecture: main-thread 1.5s tick; panel full rebuild triggers on exactly two events (session-set change, or abort-button None-to-Some transition while open). A bare working/idle flip never rebuilds (open: in-place update; closed: bar icon blinks only).

AppKit/Carbon:
- Carbon hotkey CFUNCTYPE/handler refs (hotkey_carbon, digits, arrows, controller global handles) and desktop_detection's module-level CFUNCTYPE refs must stay referenced for the app lifetime: GC corrupts the IMP pointer table and crashes (SIGSEGV/SIGABRT) on the next hotkey event.
- NSGridView disables translatesAutoresizingMaskIntoConstraints on every cell content view: any NSView in a grid cell needs explicit height and width anchor constraints or it renders at zero size / bleeds out of its row.
- The keyable panel overrides canBecomeKeyWindow to True because NSWindowStyleMaskNonactivatingPanel blocks key-window status by default, which would break keyboard routing to any editable field.
- Sessions grid has 7 columns; the seventh holds the skill button (main rows only). Horizontal merges for project separator rows and every addRowWithViews list in panel_manager must keep 7 entries or NSGridView raises.
- Tab header: four real tab buttons per panel (tag = ring index, action selectTab:) plus three separator labels in a strip; static per panel. The wiring step must run for every panel's header or clicks do nothing. panel_lifecycle derives ring neighbours from a ring tuple; adding a tab means one entry in the ring, one in panel_tabs, plus the panel open/close cases.
- Side-panel scaffolding (RAG, Models, Launch) lives once in panel.py; all four controllers resize through the keep-top resize helper. The Sessions panel keeps its own panel factory and reposition function on purpose (footer, own content view class, no status-window None guard).

Ghostty:
- Ghostty exposes no tty or pid via AppleScript. tty-to-UUID mapping and the desktop detection per-window resolution both bootstrap via an OSC 2 title-marker write plus an AppleScript name query. The marker only works when the target tab is the FOCUSED tab of its window (background tabs do not propagate OSC-2 to kCGSWindowTitle).
- The monitor-open action always kills an existing monitor_cc_* tmux session before relaunching; no focus-only branch, since that session commonly outlives its Ghostty window and a focus-only click would silently no-op.
- Focus AppleScripts (both session routes, the shared terminal-id focus used by both worker attempts) call app-level `activate` AFTER the terminal-level focus command in the SAME osascript invocation (since 2026-09-20). This reverses part of the 2026-06 process-docs in area ghostty_foreground (which removed activate because it brought Ghostty forward on every desktop); the user retracted that (area menubar_worker_focus, 2026-09-20) in favor of one narrower constraint: a Ghostty window must never change its own desktop. activate is only reached after a successful focus and is naturally unreached on the id route if `focus terminal id` throws. Do not reintroduce activate as standalone/first command and do not split it into a second osascript call (order matters, one round trip).
- Worker-viewer focus self-heals one stale-id failure: on a non-OK first attempt it reprobes that single tty and retries once. Log lines: focus_worker with status OK / ERR rc stderr / TIMEOUT plus attempt=1; on failure a focus_worker_reprobe line (tty, cost, fresh id or miss) and, if a fresh id was found, a second attempt=2 line. The reprobe path is the only added cost and never runs on first-attempt success.
- The single-tty reprobe deliberately has NO fixed sleep after the OSC2 write, unlike the batch refresh (120ms). Measured live (60 trials, area menubar_worker_focus): immediate query finds the marker about 88% of the time; on a miss one immediate retry found it 100% (0 double-misses), average total about 92ms vs about 210ms with the fixed sleep. This applies ONLY to the single-tty path; the batch refresh sleep was not re-measured (different shape: N markers before one shared query). Do not assume the conclusion carries over.
- Path oddities: proc_cache's proxy-log directory is a hardcoded absolute path (breaks if the checkout moves). ghostty writes the cwd-to-UUID map through its own inline path, not through the paths constant; that constant and the orchestrator-signals constant have no reader inside this package (the signals file is written by the iterative-dev plugin's worker-cli send).

Launch tab:
- Needs PostEvent permission for the bundle. The request runs on the MAIN thread when the tab opens; the launch thread never requests. Without the grant a click only logs `[launch] FAILED ... postevent_not_granted` and nothing switches; there is no fallback, by design.
- The launch workflow blocks about 1.5s (switch plus 1s settle), so it runs on a daemon thread; a busy flag drops clicks while it runs (cleared in a finally). Occupied desktops are only marked, never refused.

Skill picker:
- Plugin skills come ONLY from the manifest's skills array; full name is `<manifest name>:<frontmatter name or directory name>`. Project and personal skills use the directory name (frontmatter name is a label only). An enabled plugin with neither manifest nor skills/ directory is skipped silently; a missing manifest with a skills/ directory, a manifest without a skills array, or a missing skill file logs `[skill] FAILED` and is skipped. Inserted text `Aktiviere den Skill <full name>.` is typed with `input text` and never submitted (no send key, no activate).

State ownership (per controller on the app object):
- settings (panel width, min height): app.py, read by the panel, rag, model and launch controllers.
- panel controller: open/backgrounded/initialized/rebuild flags, lookup state (displayed items, cwd map, worker tag map, desktop-to-cwd, abort button maps), widgets.
- rag, models (pending selection incl. per-side thinking, row buttons), launch (selected desktop, occupied set, desktop buttons, in-progress flag), skills (the row whose menu is open), sessions (last sessions and bg map), focus (last statuses), hotkey (digit/arrow GC refs plus global handles for Cmd-L/Cmd-K).
- Caches: CC process cache (pid to tty,cwd; written only from discovery thread; cross-thread read via snapshot), tmux session set (3s refresh), hook state (session_id to status,cwd,updated_ts; 1s TTL), Ghostty tty-to-id map, desktop result cache (10s TTL) plus previous result for transition logging.

## Notes on tool behavior (2026-09-25)
- docs-drift-check flags a `### <module>.py` heading whose file is not in the documented directory. setup_py2app.py sits at the project root and was therefore dropped from src/menubar/DOCS.md. It is the py2app build/install/bootstrap script (reads menubar_main.py entry and the plist template, writes dist bundle, ~/Applications copy and the LaunchAgent plist; run manually once and after a Python upgrade; uses py2app and setuptools). It was 200 LOC on 2026-09-25.
- docs-drift-check also flags a `src/logs` path mention as NOT FOUND (the directory is gitignored, absent in worktrees). DOCS.md refers to "the gitignored logs directory" instead.
- Size after rewrite: src/menubar/DOCS.md is above 400 lines (about 455) because of the mandatory per-module template with 45 modules; hooks/DOCS.md about 375.
