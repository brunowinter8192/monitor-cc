# Split the shared "workers" tmux window into w-tokens/w-proxy (2026-09-18)

## Task

Window 2 (`workers`) held two panes side by side: `worker-tokens` (left, 34%) and `worker-proxy`
(right, 66%). The two panes are coupled only through an IPC file
(`/tmp/monitor_cc_selected_worker_<hash>.txt`, written by `src/workers/worker_selection.py`), never
through tmux geometry. User wanted each pane in its own fullscreen window. Target layout (fixed by
the user, not derived): 7 windows, 8 panes —

```
0  tokens      tokens
1  proxy       proxy
2  w-tokens    worker-tokens
3  w-proxy     worker-proxy
4  debug       warnings
5  gpu         gpu
6  news        news (50%) | news-log (50%)
```

`--mode` strings (`worker-tokens`, `worker-proxy`, ...) are unchanged — only tmux window/pane
geometry moved. Full task text lives in the issue that spawned this session, not repeated here.

## What actually changed

Only `src/tmux_launcher.py`. Confirmed by grep across the whole repo (`session_name}:2`,
`:2\.`, `worker-tokens`/`worker-proxy` as tmux addresses rather than `--mode` values, `_WINDOW_LAYOUT`)
that nothing outside this one file hardcodes a window index for this layout. `src/menubar/system.py`,
`src/monitor_janitor.py`, `src/workers/worker_selection.py`, `src/proxy_display/worker_proxy_pane.py`
address tmux only by session name (or not at all); every other `worker-tokens`/`worker-proxy` hit in
the repo is a `--mode` string or an IPC-file lookup, confirming the background claim ("coupled only
through the IPC file") was accurate.

Four things inside `tmux_launcher.py` needed updating beyond the obvious `_WINDOW_LAYOUT` table and
`_create_windows` call sequence — the task flagged these up front and all four were real:

1. `_WINDOW_LAYOUT`: 6 entries -> 7. Old window 2 (`workers`, 2-pane spec with a `66%` split) becomes
   two single-pane entries: window 2 `w-tokens` and window 3 `w-proxy`. Old windows 3/4/5
   (`debug`/`gpu`/`news`) shift to 4/5/6 unchanged in shape.
2. `_create_windows`: one `new-window`+`split-window` pair replaced by two plain `new-window` calls;
   every subsequent window index bumped by one; the `news`/`news-log` split moves from `:5.0` to
   `:6.0`.
3. `configure_tmux_session`'s `pane_titles` dict: `'2.0'/'2.1'` -> `'2.0'` (WORKER-TOKENS) + `'3.0'`
   (WORKER-PROXY); `'3.0'/'4.0'/'5.0'/'5.1'` (warnings/gpu/news/news-log) shift to
   `'4.0'/'5.0'/'6.0'/'6.1'`. The `for win in range(6):` per-window-option loop becomes `range(7)`.
4. `M-*` copy bindings: `M-t` (`0.0`) and `M-p` (`1.0`) untouched. `M-k` (worker-tokens) stays `2.0`
   by coincidence — worker-tokens keeps window-index 2 as a lone pane, so the address didn't move
   even though the window's shape did. `M-w` (warnings) moves `3.0` -> `4.0`. `M-n` (news-log) moves
   `5.1` -> `6.1`. No binding existed for worker-proxy before or after; not adding one was in scope
   ("only tmux geometry changes").

`restart_panes`/`_respawn_all_panes` needed zero direct edits — both already iterate
`_WINDOW_LAYOUT`, so the new table drives them for free. Verified this by running the rewritten
harness (see below) and by tracing `_create_missing_window`/`_fill_missing_panes` against the new
table by hand before trusting the harness's green result.

`dev/display/screenshot_panes.py` hardcodes `session:pane` addresses (`"2.0"`, `"3.1"`, etc.) for a
5-window/10-pane layout that does not match even the PRE-task 6-window/8-pane layout (it references
panes named "rules"/"hooks" that don't exist anywhere in `_WINDOW_LAYOUT`, current or past). It was
already stale before this task, is not part of the read-list, and touching it would be scope creep
per the worker rules ("bleib im Geltungsbereich des Prompts") — left untouched on purpose. Flagged to
main so it can become its own issue; do not assume this task's diff explains that file's drift.

## Real bug found in the dev harness, not a hypothetical

Ran `dev/tmux_launcher/argv_byte_identity.py` BEFORE touching anything, to understand its mechanics
before rewriting it. `_all_present_state()`'s window-2 fixture said
`--mode workers` on the first pane, while `_WINDOW_LAYOUT`'s actual mode-name for that pane is
`worker-tokens`. `restart_panes`'s `_fill_missing_panes` decides "is this pane already present" by
regex-extracting the `--mode` value out of `#{pane_start_command}` and checking it against the
pane-spec's mode name — so this mismatch made `present = {'workers': '0', 'worker-proxy': '1'}`,
`worker-tokens` was never found in `present`, and the "everything already present" restart scenario
silently emitted an extra `split-window` call that duplicated a worker-tokens pane into an
already-full 2-pane window. Confirmed by hand-running just that one scenario in isolation
(`_capture_restart(tl, m._all_present_state(), {0,1,2,3,4,5})`) and reading the argv list — the
`split-window -h -t ...:2.0 -l 50% ... --mode worker-tokens ...` call is right there.

This directly contradicted the module's own `dev/tmux_launcher/DOCS.md` claim at the time: "`restart_panes`
with every window/pane already present (pure respawn, zero create calls)". The bug was completely
invisible from the harness's own output, because the harness folded ALL THREE scenarios into one
combined `sha256` digest and printed only `HASH: <hex>`. A hash proves "did anything about the argv
stream change since last time", never "does this specific scenario actually hold the invariant it
claims to hold" — any real refactor changes the hash anyway, for legitimate reasons, so a hash delta
carries zero diagnostic information about which of the three scenarios broke, or how. Nobody would
have noticed this bug from staring at hash output; it only surfaced because this task required
throwing the hash away and rebuilding the harness around named, readable assertions instead.

Fixed by writing `_all_present_state()`'s pane commands with mode strings that actually match
`_WINDOW_LAYOUT` (`worker-tokens` on window 2, `worker-proxy` on window 3, etc.), and by asserting
the "zero create/split calls" invariant explicitly as its own named check instead of letting it hide
inside a combined hash. Re-ran the new harness with the old bug artificially reintroduced (reverted
the mode string on one fixture line) to confirm the new "restart, all present: zero create/split
calls" check actually catches it — it does (produces an explicit `FAIL:` line).

## Harness rewrite: hash dropped in favor of named PASS/FAIL checks

`dev/tmux_launcher/argv_byte_identity.py` no longer prints a single `HASH:` line. It now runs three
scenarios and asserts 7 named, independent properties, printing one `PASS:`/`FAIL:` line each plus a
summary, exiting 1 if anything failed:

- Launch: exact `new-session`/`rename-window`/`new-window`/`split-window`/`select-window` sequence
  for all 7 windows/8 panes.
- Launch: exact pane-title `select-pane -T` calls (proves the `2.0`/`3.0` split and the `4.0`/`5.0`/
  `6.0`/`6.1` shift).
- Launch: exact `M-*` binding argv (proves `M-w` -> `4.0`, `M-n` -> `6.1`, `M-k` stays `2.0`).
- Launch: the per-window `set-window-option` loop touches exactly windows `{0..6}`.
- Restart, all present: zero `new-window`/`split-window` calls (the invariant the old fixture
  silently violated — see above).
- Restart, self-heal: exact argv for a whole-window-missing recreate (used window 3, `w-proxy`,
  since it's a genuinely new case — every OLD "whole window missing" case had a coupled sibling pane
  going missing with it, this is the first lone-pane whole-window-missing case that exists) and a
  single-missing-pane split (kept `news-log` missing from window 6, same spirit as before).
- Restart, self-heal: exactly 8 panes get `respawn-pane`'d after healing (catches a wrong split
  fixture leaving a stray or missing pane, the same class of bug as the one described above, just
  from the other direction).

Sanity-checked the harness's ability to catch regressions twice: once by moving `M-w`'s target back
to `3.0` in `tmux_launcher.py` (harness produced exactly one `FAIL:` line, the M-* check, all others
stayed `PASS:`) and once via `git checkout -- src/tmux_launcher.py` (accidentally reverted the real
edit mid-session — see next section — which flipped all 7 checks to `FAIL:` at once, as expected for
a full revert to the pre-task 6-window shape).

**Caution for whoever touches this file next:** `git checkout -- <path>` inside a worktree discards
uncommitted edits unconditionally — it doesn't ask "are you sure", and there is no local stash of
what it clobbers unless you made one. Hit this firsthand: ran `git checkout -- src/tmux_launcher.py`
as part of a "restore the file after an intentional regression test" step, forgetting the real
(intended, uncommitted) 7-window edit was sitting in that same file with no commit yet. Lost the
edit, had to redo it verbatim from memory/the diff already shown in this session. If you need to
temporarily corrupt a file for a negative test and then restore it, either `git stash` first or keep
the known-good content in a variable/second file — never rely on `git checkout --` mid-session
unless the file is already committed.

## Known migration case: old-layout live session + Ctrl+R

Investigated via the fake-tmux harness (ad hoc script, not committed — lives in `/tmp/migration_probe/`
for this session only, gone once the sandbox recycles) rather than guessing: seeded `_FakeTmux` with
the OLD (pre-task) 6-window state (window 2 holding both `worker-tokens` pane 0 and `worker-proxy`
pane 1, windows 3/4/5 = debug/gpu/news, windows set `{0..5}`), then ran the NEW `restart_panes`
against it.

Result: no crash, nothing gets killed, but the layout comes out genuinely wrong:

- Window 2 (still named `workers` in tmux — self-heal never renames existing windows, renaming only
  happens via `new-window -n` when a window is created from scratch) is left exactly as it was:
  `worker-tokens` mode is already "present" by the mode-matching logic, so nothing touches it. The
  new table's window-2 entry (`w-tokens`, single pane) is satisfied by presence-check alone; the
  stray second pane (`worker-proxy`) is simply never noticed as "extra".
- Window 3 (old name `debug`, one `warnings` pane) gets a `worker-proxy` pane `split-window`'d in at
  50%, because the new table says window 3 should contain a `worker-proxy` pane and none is present.
- Window 4 (old name `gpu`, one `gpu` pane) gets a `warnings` pane split in at 50%, same mechanism —
  new table says window 4 = warnings.
- Window 5 (old name `news`, two panes) gets a THIRD pane, `gpu`, split in at 50% off pane 0 — new
  table says window 5 = gpu.
- Window 6 (didn't exist in the old session) gets created fresh with `news` + `news-log`, duplicating
  what's already tangled into window 5. Two tmux windows end up literally named `news`
  (the old window 5's tmux name was never touched, and the new window 6 is created with `-n news`).
- End state: 7 windows, 15 panes total (vs. the intended 8) — every pane still alive, nothing crashed,
  `display-message` still fires "Monitor restarted", the user just sees a visually broken session with
  unrelated panes glued into the wrong windows and a duplicate `news` window.

Per the task's own steer ("do not build a migration mechanism unless your finding shows one is
genuinely needed — a fresh launch kills and recreates the session anyway"): no migration code added.
`launch_split_screen` already unconditionally kills any existing session for the same project and
recreates it fresh on every `--mode all` invocation, so the actual fix for a user stuck with an old
session is simply: quit tmux (or let the janitor's 24h sweep catch it) and relaunch, not Ctrl+R.
Ctrl+R is a self-heal for a session that's already on the CURRENT layout with a crashed pane or
killed window, not a migration tool between layout versions — that was already implicitly true
before this task (the self-heal has never known how to rename an existing window, for instance), this
change just makes the failure mode of ignoring that concrete for the first time.

## Verification status

Harness (`dev/tmux_launcher/argv_byte_identity.py`) is green, 7/7 checks. Live tmux verification
against a real session (`--mode all`, `list-windows`/`list-panes`, `restart-panes` self-heal,
`kill-session`) is the next step after this doc — see the chat/issue history for that session's
outcome if this doc predates it landing.
