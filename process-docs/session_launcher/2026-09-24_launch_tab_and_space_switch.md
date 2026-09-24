# Launch tab: desktop switch experiments and implementation (2026-09-24)

Worker "spaceprobe", area `session_launcher`, macOS 26.6.2 (build 25G83), one display, five
Mission Control desktops. Covers the experiments (runs 0-2), the removal of Auto-Jump (M1) and the
new Launch tab (M2). Everything below was observed on 2026-09-24 unless marked as hypothesis.

## Goal and decisions made by the user

- Menubar loses Auto-Jump completely and gains a 4th tab "Launch" (ring: Sessions, RAG, Models, Launch).
- Launch: pick desktop 1-5 (desktops that host a main session cannot be picked), click one of 10
  fixed projects. The menubar switches to that desktop, opens a Ghostty window and starts the main
  session with `cd <monitor-cc> && PATH="$HOME/.local/bin:$PATH" ./src/claude_proxy_start.sh --project <path>`.
- Switch mechanism chosen by the user: CGEventPost of Ctrl+N (variant a1 below).
- The `; exit` appended by `_launch_monitor_ghostty_native` stays (window closes when the session ends, same as the mon button).
- No warning line for mains without a detected desktop. Names `focus_controller.py`/`FocusController` stay.

## Why the approach is "switch first, then open"

Moving an existing window to another space is impossible without disabling SIP on macOS 26
(five private move APIs were silent no-ops; see the `desktop_allocation` area). A new window
appears on the active space, so the only working order is: switch space, then open the window.

## Experiments

Scripts: `dev/session_launcher/` (`space_lib.py`, `s0_preflight.py`, `s1_switch_probe.py`,
`s2_ghostty_window_probe.py`), reports in `dev/session_launcher/md/`. Run as
`venv/bin/python -m dev.session_launcher.<script>` from the project root. The venv has no PyObjC,
so the helpers are pure ctypes (CoreFoundation + CoreGraphics). Each screen-moving run was
announced and only started after the user's go; every run started on desktop 2 and returned there.

### Run 0: preflight (read-only)

- Five desktops, all type 0 (no fullscreen spaces): space ids 3,4,5,6,7 = desktop 1..5.
- Symbolic hotkeys 118-122 enabled with key codes 18,19,20,21,23 and Ctrl.
- `AppleSpacesSwitchOnActivate` = 0.
- TCC ancestry of the Bash: python <- zsh <- claude.exe <- bash <- tmux (no GUI app in the chain,
  so which app macOS treats as responsible is unknown). Preflight calls reported Accessibility,
  PostEvent, ListenEvent and ScreenCapture all True.

### Run 1: which technique switches the space (14 of 14 worked)

Measured as time from posting until `CGSGetActiveSpace` equals the target space (poll 20 ms).

| variant | ms |
|---|---|
| a1 CGEventPost Ctrl+N, session tap, flags on the key event (desktop 3 / 5) | 284 / 288 |
| a2 same, HID tap | 283 / 276 |
| a3 same, session tap with explicit Ctrl key down/up | 270 / 276 |
| b System Events `key code N using control down` | 283 / 271 |
| d1 CGEventPost Ctrl+Right, one step | 994 |
| d2 System Events Ctrl+Right, one step | 990 |
| c swipe, `iss.c` flavor, 1 step / 3 gestures | 23 / 68 |
| c swipe, InstantSpaceSwitcher flavor (velocity x steps), 1 step / 3 steps | 48 / 25 |

- The hotkey path is NOT blocked for CGEventPost on 26.6.2 (the external "tahoe hotkey dead end"
  article was about Carbon RegisterEventHotKey listeners, not the Mission Control hotkeys).
- Swipe direction: posting "right" moved to the higher index, no inversion on this machine.
- Ctrl+Arrow takes about 1 s per step (animation), unusable for jumping.
- Not measured: which single TCC permission each variant needs (all four were granted, none revoked).
  System Events variants additionally rely on Automation for System Events, which was present.

### Run 2: where does a new Ghostty window land

Cycle: switch (a1), wait 1 s, `tell application "Ghostty" to set win to new window` (with or
without `activate`), diff the CG window ids, read `CGSCopySpacesForWindows`, close, return home.

- 10 cycles (5 without, 5 with `activate`), targets 1,3,4,5,1. 8 of 10 windows were confirmed on
  the target desktop and on screen. The other 2 (no_activate #5, activate #3) returned an empty space
  list and not-on-screen for the window the script picked. In all 10 cycles the active desktop
  stayed on the target (after the script and after 1 s).
- Hypothesis (never observed): the script picks the first NEW CG window id, and Ghostty may create
  a transient CG window without a space first. Not verified; a follow-up run would record all new ids.
- Timing: `new window` returned after 114-131 ms, the CG window was visible 135-158 ms after starting the script.
- `activate` did not pull the screen away (setting above is 0).

### Ghostty AppleScript facts learned the hard way

- Window ids are strings like `tab-group-aa70da940`; `new window` returns the window, `id of win` works.
- Close a window with `close window (first window whose id is "<id>")`. The plain `close (first window ...)`
  is the terminal command (sdef: `close` closes a terminal) and silently did nothing. First Run 2 attempt
  aborted in cycle 1 for that reason and left one test window; it was found by writing an OSC-2 marker title
  to the only Ghostty login tty started at that minute (`ps -o lstart`), then closed by id.
- `count of windows` / `every window` list new windows LAST.
- A closed window can stay in the CG window list for a while as an off-screen zombie with no space
  (same shape as four stub windows 65-68 that always exist). So "closed" must be checked against the
  AppleScript window list, not the CG list. The zombies were gone minutes later.

## Implementation

### M1: Auto-Jump removed

Removed: `toggleAutoJump_` and wiring, `PanelSettings.auto_focus`, `auto_focus` in
`app_settings.py`, `FocusController.tick` (and the `focus_tick` phase in `app.py:_tick`), the three
copies of the "Auto-Jump: ON/OFF" header. `settings.json` files that still contain `auto_focus` load
fine (key ignored) and lose the key on the next save (a resize). The header text is now built only by
`panel_tabs.py:tab_header_text`; the top-bar button is `header_btn` (no target, no action).

### M2: Launch tab

Modules (all in `src/menubar/`): `launch_config.py` (10 projects, desktops 1-5), `space_switch.py`
(PostEvent check, desktop to space id via `desktop_detection._build_space_map`, Ctrl+N via CGEventPost,
wait until active), `session_launch.py` (workflow), `launch_controller.py`, `launch_panel_ui.py`,
`panel_tabs.py`. `panel_lifecycle.py` now derives ring neighbours from one tuple instead of hard-coded chains.

Behavior decisions (each has a reason):
- Failure policy: any failure logs `[launch] FAILED desktop=.. project=.. stage=<validate|switch|open_window> <detail>`
  to `menubar.log` and stops. No window is opened after a failed switch. No fallback (System Events,
  swipe) exists in production, because nothing was observed for the bundle; those were only measured in the dev process.
- Missing PostEvent: `CGPreflightPostEventAccess` false -> `CGRequestPostEventAccess()` once ->
  `SpaceSwitchError('postevent_not_granted')`. Without the preflight the events would be dropped silently
  and the only symptom would be a 3 s timeout.
- 1 s settle between "space active" and "new window" is the condition Run 2 was observed under; it was not shortened.
- The launch runs on a daemon thread (about 1.5 s blocking). A busy flag drops further clicks.
- The Launch panel closes on the click (it is CanJoinAllSpaces and would otherwise float over the new session).
- Selection resets on every open of the tab; the occupied check is repeated at click time.
- Occupied = `SessionInfo.desktop_no` of main sessions. A main whose desktop was not detected has
  `desktop_no=None`, its desktop therefore looks free (accepted by the user, no warning).
- Project rows show the path after `/Documents/` (e.g. `ai/Meta/ClaudeCode/cli/gh-cli`).

## Tests (none of them move the screen)

- `t1_autojump_removal.py`: 7 checks PASS (no identifier left in any `.py` under `src/` and `dev/`, old
  settings load, save drops the key, `FocusController` has no `tick`, `PanelSettings` two fields, header buttons static).
- `t2_launch_tab.py`: 9 cases PASS, each in its own subprocess, all in parallel (headers, occupied marking,
  tick/selection, project rows, exact start command for all 10 projects, workflow success order
  switch -> settle -> open, failure stages, click handling, `space_switch` units).
- `dev/model_selector/verify_four_tab_ring.py` (renamed from the three-tab guard): forward and reverse ring PASS.
- Byte-identity scripts in `dev/menubar/` gave identical hashes before and after M1.
- Mutation check: removing the `PATH=` part from the start command made two cases fail. Removing the
  `not s.is_worker` filter did NOT fail any case (no test gives a worker a desktop number), so that filter is untested.
- Nothing has run in the real bundle. Real switching and window opening were only exercised by runs 1 and 2 (dev process).

## Real bundle: what the user has to do (not yet done as of 2026-09-24)

- The installed `~/Applications/monitor-cc-menubar.app` is signed with the stable identity
  `monitor-cc Code Signing` (designated requirement `identifier "com.brunowinter.monitor-cc-menubar" and
  certificate leaf = H"1b55359..."`), NOT ad-hoc. The task text assumed ad-hoc; grants therefore survive
  rebuilds (see the `menubar_build` area for the identity and its verification).
- Build only from the MAIN checkout after merging: `./venv/bin/python setup_py2app.py py2app` (build, install, sign,
  write plist, bootstrap). The plist's `PROJECT_ROOT` is the build directory and becomes `MONITOR_CC_ROOT`;
  built from a worktree, every Launch command would `cd` into the worktree. Build output must say `signed-with: monitor-cc Code Signing`.
- PostEvent must be granted to the bundle. UNVERIFIED for the bundle: the pane (expected Privacy & Security ->
  Accessibility), whether the prompt from `CGRequestPostEventAccess` appears when called from the launch thread, and
  that ad-hoc dev runs behave the same. If no prompt appears the user adds the app manually in that pane.
  Check `menubar.log` for `[launch]` lines.
- Ghostty Automation and Screen Recording come from the existing mon button and desktop detection.

## Mistakes and lessons

- Ran `dev/model_selector/verify_four_tab_ring.py` once without announcing it. Its DOCS entry says it builds real NSPanel
  objects and must not be run. No side effect was noticed, but the screen was not watched. Read the DOCS caveat of a
  dev script before running it.
- A chained shell command ended in a grep error; the earlier Python edit heredoc in the same call had printed nothing and
  had not applied. Check that edits landed (grep for the old strings) instead of trusting a silent heredoc.
- macOS `sed -i` needs an empty suffix argument (`sed -i ''`); the GNU form fails and applies nothing.
- The Run 2 close bug (wrong AppleScript command plus a CG-based closed check) cost one aborted run; check
  the app's sdef (`/Applications/Ghostty.app/Contents/Resources/Ghostty.sdef`) before writing AppleScript.

## Open items for a successor

- Real-bundle verification (PostEvent grant, one live launch, `[launch]` log lines).
- Follow-up Run 3 suggestion (only with the user's go): 20 cycles without `activate`, record all new CG window ids per cycle to explain the 2 unconfirmed windows.
- The Launch panel factory is a third near-copy of the RAG and Models panel factories; not consolidated.
- Multi-display is unsupported: `space_switch` raises when two displays map to the same desktop number.
- Layout (desktop row widths, project label width) was only checked headless.
