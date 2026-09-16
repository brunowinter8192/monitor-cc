## Salvage from dev/coteditor/07_space_jump_probe.py

```
# True when bit 0 (left button) of NSEvent.pressedMouseButtons() is set
```

```
# Global mouse position, bottom-left origin (NSEvent.mouseLocation semantics)
```

```
# True when (x, y) is within _EDGE_PX of any edge of its containing NSScreen;
# also True when no screen contains the point (cursor pushed past all bounds)
```

```
# Frontmost application's localized name, "" if unavailable
```

```
# Active Space ID via CGS bridge (connection ID + active space, no full space map needed)
```

```
# Wall-clock timestamp, millisecond precision
```

```
# One poll: all required fields for a single sample
```

```
# Dense one-line rendering of a sample
```

```
# Write JUMP header + full rolling buffer to the log, flush immediately
```

## Salvage from dev/coteditor/DOCS.md

```
## Gotchas

**The `CGS*` symbols are undocumented, private CoreGraphics/SkyLight APIs**, loaded via a raw
`ctypes.CDLL` bridge rather than a PyObjC framework binding — no `import Quartz` fallback exists in
this probe (the venv it was built against had only `pyobjc-core`/`pyobjc-framework-Cocoa`
installed, not `pyobjc-framework-Quartz`).

**Edge detection (`_EDGE_PX = 3`) treats "no containing screen" as also at-edge** — a cursor pushed
past every `NSScreen`'s bounds returns `True`, not `False`, from `_at_edge`.
```

## Notes for successor

- 1 file, 10 comments, 0 docstrings — matches the measured state exactly. All 10 are standalone one-line (or, in one case, two-line) comments directly preceding a `def`; none are trailing inline comments. Line 37-38 is a single two-line comment block, counted as 2 comment lines.
- No load-bearing docstring — there were none to begin with (measured state says 0 docstrings, confirmed: no triple-quoted strings anywhere in the file).
- **Not run**: `probe_workflow()` (the module's real entry point) runs an infinite polling loop (10 Hz mouse/Space/frontmost-app sampling) that only exits on `SIGINT`/`SIGTERM`, and every sample it reads (mouse position, active Space ID, frontmost app) depends on live, real, currently-changing macOS desktop state — there is no way to feed it "identical input" across two separate runs, and it reads Space state continuously (adjacent to, though not identical to, the explicitly forbidden "switches Spaces"/"sends hotkeys" cases). Classified as unsafe/impractical to run for this milestone's proof; used a token-skeleton diff instead.
- Verification: same token-skeleton method as `dev/bead_tracker/smoke.py` (see that area's salvage notes for the exact mechanism) — `tokenize` output with `COMMENT` tokens and structural tokens (`NL`/`NEWLINE`/`INDENT`/`DEDENT`/`ENCODING`/`ENDMARKER`) stripped, compared before vs. after the edit. No docstring spans existed in this file, so the `ast`-located-span exclusion had nothing to exclude here — only comments were stripped. The two token sequences are byte-identical.
- DOCS.md rewrite: the `## Gotchas` section (private `CGS*` API loading rationale + the `_at_edge` "no containing screen" edge case) has no home in the new fixed format, so it moved here in full — both facts are still true and load-bearing for anyone touching `_at_edge` or the `ctypes.CDLL` bridge.
