# Strip tool_use/tool_result + Cache-BP Shift

## Idea

Workers die at the context limit. `tool_use` + `tool_result` blocks are the most
voluminous parts of the message array. Speculation: set the cache breakpoint AFTER
`tool_use`+`tool_result`, let AI thinking/text run on top, then in the next REQ strip
the tool_* blocks from messages → context stops growing unbounded, thinking/text as
memory is preserved.

## Hypothesis (unverified)

Would invalidate the cache. The cached prefix is `messages[0..K]` (bytes up to BP). REQ
N contains `tool_use`+`tool_result` at index <K → cached. REQ N+1 strips them → different
bytes before K → cache miss → CC for the whole messages prefix. `tools`+`system` stay
cached (separate BP), but `messages` is the largest block. Effect: 100% messages rebuild
per REQ — likely more expensive than the current accumulation.

## Verification Needed (before implementation)

- Live measurement: two consecutive REQs, one with normal accumulation, one with
  strip-and-move-BP. Compare CR/CC.
- Check Anthropic's `PromptCaching*.md` docs — is there a mechanism to "shift" a BP
  without a rebuild?

## Status

Spec only. Verification measurement not run. Idea parked — the hypothesis strongly
suggests "more expensive than accumulation"; the small measurement is worth doing before
any implementation.

## Where (if reactivated)

- `src/proxy/strip_*.py` (strip hook)
- `proxy_rules.json` (BP control via `sent_cache_breakpoints`)
- `sources/PromptCaching*.md`
