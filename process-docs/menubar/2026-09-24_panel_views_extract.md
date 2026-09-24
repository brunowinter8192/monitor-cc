# panel.py Extract Module: panel_views.py (2026-09-24)

## Why
`src/menubar/panel.py` measured 412 LOC (limit 400). Refactor-scan Phase 1 finding, behaviour-preserving.

## What moved
`_cursor_log`, `_PanelContentView`, `_CursorlessLabel`, `_CursorlessButton`, `_KeyablePanel`, plus the constants only they use (`EDGE`, `_TA_TRACKING_OPTS`) went verbatim into the new leaf module `src/menubar/panel_views.py` (148 LOC). `panel.py` is now 276 LOC and imports the four classes from it. `_TA_CURSOR_OPTS` stayed in `panel.py` because only `_make_nspanel` uses it.

`model_panel_ui.py` and `launch_panel_ui.py` import `_CursorlessButton` from `.panel_views` directly; `panel.py` does not re-export it. No other importer of `panel.py` used a moved name (`EDGE` had no outside user).

## Verification (nothing shown, no hotkey, no launchctl)
- AST: every top-level non-import node of the old `panel.py` (from git HEAD) compared by `ast.dump` as a multiset against `panel.py` + `panel_views.py`: identical.
- `dev/menubar/panel_manager_byte_identity.py` and `dev/menubar/model_controller_byte_identity.py` run before and after: output files byte-identical (`cmp`). Baselines: `HASH: b65e982a...`, `PERSISTENCE_HASH: 635d6108...`, `UI_HASH: 662318b9...`.
- Headless import of panel, panel_views, panel_manager, model_controller, rag_controller and both `*_panel_ui` modules succeeds; a load-name scan found no undefined module-level name in the two split files.
- Not exercised at runtime: the `_PanelContentView` event handlers and `_KeyablePanel.performKeyEquivalent_` (need a live window); covered by the AST comparison only.

## Note for successors
The frozen py2app bundle does not pick this up until it is rebuilt (`setup_py2app.py py2app`); the new module is found by modulegraph via the import in `panel.py`.
