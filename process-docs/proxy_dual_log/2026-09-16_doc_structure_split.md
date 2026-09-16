# 2026-09-16 — Doc-structure split of dev/proxy_dual_log/

## Context for whoever picks this up

`dev/proxy_dual_log/DOCS.md` had grown to 408 lines (over the 400-line split threshold). This
entry documents the resulting unit split: 8 entry scripts + their exclusively-owned sibling
modules moved into subfolders named after the entry script; 5 entry scripts with no exclusive
module stayed as single files at the area root. 38 `.py` files total, 13 entry scripts, zero
shared modules, zero unowned modules — confirmed by an independent closure analysis before moving
anything, which matched Main's own analysis exactly.

## The path-resolution mechanism, and why it has two tiers

**Tier 1 — code, imports, and every output path (`*_reports/`, `fixtures/`).** Every file needing
this walks up from `Path(__file__).resolve().parent` until a directory literally named
`proxy_dual_log` is found (0 hops for a file staying at the root, 1 hop for a file now living in a
unit subfolder) — this is `_AREA_ROOT`. `_PROJECT_ROOT = _AREA_ROOT.parent.parent`
(`proxy_dual_log` → `dev` → project/worktree root) follows from there, unconditionally correct in
both a main checkout and a worktree, since it counts from a name-matched anchor, never from
`__file__`'s raw nesting depth. This is inlined identically (same 3-4 lines) in every one of the
16 files needing it — not a shared importable module — because a shared module sitting at the
area root would need its importing subfolder-script to already know how many `.parent`s to add to
reach it, which is exactly the chicken-and-egg problem this fix removes.

**Tier 2 — the dual-log corpus specifically (`src/logs/dual_log/`).** Main caught my first draft
of the mechanism here: `_PROJECT_ROOT` is NOT sufficient for the corpus, because in a worktree
`_PROJECT_ROOT` is the worktree root, and `src/logs/dual_log/` is gitignored and lives ONLY in the
main checkout (verified on disk: `.claude/worktrees/c3/src/logs/` has no `dual_log/` at all, only
`monitor_sweep.log`). This is a "this data only exists in one place" problem, not a depth problem.
The fix: a `_main_checkout_root(project_root)` helper that checks whether `project_root`'s tail is
literally `.claude/worktrees/<name>` (3 path components) and, if so, strips them; otherwise returns
`project_root` unchanged. Marker-driven, not count-driven — correct whether invoked from the main
checkout directly or from any worktree.

**The existing two-candidate `exists()`-else corpus lookup was kept exactly as a lookup shape, per
Main's explicit instruction — only the two candidates' own computation changed.** Four files
(`composition_probe_corpus.py`, `green_overlay_probe_cases.py`, `groundtruth_spans_cases.py`,
`attribution_coverage.py`) already tried "the project root's own `src/logs/dual_log`" first and
fell back to "the derived main-checkout's `src/logs/dual_log`" only if the first didn't exist. That
two-step shape is preserved; only the two paths themselves are now computed via `_PROJECT_ROOT` and
`_main_checkout_root(_PROJECT_ROOT)` instead of blind `parents[1]`/`parents[4]`. One file,
`span_inline_probe.py`, never had a two-candidate fallback at all — its original single expression
(`parents[5]`) unconditionally jumped straight to what would be the main checkout in a worktree
context (and would have been WRONG if ever run from the main checkout directly, since `parents[5]`
from that location overshoots by 3 levels — a pre-existing, never-fixed limitation). Its
replacement matches that same unconditional shape: always `_main_checkout_root(_PROJECT_ROOT)`, no
`exists()` check added. Main was explicit that **simplifying or removing the two-candidate
fallback pattern is out of scope for this milestone** — it belongs to a later phase, once someone
decides whether the worktree-local candidate is ever actually going to exist for these scripts.

## A mistake I made and caught before it shipped — worth remembering

My first pass at `main_log_elimination_io.py`'s `_resolve_root()` fallback (used when
`MONITOR_CC_ROOT` is unset) applied the Tier-2 main-checkout derivation, on the assumption that
"any `src/logs/...` lookup must be corpus-shaped." That was wrong. The ORIGINAL code
(`Path(__file__).parent.parent.parent`, 3 plain parents from the file's pre-move flat location)
resolved to `_PROJECT_ROOT` — the **worktree root**, not the main checkout — because this
function's caller builds BOTH a flat top-level `src/logs/api_requests_<session>.jsonl` path AND a
`src/logs/dual_log/...` quartet path from the same resolved root, and the pre-existing code never
tried to reach across a worktree boundary for either. Applying `_main_checkout_root` here silently
changed the resolved path from the worktree root to the main checkout root — caught immediately
because I run every edited script before moving to the next one: the before/after `ERROR: main log
not found: <path>` message literally showed a different absolute path
(`.../worktrees/c3/src/logs/...` before my error, `.../monitor-cc/src/logs/...` after). Fixed by
reverting this one file to plain `_PROJECT_ROOT` (matching every other "Tier 1" file). The lesson:
"this file touches `src/logs/`" is not sufficient signal for "this needs the main-checkout
derivation" — check what the ORIGINAL blind computation actually resolved to (by counting its
literal parent-hops from the file's pre-move location) before deciding which tier a fix belongs to,
then verify by running before/after, not by inspection alone.

## Additional depth-dependent / anchor-point issues found beyond Main's original table

Main's own table was a `parents[` grep and was accurate for what it searched; I found 9 more
issues using different syntax or targeting an output-directory anchor rather than a `sys.path`/
corpus lookup, all of which **would have broken silently** the moment their file moved a level
deeper had they been left alone:

- `proxy_176_bg_launch_ack_tests.py` (line 4): `os.path.join(os.path.dirname(__file__), '..', '..', 'src')` — `os.path.join`/`'..'` style, not `parents[`.
- `main_log_elimination_io.py` (line 13): `Path(__file__).parent.parent.parent` — chained `.parent.parent.parent`, not bracket syntax.
- `A_render_refactor_proof.py`, `attribution_coverage.py`, `composition_probe.py`, `green_overlay_probe.py`, `groundtruth_message_spans_probe.py`, `main_log_elimination_report.py` (6 files): each computed its own `*_reports/` output directory as `Path(__file__).parent / "<name>_reports"` — correct today only because these files currently sit directly at the area root; the reports directory is one of the four explicitly-named "stays at the area root" bus directories, so this needed the same `_AREA_ROOT` anchor as everything else, not `_PROJECT_ROOT`.
- `test_composition_invariant.py` (line 13): `FIXTURE_PATH = _HERE / "fixtures" / "invariant_corpus.jsonl"` — same class, `fixtures/` is also a named stay-at-root bus directory.

`span_inline_probe.py`'s `REPORT_DIR = Path("dev/proxy_dual_log/span_inline_probe_reports")` is a
literal string relative to CWD, not `__file__` — already correctly anchored regardless of the
file's depth, confirmed unchanged.

## Verification method and results

Ran all 13 entry scripts (plus `composition_probe.py`, which has its own `__main__` in addition to
being imported by `test_composition_invariant.py`) from the project root, before the move and
after, using the smallest real dual-log stem with a complete quartet on disk
(`api_requests_worker_52fce57c_wsrefactor_1789506614`, 39 lines) for the CLI-arg scripts
(`diff_strip_inject.py`, `verify_delta.py`, `tt_delta_skip_replay.py`), and each script's own
documented no-argument invocation for the rest.

- **`test_composition_invariant.py`, `tt_delta_skip_replay.py`, `verify_delta.py`,
  `proxy_176_agent_types_tests.py`, `proxy_176_bg_launch_ack_tests.py`, `proxy_176_strip_tests.py`**:
  stdout byte-identical before/after.
- **`A_render_refactor_proof.py`, `diff_strip_inject.py`, `span_inline_probe.py`**: each has a
  genuine pre-existing crash unrelated to this milestone (`KeyError: '_stripped_spans'`,
  `KeyError: 'spans'`, and a rotated hardcoded stem's `FileNotFoundError` respectively) — verified
  identical via normalized-traceback comparison (exception type + message + frame file-basename +
  function name, line numbers stripped since the move itself shifts every line below the inserted
  `_AREA_ROOT` snippet).
- **`green_overlay_probe.py`, `groundtruth_message_spans_probe.py`, `composition_probe.py`**: each
  succeeds (exit 0) but has one or more internal `try/except` blocks around a hardcoded-stem
  corpus read that's currently rotated off disk, embedding the caught traceback as an `ERROR:`
  block in the written report rather than crashing — verified identical via the same
  normalized-traceback comparison applied to both stdout and the report file content (with the
  report's own live-timestamp header line additionally excluded).
- **`main_log_elimination_probe.py`**: no flat top-level `src/logs/api_requests_*.jsonl` file
  exists anywhere in this corpus (confirmed on disk — only the six-stream `dual_log/` split
  exists today), so this script deterministically exits 1 at its earliest file-existence check,
  before touching any of the fixed code this milestone edited — verified byte-identical stdout
  (using a fixed literal session argument both times so the embedded path string doesn't vary).
- **`attribution_coverage.py`**: reads the corpus by glob (no hardcoded stem), and the corpus is
  genuinely live — one of the scanned files,
  `api_requests_worker_25c51a2e_c3_1789544702_stripped.jsonl`, is this very own agent session's
  own live proxy log (worktree name `c3`), which kept growing while I worked. The first
  before/after diff showed new rows from that exact file. To prove this was corpus drift and not a
  code regression, I ran the (already-fixed, already-moved) script twice in a row with nothing
  else changed — the report STILL differed between those two consecutive runs, conclusively
  proving the drift source is the live corpus, not my edit.

## Cleanup notes

Every report file/directory my own test runs created was untracked (confirmed via `git status`/
`git ls-files` before deleting) and removed by exact filename, never a wildcard. The two tracked
report artifacts under this area
(`A_render_refactor_proof_reports/baseline_20260818.json`,
`A_render_refactor_proof_reports/baseline_20260905.json`) were never touched by any run (that
harness's own `--output`/`--baseline` flags were pointed at `/tmp` for every capture-mode
invocation during verification) — confirmed untouched via `git status --short` showing no diff
for that directory at the end.
