# dev/proxy_dual_log/

## Role

Verification suite for the dual-log quartet (`_original`/`_forwarded`/`_stripped`/`_injected`)
written by `src/proxy/addon.py`. Proves losslessness of the forwarded-delta log, and completeness
of the strip/inject diff engine. Touch when changing the dual-log write side, the diff engine, or
read-side badge/render logic. Do not add features beyond verification.

## Public Interface

No `__init__.py` in this directory. Entry path: run each script directly, e.g.
`./venv/bin/python dev/proxy_dual_log/attribution_coverage/attribution_coverage.py` (most scripts
expect to be run from the project root so their own `sys.path`/`from src.` setup resolves). Eight
entry scripts live one level deeper, in a subfolder named after themselves (see Modules below);
five single-file scripts live directly in this directory.

## Flow

A script reads one or more dual-log JSONL files (real corpus data or synthetic fixtures). It
replays the delta chain, or runs the real `src/proxy`/`src/proxy_display` functions directly, over
that data. It either asserts an invariant via `check()`/exit code, or builds Markdown report lines
and writes them to its own `*_reports/`/`md/` directory at this area's root — output directories
never move into a subfolder, even for scripts that do. Every script resolves its own area root by
walking up from `__file__` until a directory named `proxy_dual_log` is found, then derives the
project/worktree root as two levels above that; a handful additionally derive the main-checkout
root specifically for the dual-log corpus, since that data is gitignored and worktree-local copies
never have it (see `process-docs/proxy_dual_log/` for the exact split and why the corpus lookup
keeps its pre-existing two-candidate fallback rather than being collapsed to one).
Converted suites run as parallel strands through `dev/refactoring/strand_runner.py`: `python <file>` starts one subprocess per strand (`--strand <name>`), each strand aborts at its first failing `check`, sibling strands still finish, and the exit code is 1 if any strand aborted. The strand names are the module constant `_STRANDS`.

## Modules

### verify_delta.py (279 LOC)

**Purpose:** Reconstructs the full forwarded payload from a `_forwarded.jsonl` delta stream and
verifies element counts match the delta's declared counts.
**Reads:** an `_original.jsonl` + `_forwarded.jsonl` pair (positional or `--original`/`--forwarded`).
**Writes:** a per-request table and PASS/FAIL summary to stdout.
**Called by:** none — manual CLI, exits 1 on a hard-check failure.
**Calls out:** none at import time — parses JSONL directly.

---

### tt_delta_skip_replay.py (279 LOC)

**Purpose:** Replays an `_original.jsonl` through the real modification/delta-build/accumulator
pipeline to prove the total_tokens badge-suppression fix.
**Reads:** a dual-log stem's `_original`/`_stripped`/`_injected` triplet under the main checkout's
`src/logs/dual_log`.
**Writes:** PASS/FAIL classification report to stdout.
**Called by:** none — manual CLI, exits 1 if a class regresses.
**Calls out:** `src.proxy.rules`, `src.proxy_display.dual_log_accumulator`, `src.proxy_display.proxy_badge`.

---

### diff_strip_inject.py (255 LOC)

**Purpose:** Span-level strip/inject diff of an original vs. forwarded proxy log pair, classifying
spans as equal/stripped/injected via `difflib`.
**Reads:** an `_original.jsonl` + `_forwarded.jsonl` pair (positional or `--original`/`--forwarded`).
**Writes:** per-request diff sections with IDENTICAL/REPLACED/STRIPPED/INJECTED tags to stdout.
**Called by:** none — manual CLI.
**Calls out:** `src.proxy.diff_engine`.

---

### proxy_176_agent_types_tests.py (148 LOC)

**Purpose:** Unit tests for the CC 2.1.176 agent-types system-reminder strip and its attribution
code.
**Reads:** nothing — synthetic in-script fixture text.
**Writes:** PASS/FAIL lines to stdout.
**Called by:** none — manual CLI.
**Calls out:** `proxy.message_passes`, `.strip_inject_delta`, `.diff_engine`, `.logging`,
`.rule_ops` (via direct `sys.path` insertion, 2 levels up from this file's fixed root-level
location).

---

### proxy_176_strip_tests.py (171 LOC)

**Purpose:** Unit tests for two CC 2.1.176 proxy drift fixes — the Workflow tool blocklist entry
and the role=system message strip.
**Reads:** nothing — synthetic in-script fixture text.
**Writes:** PASS/FAIL lines to stdout.
**Called by:** none — manual CLI.
**Calls out:** `proxy.tools`, `.message_passes`, `.strip_inject_delta`, `.diff_engine`, `.logging`
(via direct `sys.path` insertion, 2 levels up from this file's fixed root-level location).

---

### A_render_refactor_proof/ (3 modules — see its own `DOCS.md`)

Byte-identical differential test harness for the proxy_display render cluster (capture/verify
modes over 14 synthetic cases).

---

### attribution_coverage/ (4 modules — see its own `DOCS.md`)

Read-only coverage analysis of the dual-log corpus — can every stripped/injected entry be
attributed to a proxy function?

---

### green_overlay_probe/ (3 modules — see its own `DOCS.md`)

Reproduces a green-overlay false-injection bug and validates a char-level diff fix.

---

### groundtruth_message_spans_probe/ (4 modules — see its own `DOCS.md`)

Validates the ground-truth span-construction algorithm that replaces blind diffing for messages.

---

### main_log_elimination_probe/ (5 modules — see its own `DOCS.md`)

Feasibility probe on eliminating the main proxy log in favor of the dual-log quartet.

---

### proxy_176_bg_launch_ack_tests/ (5 modules — see its own `DOCS.md`)

Unit tests for the CC 2.1.176 background-launch-ack strip across all 3 observed wordings.

---

### span_inline_probe/ (4 modules — see its own `DOCS.md`)

Compares the Form A vs Form B inline-render data model on one fixed recorded session's blocks.

---

### test_composition_invariant/ (5 modules — see its own `DOCS.md`)

CI-style regression test plus the underlying multi-pass span-composition probe it imports as a
module.

---

## State

No shared or mutating state across modules or subfolders. Each CLI entry point owns its own
report-writing (`REPORT_DIR`/`_REPORT_DIR` constants, always anchored at this area's root via the
`_AREA_ROOT` walk, never at a subfolder); sibling helper modules are pure functions with no
module-level mutable state, except `tt_delta_skip_replay.py`'s `has_content_map`, which
monkeypatches and restores `_accumulator._msgs_delta_is_substantial` for the duration of one
baseline comparison call. `md/`, `json/`, `fixtures/`, and every `*_reports/` directory are this
area's shared bus, read/written across whichever unit needs them, and never move.
