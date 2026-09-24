# Skill picker: per-session skill dropdown in the Sessions panel (2026-09-24)

Worker "spaceprobe", area `skill_picker`, macOS 26.6.2. Commits `275562aa` (feature) and `200b8cb0` (pyright-lsp handling).
Live verification by the user on 2026-09-24: the menu opens in the real panel and the text lands unsent in the right session's input field.

## What the user wanted

Every MAIN session row in the Sessions panel gets a `skill` button directly after the blue `mon` button; worker rows get nothing.
A click lists skills; choosing one types `Aktiviere den Skill <full name>.` into THAT session's Claude Code input field, not submitted (no Enter).
The list shows the short name, the typed text uses the full invocation name. The Sessions panel stays open after a choice, nothing else happens.

## Which skills a row shows (order: project, personal, plugin, separators between groups)

- Plugin skills: every plugin with `true` in `~/.claude/settings.json` `enabledPlugins`. Install path from `~/.claude/plugins/installed_plugins.json`
  (the `user`-scope entry is preferred, else the first entry). Skill directories come ONLY from the `skills` array of `<installPath>/.claude-plugin/plugin.json`
  (all four skill-bearing plugins have one; a union with the default `skills/*/` folder was rejected as an unobserved condition).
  Full name = `<manifest name>:<frontmatter name, or directory name if empty/missing>` (manifest name, not the `name@marketplace` key prefix).
  Observed: iterative-dev (doccheck, duallog, refactor), websearch (web-research, capture-and-index, pdf), gh-cli (gh-cli-search), reddit-cli (reddit-cli-search).
- Project skills: `<row cwd>/.claude/skills/<dir>/SKILL.md`. Full name = directory name; the frontmatter `name` is only a label (Claude Code docs rule).
  Observed: only `/Users/brunowinter2000/Documents/general` has two (`penny`, `wise2627-tracker`); a session in another project sees none of them.
- Personal skills: `~/.claude/skills/<dir>/SKILL.md`, same naming. Observed: the directory only holds an empty `synced` folder (no SKILL.md), so nothing is listed.
- Not covered on purpose: plugins installed with `local` scope for another project (ralph-loop, not in the user `enabledPlugins`), project-level `enabledPlugins`.
- Discovery runs on every menu open (about ten small files), no cache.
- Frontmatter is parsed by hand (only the `name:` line, quotes stripped); the bundle has no YAML library.

Tripwires (each logs `[skill] FAILED plugin=<key> reason=<reason>` and skips only that plugin or entry): `not_installed`, `manifest_missing`,
`manifest_name_missing`, `no_skills_array`, `skill_file_missing entry=<path>`; unreadable `settings.json` or `installed_plugins.json` log
`settings_unreadable` / `installed_plugins_unreadable` and yield no plugin skills.
Observed exception: `pyright-lsp` (enabled) has neither `.claude-plugin/plugin.json` nor a `skills/` directory. That is a plugin without skills and is skipped
WITHOUT a log line (the first version logged `manifest_missing` on every click; the user changed the rule after observing it). A missing manifest WITH a `skills/` directory stays a FAILED tripwire.

## Insertion mechanism

Ghostty AppleScript, established earlier in the `message_queue` area (native delivery pivot), works from the launchd menubar with only the existing Automation permission for Ghostty:

    tell application "Ghostty"
      set t to first terminal whose id is "<terminal id>"
      input text "Aktiviere den Skill <full name>." to t
    end tell

No `send key`, no `activate`, no `focus`, no System Events. The terminal id is `ghostty.get_ghostty_terminal_id(cwd)` (tty of the row's Claude process mapped to a terminal id;
the map refreshes about every 10 s). Quoting reuses `system._applescript_quote`. osascript timeout 5 s.
Failure policy, no fallback: no terminal id -> `[skill] FAILED cwd=... skill=... stage=terminal_id no_terminal_id`; osascript rc != 0 or timeout -> `stage=osascript ...`; nothing else happens.
Success logs `[skill] OK ... terminal=<id> osascript_ms=<n>`. The insertion runs on the main thread (same as the existing focus calls).

## UI design and why

- NSMenu popped from an ordinary borderless `_CursorlessButton` (`popUpMenuPositioningItem:atLocation:inView:`, bottom-left of the button), not an NSPopUpButton:
  the click handler gets the same row tag as every other row button and does not depend on NSPopUpButton's mouse tracking inside the panel.
  The panel is non-activating and the app is an LSUIElement; an earlier NSTextField failed there because the panel never became key. A popup menu runs its own
  tracking loop and does not need the panel to be key. This was an expectation before the live check and turned out to work.
- Menu items carry the short name as title and the full name as `representedObject`; the controller remembers which row's cwd opened the menu (`_menu_cwd`).
  Empty result: one disabled item "no skills". A missing row cwd or missing choice logs `[skill] FAILED stage=menu|choice`.
- Grid: 7th column (46 px), `_GRID_COL6_W` in `panel_grid.py`. Every `addRowWithViews_` list and the separator-row merge range in `panel_manager.py` has to carry 7 entries.
  Layout risk seen in planning: about 252 px of fixed columns leave about 170 px for the name column at the default 422 px panel width. No clipping was reported in the live check.
- Fallback design if the menu ever fails (not built): a small in-app list of ordinary buttons, as the Launch tab does.

## Tests

`dev/skill_picker/t1_skill_picker.py`: twelve parallel subprocess cases, each with an isolated `HOME` (see the `session_launcher` process-docs on why): discovery of plugin skills
(enabled/disabled, user vs local scope entries), the tripwires, name rules (manifest name vs key, frontmatter vs directory), project/personal/other-project filtering and group order,
exact inserted text for all ten real-shaped names, the AppleScript (exact text, no `send key`/`activate`/`focus`/`System Events`, quoting, `osacompile` compile-only check),
insert paths (no terminal id, rc=1, timeout, success) with `subprocess.run` mocked, menu construction with real AppKit (never popped up), the 7-column grid with the skill
button only on main rows and matching tags, the controller (popup called with the button and its bottom-left point), the manifest-missing variants, and log isolation.
All PASS on 2026-09-24. Mutation checks made the tests fail: project skills named by frontmatter, `send key` added to the script, a skill button added to worker rows.
`dev/skill_picker/p1_real_discovery.py` is a read-only probe against the real `~/.claude` (HOME isolated so log lines go to a temp file). Result on 2026-09-24:
`general` -> penny, wise2627-tracker plus the 8 plugin skills; `monitor-cc` -> the 8 plugin skills only; after the pyright change no log lines.
`dev/menubar/panel_manager_byte_identity.py` hash changed once because of the new grid column (expected, not a regression).
Nothing in the tests types into a terminal; the real typing was only exercised by the user's live check.

## Open items / unobserved

- Text lands wherever the Claude Code input has focus; a permission dialog or other modal state is not detected.
- A session whose tty-to-terminal map entry is not built yet (up to about 10 s after start) gets `no_terminal_id`.
- Plugins whose skills are declared differently (no manifest `skills` array, default folder only) log `no_skills_array` and show nothing; no such plugin has been observed.
- Skills from `local`-scope plugin installs and from project-level `enabledPlugins` are not listed.
