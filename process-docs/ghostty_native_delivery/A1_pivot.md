# Ghostty-Native AppleScript Delivery — Replacing System Events Keystroke

## Problem

Delivery code (queue.py:`_deliver_via_uuid`, hook_writer.py:`_deliver_message`) used:

```
tell application "Ghostty"
  activate
  focus terminal id "UUID"
end tell
delay 0.1
tell application "System Events"
  keystroke "<text>"
  key code 36
end tell
```

osascript returned `rc=0` with empty stderr (script ran successfully), but no keystroke arrived at the target terminal. Reproducible from production menubar. Hours of debugging:

| Hypothesis | Verdict |
|---|---|
| Accessibility permission missing | False — user granted Python 3, manual `osascript -e` from Bash worked |
| Secure Input enabled | False — `IsSecureEventInputEnabled()` returned False |
| Stale Ghostty UUID | False — UUID present in `tell application "Ghostty" to get id of every terminal` |
| `activate` missing in script | False — adding `activate` did not fix delivery, only made Ghostty come to foreground briefly |
| Delay too short | False — 0.5s delay had identical effect (none) |
| launchd-spawned process vs login-shell process | Closer — production menubar (launchd) failed, manual menubar from Bash also failed when interactive focus was elsewhere |

The actual constraint: macOS routes `System Events keystroke` to whichever app is the current foreground app. When osascript runs from a non-foreground process tree (background Python invoked by launchd, OR a Python whose triggering window is not in front when the click fires), `activate Ghostty` requests app-switching but the keystroke is dispatched IMMEDIATELY after — possibly before the switch is fully committed by WindowServer. The script returns 0 because the AppleScript commands all succeeded; the keystroke just goes nowhere visible.

## Solution

Ghostty has its own AppleScript dictionary (`/Applications/Ghostty.app/Contents/Resources/Ghostty.sdef`) that exposes per-terminal input commands, bypassing System Events entirely:

```
<command name="input text" code="GhstInTx" description="Input text to a terminal as if it was pasted.">
  <direct-parameter type="text"/>
  <parameter name="to" type="terminal"/>
</command>

<command name="send key" code="GhstSKey" description="Send a keyboard event to a terminal.">
  <direct-parameter type="text"/>  <!-- "enter", "a", "space", ... -->
  <parameter name="modifiers" type="text" optional="yes"/>
  <parameter name="to" type="terminal"/>
</command>
```

Plus property `working directory` per terminal — usable as a fallback selector when no UUID is known.

New delivery scripts:

```
# UUID path
tell application "Ghostty"
  set t to first terminal whose id is "<UUID>"
  input text "<message>" to t
  send key "enter" to t
end tell

# cwd-match fallback
tell application "Ghostty"
  set targets to (every terminal whose working directory is "<cwd>")
  if (count of targets) > 0 then
    set t to item 1 of targets
    input text "<message>" to t
    send key "enter" to t
    return true
  end if
  return false
end tell
```

## Verified behavior

- osascript returns rc=0
- Text arrives at the target terminal AND Enter is pressed
- Ghostty does NOT come to foreground (no `activate` in the script) → user's current focus stays intact
- Works identically from launchd-spawned production menubar AND from manually launched menubar — TCC scope problem dissolves entirely because the delivery is direct app-scripting via Apple Events, not synthetic keyboard events

## Permission requirement

Single AppleScript permission: "Monitor_CC menubar → Ghostty" (Apple Events automation). NOT "System Events" Accessibility. The user grants once on first delivery attempt; persisted by macOS in TCC.

## Sources

- `/Applications/Ghostty.app/Contents/Resources/Ghostty.sdef`
- Live osascript probes from Python subprocess (manual Bash invocation + production menubar with TS-Logging)
- Cross-reference: queue.py:`_deliver_via_uuid`, `_deliver_via_cwd`; hook_writer.py:`_deliver_message`
