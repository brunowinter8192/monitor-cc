# ProxyAddon collaborator-object split (2026-09)

## Task

`src/proxy/addon.py`'s `ProxyAddon` class carried 15 distinct `self.<attr>` (threshold: 10).
`request()` was 74 LOC and `response()` was 51 LOC (threshold: 50), and the file itself later hit
421 LOC (threshold: 400) after the first pass. Goal: split `ProxyAddon` into collaborator objects
by concern, get both hook methods under 50 LOC, keep the whole module under 400 LOC, with
byte-identical proxy behavior end to end.

## Concern grouping

`ProxyAddon`'s 15 attributes split cleanly into 4 groups by how they were actually used in
`request()`/`response()`, and these became 4 plain classes in a new `src/proxy/addon_state.py`:

- `DualLogPaths` — the six dual-log file `Path`s (previously `self.original_log_file` etc.)
- `DeltaState` — the five per-model-family delta-chain dicts (BP3 message summaries, forwarded/
  stripped/injected hash chains, error-id dedup set)
- `FixationState` — `fixated` (sys2/msg0 snapshot) + `model_params_fixated` (per-exact-model-id
  snapshot, owned by `inject_helpers._inject_model_override`)
- `SessionIdentity` — `session_id` + `worker_context`, both computed once at `__init__`

`ProxyAddon.__init__` ended up holding exactly 4 attributes (`self.paths`, `self.delta`,
`self.fixation`, `self.identity`) — plain classes were used over dataclasses, no particular reason
beyond matching the existing codebase's style in `addon.py` itself (no dataclasses anywhere else
in `src/proxy/`).

## Helper extraction for the 50-LOC hook ceiling

`request()`: extracted `_apply_sys_fixation` (capture/replay `fixation.fixated`),
`_stamp_request_metadata` (request-id/timestamp + metadata-bridge stash), `_finalize_cache_state`
(cache-control strip + breakpoints + prev-message-summary update), and
`_write_request_dual_logs` (folds the forwarded-delta write + errors write into one call — this
single fold was what got `request()` under 50 LOC; extracting the other three alone left it at
~58 LOC).

`response()`: extracted `_log_4xx_error` (the 4xx branch body) and `_write_stripped_injected` (the
success-branch body, called from inside `response()`'s own existing `try/except`).

## Second split: addon.py over 400 LOC

After the collaborator-object split, `addon.py` was 421 LOC — over the 400-LOC module ceiling,
caught in review. Fix: split by concern again, this time module-level rather than class-level.
Every function whose job is building/writing a dual-log JSONL entry (`_resolve_dual_log_file`,
`_write_entry`, `_log_original_request`, `_log_forwarded_delta`, `_log_errors_entries`,
`_write_request_dual_logs`, `_log_4xx_error`, `_write_stripped_injected`) moved to a new
`src/proxy/addon_dual_log.py` (147 LOC). What stayed in `addon.py` (286 LOC): the hook class itself
plus the request-PIPELINE helpers (fixation, cache-state, metadata-stamping, model-family
inference, request-shape checks, session/worker-identity derivation). Grepped `src/` and `dev/` for
every one of the 8 moved names first — none had an external importer, so the move needed zero
re-pointing outside `addon.py`'s own import line, and no re-export shim was needed.

## Re-pointing

Grepped every `self.<attr>` name that moved, across `src/` and `dev/` (excluding `src/logs/`,
`process-docs/`). Found no external reader of any of the 15 original attributes except one pattern:
3 dev/ scripts construct a real `ProxyAddon()` and then reach in and overwrite
`addon._worker_context` directly, post-construction, to simulate a worker session without going
through `_derive_worker_context()`'s env-var path:

- `dev/bg_wakeup_id_line/p2_bg_escape_probe.py` — was passing (29/29) before the split; re-pointed
  to `addon.identity.worker_context = ...`, confirmed still 29/29 after.
- `dev/native-model-start/p3_cache_breakpoints_probe.py` — was already failing before any of this
  work (missing fixture file, `FileNotFoundError` unrelated to `ProxyAddon`'s shape); re-pointed
  for correctness, confirmed identical failure mode (same traceback) before and after.
- `dev/timer-loop/p3_project_scope_incident_probe.py` — was already non-runnable before any of
  this work (dead import `proxy.pending_bg_state`, self-documented SUPERSEDED in its own
  docstring); re-pointed for hygiene, confirmed identical failure (same traceback) before and
  after.

Functions imported directly from `proxy.addon` by other modules (`_derive_worker_context` in the
same 3 scripts plus `_filter_response_headers` in `dev/hook_smoke/test_header_capture.py`) kept
their name and module — neither was a "write helper" so neither moved in either split pass.

## Byte-identity harness: two bugs found while building it

`dev/proxy/addon_hook_byte_identity.py` is new — nothing else under `dev/proxy_dual_log/` or
`dev/proxy_instrumentation/` drives `ProxyAddon.request()`/`responseheaders()`/`response()` end to
end through a fake mitmproxy flow (the closest existing shape, a request-only fake flow with no
response side, lives in `dev/native-model-start/p3_cache_breakpoints_probe.py` and
`dev/bg_wakeup_id_line/p2_bg_escape_probe.py` — reused and extended with a `_FakeResponse`).

Building it surfaced two real bugs, both in the harness itself, not in `addon.py`:

1. **Import-order dependency on `MONITOR_CC_ROOT`.** `src/proxy/payload_helpers.py` resolves its
   own `sys.path` insert from `MONITOR_CC_ROOT` at import time (falling back to the real `src/`
   only when the env var is unset) — a pre-existing pattern, not something this task touched.
   Importing `ProxyAddon` AFTER pointing `MONITOR_CC_ROOT` at the harness's tempdir broke
   `from constants import TOOL_BLOCKLIST` inside that import chain (`ModuleNotFoundError:
   No module named 'constants'`). Fixed by importing `ProxyAddon` at module scope, before any env
   var mutation — the harness's own `_import_proxy_addon()` indirection exists only because dev/
   scripts are blocked from a bare top-level `from src....` import (`block_dev_imports_src`); the
   import itself still had to happen before `main()` repoints `MONITOR_CC_ROOT`.
2. **Non-deterministic hash from a leaked tempdir path.** The harness's first working version
   produced a DIFFERENT hash on every run of the identical, unmodified code. Traced to
   `tool_injection.py`'s `[tool_injection] WARNING: schema store missing at <path> — ...` message,
   printed to stderr on every run (the harness's tempdir has no `src/proxy/schemas/`) — `<path>`
   embeds `tempfile.TemporaryDirectory()`'s own fresh random path every run, and stderr is part of
   the hashed signal. Fixed by replacing the tmp_root substring with a fixed sentinel in the
   captured stderr text before hashing. Any future stderr-inclusive byte-identity harness that
   constructs real objects against a temp `MONITOR_CC_ROOT` should expect this same class of leak.

## Verification

`dev/proxy/pipeline_byte_identity.py` (pure-function pipeline, unaffected by either split since it
never touches `ProxyAddon`) stayed at hash `af57a28729bce8db123ce7d26019f0388278fb305b4d7fef59517dbdc92600c1`
across both split commits (60-line pinned snapshot, 17 payloads).

`dev/proxy/addon_hook_byte_identity.py` (new): hash `dd771ac18157443ff2a69ec067126bdc861dcd5fee3dff67a75a419d2345796a`,
identical across the collaborator-object split and the follow-up `addon_dual_log.py` split (same
17-payload pinned snapshot + 1 synthetic 4xx flow).

All 7 named regression tests (`test_strip_fix.py`, `test_role_keyed_rules.py`,
`proxy_bgcomplete_tests.py`, `proxy_176_agent_types_tests.py`, `proxy_176_bg_launch_ack_tests.py`,
`proxy_176_strip_tests.py`, `test_composition_invariant.py`) passed unchanged after both splits.

## Review-driven fixes (second pass)

Review caught two issues in the first submission: `addon.py` at 421 LOC over the 400 ceiling (fixed
via the `addon_dual_log.py` split above), and two `dev/bg_wakeup_id_line/md/p2_bg_escape_probe_*.md`
report files from an ad-hoc verification run of that script accidentally staged into the first
commit — removed from the branch (`git rm --cached` + delete) in the follow-up commit.
