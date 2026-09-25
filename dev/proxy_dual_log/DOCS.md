# dev/proxy_dual_log/

## Role
Verification suite for the dual-log quartet (original, forwarded, stripped, injected) written by `src/proxy/addon.py`: losslessness of the forwarded delta log and completeness of the strip/inject diff engine. Touch when changing the dual-log write side, the diff engine or read-side badge and render logic. Verification only.

## Public Interface
No `__init__.py`. Each script is run directly from the project root. Eight entry scripts live one level deeper in a subfolder named after themselves; five single-file scripts live in this directory.

## Flow
A script reads dual-log JSONL files (real corpus or synthetic fixtures), replays the delta chain or runs real proxy and display functions over the data, and asserts an invariant or writes a Markdown report to a report directory at this area's root.
Each script derives the area root by walking up from its own file; scripts needing the gitignored corpus also derive the main-checkout root (see process-docs).
Converted suites run as parallel strands through the strand runner in `dev/refactoring/`.

## Modules

### verify_delta.py (281 LOC)

**Purpose:** Reconstructs the full forwarded payload from a forwarded delta stream and verifies element counts match the declared counts.
**Reads:** an original and forwarded log pair.
**Writes:** a per-request table and summary to stdout.
**Called by:** none; manual CLI, exits 1 on a hard-check failure.
**Calls out:** none at import time.

---

### tt_delta_skip_replay.py (278 LOC)

**Purpose:** Replays an original log through the real modification, delta-build and accumulator pipeline to prove the token-badge suppression fix.
**Reads:** one stem's original, stripped and injected logs under the main checkout's dual log.
**Writes:** a classification report to stdout.
**Called by:** none; manual CLI, exits 1 if a class regresses.
**Calls out:** `src.proxy.rules`, `src.proxy_display.dual_log_accumulator`, `src.proxy_display.proxy_badge`.

---

### diff_strip_inject.py (253 LOC)

**Purpose:** Span-level strip/inject diff of an original versus forwarded log pair, classifying spans as equal, stripped or injected.
**Reads:** an original and forwarded log pair.
**Writes:** per-request diff sections to stdout.
**Called by:** none; manual CLI.
**Calls out:** `src.proxy.diff_engine`.

---

### proxy_176_agent_types_tests.py (148 LOC)

**Purpose:** Unit tests for the CC 2.1.176 agent-types system-reminder strip and its attribution code.
**Reads:** nothing; synthetic fixture text.
**Writes:** stdout only.
**Called by:** none; manual CLI.
**Calls out:** the message-pass, delta, diff, logging and rule modules of `src/proxy`, via a direct path insert.

---

### proxy_176_strip_tests.py (171 LOC)

**Purpose:** Unit tests for two CC 2.1.176 proxy drift fixes: the Workflow tool blocklist entry and the system-role message strip.
**Reads:** nothing; synthetic fixture text.
**Writes:** stdout only.
**Called by:** none; manual CLI.
**Calls out:** the tools, message-pass, delta, diff and logging modules of `src/proxy`, via a direct path insert.

---

## Sub-directories

- `A_render_refactor_proof/`: Byte-identical differential harness for the proxy_display render cluster. See its own `DOCS.md`.
- `attribution_coverage/`: Read-only coverage analysis: can every stripped or injected entry be attributed to a proxy function? See its own `DOCS.md`.
- `green_overlay_probe/`: Reproduces a green-overlay false-injection bug and validates a char-level diff fix. See its own `DOCS.md`.
- `groundtruth_message_spans_probe/`: Validates the ground-truth span-construction algorithm that replaces blind diffing for messages. See its own `DOCS.md`.
- `main_log_elimination_probe/`: Feasibility probe on eliminating the main proxy log in favor of the dual-log quartet. See its own `DOCS.md`.
- `proxy_176_bg_launch_ack_tests/`: Unit tests for the CC 2.1.176 background-launch-ack strip across all observed wordings. See its own `DOCS.md`.
- `span_inline_probe/`: Compares two inline-render data models on one fixed recorded session. See its own `DOCS.md`.
- `test_composition_invariant/`: CI-style regression test plus the span-composition probe it imports. See its own `DOCS.md`.

## State
No shared or mutating state across modules or subfolders. Each entry point owns its report writing, always anchored at this area's root; helper modules are pure. One replay script patches and restores an accumulator predicate within a single comparison call. The `md/`, `json/`, `fixtures/` and report directories are this area's shared bus and never move.
