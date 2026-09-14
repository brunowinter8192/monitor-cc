# p4_blocklist_223_probe.py repointed at live corpus (2026-09-14)

## Context

`dev/proxy_instrumentation/p4_blocklist_223_probe.py` hardcoded one session stem
(`api_requests_opus_websearch_1786052022`) for its dual-log reads. That session has since aged
out of the live `src/logs/dual_log/` corpus (log rotation, untracked runtime data) — the probe
died on first `open()` with `FileNotFoundError`. `dev/proxy_instrumentation/DOCS.md`'s Gotchas
section already documented this exact failure as of 2026-09.

## What was actually broken vs. what looked broken

Two things were named as broken in the task: the hardcoded stem, and a stale `EXPECTED_KEPT`.
Only the first was real. `EXPECTED_KEPT` inside the `.py` file was already `{'Bash', 'Read',
'Skill'}` — correct against the current `TOOL_BLOCKLIST` (`src/constants.py`), which now
includes `Edit`/`Write` and excludes them from the kept set. The *stale report on disk*
(`dev/proxy_instrumentation/md/blocklist_223_probe_report.md`) showed `kept=['Bash', 'Edit',
'Read', 'Skill', 'Write']` because it was a leftover artifact from before commits `5410b266`
("block Read, Edit, Write") and `2eceaf55` ("take Read back out") updated the blocklist and the
probe's constant in lockstep — the report file itself was simply never regenerated after those
commits. Anyone reading only the report (not the `.py` source) would misdiagnose this as a code
bug. Lesson for a following agent: when a task frames "N things are wrong", verify each claim
against the current source before touching it — one of the two claims here was actually already
fixed in code, only the artifact on disk lagged.

## Fix

Replaced the hardcoded `STEM` module constant with `_select_session_stem()`, following
`p7_blocklist_258_probe.py`'s `_newest_main_session_log` pattern (glob `*_original.jsonl` under
`LOG_DIR`, exclude `api_requests_worker_*`, pick newest by mtime) but extended with two
requirements p4 specifically needs that p7 does not:
- a matching `_forwarded.jsonl` must exist for the same stem (p4's `agent_absent_from_forwarded`
  check reads the forwarded log; p7 never reads forwarded logs at all), and
- the original log must contain at least one line with a non-empty `payload.tools` list (p4's
  `_load_original_payload` requires this; a session with an empty first-turn tools list would
  otherwise raise).

`_load_original_payload`, `_invoked_tool_names`, `_forwarded_tool_names` were changed from
reading the module-level `STEM` to taking a `stem: str` parameter, threaded from
`_select_session_stem()`'s return value in `main()`. No assertion logic, no case, and no
threshold was touched — only session selection.

`MAIN_REPO_ROOT` / `LOG_DIR` mechanism (untracked dual-log data lives only in the main checkout,
not in worker worktrees) was kept exactly as-is, per task constraint.

## Verification

As of 2026-09-14, `_select_session_stem()` resolves to `api_requests_opus_monitor_cc_1789408648`
(the newest non-worker session in the live corpus at the time, mtime `1789409122`). Its original
log's first non-empty-tools payload carries the full CC 2.1.223+ built-in tool set including
`Artifact`, `ReportFindings`, `DeferredToolPlaceholder`, `SendFeedback`, `ListAgents`, `Edit`,
`Write` — i.e. it is a representative payload for this probe's purpose, not a degenerate one.
Ran `./venv/bin/python dev/proxy_instrumentation/p4_blocklist_223_probe.py` (worktree's own
venv) twice, both exit 0, both ALL PASS across all 5 cases. Regenerated report committed at
`dev/proxy_instrumentation/md/blocklist_223_probe_report.md`.

## Known staleness left behind (not in this task's scope)

`dev/proxy_instrumentation/DOCS.md`'s Gotchas section still states, as of 2026-09, that
`p4_blocklist_223_probe.py` "hardcodes one session stem... that has since aged out... the
script cannot run... until repointed at a session still present." That statement is now false —
this fix repointed it. The task prompt that produced this entry did not list a DOCS.md update
among its deliverables or Completion Checklist items, and the worker rules place DOCS.md
currency checks in the recap step specifically for files the task touched — `DOCS.md` itself was
not one of them until this recap. Fixed in this same recap pass (see the currency-check note
below); flagging here for traceability since the original task commit did not touch it.
