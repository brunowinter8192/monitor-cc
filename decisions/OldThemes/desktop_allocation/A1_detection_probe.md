# Desktop Detection Probe — Phase A/B Log (2026-05-27)

## Phase A — Strategy Selection

### Problem Scope

`cwd → UUID` mapping already solved in `src/menubar/ghostty.py`. The gap: UUID is Ghostty-internal, `CGSCopySpacesForWindows` needs macOS `CGWindowID` (kCGWindowNumber). No API directly maps one to the other.

### Plan-in-Prompt vs Discovered Reality

The pre-approved plan specified Primary = AppleScript `bounds of (window 1 of (terminal id "UUID"))` → bounds-match with CGWindowList. This turned out not to work:

```
osascript: "bounds of terminal id "UUID"" kann nicht gelesen werden. (-1728)
osascript: "bounds of window" kann nicht gelesen werden. (-1728)
osascript: "window of terminal id "UUID"" kann nicht gelesen werden. (-1728)
```

Ghostty's AppleScript dictionary does NOT expose `bounds` for windows or terminals, and does NOT provide `window of terminal`. The bounds-match primary strategy is unavailable.

### Alternative Discovered In Phase A

AppleScript DOES expose: `id of terminal of tab of window`. This gives UUID per tab:

```applescript
tell application "Ghostty"
  repeat with w in every window
    repeat with t in every tab of w
      set termid to id of terminal of t  -- returns UUID
    end repeat
  end repeat
end tell
```

Output sample:
```
tab-group-600002a28510|||tab-10d80e080|||A54C3B1A-D5BE-41F5-B0B7-7BA6E592472C
tab-group-600002af85a0|||tab-14be38f70|||0C80487C-42B2-4751-B071-C978E275349A
tab-group-600002aa1c20|||tab-16f8c98b0|||6A8E0946-897F-4123-AE8D-80C966B35371
```

This gives `UUID → ghostty_window_id → window_name` in one call. `kCGWindowName` in CGWindowList matches the Ghostty window's `name` (= focused tab's OSC-2 title). For sessions where the CC tab is focused and its title is unique among Ghostty windows, direct name matching finds the CGWindowID.

### Additional Discovery: working directory Bug

`working directory of terminal` in Ghostty AppleScript returns the Monitor_CC path for ALL terminals (all 14), regardless of actual session cwd. This is a Ghostty AppleScript bug — the property appears to reflect the app's launch directory, not the terminal's current working directory. **Don't use this property for cwd-based mapping.**

### API Key Names (confirmed)

| API | Key queried | Status |
|---|---|---|
| `CGWindowListCopyWindowInfo` | option=0 (not 1!) | All spaces. `1` = OnScreenOnly |
| `CGSCopyManagedDisplaySpaces` dict | `Display Identifier` (with space) | ✅ populated |
| `CGSCopyManagedDisplaySpaces` dict | `Spaces` (capital S) | ✅ populated |
| Space dict | `ManagedSpaceID` | ✅ populated |
| `CGSCopySpacesForWindows` mask | `0x7` | ✅ returns [space_id] |
| `kCGWindowBounds` sub-dict | `X`, `Y`, `Width`, `Height` | ✅ (unused — all windows same bounds on single display) |

### Revised Primary Strategy (chosen)

1. **AppleScript tab traversal** → `UUID → ghostty_window_id → window_name`
2. **CGWindowList (option=0)** filtered on ghostty_pid → `{kCGWindowName: [WID, ...]}`
3. **Name-match**: if `window_name` appears in exactly one WID → match found
4. **Space-elimination**: multiple candidates → query `CGSCopySpacesForWindows` per candidate, drop those on spaces already claimed by other mains → if one remains → match found
5. **OSC-2 injection**: remaining ambiguity → inject marker to tty, 150ms, re-match kCGWindowName → finds WID when CC tab is the focused tab in the window

The original OSC-2 fallback from the plan remains, but is now strategy 3 (after the primary and space-elimination, which handle most cases).

---

## Phase B — Probe Implementation & Results

### Implementation Notes

Built `dev/desktop_detection/01_probe.py` (389 LOC). Key ctypes pattern:

- `ctypes.CFUNCTYPE(...)` objects MUST be held at module level — GC'ing them corrupts the IMP pointer table (causes SIGSEGV when called after GC).
- Correct pattern: `ctypes.cast(_IMP, _FT_TYPE)(obj, sel, ...)` where `_FT_TYPE` is a module-level CFUNCTYPE ref.
- `objc_msgSend` is the IMP; cast to the appropriate CFUNCTYPE for each call signature.

### Probe Run Results (2026-05-27, run 1)

4 mains in ghostty_cwd_uuid.json (Reddit dropped between run 1 and run 2 — TTY-map stale):

**Run 1 (4 mains):**
```
session_name  cwd                                    tty       uuid[:8]  cgwindow_id  space_id  display   desktop_no
searxng       .../Meta/ClaudeCode/MCP/searxng        ttys035   9A6B3B0B  3702         511       37D8832A  4
Monitor_CC    .../Monitor_CC                         ttys013   6A8E0946  5582         780       37D8832A  5 (*)
Trading       .../Trading                            ttys001   0C80487C  364          4         37D8832A  2
Reddit        .../Meta/ClaudeCode/MCP/Reddit         ttys012   A54C3B1A  580          53        37D8832A  3

Active Space: 53 (desktop 3)
Space map: {2→D1, 4→D2, 53→D3, 511→D4, 780→D5}
Strategy breakdown: name-unique:3  osc2-injection:1
```

(*) Space ordering changed between probes — Mission Control re-indexed. This is expected: `CGSCopyManagedDisplaySpaces` array-index = current user-visible order, which changes when desktops are reordered.

**Run 2 (3 mains, Reddit gone from JSON):**
```
session_name  tty       cgwindow_id  space_id  desktop_no
searxng       ttys035   3702         511       4
Monitor_CC    ttys013   5582         780       3
Trading       ttys001   364          4         2

Active Space: 4 (desktop 2)
Space map: {2→D1, 4→D2, 780→D3, 511→D4, 53→D5}
Strategy breakdown: name-unique:3
```

Trading matched via `osc2-injection` in run 1 (CC tab was NOT focused in its Ghostty window, name=`/Users/.../Monitor_CC` was ambiguous among 10+ windows). In run 2, Trading matched via `name-unique` (user switched to Trading desktop between runs, making the CC tab the focused tab, giving it a unique title).

### Negativ-Befunde

1. **AppleScript `bounds`**: Not exposed — `-1728` on `bounds of terminal id "UUID"`, `bounds of window id "..."`, `bounds of window 1`. Original plan's primary strategy dead.
2. **AppleScript `working directory`**: Returns Monitor_CC for ALL terminals — Ghostty AppleScript bug. Do NOT use for cwd correlation.
3. **`kCGWindowListOptionAll=1`**: Maps to `kCGWindowListOptionOnScreenOnly` (only 26 of 279 windows visible). Option=0 is the correct "all windows" flag.
4. **Bounds uniqueness**: All Ghostty windows have identical bounds `(0,38,1728,998)` on this single-display fullscreen setup. Bounds-based matching would not disambiguate.
5. **`tab-group-XXXXXX` → CGWindowNumber**: No direct mapping. The hex in Ghostty's window id is a Swift object pointer, not a CGWindowNumber.

### Dict-Keys Populated

| Key | Dict | Populated |
|---|---|---|
| `Display Identifier` | `CGSCopyManagedDisplaySpaces` display dict | ✅ `37D8832A-2D66-02CA-B9F7-8F30A301B230` |
| `DisplayIdentifier` | same | ❌ |
| `Spaces` | same | ✅ CFArray of space dicts |
| `spaces` | same | ❌ |
| `ManagedSpaceID` | space dict | ✅ int (e.g. 53, 511, 780) |
| `id` | space dict | ❌ |
| `ID` | space dict | ❌ |
| `kCGWindowOwnerPID` | CGWindow dict | ✅ |
| `kCGWindowNumber` | CGWindow dict | ✅ |
| `kCGWindowName` | CGWindow dict | ✅ (None for some windows) |
| `kCGWindowLayer` | CGWindow dict | ✅ (0 for regular windows, 103 for toolbar) |
| `kCGWindowBounds` | CGWindow dict | ✅ sub-dict with X/Y/Width/Height |

### Detection Rate

| Run | Mains in JSON | With CGWindowID | Rate |
|---|---|---|---|
| Run 1 | 4 | 4 | 100% |
| Run 2 | 3 | 3 | 100% |

### Mapping Strategy per Session (Run 1)

| Session | Strategy | Reason |
|---|---|---|
| searxng | name-unique | `kCGWindowName = '✳ News Aggregation Layer...'` — unique |
| Monitor_CC | name-unique | `kCGWindowName = '✳ Zugriffe auf Menu Bar...'` — unique |
| Reddit | name-unique | `kCGWindowName = '✳ Conversation Continuation'` — unique |
| Trading | osc2-injection | `kCGWindowName = '/Users/.../Monitor_CC'` — 12+ candidates with same name; CC tab was background tab |

### Status

Etappe 1 complete. Pipeline `cwd → UUID → CGWindowID → SpaceID → desktop_no` proven, 100% detection rate on active Mains. Etappe 2 (Menubar display `[N]`) can proceed.
