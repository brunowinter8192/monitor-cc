# Remaining function/class threshold hits — five-file cleanup (2026-09)

Process record for a small, disparate batch of leftover threshold violations across the codebase
(`tmux_launcher.py`, `ram_audit/instrument.py`, `dual_log_cli/cli_args.py`,
`proxy/payload_helpers.py`, `menubar/app.py`+`hotkey_controller.py`) — a mop-up pass distinct from
the package-scoped split milestones already recorded in the `menubar` area, following the same
extraction-not-rewrite discipline.

## Findings and thresholds

Function < 50 LOC; a class with ten or more distinct `self.<attr>` (reads count too) splits by
concern; file ≤ 400 LOC. All five files' violations, findings, and extraction hints came
pre-specified in the task brief; the investigation here was verifying each hint's premise before
implementing, and designing the three new/extended byte-identity harnesses.

## Investigation before implementing

Read all five source files, `hotkey_controller.py`, `panel_lifecycle.py`, and the DOCS.md of every
touched package in full, plus `dev/proxy/DOCS.md` and `dev/ram_audit/DOCS.md` for their existing
pinning conventions.

**`tmux_launcher.py:launch_split_screen`'s 8 inline `*_cmd` strings vs. `_build_mode_commands`:**
the brief's finding asked to check whether `_build_mode_commands(script_path, project_arg)`
already builds the same strings. Read both constructions side by side — identical (same
`project_arg` ternary, same f-string template, same mode list) — so the inline duplication was
deleted and `launch_split_screen` now calls `_build_mode_commands(script_path, project_filter)`.
The one exception: `configure_tmux_session` still needs the bare `project_arg` string (not the
`mode_cmds` dict) for its own `restart_cmd` construction, so that one-line ternary stays computed
separately in `launch_split_screen` — a real, unavoidable 1-line duplication, not "the duplicate"
the finding was pointing at (the 8 cmd strings).

**`register_ram_dump` needed a 5th helper beyond the finding's named four:** extracting only
`_rss_line`/`_gc_top_lines`/`_tracemalloc_lines`/`_module_state_lines` (as the finding named)
shrank `_handle_ram_dump` enough, but `register_ram_dump`'s own outer span — which structurally
includes its nested `_handle_ram_dump` closure's full body — was still 51 LOC, one over. Added
`_resolve_dump_path(pane_name, ts)` (the `MONITOR_CC_ROOT`/dump-dir resolution block) as a 5th
helper, bringing `register_ram_dump` to 45 LOC. Lesson for future closure-heavy LOC splits: a
nested function's own line count is necessarily double-counted into its enclosing function's span,
so shrinking only the nested function may not be sufficient — check the OUTER span too before
declaring a split done.

**`app.py`'s `_global_hotkeys` deletion — plain tuple, not a relocated class:** the brief said
"delete `_global_hotkeys`/its class," which read as "delete both the attribute and the
`_GlobalHotkeys` class entirely," not "move the class to `hotkey_controller.py`." Went with a
plain `(cmd_l_cb, cmd_l_ref, cmd_k_cb, cmd_k_ref)` tuple on a new `HotkeyController.global_handles`
attribute instead — matches the flat-attribute pattern `HotkeyController` already uses for its
digit/arrow GC anchors (`_hotkey_digits_cb`, `_hotkey_arr_right_ref`, etc.), rather than
introducing a second storage convention for the same concern in the same class. Required moving
`self.hotkey = HotkeyController(self)` to right before the `register_cmd_l`/`register_cmd_k`
calls (previously constructed after) so there was somewhere to assign `global_handles` to
immediately after registration — verified `HotkeyController.__init__` has zero side effects
(pure attribute initialization) before treating this reorder as behavior-invisible.

## Byte-identity harness design notes

**`dev/tmux_launcher/argv_byte_identity.py` — a stateful fake tmux, not a static stub:**
`restart_panes`'s own code has a "refresh pane list so subsequent iterations see the new pane"
comment — meaning a `list-panes` call issued after an earlier `split-window`/`new-window` call in
the SAME run must reflect that earlier call's effect, or the harness would never actually exercise
the refresh path the LOC split touches. Built `_FakeTmux` to track observed `new-window`/
`split-window` calls and mutate its own `panes_by_window` state accordingly, so a later
`list-panes` dispatch reflects it. Verified by hand-inspecting the recorded argv for the
window-2-missing/window-5-one-pane-missing scenario before trusting the hash — confirmed it hits
exactly the intended branches (whole-window recreate + single-pane fill + the final respawn loop
covering the newly-created panes too).

**`dev/ram_audit/dump_byte_identity.py` — normalizing out real memory-state, keeping structure:**
gc object counts and tracemalloc size/count rows are genuinely non-deterministic across separate
process runs (real live objects differ). A section-aware normalizer (track "currently inside the
gc/tracemalloc section" via the section header lines) strips the actual data rows there while
keeping every section header, column-header line, and dash separator — plus the entire
module-state section untouched, since that's driven by a fixed fake provider and IS deterministic.
Verified hash stability across 3 independent process runs on the unmodified code before trusting
it as a baseline (a single run's hash matching itself proves nothing about determinism).

**Proxy pipeline pinning — real dual_log data from this project, not another project's session
transcript.** Initially reached for a real session JSONL from an unrelated project under
`~/.claude/projects/` for an earlier, separate milestone in this same work session — correctly
rejected as inappropriate (reading another project's private transcript content). For THIS
milestone's proxy pipeline harness, the established `dev/proxy/DOCS.md` convention already calls
for pinning a real `*_original.jsonl` from THIS project's own `src/logs/dual_log/` (proxy
request/response payloads, not session transcripts) — a materially different, already-sanctioned
case, used by two prior proxy-split milestones the same way. Pinned a 60-line prefix (the harness
only ever reads 60 lines) to `/tmp/proxy_pipeline_fixture/pinned_original.jsonl`.

## Commit-per-file mechanics with a shared pre-Go harness-build phase

The task required 5 separate commits, one per file, but both new dev harnesses
(`dev/tmux_launcher/argv_byte_identity.py`, `dev/ram_audit/dump_byte_identity.py`) were built and
baselined together in the pre-Go investigation phase, before any of the 5 source files were
touched — so both sat as untracked working-tree changes simultaneously once the source edits
began. `gcommit` stages everything unconditionally (no partial-staging option), which would have
folded both harnesses into whichever file's commit ran first. Resolved by temporarily moving the
ram_audit harness's files out of the working tree (copied to `/tmp`, `git checkout`'d the DOCS.md
diff away, deleted the new script) before the tmux_launcher commit, then restoring them before
starting the ram_audit file's own edits — kept each of the 5 commits scoped to exactly its own
file plus its own new harness, with no cross-contamination.

## Verification

`launch_split_screen` 57→28 LOC, `restart_panes` 80→26 LOC (`_create_windows`=16,
`_list_pane_modes`=7, `_create_missing_window`=15, `_fill_missing_panes`=17,
`_respawn_all_panes`=10). `register_ram_dump` 84→45 LOC, `_handle_ram_dump` 60→21 LOC
(`_rss_line`=12, `_gc_top_lines`=8, `_tracemalloc_lines`=14, `_module_state_lines`=8,
`_resolve_dump_path`=7). `_add_reqs_subparser` 54→25 LOC (`_REQS_DESCRIPTION` constant
extracted); `reqs --help` diffed byte-identical before/after. `_walk_replace_marker_blocks`
50→27 LOC (`_walk_tool_result_inner`=23). `CCMenuBarApp` 10→9 distinct `self.<attr>` (incl.
`_nsapp`, read-only); `HotkeyController` 5→6 attrs, both under the 10-attr threshold. All three
byte-identity harnesses (`dev/tmux_launcher/argv_byte_identity.py`,
`dev/ram_audit/dump_byte_identity.py`, `dev/proxy/pipeline_byte_identity.py`) hashed identical
before and after; all 9 named behavior-proof scripts + `IMPORT_OK` passed unchanged.
