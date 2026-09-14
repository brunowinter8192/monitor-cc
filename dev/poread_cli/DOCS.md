# dev/poread_cli/

## Role

Regression suite for `src/poread_cli/__main__.py` — the CLI half of the poread mechanism. Proves
the CLI's own boundary behavior (valid file, oversize file, missing file, directory, bad argv) in
isolation, calling `main()` directly rather than through a subprocess. Touch this directory when
changing `src/poread_cli/__main__.py`'s argument handling, size-ceiling check, or marker format.
The end-to-end proof that a marker this CLI mints is correctly recognized and expanded by the
proxy lives in `dev/proxy/poread_inject_tests.py` instead (it invokes this CLI as a real
subprocess to mint its fixtures, rather than duplicating this suite).

## Flow

Each test calls `src.poread_cli.__main__.main(argv)` directly with `sys.stdout`/`sys.stderr`
redirected to `io.StringIO()`, captures the return code and both streams, and asserts against them
— no subprocess, no real clipboard/terminal dependency.

## Modules

### test_poread_cli.py (138 LOC)

**Purpose:** Unit-level regression guard for `main()`'s five boundary cases — valid file, oversize
file (refused before ever being opened), missing file, directory path, malformed argv.
**Reads:** nothing external — builds its own temp files/directories per test, cleans them up.
**Writes:** stdout (pass/fail via `check()`); no filesystem writes outside its own temp fixtures.
**Called by:** none — manual regression guard, re-run after any change to
`src/poread_cli/__main__.py`.
**Calls out:** `src.poread_cli.__main__` (`main`), `src.constants` (`POREAD_MAX_BYTES`,
`POREAD_HASH_LEN`, `POREAD_MARKER_PREFIX`).
