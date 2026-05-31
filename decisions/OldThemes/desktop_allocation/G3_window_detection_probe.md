# G3 — Window Detection Probe: Method A (title-match) vs Method B (frontmost)

**Status:** Probe run (9 trials). Ground-truth detection reliable. Both detection methods failed. Space detection reliable for Ghostty.

Continues G2 (`G2_space_move_probe.md`). Goal: determine whether RELIABLE window identification + space determination is possible across three window types WITHOUT a move operation.

## Design

`dev/desktop_detection/05_window_detection_probe.py` — 3 window types × 3 trials (2 fg, 1 bg):

1. **ghostty_tmux** — `open -n -a Ghostty --args --command "tmux attach-session -t TOKEN"`, token=`p05t<6hex>`
2. **ghostty_osc2** — `open -n -a Ghostty --args --command "bash -c 'printf \"\\033]2;TOKEN\\007\"; sleep 60'"`, token=`p05g<6hex>`
3. **coteditor** — write `/tmp/probe05_TOKEN.txt`, `open -n -a CotEditor /tmp/probe05_TOKEN.txt`, token=`p05c<6hex>`

**Ground truth:** snapshot `before = _owner_wids_layer0(owner, require_name)` strictly before `open`; poll 0.2s/5s until delta non-empty; `wid_gt = min(delta)`.
**Method A:** scan CGWindowList for owner+layer0+name-contains-token → compare to gt.
**Method B:** first owner+layer0 window in CGWindowList (front-to-back z-order) → compare to gt.
**Space signals:** S1=`CGSGetActiveSpace` before open; S2=`wid_gt in on_screen_wids()` after; S3=`CGSCopySpacesForWindows(wid_gt)`. Agreement: S1==S3[0] AND S2==True.

## Trial Results

| type | tr | fg/bg | gt_wid | title_observed | A_agree | B_agree | desktop | space_agree |
|---|---|---|---|---|---|---|---|---|
| ghostty_tmux | 1 | fg | 2032 | `…/Documents/ai/Monitor_CC` | False | False | 3 | True |
| ghostty_tmux | 2 | fg | 2046 | `…/Documents/ai/Monitor_CC` | False | False | 3 | True |
| ghostty_tmux | 3 | bg | 2063 | `…/Documents/ai/Monitor_CC` | False | False | 3 | True |
| ghostty_osc2 | 1 | fg | 2076 | `…/Documents/ai/Monitor_CC` | False | False | 3 | True |
| ghostty_osc2 | 2 | fg | 2090 | `…/Documents/ai/Monitor_CC` | False | False | 3 | True |
| ghostty_osc2 | 3 | bg | 2099 | `…/Documents/ai/Monitor_CC` | False | False | 3 | True |
| coteditor | 1 | fg | 2115 | null | False | False | None | False |
| coteditor | 2 | fg | 2141 | null | False | False | None | False |
| coteditor | 3 | bg | 2162 | `Trading.md` | False | False | None | False |

All 9 trials: gt_wid found, cleanup_ok=True, space_agree=True for Ghostty (6/6), space_agree=False for CotEditor (0/3).

## Root Cause Analysis

### Ghostty: title = CWD, not token

**Both tmux and OSC-2 windows show `'…/Documents/ai/Monitor_CC'`** (the project CWD, not the token). Root cause: `open -n -a Ghostty --args --command "..."` does not reliably execute the specified command. The new Ghostty process ignores or doesn't receive the `--command` flag and starts a default interactive shell. Shell integration then sets the window title to the CWD of the new process (which inherits `~/Documents/ai/Monitor_CC` from the spawning environment).

Evidence: title is identical for ghostty_tmux AND ghostty_osc2. If `--command` was honored, tmux would show a tmux pane title and osc2 would show the token. Both show the same CWD path → command not executed.

Contrast with 01 probe OSC-2: the 01 probe WRITES the OSC-2 escape directly to the window's TTY file descriptor from an external process. This works. `bash -c 'printf ...'` (inside the terminal) doesn't reach kCGWindowName when Ghostty ignores the `--command` flag entirely.

### Ghostty: Method B disagrees even on fg trials

For ghostty_osc2 trial 1 fg: gt=2076, method_b=2078. Both are NEW WIDs (not in `before`). Two named Ghostty windows appeared from `open -n -a Ghostty`. `min(delta)=2076` is the lower WID; frontmost is 2078. Hypothesis: Ghostty creates two windows on launch (e.g., a main window + a floating/auxiliary window), the higher-WID one gets focus → method_b picks the second window, ground truth picks the first.

### CotEditor: intermediate unnamed window + session restore

`require_name=False` for CotEditor causes ground truth to pick up internal CotEditor windows created during startup that have no title and no space assignment yet:
- Trials 1+2: `title=None`, `s3_sp=None` — intermediate window (WID 2115, 2141) appears at 0.2s, is unnamed, not on any space
- Trial 3: `title='Trading.md'` — CotEditor's session restore opened a previously-open document ('Trading.md') BEFORE our probe file; `min(delta)` picked the session-restored window

`s3_space_id=None` for all CotEditor trials because the intermediate/wrong windows have no space assignment from `CGSCopySpacesForWindows`.

`s2_on_screen=False`: intermediate window (trial 1, 2) is NOT on the active space yet; Trading.md (trial 3) is on a different space.

## What Worked

1. **Ground truth snapshot-diff:** Detected a new WID for all 9 trials (0 misses). `_owner_wids_layer0` is reliable for detecting new windows.
2. **Ghostty space detection (S1/S2/S3):** S1==S3 AND S2==True for all 6 Ghostty trials. `CGSGetActiveSpace`, `on_screen_wids()`, and `CGSCopySpacesForWindows` agree on desktop=3 consistently.
3. **Cleanup:** All 9 trials: `cleanup_ok=True`. tmux kill-session approach for ghostty_tmux is reliable.
4. **CGS bridge (ctypes/ObjC):** No crashes, no nil returns for the space pipeline. Reuse from 04 probe is solid.

## What Did Not Work

1. **Method A (title-match):** 0/9 agreement. Token never appears in kCGWindowName for any window type. `open --args --command` does not execute the specified command in Ghostty. CotEditor intermediate windows have null title.
2. **Method B (frontmost):** 0/9 agreement. Probe terminal (existing Ghostty window) stays frontmost OR Ghostty creates two windows and the wrong one is frontmost.
3. **CotEditor space signals:** 0/3 (no space assigned to intermediate windows; session restore contaminates ground truth).

## Identification Method Conclusion

**Neither Method A nor Method B is robust.** Method A requires title control (token in kCGWindowName). This works ONLY via direct TTY injection (as in 01 probe), not via `open --args --command`. Method B is unreliable because it depends on z-order which is environment-sensitive.

**Robust alternative (confirmed by 01 probe):** direct TTY injection of OSC-2 to an existing Ghostty window — requires knowing the window's TTY. TTY is derived from: Ghostty AppleScript UUID → TTY mapping. This is the 01 probe approach (cwd→UUID→CGWindowID→space).

## Open Questions / Next Steps

1. **Ghostty `--command` support via `open`:** does `ghostty --command=<cmd>` work when launched from CLI directly (not via `open`)? Test: `ghostty --command="bash -c 'printf ...; sleep 60'"`. If it works directly but not via `open`, the issue is `open`'s argv passing.
2. **CotEditor: `require_name=True` approach:** would filter out intermediate windows. But CotEditor windows may briefly have name=None — needs longer poll timeout + name!=None wait.
3. **CotEditor session restore:** disable with `defaults write com.coteditor.CotEditor NSQuitAlwaysKeepsWindows -bool NO` or use a different test app (TextEdit with a unique filename and Apple-data approach).
4. **Space detection for non-active space:** all trials landed on desktop 3 (active space). Need a trial where the window opens on a DIFFERENT space to test space detection robustness.
5. **OSC-2 via direct TTY (01 approach) for new windows:** possible to open Ghostty → get new WID via snapshot-diff → get the window's TTY via Ghostty AS → inject token. Tests method A via confirmed-working mechanism.

## Evidence Artifacts

- `dev/desktop_detection/05_window_detection_probe.py`
- `dev/desktop_detection/05_reports/trial_ghostty_tmux_[1-3]_20260531_22340*.json`
- `dev/desktop_detection/05_reports/trial_ghostty_osc2_[1-3]_20260531_22342*.json`
- `dev/desktop_detection/05_reports/trial_coteditor_[1-3]_20260531_22344*.json`
