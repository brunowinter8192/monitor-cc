# Pane flicker: in-place synchronized frames (M1) and frozen turns (M2), 2026-09-24

## Problem as observed by the user
Tokens and proxy panes flicker only while the mouse moves over the pane and only in sessions with many messages. Every hover motion event returned "changed" and triggered a full build, then `\033[2J\033[3J\033[H` + print. Two causes: the blank intermediate frame (clear then print) and the O(all turns) rebuild per hover.

## M1: frame write path (`src/frame_writer.py`, commit "feat: flicker-free in-place frame write ...")

Frame = `\033[?2026h` `\033[H` rows `\n` `\033[J` `\033[?2026l`, sent in one `write()` + flush. Rows are joined by `\n`; a row that contains no `\033[K` gets `\033[0m\033[K` appended, rows that already contain `\033[K` are left alone.

Decisions and why:
- Row-end erase rule. Search-bar rows and worker-header rows carry no `\033[K` (on a cleared screen they never needed it). In place they would keep stale characters when the text got shorter (observed test: type `abcdefgh` in the search bar, backspace 6 times). Appending `\033[K` to rows that already have one is wrong: it runs after the row's `RESET`, so it erases with the default background and destroys the zebra/hover fill. Hence the `in row` check.
- Header overdraw dropped. The worker panes printed `\033[H{header}\033[K` after the body. The header is already the first rows of `output`; the overdraw only added an erase on the header's last line. The per-row rule reproduces that. `_build_worker_tokens_output` and `_build_worker_proxy_output` now return only the output string (was `(output, header)`); p5/p7 dev tests were adapted (they take `output.splitlines()` for the header check).
- Trailing `\n` before `\033[J` is required. First version emitted `\033[J` directly after the last row: ED erases from the cursor cell inclusive, and the cursor sits on the last column of the last row (rows with the copy symbol are exactly width-1 wide plus the erase-filled last cell). Result: the last cell of the last row lost its background (default instead of zebra). Observed on proxy and worker-proxy row 13/14 in the e2e run; tokens panes did not show it because their last row has no copy symbol. Old code got this for free from `print(output)` newline.
- tmux 3.6a server ignores mode 2026 (unknown private mode), so until the user restarts the server on 3.7c the fix is the in-place overwrite alone; 3.7c adds the atomic frame on top. tmux `screen_write_clearendofline` returns early when the cursor is past the last column, so a full-width row followed by `\033[K` is safe.

M1 test (`dev/pane_flicker/m1_frame_e2e_*.py`, report `md/m1_frame_e2e_test.md`): real `run_*_loop` of all four panes, `_refresh_*` patched out, state seeded, keys via `tmux send-keys -l` (SGR mouse sequences work verbatim), 100x30 windows, one private tmux server per pane and tree, old tree = `git archive integration`. Raw bytes via `tmux pipe-pane`. 92 checks: old tree emits `\033[2J` (harness sanity), new tree emits no 2J/3J, every frame is one properly nested 2026 pair, nothing outside a pair, and `capture-pane -p -e -N` after each of 15-17 steps is identical old vs new (hover, expand, collapse, scroll, search type/backspace/commit, worker switch to a worker with fewer/no data and back).
- Screen comparison needs normalization, not string equality: `capture-pane -e -N` prints the same screen differently depending on grid history (trailing cleared cells, leading resets carried across lines). The test interprets SGR into per-cell state and drops trailing default blank cells. Trailing cells with a non-default background are still compared, that is how the last-cell bug above was found.
- Mutation check: with `ERASE_BELOW` emptied the harness fails on shrinking frames (worker switch, collapse), so it does detect stale content.
- Parity suites re-run after the tuple change: p2 48, p3 62, p5 77, p6 78, p7 83 checks, 0 failures. Run them inside a tmux pane WITHOUT any pipe or redirect (`os.get_terminal_size()` fails when stdout is not a tty); read results via `capture-pane -S -`.

## M2: frozen turns (`src/format/turn_cache.py`, commit "feat: frozen-turn cache ...")

`format_cache_tracker(..., turn_cache=None)`; the two panes own a module-level cache dict from `new_turn_cache()`. Without the argument every call renders fresh (same code path with a throwaway cache), so the existing dev callers are unchanged. Hover is not an input to `format_cache_tracker` at all; the only per-hover work left is `_render_tokens_rows` on the visible slice.

Per-turn dirty rules (turn index set, recompute only those):
- turn object identity (`is`), plus request-number base (calls in preceding turns). `build_cache_turns` never mutates turn dicts; the merged last turn is a new dict, so a growing last turn is detected by identity.
- expand: diff of the frozenset of truthy expand keys against the previous one.
- copy feedback: diff of the set of keys with `until > now`; `copy_feedback is None` vs dict is part of the global signature.
- search: identity + len of `match_set` (panes replace the set, never mutate it), current key and query. Changed keys = symmetric difference of match sets plus old/new current key; a query change also dirties every turn holding a match.
- response data: only expanded calls are fingerprinted (`repr` of the `_response_rid_map` entry plus today's date, because `_fmt_rl_reset_time` renders "HH:MM" vs "Day HH:MM" relative to now). An entry mutated in place is detected.
- global signature (pane width, wide flag, feedback-None flag, preamble line): any change drops all entries.

The assembled document (lines, keys, nav, parent prefix array) is rebuilt only if a turn changed; the prefix array replaces the O(N) `sum(... line_keys[:start])`. `nav_out` is refilled only when the cache generation changed or the dict was cleared externally (session reset clears `_tokens_nav`).

Observed numbers (process CPU time, `dev/pane_flicker/md/m2_hover_timing.md`; the machine had load average 30-50 from other workers, wall time varied up to 10x, even CPU time varied ~2x between runs, so read them as orders of magnitude):
- real session 869 calls / 35 turns: hover build 47 ms old, 0.66 ms new (tokens); 54 ms old, 0.80 ms new (worker-tokens).
- real session 460 calls / 104 turns: 15 ms old, 0.42 ms new.
- the same turn lists repeated 10x (synthetic, 4600-8690 calls): 150-250 ms old, 0.5-1.2 ms new.
- First build after start/width change is as expensive as before (cold column, no regression).
- Earlier runs with wall time showed single outliers (217 ms for the 869-call tokens case, 871 ms for worker 10x); they came from CPU contention, not from the code. Use `time.process_time()`.

M2 test (`m2_byte_identity_test.py`, `m2_state_sequence_driver.py`, report `md/m2_byte_identity_test.md`): 1328 checks. The driver patches `os.get_terminal_size` (so no tmux needed) and replays 47 steps per pane on two real sessions (869 calls/35 turns, 460 calls/104 turns) against old (`git archive integration`) and new trees, comparing built output, line map, copy rows, nav, scroll, width per step. Steps: 7 hover moves, scroll, expand/collapse in visible and oldest turns, copy feedback on/off (forced far-future expiry to avoid timing dependence), response entry added / mutated in place / replaced, search commit + n/N + hover + cancel + no-match, width 120 -> 50 -> 120, new turn appended, last turn grown twice, empty turns and restore with a new list. Every hover step also asserts 0 turn renders in the new tree (counted by wrapping `_render_turn_lines`). Mutation checks: removing the response-data check or the flash check makes the harness fail at the expected steps. `dev/panes/render_byte_identity.py` hash is identical old vs new (02e15f4f...).

## Notes for a successor
- The 4-tuple footgun of `format_cache_tracker` on empty turns from older notes no longer exists: the empty branch returns 5 values; kept as is.
- Real sessions on this machine are small in call count (largest by size, 205 MB, holds only 7 turns; most calls are elsewhere). "Large session" flicker therefore already appears at a few hundred calls.
- macOS `sed -i` needs a backup-suffix argument; use python for edits. Do not print full screen diffs from the tests (thousands of characters); the harness prints row/token of the first difference.
- Hypotheses, not observed: the proxy panes' `format_proxy_block` rebuild (other worker's scope) is probably the dominant cost there; tmux server restart to 3.7c is needed to see mode 2026 take effect.
- Out of scope this cycle and still clear-then-print: warnings, workers, gpu, news panes.
