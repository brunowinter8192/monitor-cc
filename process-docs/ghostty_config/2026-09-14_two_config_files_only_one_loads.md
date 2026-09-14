# 2026-09-14 — Ghostty reads one config file, and this machine has two

New area. Both existing Ghostty areas in this project (`process-docs/ghostty_foreground/`,
`process-docs/ghostty_scroll_lock/`) reason about settings without establishing which file those
settings have to live in. On this machine that turned out to be the deciding question.

## The finding

Two config files exist:

- `~/.config/ghostty/config` — 863 bytes, holds `scroll-to-bottom` and `bold-color`.
- `~/Library/Application Support/com.mitchellh.ghostty/config` — 2035 bytes, holds
  `scrollback-limit = 10000000`, its own `scroll-to-bottom`, and two keybinds
  (`cmd+n=new_window`, `cmd+t=new_tab`).

Only the first is loaded. `ghostty +show-config` on Ghostty 1.3.1 returns exactly six lines:

```
scroll-to-bottom = no-keystroke,no-output
command = /bin/zsh
working-directory = inherit
click-repeat-interval = 500
bold-color = #8fbc8f
auto-update-channel = stable
```

No `scrollback-limit`, no `keybind` entry at all. The Application Support file's contents never
reach the running terminal. The ten-million-line scrollback and both keybinds were inert.

## Why this matters beyond the one setting

Anything written into the Application Support file silently does nothing while the XDG file exists.
There is no warning, no error, and the file itself is the one Ghostty's own template text says it
created for you — so it reads like the canonical location. `ghostty +show-config` is the only
reliable check, because it reports the merged, actually-loaded configuration rather than any file's
contents.

## The bold-color question this came from

Bold text renders in `#8FBC8F` (DarkSeaGreen), set deliberately so markdown bold anchors stand out.
The user found the contrast too high and asked for the darker green. That is a single-value edit in
`~/.config/ghostty/config`, applied with the reload-config binding (Command+Shift+comma on macOS) —
color settings take effect on reload, no restart needed. Not done in this session; captured as an
issue instead.

One trap for whoever changes it: Ghostty's `minimum-contrast` option forcibly lightens a foreground
color that falls below the configured ratio against its background. It is not set on this machine,
so it cannot currently interfere, but a dark green that refuses to look dark is what that option
looks like when it is set.
