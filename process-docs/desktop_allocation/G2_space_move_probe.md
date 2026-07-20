# G2 — Space-Move Probe: SLSBridgedMoveWindowsToManagedSpaceOperation on macOS 26.5

**Status:** Probe run. bridged-op ObjC chain executes cleanly (no crash, no nil) but window does NOT move. Root cause: unknown — possible entitlement gate or regression between 26.4.1 (validated) and 26.5.

Continues the prior space-move research, which established the technique and the macOS version table.

## What we built

`dev/desktop_detection/04_space_move_probe.py` — self-contained ctypes probe:
- Picks lowest-WID named layer-0 Ghostty window that is NOT on the active space
- Calls `SLSBridgedMoveWindowsToManagedSpaceOperation initWithWindows:spaceID:` + `performWithWMBridgeDelegate`
- Verifies via `CGWindowListCopyWindowInfo(kCGWindowListOptionOnScreenOnly=1, 0)` on-screen-list delta
- Takes before / after / restore screenshots to `dev/desktop_detection/04_reports/`
- Restores via another bridged-op call back to original space
- Precondition guards: ≥ 2 spaces, ≥ 1 named Ghostty window on non-active space, orig_space known

Two CFUNCTYPE additions beyond `01_probe.py`:
- `_FT_0vv = CFUNCTYPE(None, c_void_p, c_void_p)` — `performWithWMBridgeDelegate` (self + sel, void return)
- `_FT_vvvu64 = CFUNCTYPE(c_void_p, c_void_p, c_void_p, c_void_p, c_uint64)` — `initWithWindows:spaceID:` (self, sel, NSArray*, uint64) → id

NSArray shape: `_make_uint_array` from `01_probe.py` (NSMutableArray of NSNumber(numberWithUnsignedInt:)) — confirmed correct for CGWindowID = uint32_t.

## Probe run results

**Run 1** (active=5, target=369, orig=4): FAIL. `original_space: None` — CGSCopySpacesForWindows returned [] for WID 369.

Investigation revealed WID 145 (initial min pick) is a Ghostty **tab-bar strip**: `bounds=(0,0) 1728x33`, `name=None`. Fix: added `kCGWindowName is not None` filter to `_ghostty_wids_all()`.

**Run 2** (active=5, target=369, orig=4): FAIL. ObjC chain clean. WID 369 not in on-screen list after call. On-screen delta added=[1629, 1630] (transient UI elements, unrelated).

**Run 3 (final)** (active=4, target=1433, orig=5): FAIL.
```
[BEFORE] wid 1433 in on-screen list : False  (expected: False)
[AFTER]  wid 1433 in on-screen list : False  (expected: True)
RESULT: FAIL -- absent-before=True present-after=False (expected both True)
[RESTORE] window returned to original space  : True
```
On-screen delta added=[1740, 1741] — transient elements, WID 1433 absent.

Window restored correctly (on-screen list confirms absence from active space after restore call, consistent with window never having moved).

## Class introspection findings (macOS 26.5)

```
SLSBridgedMoveWindowsToManagedSpaceOperation instance methods (7):
  .cxx_destruct  encodeWithCoder:  initWithCoder:
  windows  spaceID  initWithWindows:spaceID:  invokeFallback

SLSAsynchronousBridgedWindowManagementOperation (parent, 4 methods):
  encodeWithCoder:  _init  initWithCoder:
  invokeFallback  performWithWMBridgeDelegate
```

`performWithWMBridgeDelegate` is NOT defined in the child class — it is **inherited** from the parent `SLSAsynchronousBridgedWindowManagementOperation`. ObjC dispatch does walk the hierarchy, so the call reaches the parent's IMP. The call returns without crash.

The child **overrides** `invokeFallback`. The parent's `performWithWMBridgeDelegate` presumably tries the WM bridge first, then calls `invokeFallback` as a fallback (name suggests this pattern). The child's `invokeFallback` override is the actual move implementation.

Both selectors were tested directly during diagnostic (not part of the approved probe):
- `performWithWMBridgeDelegate`: silent no-op on WID 369, space stays [4]
- `invokeFallback` (direct call on the child's override): silent no-op, space stays [4]

## Hypotheses on why the op fails

| Hypothesis | Status | Evidence |
|---|---|---|
| entitlement gate on 26.5 — Python/ctypes lacks com.apple.private.skylight or similar | Active | DockDoor runs inside Dock.app via SIP-off SA → has correct entitlements; Python has none |
| regression between 26.4.1 and 26.5 — API behavior changed | Active | G1 validates 26.4.1 (ejbills DockDoor #855 c7, yabai #2788); probe runs 26.5; no test on 26.4.1 |
| wrong delegate — performWithWMBridgeDelegate requires a pre-set delegate object | Active (weaker) | DockDoor calls it with no delegate setup; but maybe 26.5 added that requirement |
| `_init` missing — parent's `_init` must be called before `performWithWMBridgeDelegate` | Active (weaker) | `initWithWindows:spaceID:` may not call `[super _init]`; parent has separate `_init` IMP |
| ObjC exception swallowed silently by ctypes call | Active | Python ctypes doesn't install an NSException handler; exceptions terminate silently |

## What to verify next

1. **Test on 26.4.1** — the only way to distinguish regression vs entitlement gate. If it works on 26.4.1 from Python/ctypes, the hypothesis is entitlement-gated on 26.5 only. If it also fails on 26.4.1, the validation in G1 was from Dock.app context (entitlement gate always present).

2. **Entitlement probe** — examine DockDoor's entitlements (or the scripting-addition binary that injects into Dock) to see what private SkyLight entitlements it carries. Can be done with `codesign -d --entitlements :- <binary>`.

3. **Add `[super _init]` call** — explicitly call `_init` on the operation object before `initWithWindows:spaceID:` to see if that changes behavior.

4. **Scripting Addition route** — if the API truly requires Dock.app context, the only SIP-free path is a scripting addition that injects into Dock and calls the op from there (yabai's approach). That is SIP-off.

## Evidence artifacts

- `dev/desktop_detection/04_reports/04_before_move_20260531_211924.png`
- `dev/desktop_detection/04_reports/04_after_move_20260531_211924.png`
- `dev/desktop_detection/04_reports/04_after_restore_20260531_211924.png`
- `dev/desktop_detection/04_reports/04_onscreen_dump_20260531_211924.txt`
