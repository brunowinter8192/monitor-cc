# 2026-09: splitting `__main__.py`/`render.py`/`timeline.py` by concern for the 400-LOC file limit

## Trigger

Three modules in `src/dual_log_cli/` exceeded the 400-LOC file limit and one function exceeded the
100-LOC hard limit: `__main__.py` (492 LOC, `_parse_args` alone 131 LOC), `render.py` (760 LOC),
`timeline.py` (545 LOC). The mandate was a split by CONCERN, not a cosmetic LOC-shrink — comments
and docstrings had to move with the code they describe, unchanged, and every one of the 13 tests in
`dev/dual_log_cli/tests/` had to keep passing byte-for-byte.

## Investigation

Read every `.py` file in `src/dual_log_cli/` (11 files) and all 13 test files in
`dev/dual_log_cli/tests/` in full before touching anything, to build the exact symbol→module map
and confirm which private (underscore-prefixed) names the tests import directly — `_clock`,
`_fmt_duration`, `_system_block_chars`, `_tool_chars`, `_window_date`, `_group_markers_by_turn`,
`_is_turn_opener`, `_turn_preview`, and others. Since none of these are re-exported through
`__init__.py`, every test import had to be re-pointed to the new module by hand rather than
discovered by import error alone — a grep-first pass (`from src.dual_log_cli.render import`,
`from src.dual_log_cli.timeline import`) against every test file up front avoided missing one.

Grouped each of the three files' functions into the concerns the milestone spec already named
(argparse construction vs. command bodies for `__main__.py`; shared formatters vs. one render
function per command for `render.py`; turn-row construction vs. boundary derivation vs. marker/
numbering vs. turn-grouping vs. the `load_timeline` assembly point for `timeline.py`), then checked
cross-references between concerns by grepping each helper's callers within the same file — this is
what confirmed, for example, that `_group_markers_by_turn` (turn grouping) needed `request_markers`
(markers) but nothing from turn-row construction, and that `render_msgs`'s helpers never touch
`stem_identity`/`_group_markers_by_turn` (both `reqs`-only concerns).

## Decisions

**`__main__.py` → `cli_args.py` + `commands.py`, `__main__.py` reduced to dispatch + docstring.**
The module docstring is also argparse's `epilog=__doc__` — moving parser construction into
`cli_args.py` meant `__doc__` inside THAT module would resolve to `cli_args.py`'s own docstring, not
`__main__.py`'s usage text. Rejected: having `cli_args.py` import `__main__.__doc__` (circular
import risk, and backwards — the entry point should not depend on a helper module reading its
globals). Chosen: `cli_args._parse_args(argv, epilog)` takes the epilog as an explicit parameter;
`__main__.py`'s own thin `_parse_args(argv)` wrapper passes its own `__doc__` in. This keeps the
docstring physically in `__main__.py` (where a reader expects the entry point's own usage text to
live) with zero cross-module global reads. `_parse_args` itself dropped from 131 LOC to 16 by
extracting one `_add_*_subparser(sub)` helper per subcommand (sessions/msgs/expand/search/reqs) —
each subparser's own argument set, help text and the one `add_mutually_exclusive_group()`
(`reqs`' `--main`/`--worker`) carried over unchanged.

**`render.py` deleted entirely — no assembly-point file survives there**, unlike `timeline.py`.
Split into `render_format.py` (the six shared formatters: `fmt_chars`, `fmt_timestamp`, `_clock`,
`_window_date`, `_fmt_duration`, `_skipped_lines` — the ONE place every other renderer imports them
from, per the milestone's own requirement), `render_sessions.py`, `render_msgs.py`,
`render_search.py`, `render_reqs.py`, `render_expand.py` — one module per command's own render
function plus its private helpers, matching the milestone's named concern boundaries (a), (b)..(f)
exactly. `render_msgs.py` and `render_reqs.py` came out largest (297 and 294 LOC respectively) since
each command's helper cluster is large but cohesive — both still comfortably under 400.

**`timeline.py` kept as the assembly point — `load_timeline` only**, per the milestone's explicit
allowance. Split into `timeline_turns.py` (turn-row construction: `build_turns`,
`iter_block_texts`, `full_turn`, `_preview`, `_block_label`, `_block_preview`), `timeline_boundaries.py`
(request-boundary derivation from `_forwarded`: `request_boundaries`, `build_turn_times`,
`_sys_lines`, `_tool_lines`, `_is_sidecar`, `_system_block_chars`, `_tool_chars`,
`_BILLING_HEADER_SYS_INDEX`), `timeline_markers.py` (marker/numbering: `request_markers`,
`_running_request_numbers`, `request_numbers_by_flow`, `request_msg_range`, `resolve_req_range`,
the two request-number error classes), `timeline_grouping.py` (turn grouping:
`_is_turn_opener`, `turn_openers`, `_turn_preview`, `_group_markers_by_turn`). Cross-checked that
`_group_markers_by_turn`'s own dependency on `request_markers` is the only inter-submodule import
needed among the four — every other submodule is self-contained given a boundaries/turns list as a
plain parameter.

**`overlay.py` and `search.py` needed import re-pointing even though they were not named in the
milestone's three target files** — both import symbols that moved (`request_numbers_by_flow`,
`iter_block_texts`). Caught by the mandated "grep every reference across `src/`, `dev/`, `bin/`"
pass rather than by an import error, since both files are inside the same package and Python would
not have failed loudly until first actually exercised by a test or a real run.

## Verification

All 13 `dev/dual_log_cli/tests/test_*.py` passed after the re-point (`for t in
dev/dual_log_cli/tests/test_*.py; do ./venv/bin/python "$t" ...`), and `./venv/bin/python -m
src.dual_log_cli --help` / `reqs --help` both printed without error — the `epilog=__doc__` text
matched the pre-split docstring byte-for-byte (diffed programmatically against the pre-split
`__main__.py`'s own docstring before committing, not just eyeballed). Final `wc -l` across all 21
files in `src/dual_log_cli/`: largest is `render_msgs.py` at 297 LOC, well under the 400 limit;
`_parse_args` (now in `cli_args.py`) is 16 LOC, under the 50-LOC target. No re-export shim was left
in `render.py` (deleted) or the reduced `timeline.py`/`__main__.py` — every caller, including all 13
tests, was re-pointed to the new module directly.

## Left unresolved

The historical Gotcha entries in `DOCS.md` describing the ALREADY-removed `turns` subcommand
(2026-09-08 pivot, predating this split) still label some now-defunct functions with the file names
they lived in AT THE TIME they were removed (`timeline.py`, `render.py`) — those are historical
statements about a past removal, not claims about the current tree, so they were left as-is rather
than rewritten to name today's split modules.
