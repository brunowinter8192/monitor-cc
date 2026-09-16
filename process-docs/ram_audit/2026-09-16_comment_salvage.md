## Salvage from dev/ram_audit/dump_byte_identity.py

```
"""
Byte-identity harness for src/ram_audit/instrument.py:register_ram_dump/_handle_ram_dump
(function-LOC split into module-level report-section helpers).

Calls register_ram_dump with a fake pane name + a fixed module_state_provider, sends SIGUSR1 to
this very process, reads the resulting dump file, strips out the lines that are inherently
non-deterministic across separate process runs (timestamp, pid, rss, the actual gc object-count
rows, the actual tracemalloc size/count rows — real memory state varies run to run), and hashes
what's left: the report's fixed section headers/structure plus the fully-deterministic
module-state section (driven by the fake provider).

Usage (from project root):
    ./venv/bin/python dev/ram_audit/dump_byte_identity.py

Prints one HASH line. Run before and after the register_ram_dump/_handle_ram_dump split; the hash
must match. Cleans up its own dump file and PID file on exit.
"""
```

```
# Loaded via importlib (not a literal 'from src.' module-level line) — dev/ scripts may not use
# that form (block_dev_imports_src).
```

```
# Fixed, fully-deterministic module state: one container (len+sizeof line) and one scalar line.
```

```
    time.sleep(0.2)   # signal handler runs synchronously on delivery, but give it a beat
```

```
# Strips inherently-non-deterministic lines (timestamp/pid/rss headers; the actual gc-count and
# tracemalloc data rows — real memory state varies run to run) while keeping section
# headers/structure and the fully-deterministic module-state section (driven by the fixed fake
# provider) intact.
```

```
    section = None   # None | 'gc' | 'tracemalloc'
```

## Salvage from dev/ram_audit/DOCS.md

Nothing cut — the pre-existing `## Role`, `## Flow`, and `## Modules` sections already fit the required format. The pre-existing `## Gotchas` section (dump-triggering command + dump-file section layout) has no home in the new fixed format and moved here in full:

```
## Gotchas
- To trigger a dump on a live pane: `kill -USR1 $(cat /tmp/.monitor_cc_pid_<pane>)`. The handler
  prints `[ram-dump] wrote <path>` to stderr, visible in the pane's tmux output.
- A dump file has four sections: header (timestamp/pid/rss), top-30 gc objects by class, top-30
  tracemalloc allocations by source line (requires `tracemalloc.start(25)` at module import), and
  per-pane module-level state (len + sizeof for containers, scalar values for numbers/strings).
```

## Notes for successor

- 1 `.py` file in scope (`dump_byte_identity.py`; `dump_all.sh` is bash, out of this milestone's scope entirely — no `.py` files there to touch). 9 comments + 1 docstring — matches the measured state exactly. Two are trailing inline comments (`time.sleep(0.2)   # ...` and `section = None   # ...`); the rest are standalone comment blocks (one 2-line, one 4-line, one 1-line) each directly preceding a `def`.
- No load-bearing docstring: grepped `__doc__` — zero hits. Docstring deleted outright.
- **Run directly** (safe): this script is itself a self-contained, self-cleaning byte-identity harness — it registers a fake RAM-dump provider under pane name `byteidentity`, signals itself with `SIGUSR1`, reads back the one dump file that produces, deletes that dump file and its scratch PID file before exit, and prints one `HASH:` line to stdout. Confirmed empirically: `ls dev/ram_audit/dumps/` before and after a run is byte-identical (the script's own cleanup removes the file it wrote; the directory's many pre-existing tracked dumps are named `*_main.txt`/`*_proxy.txt`/etc., never `*_byteidentity.txt`, so there is no collision risk).
- Verification: ran the script before and after the comment/docstring strip, `HASH:` line identical both times (module state hashed is driven entirely by the hardcoded `_fake_provider()`, not by any real process memory, so the hash is deterministic run to run on unchanged code). No dumps-directory diff either time.
- DOCS.md rewrite: the `## Gotchas` section has no home in the new fixed format, moved here in full — both facts (the `kill -USR1` trigger command, and the four-section dump-file layout) remain true and load-bearing for anyone re-running `dump_all.sh` or adding a new dump section.
