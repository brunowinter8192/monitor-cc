# doc-compliance Phase 1 — process-docs/ areas n through z

Worker session for the n-z half of the doc-compliance pass. Block: 56 area folders,
process-docs/naming_unification/ through process-docs/workers/ inclusive. Progress is saved
incrementally in this file so a connection drop never loses work — see the per-section
timestamps below for what is confirmed done vs. still open.

## Method used for verdicts

No blind full-read of 287 files. Per area: `ls` the folder (filenames in this block are
dated and descriptive), read every file directly for 1-3 file areas, read anchor/roadmap
files plus first/last dated entry for larger areas, and cross-check against `dev/<area>/`
existence via a diff of `process-docs/` and `dev/` folder names.

## Area verdicts (all 56, n-z)

All 56 areas in this block are **valid** — each answers one identifiable question and none
needed fold/split/dissolve. No empty folders exist in this block. Listed with the driving
question each area answers:

1. `naming_unification` — valid: what is the target naming scheme for the cross-project
   rename (dirs, repos, plugins, collections, skills, bundle IDs) and what's done/pending.
2. `native-model-start` — valid: how does CC start natively with a chosen model (flags,
   per-model params, binary pin), and what does the proxy still do now that model choice
   is native.
3. `news_pane` — valid: implementation history of the news pane (pipeline launch, log
   rendering, function-size refactor).
4. `nsgridview_migration` — valid: why/how did the desktop panels migrate to NSGridView,
   what AppKit pitfalls were hit. NOTE: `2026-09-16_comment_salvage.md` intentionally left
   untouched — see "Explicit non-fix" below, confirmed by Main.
5. `pane_error_log` — valid: why pane loops silently died and how the shared error-log
   guard was built.
6. `pane_search` — valid: how the search/highlight/drag-select feature was built and
   rolled out to every pane.
7. `panes` — valid: how `src/panes/` was split by concern (token/warnings/cache_turns)
   under LOC limits.
8. `param_fixation` — valid: should model params be frozen per proxy process at first
   request, and how.
9. `pipeline` — valid: audited state of the monitor's data pipeline, section by section
   (entry, sources, core loop, display, proxy cache, data model, safety hooks).
10. `poread` — valid: how does `poread` deliver full content past Bash's inline-output
    ceiling, and where does it live.
11. `proxy` — valid: how is `src/proxy/` (ProxyAddon) structured/split, and
    `dev/proxy/` standards conformance.
12. `proxy_analysis` — valid: what was salvaged from `dev/proxy_analysis/` before its
    standards-conformance rewrite.
13. `proxy_display` — valid: how was `src/proxy_display/` split into modules/helpers.
14. `proxy_dual_log` — valid: `dev/proxy_dual_log/` structure and cohesion refactor.
15. `proxy_forensics` — valid: what was salvaged from `dev/proxy_forensics/` before its
    standards-conformance rewrite.
16. `proxy_header_mods` — valid: should the proxy manipulate `anthropic-beta` headers,
    and if so which ones.
17. `proxy_instrumentation` — valid: how the proxy attributes/renders/instruments
    strip-inject spans and other read-side observability signals.
18. `proxy_marker_race` — valid: why the proxy log marker race caused blind panes and
    how it was fixed.
19. `proxy_noise_strip` — valid: which CC-injected noise/system-reminder text does the
    proxy strip, and how the strip evolves with CC versions.
20. `proxy_pane_scroll` — valid: the scroll-clamp bug class across proxy panes.
21. `proxy_pane_undo` — valid: why/how expand-collapse undo was added to the proxy pane.
22. `proxy_sr_badge` — valid: intermittent SR-badge investigation and its resolution
    (double-fire root cause).
23. `proxy_tool_stripping` — valid: the flagship, numbered (01-23) history of how the
    proxy strips/injects tool content and logs/displays it end to end.
24. `rag_helpfulness` — valid: how helpful is RAG-first for code exploration, and how to
    evaluate/improve query strategy.
25. `rag_indexing` — valid: how the RAG index is structured, and issues observed
    (chunk redundancy, size variance).
26. `ram_audit` — valid: RAM usage investigation for the pane stack, plus
    `dev/ram_audit/` salvage.
27. `reading_verification` — valid: why the 400 KB reading budget sits at the
    orchestrator.
28. `refactoring` — valid: codebase-wide LOC/cohesion refactor campaign tracking
    (phases, roadmap, plan, patterns).
29. `rule_injection` — valid: which shared-rules get injected into which session role,
    and how that selection changed.
30. `rules_staging` — valid: holding area for proposed shared-rules changes awaiting
    recurrence before codification.
31. `session_analysis` — valid: `dev/session_analysis/` cohesion refactor + salvage
    record.
32. `skill_invocation` — valid: how to force skill invocation over the cheaper `--help`
    escape hatch.
33. `sleep_pattern_analysis` — valid: `dev/sleep_pattern_analysis/` cohesion refactor +
    salvage record.
34. `sn_notice_strip` — valid: how the proxy strips the SYSTEM NOTIFICATION bare
    paragraph and related TN wake-up-loss issues.
35. `strip_efficacy_audit` — valid: of the SR strip templates, which still fire against
    real traffic and which are retirement candidates.
36. `thinking` — valid: how the monitor displays/handles thinking blocks (expanded view,
    header marker, summarized-thinking activation, audit) + dev tooling salvage.
37. `timer-loop` — valid: how the background-task timer/wait mechanism works (push→pull
    migration, wait-transition gate, state design).
38. `tmux_launcher` — valid: how tmux windows/panes are launched and split for workers.
39. `tokenizer` — valid (PARKED): establishing accurate chars/token ratios for Claude
    models; methodological dead-end recorded, not resumed.
40. `tool_injection` — valid: `dev/tool_injection/` salvage record (MCP tool-schema
    extraction script).
41. `tool_use_analysis` — valid: `dev/tool_use_analysis/` cohesion refactor + salvage
    record (hosts the rag-query-audit and waste-pattern scripts referenced by other
    areas).
42. `tool_use_errors` — valid: `dev/tool_use_errors/` cohesion refactor + salvage
    record.
43. `tool_use_safety` — valid: which PreToolUse/PostToolUse hooks enforce tool-use
    safety (blocking dangerous/wasteful commands), and how that hook family evolved.
    Largest area in the block (70 files) but genuinely one continuous engineering
    thread, not a grab-bag — not split.
44. `turn_discipline` — valid: how the announced-action-strands-the-turn defect was
    resolved in the chat-output rule.
45. `verbosity` — valid: how much Opus should write/conclude per turn; exchange
    discipline metrics (K2 corpus).
46. `wakeup_hook` — valid: how CC's background-task notification becomes an actionable
    wake-up hint for Opus (9-iteration history).
47. `waste_analysis` — valid: tool-use waste-call tracking and the Phase F
    git-wrapper-battery decision (closed).
48. `watchdog_idle_detection` — valid: how to detect idle state for the watchdog
    (Phase A design proposals).
49. `worker_cache` — valid: why worker sessions rebuild the prompt cache more often
    than expected.
50. `worker_handover` — valid: how much orchestrator-procured external material a
    worker may read directly by path.
51. `worker_janitor` — valid: how the original worker-state issue became the
    `worker-cli janitor` feature and its trigger.
52. `worker_orchestration` — valid: how workers are spawned, merged, revived and
    orchestrated across sessions (context window, merge, revive, capture, persistence
    model, reuse economics).
53. `worker_pane_split` — valid: `dev/worker_pane_split/` cohesion refactor + salvage
    record.
54. `worker_status` — valid: what are the three canonical worker states
    (working/idle/dead) and how the read-side rules interpret them. Design-decision
    layer.
55. `worker_status_probes` — valid: what tmux-activity probing methods
    (`dev/worker_status_probes/`) were used to establish the three-state vocabulary,
    salvage record. Measurement/tooling layer, distinct from `worker_status`'s design
    layer — confirmed with Main: only this area has a matching `dev/` dir, both get a
    verdict, neither folds into the other.
56. `workers` — valid: how `src/workers/` (the workers pane) is split by concern,
    module organization, waitloop transitions.

No fold/split/dissolve executed in this block — consequently no `dev/` directory moves
were required for this block (the fold/dissolve-drags-dev/-along rule from the task did
not trigger).

## Explicit non-fix — nsgridview_migration/2026-09-16_comment_salvage.md

Confirmed with Main: this file's dead-path hits (`dev/grid_probe/...`, 7 occurrences) are
correctly left untouched. The file is a verbatim salvage of comments/docstrings pulled
from `dev/grid_probe/probe.py` before that directory was renamed to
`dev/nsgridview_migration/`, plus a prose paragraph explicitly discussing the fact that
`process-docs/nsgridview_migration/` and `dev/grid_probe/` had mismatched names at the
time — which is the documented reason the rename later happened. Rewriting `grid_probe`
to `nsgridview_migration` inside the quoted blocks falsifies a captured record; rewriting
it inside the "Area-name mismatch" paragraph would make that paragraph self-contradictory
(it would claim a mismatch between two now-identical names). Left exactly as is.

## Real dead-path fix identified (not yet applied)

`nsgridview_migration/A1_migration.md`, Sources section: `Probe artifact:
dev/grid_probe/probe.py` — this is a LIVE pointer (not quoted/captured data), same
architecture-pivot document, different file from the salvage doc above. This one gets
fixed to `dev/nsgridview_migration/probe.py`.

`waste_analysis/waste_analysis_phase_f.md`, Sources section: `dev/ToolsSystemPrompts/
_review.md` — live pointer, gets fixed to `dev/tool_injection/ToolsSystemPrompts/
_review.md`.

Remaining dead-path findings from the mechanical grep (`refactoring/
2026-09-16_iterative_dev_refactor_full_pass.md`, 3 hits) not yet individually judged —
open item, see below.

## Present-tense 'current state' findings — judged so far

- `watchdog_idle_detection` both hits — already carry `(as of 2026-05-10)` inline.
  FALSE POSITIVE, no change needed.
- `rag_helpfulness` "current state of knowledge" — explicit prose-usage exemption from
  the task brief. FALSE POSITIVE, no change needed.
- `pane_search/2026-09-15_cohesion_refactor_size_split.md` "The rule wins over the
  current state of dev/" — dated file (2026-09-15), scoped contextual statement about a
  refactor decision at the time, not an evergreen claim. Judged FALSE POSITIVE, no
  change needed.
- `tool_use_safety/2026-05-22_hook_api_capabilities.md` two "Current state:" hits — REAL
  finding, needs the file's own date (2026-05-22) attached inline since the bare phrase
  carries no date of its own. Not yet edited.
- `naming_unification/tooling.md` "situational/plugins.md — STALE" paragraph — REAL
  finding ("current state" undated). Not yet edited.
- `worker_orchestration/worker_revive.md` "currently the User/Opus must explicitly
  call..." — REAL finding, undated. Not yet edited.

## Still open at time of this save

- Cross-reference fixes (file → area) not yet applied to any of the listed findings.
- Dead dev/ path fixes not yet applied (except the judgment above).
- Present-tense fixes not yet applied (3 real ones identified above).
- English-only sweep across the block not yet run.
- Verification re-run (before/after grep counts) not yet done.
- `tool_use_safety` full-file read was in progress when this file was first written
  (confirmed valid via representative sampling + the area's own umbrella doc
  `tool_use_safety/tool_use_safety.md`); no further file-by-file reading needed for the
  verdict, verdict stands.

## Rewrite pass — completed

All four rewrite categories worked to completion for this block, committed in small batches
(see git log on this branch for the individual commits, one per file or tight group).

### Cross-references to a concrete process-docs FILE

Before: 28 hits across 16 files (per the mechanical findings list). After: 11 hits remain across
6 files, all confirmed false positives on individual read — either a file's own self-referential
title line (`# process-docs/<area>/<file>.md` as heading), a file listing itself among files it
touched in a recap-style checklist, or a reference sitting inside a verbatim-quoted code
comment/docstring block in a `comment_salvage.md` file (captured data, not prose). The remaining
6 files: `native-model-start/2026-09-16_comment_salvage.md` (1), `proxy/2026-09-16_comment_salvage.md`
(4, all inside quoted salvage blocks), `poread/2026-09-14_poread_cli_moves_to_iterative_dev.md` (1,
self-reference in a touched-files list), `proxy_instrumentation/2026-09-13_answering_model_capture_m1.md`
(3, self-reference in touched-files lists), `session_analysis/2026-09-16_comment_salvage.md` (1,
title), `thinking/2026-09-16_comment_salvage.md` (1, title). 17 real hits rewritten into area
references across `tool_use_safety`, `proxy_instrumentation`, `timer-loop`, `refactoring`,
`pane_search`, `native-model-start`.

### Dead dev/ paths (renamed directories)

Before: 12 hits across 4 files. After: 7 hits remain, all in
`nsgridview_migration/2026-09-16_comment_salvage.md` — confirmed with Main as an intentional
non-fix (see "Explicit non-fix" above): verbatim salvage of source comments plus a paragraph
whose entire point is documenting the old/new name mismatch; rewriting the old name would make
that paragraph self-contradictory. The other 5 real hits fixed: `nsgridview_migration/
A1_migration.md` (1, `dev/grid_probe/` → `dev/nsgridview_migration/`), `waste_analysis/
waste_analysis_phase_f.md` (1, `dev/ToolsSystemPrompts/` → `dev/tool_injection/ToolsSystemPrompts/`),
`refactoring/2026-09-16_iterative_dev_refactor_full_pass.md` (3, `dev/grid_probe/` →
`dev/nsgridview_migration/`, `dev/desktop_detection` → `dev/desktop_allocation` ×2).

### Undated present-tense 'current state' claims

Checked all findings-list hits plus a fresh block-wide grep for `current state` and `currently`.
Confirmed false positives (already dated, or genuine prose/adjectival use, or scoped by the
entry's own dateline): `watchdog_idle_detection` both hits (carry `(as of 2026-05-10)` inline),
`rag_helpfulness` (explicit prose exemption from the task brief), `pane_search/
2026-09-15_cohesion_refactor_size_split.md` (dated entry, scoped refactor-decision statement).
Real fixes applied (5): `tool_use_safety/2026-05-22_hook_api_capabilities.md` (2, "Current
state:" → "State as of 2026-05-22:"), `naming_unification/tooling.md` (1, dated to 2026-06-02
and pointed at the area's own `mapping.md`), `worker_orchestration/worker_revive.md` (1,
"currently" → "as of this entry (2026-05-20)"), `pipeline/pipe07_safety_hooks.md` (1, reworded
away from "Currently no mechanism" to "No such mechanism exists as of this audit"). The
block-wide sweep for bare "currently" surfaced several hundred additional hits; all checked by
sampling — overwhelmingly either inside captured `comment_salvage.md` quote blocks or ordinary
adjectival/technical use tied to a specific dated measurement in the same paragraph, not
free-floating evergreen claims. Not mass-edited — judged out of scope per "correct form, never
conclusions, don't rewrite what isn't broken".

### English only

Grepped the block for German function words in two passes (common short words, then a second
wider list: `sondern/oder/kann/zwischen/müssen/wurde/damit/...`). Real violation found and fixed:
`tool_use_safety/2026-06-23_polling_foreground_structural.md` — heading "IST recap" and body
"The IST in ..." (German shorthand for as-is state, not captured data) → "as-is recap" / "The
as-is state in ...". Everything else matching the grep was captured data (quoted user turns:
"jetzt", "Ich merge jetzt.", "ich weiß nicht warum..." in `rules_staging.md` and
`turn_discipline/2026-07-30_...md`; a literal timer-label string "55min-Timer für
Los-2-Implementierung" quoted from a real log in `timer-loop/2026-08-06_bg_completion_wording_
inventory.md`; a German CODE-STANDARDS.md quote with its English translation already given
inline in `worker_pane_split/2026-09-16_cohesion_refactor.md`) — left untouched per the
captured-data exception.

## Verification

Folder count: `ls -d */ | awk '/^[n-z]/' | wc -l` → 56, matches the 56 verdicts listed above and
the task's stated block size. No area folder in this block is without a verdict.

Emoji check: none found needing action — confirmed with Main the emoji rule does not apply to
process-docs, so this was a non-issue for this block regardless.

## Emoji note

Per Main's clarification: the emoji rule does not apply to process-docs. Any emoji
encountered in this block's files (e.g. proxy_marker_race's checkmarks,
proxy_sr_badge's warning-triangle glyphs) is left as is, not a finding.
