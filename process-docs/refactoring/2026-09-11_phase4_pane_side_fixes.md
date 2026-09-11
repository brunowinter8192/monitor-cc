# Phase 4 (pane side) — control-flow integrity fixes

## Scope

Refactor-scan Phase 4, pane side: eliminate terminal-size fallback branches (a branch that
produces derived output a second way, classified as a fallback) and make two log-read `OSError`
handlers visible in `pane_error_log` before they retry-next-poll (classified as tripwires that
were silently swallowing evidence, not as fallbacks — the retry semantics stay).

## Item 1 — terminal-size defaults eliminated

Removed the `except OSError: pane_width = <N>` / `pane_height = <N>` substitution at every listed
call site, so `os.get_terminal_size()`'s `OSError` propagates to the pane's own blocking-loop
`except Exception: log_pane_error(<pane>)` guard:

- `src/gpu_pane/pane.py` — `_gpu_search_on_commit` (`pane_width = 100`), `_build_gpu_output`
  (`pane_width = 100` / `pane_height = 30`). Both reached from inside `run_gpu_loop`'s
  `except Exception: log_pane_error('gpu')`.
- `src/news_pane/pane.py` — `_build_news_output` (`pane_width, pane_height = 80, 24`),
  `_news_search_on_commit` (`pane_width = 80`). Both reached from inside `run_news_loop`'s
  `except Exception: log_pane_error('news')`.
- `src/panes/token_pane.py` — `_ensure_tokens_match_visible` (`pane_height = 50`),
  `_build_tokens_output` (`pane_height = 50` / `pane_width = 80`). Both reached from inside
  `run_tokens_loop`'s `except Exception: log_pane_error('tokens')`.
- `src/panes/warnings_pane.py` — `_build_warnings_output` (`pane_height = 50` /
  `pane_width = 80`), reached from inside `run_warnings_loop`'s
  `except Exception: log_pane_error('warnings')`.
- `src/workers/worker_render.py` — `_workers_terminal_size` (`default_lines=50`,
  `default_cols=80`). Removed the try/except body and the now-dead default parameters (sole
  caller `worker_pane.py:310` passed no args). Reached from `_build_workers_output`, inside
  `run_workers_loop`'s `except Exception: log_pane_error('workers')`.

**Addition during Go, found via a follow-up scan miss:** `src/news_pane/log_pane.py:run_news_log_loop`
had its own inline `try: os.get_terminal_size()... except OSError: pane_width, pane_height = 80, 24`
— same class as item 1, not originally listed. Its own `while True: try: ... except Exception:
log_pane_error('news_log')` guard confirmed the same way; the substitution is removed the same way.

## Item 2 — log-read OSError handlers become visible

- `src/panes/warnings_pane.py:_read_errors_log` — `except OSError:` now calls
  `log_pane_error('warnings')` before its existing `return records, last_pos`. `log_pane_error`
  was already imported in this module.
- `src/news_pane/log_parser.py:find_current_run_lines` — `except OSError:` now calls
  `log_pane_error('news_log')` before its existing `return []`. Added
  `from ..pane_error_log import log_pane_error` (module had no prior import of it). Tag chosen as
  `'news_log'`, not `'news'`, because the sole caller is `log_pane.py:run_news_log_loop` (the
  right-hand NEWS-LOG pane, a separate blocking loop/tmux pane from `news_pane/pane.py`'s NEWS
  pane), and `'news_log'` is that loop's own existing `log_pane_error` tag.

Retry-next-poll semantics are unchanged in both cases — the return value is identical to before,
only the error log line is new.

## Verification

Baselines captured against a frozen, non-growing 3000-line prefix of a real session JSONL at
`/tmp/p4fix_frozen_session.jsonl` (env vars `PANES_BYTE_IDENTITY_JSONL` /
`WORKERS_BYTE_IDENTITY_JSONL`), rerun after editing — all four hashes/pass-counts matched exactly:

- `dev/panes/render_byte_identity.py`: `HASH: 5c6576ae6ffb71eb21f711e2fbbbbc409fc71e32c82e7d3534ee9d048dc201fa` (before == after)
- `dev/workers/format_byte_identity.py`: `HASH: 9073eb47174508418724ea4c1ba9ca609bc02bc3f0193de14f9eabf459145ced` (before == after)
- `dev/gpu_pane/render_byte_identity.py` (fully synthetic): `HASH: e33158d622d325e1ece673c5afbfc79217c7dd3842b4243225a338df58a14a52` (before == after)
- `dev/pane_search/p8_warnings_gpu_news_parity_test.py` (covers `gpu_pane/pane.py`,
  `news_pane/pane.py`, `panes/warnings_pane.py` render + search dispatch — no dedicated
  `dev/news_pane/` harness exists): `82/82 checks passed` both times.

**Environment gap surfaced by item 1, not fixed:** this worker sandbox has no controlling
terminal at all — bare `os.get_terminal_size()` always raised `OSError` here, even un-piped. The
`p8_...` harness calls `_build_warnings_output()`/`_build_gpu_output()`/`_build_news_output()`
with no arguments, relying on a real terminal; before this change the removed fallback silently
masked that dependency in this sandbox. After the change, the harness crashed on the very first
run in this environment until re-run under a real pty (`script -q /dev/null sh -c "stty cols 213
rows 58; ..."`), which reproduced the prior 82/82 result. This is an existing environment
dependency of that harness, not a regression from removing the fallback — noted here in case
another agent hits the same crash in a tty-less sandbox and wonders whether it's caused by this
change (it is only *revealed* by it, not caused by it).

Error-path demonstrations (throwaway `/tmp` scripts, not staged):

- **Item 1:** `os.get_terminal_size` monkeypatched to raise `OSError`; called
  `warnings_pane._build_warnings_output()` wrapped in the exact `except Exception:
  log_pane_error('warnings')` guard replicated from `run_warnings_loop`. Confirmed the exception
  propagated past the (now-removed) inner try/except and the resulting traceback landed in
  `/tmp/monitor_cc_error.log` tagged `[warnings]`.
- **Item 2:** created a `chmod 000` file and called both `warnings_pane._read_errors_log(bad_path,
  0)` and `news_pane.log_parser.find_current_run_lines(bad_path)` directly. Both returned their
  original retry-next-poll values (`([], 0)` and `[]` respectively — unchanged from before this
  change) and both produced a new line in `/tmp/monitor_cc_error.log`, tagged `[warnings]` and
  `[news_log]` respectively.

Import smoke: `src.gpu_pane.pane`, `src.news_pane.pane`, `src.news_pane.log_parser`,
`src.news_pane.log_pane`, `src.panes.token_pane`, `src.panes.warnings_pane`,
`src.workers.worker_render` — all imported cleanly.

`docs-drift-check` from the worktree root: 3 pre-existing LOC-drift findings on the touched files
(`gpu_pane/pane.py` 233→226, `news_pane/pane.py` 302→296, `panes/token_pane.py` 333→326) fixed in
the corresponding DOCS.md headings; `news_pane/log_pane.py` (79→76) and `news_pane/log_parser.py`
(76→79) and `panes/warnings_pane.py` (332→329) and `workers/worker_render.py` (97→94) LOC
headings updated too. Remaining 16 path-drift findings after the fix are pre-existing and
unrelated (gitignored `src/logs/dual_log/` references, `.claude/worktrees` references) — same
count before and after this change.
