# dev/native-model-start/

## Role
Verification scripts for starting the orchestrator's main CC session natively on a chosen model.
Covers the launcher's `--fable`/`--opus`/`--model` argument precedence (`src/claude_proxy_start.sh`),
the proxy's per-model `model_params` injection path (`src/proxy/inject_helpers.py`), and a live-verify
of the CC 2.1.223 pin bump (cache breakpoint stability, dual-log composition integrity, strip-wording
coverage) against two recorded 223-era sessions. Touch when changing the launcher's flag precedence or
`inject_helpers.py`'s model-override resolution; the 223 pin-bump probes are historical live-verify
records and don't need re-running unless the same class of pin bump recurs. `md/` holds every script's
report.

## Flow
Each script drives real production code (the launcher's parse loop mirrored in bash, or a real
`ProxyAddon`/`apply_modification_rules` instance) against synthetic argv or recorded dual-log payloads,
then asserts specific invariants and writes a timestamped report to `md/`.

## Modules

### p1_arg_parse_dry_run.sh (154 LOC)

**Purpose:** Dry-runs the `--fable`/`--opus`/`--model` precedence logic mirrored verbatim from
`src/claude_proxy_start.sh`'s parse loop — 8 cases covering explicit-vs-shortcut precedence,
position-independence, and last-shortcut-wins ordering. Never starts the proxy or claude.
**Reads:** nothing persistent — pure in-process argv simulation.
**Writes:** `md/p1_arg_parse_dry_run_<timestamp>.md`.
**Called by:** none — manual regression guard, re-run after editing `claude_proxy_start.sh`'s parse loop.
**Calls out:** stdlib bash only.

---

### p2_model_params_probe.py (356 LOC)

**Purpose:** Verifies `src/proxy/inject_helpers.py::_inject_model_override` — the per-model
`model_params` config lookup (exact model-id match, never writes `model`) vs. the legacy
family-bucketed `model_override`/`model_override_worker` fallback, plus the fixation mechanism that
pins a resolved override to a caller-owned dict across calls. 12 test groups, 55 checks.
**Reads:** nothing persistent — builds all fixtures in-process, config injected via
`mock.patch.object(inject_helpers, "_load_config", ...)`.
**Writes:** `md/p2_model_params_probe_<timestamp>.md`.
**Called by:** none — manual regression guard, re-run after changing `_inject_model_override` or its
fixation mechanics.
**Calls out:** `src.proxy.inject_helpers`.

---

### p3_cache_breakpoints_probe.py (311 LOC)

**Purpose:** Replays every recorded request from two 223-era sessions through a real `ProxyAddon()`
instance in order (fresh addon per session) and checks breakpoint positional stability (BP1
`system[2]`, BP2 last non-defer tool) and message-content diffs at shared indices.
**Reads:** recorded dual-log `_original.jsonl` pairs under src/logs/dual_log (gitignored runtime data,
session stems `api_requests_opus_posts_1786051932` and `api_requests_opus_websearch_1786052022`).
**Writes:** `md/p3_cache_breakpoints_probe_report.md`.
**Called by:** none — manual, historical 223 pin-bump live-verify.
**Calls out:** `src.proxy.addon` (`ProxyAddon`, `_derive_worker_context`).

---

### p4_dual_log_integrity_probe.py (237 LOC)

**Purpose:** Verifies the composition invariant (C0/Cfwd reconstruction from recorded ops matches
`compose_block`) and top-level payload/schema stability, on the same two 223-era sessions as `p3_`.
**Reads:** the same two `_original.jsonl` files as `p3_cache_breakpoints_probe.py`.
**Writes:** `md/p4_dual_log_integrity_probe_report.md`.
**Called by:** none — manual, historical 223 pin-bump live-verify.
**Calls out:** `src.proxy.rules` (`apply_modification_rules`), `src.proxy.diff_engine`
(`compose_block`, `_get_inner_text`).

---

### p5_strip_wordings_probe.py (207 LOC)

**Purpose:** Checks bg-launch-ack / bg-completed / task-notification strip coverage on 223-era
wordings — a fn_map census over the recorded `_stripped`/`_injected` dual-logs, plus a replay sweep
through the current `apply_modification_rules` for any surviving marker string.
**Reads:** the same two sessions' `_original.jsonl` + `_stripped.jsonl` + `_injected.jsonl` files.
**Writes:** `md/p5_strip_wordings_probe_report.md`.
**Called by:** none — manual, historical 223 pin-bump live-verify.
**Calls out:** `src.proxy.rules` (`apply_modification_rules`), `src.proxy.payload_helpers`
(`_top_level_content_contains`).

---

## Gotchas
- The two 223-era recorded sessions under src/logs/dual_log are live/growing corpus files — a re-run
  shifts denominators (composition-block and marker-occurrence counts change run to run) but does not
  change the CLEAN/FINDING classification itself.
- `p3_`'s cache-content comparison needs TWO shape normalizations before comparing message content
  across requests: `cache.py`'s own `_normalize_user_content_shape` (role='user' only), plus a second
  normalization for `_add_cache_control_to_message`'s string-to-single-block wrapping (applies to ANY
  role). Skipping the second normalization produces large false-positive "content changed" counts.
- The ready-to-paste `model_params` JSON values for `~/.claude/shared-rules/proxy_rules.json` are not
  in this directory — see `process-docs/native-model-start/` (user config outside the repo, never
  edited by any script here).
