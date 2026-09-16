# dev/proxy_dual_log/test_composition_invariant/

## Role
CI-style regression test plus the underlying multi-pass span-composition probe it imports as a
module. One unit of `dev/proxy_dual_log/` (see the area's own DOCS.md); split out because its 5
files import only each other.

## Public Interface
No `__init__.py` in this directory. Entry paths: `./venv/bin/python
dev/proxy_dual_log/test_composition_invariant/test_composition_invariant.py` (regression test,
synthetic fixture) and `./venv/bin/python
dev/proxy_dual_log/test_composition_invariant/composition_probe.py` (manual probe, real corpus).

## Flow
`test_composition_invariant.py` loads a synthetic fixture corpus and asserts the two composition
invariants hold for every modified block via `composition_probe`'s span algebra.
`composition_probe.py` runs the same span algebra over the real dual-log corpus and writes a
Markdown report.

## Modules

### test_composition_invariant.py (116 LOC)

**Purpose:** CI-style regression test asserting the two composition invariants hold for every
modified block in a synthetic fixture corpus.
**Reads:** `fixtures/invariant_corpus.jsonl` (the fixtures directory stays at the area root,
`dev/proxy_dual_log/`, not in this subfolder).
**Writes:** PASS/FAIL summary to stdout; exits 1 on any invariant violation.
**Called by:** none — manual CLI, exit code suitable for CI use.
**Calls out:** `composition_probe` (same-directory module, re-exports helpers from its sibling
modules).

---

### composition_probe.py (213 LOC)

**Purpose:** CLI entry point proving multi-pass span composition over the original content,
validating two reconstruction invariants across the corpus.
**Reads:** the full dual-log corpus (`*_original.jsonl` and siblings) present at run time.
**Writes:** `01_reports/composition_probe_<date>.md` (the reports directory stays at the area root,
`dev/proxy_dual_log/`, not in this subfolder).
**Called by:** `test_composition_invariant.py` (imports it as a module); otherwise run manually.
**Calls out:** `src.proxy.strip_bg_completed`; `composition_probe_ops.py`, `_passes.py`, `_corpus.py`.

---

### composition_probe_ops.py (145 LOC)

**Purpose:** The span algebra — cache_control strip, inner-text extraction, op extraction, the core
span-list edit primitive, and invariant checking.
**Reads:** nothing — pure data transforms.
**Writes:** nothing.
**Called by:** `composition_probe.py`, `_passes.py`, `_corpus.py`, `test_composition_invariant.py`.
**Calls out:** none.

---

### composition_probe_passes.py (61 LOC)

**Purpose:** Runs the 8 production proxy passes plus wakeup-dedup in sequence, collecting per-block
ops from each pass's real return value.
**Reads:** message list passed in by the caller.
**Writes:** nothing — returns `(final_messages, ops_by_msg_blk)`.
**Called by:** `composition_probe.py`, `_corpus.py`, `test_composition_invariant.py`.
**Calls out:** `src.proxy.rules`; `composition_probe_ops.py`.

---

### composition_probe_corpus.py (147 LOC)

**Purpose:** Scans the 5 fixed corpus stems, running every modified block through the pass chain
and aggregating pass/fail stats.
**Reads:** the 5 fixed `LOG_STEMS`' `_original.jsonl` files under `src/logs/dual_log`.
**Writes:** nothing — returns stats dicts.
**Called by:** `composition_probe.py`.
**Calls out:** `composition_probe_ops.py`, `_passes.py`.

---

## State
No shared or mutating state across modules. `test_composition_invariant.py`, `composition_probe.py`,
and `composition_probe_corpus.py` each independently resolve `_AREA_ROOT`/`_PROJECT_ROOT` (by
walking up from `__file__` until the directory named `proxy_dual_log` is found); the dual-log
corpus lookup in `composition_probe_corpus.py` falls back from the project root to the
main-checkout root (stripping a trailing `.claude/worktrees/<name>` when present) if the direct
path doesn't exist. All 5 of `composition_probe_corpus.py`'s fixed `LOG_STEMS` are currently
rotated off disk — `run_corpus()` skips each missing stem (existence-checked, returns zero-stats),
but `get_money_shot_case()` has no such guard and raises `FileNotFoundError`, caught by
`composition_probe.py`'s own `_emit_money_shot` and embedded as an `ERROR:` block in the report.
