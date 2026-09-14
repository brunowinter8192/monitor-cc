# 2026-09-14 — Both Ghostty config files load on macOS; the Application Support file was removed

Main session entry. Continues this area. Written after issue "Ghostty" was closed.

## The earlier claim in this area is wrong

An entry in this area dated the same day concluded that Ghostty loads only
`~/.config/ghostty/config` and that `~/Library/Application Support/com.mitchellh.ghostty/config`
"never reaches the running terminal". That conclusion was drawn from `ghostty +show-config`
returning six lines with none of the Application Support file's settings among them. It does not
hold. The file was loaded the whole time. That file is not edited here — the correction is recorded
in this entry only.

## What the source says (Ghostty v1.3.1, shallow clone of tag v1.3.1)

`src/config/Config.zig:loadDefaultFiles` loads XDG **and**, on macOS, Application Support:

- XDG first: legacy `~/.config/ghostty/config`, then `~/.config/ghostty/config.ghostty`.
- Then, on macOS only: `.../com.mitchellh.ghostty/config` (legacy) and `config.ghostty`.

Application Support loads **last**, so its values override the XDG file's. The 1.3.x rename
(`config` → `config.ghostty`) is why both a legacy and a new name are probed per location.

`src/cli/show_config.zig` explains the empty output: `Options.@"changes-only"` defaults to `true`,
so `+show-config` prints only options that differ from the default. Every setting in the
Application Support file equalled a default, so none of them could appear.

`writeConfigTemplate` is called only when neither XDG nor Application Support loaded anything. With
an XDG file present, deleting the Application Support file cannot trigger template recreation.

## Measured on this machine

`window-padding-x = 7` (default `2`) was appended to the Application Support file, then
`ghostty +show-config` printed `window-padding-x = 7`. The file was restored byte-exact (2035
bytes) afterwards. That is the direct proof that the file was being read.

The four entries in `+show-config` that come from no file at all — `command = /bin/zsh`,
`working-directory = inherit`, `click-repeat-interval = 500`, `auto-update-channel = stable` — are
resolved in `Config.finalize` at load time (shell detection, macOS click interval via
`internal_os.clickInterval()`, build release channel). There is no third config source.

## Evaluation of the four settings, and the removal

Measured against the installed binary, not assumed:

- `scrollback-limit = 10000000` — identical to the shipped default (`+show-config --default`). The
  unit is **bytes**, not lines, per the option's own docs; the earlier entry read it as ten million
  lines. Ten megabytes per terminal surface.
- `scroll-to-bottom = no-keystroke, no-output` — a verbatim duplicate of the XDG file's line.
- `keybind = cmd+n=new_window` / `keybind = cmd+t=new_tab` — identical to the active defaults,
  which `+list-keybinds` reports as `super+n=new_window` / `super+t=new_tab`.

So the file was loaded and changed nothing, while still being the last-loaded file and therefore
able to silently override the XDG file for anything written into it later. It was deleted.
`+show-config` afterwards returns the same six lines as before the deletion, and the directory
stayed empty across subsequent full config loads — no template was recreated.

## bold-color

`bold-color` went from `#8FBC8F` to `#6B8E6B` in `~/.config/ghostty/config`, same hue, lower
contrast. Applied via the `Reload Configuration` menu item (osascript click, the method this
project already used in `process-docs/ghostty_scroll_lock/`); `+show-config` then reported
`#6b8e6b`. No restart needed. `minimum-contrast` is still unset, so it cannot lighten the value
back up.

## For whoever touches Ghostty config next

`+show-config` alone cannot tell you whether a file was read — it hides everything that matches a
default. To answer "is this file loaded", write a value into it that differs from its default and
look for that value. `+show-config --default` gives you the default to compare against.
