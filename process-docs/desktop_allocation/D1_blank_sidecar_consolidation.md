# D1 — blank Desktop-Targeting Robustness via Menubar Sidecar (2026-05-28)

**Status:** Decision made, NOT implemented. Sequenced AFTER the menubar refactor. Cross-repo: Monitor_CC (menubar publishes) + Meta/blank (helper consumes).

## Context

Stage 3 (worker spawn on the caller's desktop) + Stage 4 (file-open via `show`) are implemented in `Meta/blank` commit `cfd0d14`, but best-effort. User goal: both placements should **always** land, not just best-effort.

`Meta/blank/src/desktop/desktop_targeting.py` is the naive predecessor of the menubar detection. It breaks reproducibly — the user pointed at the `n_cand=0` effect, where AppleScript returns the window name but no matching CGWindow is found after a worker spawn.

## Root Cause (verified by a full read of both files, 2026-05-28)

`desktop_targeting.py` is missing three robustness mechanisms that `src/menubar/desktop_detection.py` (verified, 100% detection rate) has:

| Mechanism | Menubar `desktop_detection.py` | blank `desktop_targeting.py` |
|---|---|---|
| Title source | `CGSCopyWindowProperty` key `kCGSWindowTitle` (SkyLight, TCC-bypass) | raw `kCGWindowName` (empty under TCC restriction) |
| Spinner normalize | `_normalize_window_title` strips the CC spinner glyph from both sides before matching | none → mismatch as soon as the spinner is asymmetric |
| Resolver | 3-stage: name-unique → space-elimination → OSC-2 injection (`_resolve_cgwindow_id`) | stage 1 only; `len(wids) != 1 → None` |

The spinner mismatch alone produces `n_cand=0` independent of the spawn. The missing fallback turns every ambiguity or cache-churn case into a total failure.

## Paths Considered

**Path 1 — port the 3 mechanisms into blank.** Purely blank-side, immediately feasible, doesn't collide with the refactor. For a single caller, OSC-2 injection into the caller's own tty is especially strong (marks the window directly instead of guessing by name). Downside: a third copy of the same CGS logic (probe / menubar / blank) → drift hazard.

**Path 2 — menubar publishes a verified result as a sidecar ← CHOSEN.** The menubar already detects robustly every 10s and knows the space ID per main. It writes `cwd → space_id` (last-known-good) to a JSON; the blank helper only reads, no longer runs its own fragile detection.

## Chosen: Path 2

**Reasoning:**
1. No third copy of the CGS detection — blank consumes the already-verified pipeline directly.
2. More robust against the spawn moment: last-known-good bridges the transient `n_cand=0` dip (the main's space ID is stable, the menubar knew it from earlier cycles).
3. blank already depends on the menubar (reads `ghostty_cwd_uuid.json`) — Path 2 deepens the existing coupling instead of adding a new one.

Trade-off accepted: needs a menubar source change → hence sequenced after the refactor (menubar was mid-rework at the time, to avoid a collision).

## Implementation Sketch (for pickup after the refactor)

**Menubar side (Monitor_CC, worker task — current project):**
- `desktop_detection.py` / `discover.py`: persist the verified result as `cwd → {space_id, desktop_no}` in an APP_SUPPORT sidecar (e.g. `cwd_desktop.json` next to `ghostty_cwd_uuid.json`).
- **Last-known-good:** a transient None must NOT overwrite a good space_id — keep the old value until a new valid one arrives.
- space_id is the stable identifier for the move (`CGSMoveWindowsToManagedSpace` takes space_id, not desktop_no) — must be exported too; at the time the menubar only exposed it in-memory.

**blank side (Meta/blank, Opus direct — cross-repo):**
- `desktop_targeting.py`: keep caller identification (parent-walk → claude → lsof → cwd), then look up cwd in the menubar sidecar → space_id. The fragile name-match chain (`_ghostty_uuid_to_window_name` → `_windows_by_name_for_pid` → `len(wids)!=1`) goes away.
- Window-move + new-window-polling primitives stay (not the fragile part).
- **Detect-before-disturb:** determine the caller's space_id BEFORE the triggering open/spawn (landscape stable), then only poll for and move the new window. Applies to both paths; at the time, detection ran after the open.

**Logging (blank side, its own sink — NOT Monitor logging):**
- Separate blank log (own file, not `menubar.log`).
- For worker spawn (`tmux_spawn.sh:open_tmux_viewer`) AND file open (`bin/show`): caller_pid, resolved claude cwd, space_id from the sidecar (or miss reason), window-poll result, move result.
- Replaces the then-current `>/dev/null 2>&1` silence — all 6 stages need to become diagnosable.

## Open Questions

- Worker-`show`: when a worker (not a main) calls `show`, caller identification finds the worker's Claude (cwd=worktree, not in the sidecar). Should worker-`show` target the worker's own desktop or the parent main's? — not yet decided.
- Multi-new-window: `wait_for_new_windows_and_move` moves ALL new windows within the poll window; with `app_name=""` (cross-app poll) there's a risk an unrelated window gets pulled along. Disambiguation open.
- Sidecar write frequency vs. staleness: the menubar's 10s detection cache vs. spawn timing.

## Sources

- `src/menubar/desktop_detection.py` (verified 3-stage detection — the template)
- `Meta/blank/src/desktop/desktop_targeting.py` (naive predecessor — the target)
- `Meta/blank/bin/show`, `Meta/blank/src/spawn/tmux_spawn.sh:open_tmux_viewer` (call paths)
