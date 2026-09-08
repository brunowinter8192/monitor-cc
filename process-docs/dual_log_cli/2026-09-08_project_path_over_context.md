# `sessions` shows the real PROJECT path, not a rendered CONTEXT string (Milestone 4), 2026-09-10

Continues this area's `sessions`/`resolve_stem` line. The problem, stated plainly: `sessions`
carried the project in three weaker forms and never in its real one — the stem's `1dda1c81` is
`md5(project_path)[:8]`, CONTEXT repeated `opus`/`worker` and the worker name (both already
visible in the stem), and reduced the project to its basename. The user wanted the real path, plus
a way to filter by it — the hash is noise once the path is shown.

## What changed, and what didn't

`discovery.context_for_stem` — the function that rendered `worker/<label>/<name>` /
`opus/<label>` — is GONE, along with `project_map.build_project_map` (the `{sid8: label}`
reduction that fed it; nothing else called it once `context_for_stem` was removed). Two new
functions replace it: `project_for_stem` (the REAL cwd, resolved the same way `usage.py`'s own
transcript-directory lookup already did — a worker's sid8 through `sid_to_cwd`, a main stem's
label through a `cwd_to_dir` scan) and `display_stem` (a worker's sid8 segment stripped for
DISPLAY only). `build_session` now stores `"project"` and `"display_stem"` instead of `"context"`.

Everything that used to read `"context"` was migrated to read `"project"`/the stem directly:
`filter_sessions` (both `context` and `scope` params now match PROJECT-or-stem — they were
never actually different questions once the CONTEXT string is gone), `filter_by_family`
(`stem_identity`'s own family element, not a CONTEXT prefix check), and `render._session_tag`
(`stem_identity`'s own third element — a worker's name or a main session's label — needs no
project-path lookup at all, since that tag was always just a piece of the stem).

## The worktree-vs-project trap `usage.py`'s own precedent avoided

`usage.py`'s `_candidate_dirs` already had to solve "what is a worker's REAL project" for its
transcript lookup, and got it right: `sid_to_cwd[sid8]` gives the PROJECT's own cwd (the hash is
computed from the top-level project path, never the worktree), and the worker's OWN worktree cwd
is that path PLUS `.claude/worktrees/<name>` — appended only when `usage.py` needs the worker's
OWN directory to search. `project_for_stem` reuses `sid_to_cwd[sid8]` UNCHANGED, deliberately never
appending the worktree suffix: the milestone asks for "the real project directory the session ran
in," which is the project the worker is a worktree OF, not the worktree itself. Verified against
the ground truth: `sessions trading --since 2026-09-06` lists three worker sessions
(`reldist-power`, `k-ratio`, and a later `cdf-robust`) and two main ones, and ALL FIVE print the
identical `/Users/brunowinter2000/Documents/ai/trading` — not three different worktree paths —
which is exactly the point of a project-level filter term catching a project's main sessions and
its workers together.

## `resolve_stem` matches either form, deliberately as a union, not an override

The milestone asks for a name copied out of `sessions`' own SESSION column (sid8-stripped) to
resolve via `msgs`/`expand`/`turns`. `resolve_stem` now checks `query in s or query in
display_stem(s)` per candidate stem — a strict superset of the pre-existing check — so ambiguity
is judged over the UNION of both match kinds. A regression fixture in
`test_project_display.py` deliberately constructs two DIFFERENT stems that each match a query
through a DIFFERENT one of the two forms (one via its raw stem, the other via its displayed form)
to prove the ambiguity check actually spans both, not just whichever form happens to run first.

## Verification

- `sessions trading --since 2026-09-06` lists the same 5 sessions as before this change, all
  showing `/Users/brunowinter2000/Documents/ai/trading` in PROJECT.
- Four different ways of naming the SAME session — `reldist-power` (a full-stem substring),
  `api_requests_worker_reldist-power_1788726467` (the exact displayed form), `1dda1c81_reldist`
  (a full-stem substring including the sid8), and (implicitly, since it is the same resolution
  path) `msgs reldist-power --req 2` — all resolve to
  `api_requests_worker_1dda1c81_reldist-power_1788726467` and produce identical output.
- `reqs trading --since 2026-09-06 --until 2026-09-06 --worker --merged --gap 60` correctly scopes
  to the two worker sessions in the window (`k-ratio` — `reldist-power` and `cdf-robust` fall
  outside the `--until` bound or the gap threshold) and tags each line `k-ratio`, read straight off
  the stem via the new `_session_tag`.
- `msgs`, `turns` (bare listing AND `turns <session> N` detail) confirmed BYTE-IDENTICAL
  before/after via `git stash` on `reldist-power` and `k-ratio` — neither reads `project`/
  `display_stem` at all. `expand` differs in EXACTLY the one line the milestone calls out: the
  header's second line changed from `context   worker/trading/reldist-power` to
  `project   /Users/brunowinter2000/Documents/ai/trading`, everything else identical.
- All 13 suites under `dev/dual_log_cli/tests/` pass (256 checks total): the pre-existing
  `test_reqs.py` fixtures were updated from hand-built CONTEXT strings (`"opus/monitor_cc"`,
  `"worker/monitor_cc/foo"`) to realistic stems, since `_session_tag`/`filter_by_family` read the
  stem directly now — coverage preserved, not deleted, per this area's own testing standard. A new
  `test_project_display.py` (23 checks) covers `project_for_stem`'s worker/main/fallback paths
  (including the worktree-vs-project distinction above, asserted explicitly),
  `display_stem`'s sid8-strip-with-epoch-preserved, `resolve_stem`'s dual-form matching and its
  cross-form ambiguity case, `filter_sessions`' unified PROJECT-or-stem matching, and the two
  render functions' new column/header text.

## Relevant Symbols / Paths

- `discovery.project_for_stem`, `display_stem`, `stem_identity`, `filter_sessions`,
  `filter_by_family`, `resolve_stem` (`src/dual_log_cli/discovery.py`)
- `project_map.build_project_index` (unchanged), `build_project_map` (removed)
  (`src/dual_log_cli/project_map.py`)
- `render.render_sessions`, `_session_tag`, `render_expand_full` (`src/dual_log_cli/render.py`)
- `_load_for` (`src/dual_log_cli/__main__.py`)
- Ground truth: `sessions trading --since 2026-09-06` against the five real `trading`-project
  sessions under `src/logs/dual_log/`, joined against
  `~/.claude/projects/-Users-brunowinter2000-Documents-ai-trading*/`
- Area: this same area's `2026-08-29_worker_project_resolution.md` (the original CONTEXT rendering
  this milestone replaces) and `2026-09-03_usage_join_scoped_search.md` (the sid8→cwd precedent
  this milestone's `project_for_stem` reuses)
