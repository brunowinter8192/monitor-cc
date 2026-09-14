# src/poread_cli/

## Role

Standalone CLI, invoked by an agent through Bash, that brings the full content of one named file
into the model's context without going through Bash's own ~30,000-character inline result ceiling.
It does this by printing only a short marker naming the file and its size — its own output always
stays far below that ceiling — and relying entirely on `src/proxy/inject_poread.py` to recognize
the marker inside the resulting `tool_result` and replace it with the file's full content in the
forwarded payload. This package owns only the marker-minting half; see `src/proxy/inject_poread.py`
for the recognition/replacement half and `src/proxy/DOCS.md` for how the two agree on the marker
shape and the shared size/hash-length constants in `src/constants.py`.

## Public Interface

`__init__.py` is a package marker only — no exports. The entry path is the module runner:

```bash
./venv/bin/python -m src.poread_cli <path>
```

Run from the project root, or via `bin/poread` (repo root, mode 755) once symlinked into PATH,
matching `bin/duallog`'s exact wiring — `poread <path>` from any cwd.

## Flow

`__main__.main(argv)` → one positional path argument → `os.path.realpath` resolution →
`os.path.getsize` against `constants.POREAD_MAX_BYTES` (checked BEFORE the file is ever opened, so
an oversize file is never read into memory just to be rejected) → on success, reads the file, hashes
it (`sha256`, truncated to `constants.POREAD_HASH_LEN`), prints exactly one line (the marker) to
stdout, exit 0. Any failure (missing path, not a file, unreadable, over the ceiling, malformed
argv) prints one reason to stderr, prints no marker, and exits non-zero — no truncated or partial
export is ever produced.

## Modules

### __main__.py (70 LOC)

**Purpose:** The whole CLI — argument parsing, size-ceiling tripwire, file read, marker emission.
**Reads:** The named file's bytes and size from disk; argv.
**Writes:** stdout (exactly one marker line on success, nothing otherwise); stderr (one reason line
on any failure).
**Called by:** `bin/poread` (via `-m src.poread_cli`); nothing else — this is a leaf CLI entry
point, never imported by other `src/` code.
**Calls out:** `constants` (`POREAD_MAX_BYTES`, `POREAD_HASH_LEN`, `POREAD_MARKER_PREFIX`) via a
normal relative import — unlike `src/proxy/inject_poread.py`'s special `sys.path` bootstrap, this
package always runs from the real checkout (never a frozen live copy), so the ordinary package
hierarchy resolves `..constants` correctly.

---

## Gotchas

**The marker format is a contract with `src/proxy/inject_poread.py`, maintained independently on
each side, not shared via import.** Both sides import the same three constants from
`src/constants.py` (`POREAD_MAX_BYTES`, `POREAD_HASH_LEN`, `POREAD_MARKER_PREFIX`), so the ceiling,
hash length, and marker prefix can never drift — but the exact attribute string this module emits
(`path="..." bytes="..." sha256="..."/>`) and the regex `inject_poread.py` parses it with are two
separate pieces of code that happen to agree. A change to one without the other breaks recognition
silently (the marker just never matches, and the agent sees only the tiny stdout line forever) —
change both together, and re-run `dev/proxy/poread_inject_tests.py`'s Item 1 (which mints a marker
through this real CLI as a subprocess, not a reimplementation, specifically to catch this class of
drift).
