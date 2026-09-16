# 2026-09-16 — Comment/docstring salvage for dev/panes/ standards conformance

## Context for whoever picks this up

Milestone: bring `dev/panes/` (2 `.py` files, 353 LOC) into conformance with the project's
three-marker comment standard. Every comment and both docstrings below were relocated here
verbatim before deletion from the code. Zero `__doc__`/`argparse` hits, so neither docstring was
load-bearing and both deleted outright.

**Both scripts confirmed safe to run and run for real.** Neither touches AppKit, tmux, hotkeys, or
any desktop primitive — pure computation over synthetic or real-but-read-only data.
`answering_model_line_test.py` is 100% synthetic. `render_byte_identity.py` reads one real session
JSONL for its `build_cache_turns` check; used the script's own designed-in
`PANES_BYTE_IDENTITY_JSONL` env-var override (documented in its own now-salvaged docstring and in
`DOCS.md`'s Gotchas) to pin a frozen 300-line prefix of a real session file
(`~/.claude/projects/-Users-brunowinter2000-Documents-ai-Meta-ClaudeCode-cli-gh-cli--claude-worktrees-buildlog/3588ff52-af31-43b9-b1e3-649863797ba9.jsonl`,
copied to `/tmp/panes_byte_identity_fixture.jsonl`) to a fixed path for both before/after runs —
exactly the mechanism this script exists to support, since the un-pinned default (newest session
file under the projects directory) can be actively growing mid-comparison. Both scripts ran with
identical output before and after the comment/docstring removal (see the completion checklist in
the task response for the exact hashes/output).

---

## Salvage from dev/panes/answering_model_line_test.py

Module docstring (was lines 1-10):
```
Unit-level regression guard for the M2 answering-model-in-token-pane milestone
(process-docs/proxy_instrumentation/).

Covers src/format/token_format.py's new _render_answering_model_line and the updated
_render_rate_limit_lines (both now read a full `_response` dual-log entry per request_id, not a
flat headers dict — src/proxy_display/side_logs.py's read_response_log changed shape to match).

Run: ./venv/bin/python dev/panes/answering_model_line_test.py
```

Was lines 37-38 (above `_import_target`):
```
# Imported via a function (not a module-level `from src.` line) — dev/ scripts may not use a
# literal top-level `from src.` import (block_dev_imports_src).
```

## Salvage from dev/panes/render_byte_identity.py

Module docstring (was lines 1-29):
```
Byte-identity regression harness for src/panes/ (panes-split milestone — token_pane.py /
warnings_pane.py / warnings_render.py concern split).

(1) build_cache_turns fed incrementally (in growing file-line chunks, mirroring how the real
    pane polls a growing session JSONL) over a frozen 300-line prefix of a real session JSONL
    under ~/.claude/projects/, hashing the resulting turns after EVERY chunk (not just the final
    state) — this is what actually exercises the duplicate-call merge path the function's own
    LOC-split touches.
(2) _format_warnings_pane over a synthetic tool_errors list (4 errors: mixed expanded/collapsed,
    one carrying _pre_strip_text/_stripped_chunks, one with a search match) at two pane widths,
    hashing (rendered_string, line_map).
(3) format_cache_tracker (src.format.token_format) over a synthetic 1-turn/2-call list with
    response_rid_map populated (rate-limit headers: utilization+reset for both 5h/7d windows,
    plus a non-'allowed' status and a non-'allowed' overage), expand_states all True, a
    copy_feedback entry with a future expiry, and a search query matching the turn/call — added
    for the tokens-data-render-helpers milestone (2026-09) specifically to cover the `rl:`/warn
    lines and the expanded content-blocks loop, which the workers-pane harness's own synthetic
    fixtures never populate. response_rid_map values are now full `_response` dual-log entries
    (M2, answering-model-in-token-pane milestone) — req-rl-1 carries a mismatching
    proxy_forwarded_model/answering_model pair (exercises the RED `model:` line), req-rl-2 has no
    entry at all (exercises the no-line case).

Usage (from project root):
    ./venv/bin/python dev/panes/render_byte_identity.py

Prints one HASH line. Run before and after the src/panes/ split; the hash must match. Never
commits a session-log snapshot — only reads (via a /tmp-pinned copy, see PANES_BYTE_IDENTITY_JSONL).
```

Was line 44, trailing on the `_CHUNK_SIZE` assignment:
```
_CHUNK_SIZE = 40  # lines appended per incremental build_cache_turns() feed step
```
(the comment token itself is `# lines appended per incremental build_cache_turns() feed step`)

Was lines 60-61 (above `_import_panes`):
```
# Imported via a function (not a module-level `from src....` line) — dev/ scripts may not use a
# literal top-level `from src.` import (block_dev_imports_src).
```

Was lines 69-71 (above `_session_jsonl`):
```
# PANES_BYTE_IDENTITY_JSONL overrides the source session path — pin a real *.jsonl's frozen
# 300-line prefix to a fixed /tmp path once, then point both before/after runs at it via the env
# var, same convention as dev/proxy/pipeline_byte_identity.py's own override var.
```

Was lines 96-97 (above `_hash_cache_turns`):
```
# Feeds the frozen prefix into build_cache_turns() in growing chunks (mirrors incremental polling
# of a real session file), hashing the resulting turns after EVERY chunk.
```

Was lines 120-123 (above `_make_tool_errors`):
```
# 4 synthetic tool_errors: [0] collapsed no-match, [1] expanded no-match with a strip overlay
# (_pre_strip_text/_stripped_chunks), [2] collapsed WITH a search match, [3] expanded WITH a
# search match (exercises both the collapsed-container-mark and expanded-substring-highlight
# paths in the same call).
```

Was lines 155-160 (above `_make_rate_limit_turns`):
```
# 1 turn / 2 calls, both with request_ids matched in response_rid_map — call 0 carries every
# usage-extras group (ttl/web/meta/iterations) plus rate-limit headers with a non-'allowed'
# status AND a non-'allowed' overage (exercises both the `rl:` line and the YELLOW warn line);
# call 1 has a plain content_blocks set (tool_use/thinking/text) with no rate-limit headers.
# Fixed (not "now"-relative) reset epochs so the same-day/other-day _fmt_rl_reset_time branch
# taken doesn't depend on which day this harness happens to run.
```

Was line 188, trailing on a dict-value line (inside `_make_rate_limit_turns`):
```
                'anthropic-ratelimit-unified-5h-reset': '1893456000',   # 2030-01-01, fixed
```
(the comment token itself is `# 2030-01-01, fixed`)

Was line 190, trailing on a dict-value line (same function):
```
                'anthropic-ratelimit-unified-7d-reset': '1893542400',   # 2030-01-02, fixed
```
(the comment token itself is `# 2030-01-02, fixed`)

Was line 205, trailing on a dict-value line (inside `_hash_format_cache_tracker`):
```
    copy_feedback = {(0, 0): 9999999999.0}   # far-future expiry -> is_flash branch
```
(the comment token itself is `# far-future expiry -> is_flash branch`)

## Salvage from dev/panes/DOCS.md

The pre-rewrite `DOCS.md` carried a trailing `## Gotchas` section that has no place in the
mandated DOCS.md format (Role / Public Interface / Flow / Modules / State only). Cut verbatim:

```
## Gotchas
- `PANES_BYTE_IDENTITY_JSONL` overrides the default session-JSONL source — needed because the
  default (newest session file under the projects directory) can itself be actively growing during a
  before/after comparison. Snapshot a session file's frozen line-prefix to a fixed path once, then
  point both runs at it via the env var.
- `format_cache_tracker`'s `nav_out` mixes tuple keys and a string key — check 3 stringifies every
  key before hashing (`json.dumps` with `sort_keys=True` cannot compare a tuple key against a string
  key); checks 1/2 don't hit this since their own dict keys are already homogeneous.
```

This content is preserved here in full; it is not carried into the rewritten DOCS.md.
