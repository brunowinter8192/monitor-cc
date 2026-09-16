# 2026-09-16 — Comment/docstring salvage for dev/proxy_display/ standards conformance

## Context for whoever picks this up

Milestone: bring `dev/proxy_display/` (2 `.py` files) into conformance with the project's
three-marker comment standard. Zero `__doc__`/`argparse` hits — both docstrings found here (one
per file) were not load-bearing and deleted outright.

**Confirmed safe and run for real, via the script's own designed-in pinning seam.**
`render_byte_identity.py` already ships its own `RENDER_BYTE_IDENTITY_LOG_DIR` override env var
(documented in its own now-salvaged docstring and in DOCS.md) for exactly the live-growing-log
determinism problem — pinned a frozen real dual-log quartet
(`api_requests_worker_52fce57c_wsrefactor_1789506614_{forwarded,stripped,injected,original}.jsonl`,
39 entries, copied to `/tmp/pd_fixture/`) and exported that env var for both before/after runs.
Ran before and after the edit: **identical** `entries: 39`, `expand_states keys: 555`, and
`HASH: 12aa3ce46c1b52b1767ef13052d4c3c19f8da9304a5a8413947e8ee85c017f0d` both times.
`test_standalone_sidecar.py` is fully synthetic — ran before/after, stdout diffed byte-for-byte
identical (`8/8 checks passed` both times).

---

## Salvage from dev/proxy_display/render_byte_identity.py

Module docstring (was lines 1-20):
```
Byte-identity regression harness for the proxy_display render cluster (format.py,
render_turn.py, render_sections.py, render_messages.py, forwarded_parser.py).

Reconstructs entries from a real forwarded dual-log (newest *_forwarded.jsonl under
src/logs/dual_log/), attaches the stripped/injected/original overlays exactly like
pane.py does, grows expand_states until every drill-down key (sys/tools/think/etc.)
that a render pass can discover has been visited, then hashes:
  - format_proxy_block's full (ansi_string, total_lines) output at several pane widths
  - render_system_blocks / render_tools / render_messages called directly per entry,
    per width (these are NOT fully covered by format_proxy_block's own viewport slice
    when pane_height is small, so this widens coverage beyond what a scrolled pane
    shows)

Usage (from project root):
    ./venv/bin/python dev/proxy_display/render_byte_identity.py

Prints a single HASH line. Run before and after a render-cluster refactor; the hash
must match. Reads only — never writes or commits any log content.
```

Was lines 31-33 (above `_MAIN_LOG_DIR`):
```
# RENDER_BYTE_IDENTITY_LOG_DIR overrides the source directory — used to pin a before/after
# comparison to the exact same bytes when the default (newest log under the live MAIN checkout)
# would otherwise keep growing between two runs of this script (e.g. this very session's own log).
```

Was lines 86-89 (above `_grow_expand_states`):
```
# Repeatedly render (item_positions_out captures every key the render pass produced,
# regardless of viewport) and flip every newly-seen key to expanded, until no new key
# appears — at that point every reachable drill-down (sys/tools/think/beta/ctx/fields/
# stripped_tool) has been visited at least once.
```

## Salvage from dev/proxy_display/test_standalone_sidecar.py

Module docstring (was lines 1-21):
```
Regression guard for `format._is_standalone_entry`'s coverage of the CC-internal zero-tool sidecar
call (session-titling, quota check, security-monitor) in the proxy pane's REQ numbering.

Every sidecar shape observed on disk (33/33 entries across 20 `_forwarded.jsonl` files at
investigation time, all `claude-haiku-4-5-20251001`, `tools == 0`, 1 message) is a haiku-model
call — `_is_standalone_entry`'s existing `'haiku' in model` branch already excludes every one of
them from the numbered `#N` REQ sequence, confirmed both by this file's Test 2 and by
`render_byte_identity.py` coming out byte-identical against a real log containing 2 sidecar
entries. A widened `tools == 0`-regardless-of-model predicate was tried and reverted — see
process-docs/proxy_instrumentation/ for the measurement (a repo-wide scan of every
`_forwarded.jsonl`/`_original.jsonl` on disk found zero non-haiku, zero-tool entries) and the
reasoning (the same predicate has four callers across the package, and widening it changes
behavior for a real zero-tool conversation request too, not just a hypothetical sidecar, with
nothing in real data to justify the change). `tools_total_chars == 0` (mirroring
`dual_log_cli.timeline_boundaries._is_sidecar`'s `counts.tools == 0`, model-agnostic) remains the
precise criterion to switch to if a non-haiku sidecar is ever actually observed.

Run (from project root or worktree root):
    ./venv/bin/python dev/proxy_display/test_standalone_sidecar.py
```

Was line 48 (above `test_is_standalone_entry_observed_shapes`):
```
# Test 1 — unit coverage of the shapes _is_standalone_entry actually handles today.
```

Was lines 87-89 (above `test_haiku_sidecar_does_not_consume_a_req_number`):
```
# Test 2 — end to end: a haiku sidecar (the only shape observed in real data) sharing the real
# conversation's non-haiku family, sitting between two real requests, must not consume a REQ
# number — REQ 1, H, REQ 2, not REQ 1, REQ 2, REQ 3.
```

## Salvage from dev/proxy_display/DOCS.md

The pre-rewrite `DOCS.md` carried a trailing `## Gotchas` section that has no place in the
mandated DOCS.md format (Role / Public Interface / Flow / Modules / State only). Cut verbatim:

```
## Gotchas
- The default log source (newest quartet under src/logs/dual_log) is live and growing — a concurrent
  session's own proxy log can become "newest" between two runs. Set `RENDER_BYTE_IDENTITY_LOG_DIR` to
  a fixed directory holding a frozen copy of one quartet to pin a before/after comparison.
```

This content is preserved here in full; it is not carried into the rewritten DOCS.md.
