# Comment/Docstring Conformance — Milestone B (dual_log_cli, proxy)

Continuation of the phased sweep applying the "only `# INFRASTRUCTURE` / `# ORCHESTRATOR` /
`# FUNCTIONS`" comment rule to `src/`. This entry covers milestone B: every `.py` under
`src/dual_log_cli/` (21 files) and `src/proxy/` (32 files). Triage (which comment became which
DOCS.md/Gotcha relocation vs. straight deletion) was produced by Main ahead of the worker session
(`triage_part1.md`/`triage_part2.md`) and is not repeated here; this entry records the execution,
the judgment calls the triage left to the worker, and the verification methodology.

## Scope and result

53 `.py` files touched, 1429 comment/docstring hits removed (scanner: `ast` docstring walk +
`tokenize` comment walk, excluding the three allowed marker strings and a line-1 shebang).
`git diff --stat`: 123 insertions / 1534 deletions across the milestone. A post-edit run of the
same scanner over both packages reported zero hits; `py_compile` and an import smoke over all 53
modules both passed; `dev/dual_log_cli/tests/test_*.py` (13 files) passed identically to the
pre-edit baseline captured before touching any file.

## Exception relocations applied

- `src/dual_log_cli/__main__.py` — the module docstring was runtime data (`epilog=__doc__` in
  `_parse_args`), not documentation, so it does not fall under the default-delete rule. Moved
  verbatim into a new `_USAGE_EPILOG` module-level constant in the INFRASTRUCTURE section;
  `_parse_args` now passes `_USAGE_EPILOG` where it passed `__doc__`. `--help` and
  `reqs --help` output captured before and after the change and diffed empty (byte-identical).
  `src/dual_log_cli/DOCS.md`'s `__main__.py` Purpose paragraph was rewritten to describe the
  constant instead of `__doc__` — the old text ("the top-level module docstring", "make
  `epilog=__doc__` work") was about to become factually wrong about the code's current shape.
- `src/dual_log_cli/render_msgs.py` (lines 6-11, column-width constants + `_BLOCK_INDENT` note) —
  new Gotcha appended to `src/dual_log_cli/DOCS.md`, placed next to the existing, closely-related
  "block sub-line chars column anchored to parent" Gotcha. The triage instructed comparing only
  against the render_msgs.py module's own Purpose paragraph (not the whole Gotchas section) before
  deciding whether content was already covered — it wasn't, in that narrower sense, so the full
  text was added even though a same-idea Gotcha already existed nearby; executed literally per
  triage rather than judged for redundancy, since triage explicitly reserves that judgment call to
  itself ("the worker executes exactly these and decides nothing").
- `src/proxy/addon.py` (lines 21-25, `_TrailerCrashFilter` rationale) — new Gotcha appended to
  `src/proxy/DOCS.md`.
- `src/proxy/payload_helpers.py` line 157 (`# noqa: E731`) — deleted per the triage's explicit
  linter-directives-are-comments-too instruction.

Everything else in scope was a straight deletion — the triage had already confirmed the content
was covered by the package's DOCS.md, including two module docstrings that looked candidate for
relocation but grep-confirmed were never read as `__doc__` anywhere (`src/proxy/strip_vocab.py`'s
module docstring and `classify_req`'s function docstring) and two method docstrings on
`ProxyAddon.responseheaders`/`response` in `addon.py`.

## Layout markers added

Two modules named in the triage's layout-marker list as missing a `# FUNCTIONS` section:

- `src/proxy/rules_config.py` had zero section markers at all before this pass. Added
  `# INFRASTRUCTURE` above the imports/constants and `# FUNCTIONS` above `_load_config` — no
  `# ORCHESTRATOR` marker, matching the precedent of other no-single-entry-point utility modules in
  the same package family (`project_map.py`, `discovery.py`): the module's closest-to-orchestrator
  function (`_load_system2_rules`) contains real filtering logic of its own, not a pure
  calls-other-functions dispatch, so it does not qualify as an ORCHESTRATOR function under the
  module-layout rule's own definition.
- `src/proxy/strip_interrupt_marker.py` had `# INFRASTRUCTURE` and `# ORCHESTRATOR` but no
  `# FUNCTIONS`. Added it above `_is_interrupt_marker` — the one non-orchestrator function, which
  happens to sit textually *before* the existing `# ORCHESTRATOR` marker. Following the triage's
  literal placement instruction ("above the first function that is not the orchestrator") produces
  a section order of INFRASTRUCTURE → FUNCTIONS → ORCHESTRATOR in this one file, deviating from the
  nominal INFRASTRUCTURE → ORCHESTRATOR → FUNCTIONS order — the triage's own "nothing else
  reordered" constraint forbids moving the code to fix that, so the marker went exactly where
  instructed rather than where the nominal order would put it.

`src/proxy/addon_state.py` (0 scanner hits, explicit utility-module exemption in the triage) was
left untouched.

## Verification methodology

Baselines were captured before any edit: 13/13 `dev/dual_log_cli/tests/test_*.py` PASS; `--help`
and `reqs --help` text; and, for the two proxy byte-identity harnesses
(`dev/proxy/pipeline_byte_identity.py`, `dev/proxy/addon_hook_byte_identity.py`), a pinned snapshot
of one real `*_original.jsonl` copied to a fixed `/tmp` path and referenced via each harness's own
`_LOG` env-var override — both harnesses otherwise pick the newest-mtime dual-log file by default,
which would have been this very session's own actively-growing log (the same before/after-pinning
problem milestone A1 already ran into with its own live-data harnesses). With the override set,
both harnesses reproduced the identical hash after the edit
(`pipeline_byte_identity.py`: `5e18e447f9567e7536e3116f164c5e4764ac269438f0d855264994748e84eb34`;
`addon_hook_byte_identity.py`: `7523f7db62ff4158aa69655d5863a9f6e0baf3d9cc8a77d345beb6382cd59251`).
All other listed harnesses/probes (`test_strip_fix.py`, `test_role_keyed_rules.py`,
`proxy_bgcomplete_tests.py`, the three `proxy_176_*_tests.py`, `test_composition_invariant.py`,
`p2_bg_escape_probe.py`) passed with the same counts before and after; the one report file
`p2_bg_escape_probe.py` writes to `dev/bg_wakeup_id_line/md/` was deleted before committing, per
the dev/ convention that one-shot run artifacts do not get staged.

## Cross-references

See `process-docs/dual_log_cli/` and `process-docs/proxy/` for the unrelated substantive history
behind the modules touched here — this entry is about the comment-removal mechanics only.
