# The `advisor` tool is stripped (2026-11-06)

Reverses the "advisor (not stripped)" decision of `2026-10-11_claude_ai_tools_and_total_tokens_tail.md`. Decision by the
user: the proxy removes `advisor` from every request.

## Observation
Opus main log `opus_bom1_1793980549` (428 request records, 426 with the tool) and `opus_bom1_1793960846` (511 with it): the
only structural occurrence is the tools entry `{"type": "advisor_20260301", "name": "advisor", "model": "claude-opus-5-5",
"defer_loading": true}` at `tools[18]`. Searched in both original logs: no `advisor_tool_result` block, no `tool_reference`
naming `advisor`, no mention in the system prompt (the remaining hits are conversation text and an unrelated quote of the
word). So removing the definition leaves no dangling reference in these logs.

## Change
- `src/constants.py`: `"advisor"` added to `TOOL_BLOCKLIST`. One entry covers `_strip_unused_tools` (tool entry, reported in
  `removed_names`, whole-tool strip shown as `tool_w.advisor`) and `_strip_blocked_tool_references` (a `tool_reference` with
  `tool_name: advisor` inside a tool result).
- Tests (`dev/proxy/test_strip_fix_cases_claude_ai_tools.py`, suite 131/131): CA01 now expects `Bash, Edit, Read, Skill, Write`
  and 14 removed; CA02 asserts the entry is gone and reported once; CA05 uses a list without advisor; new CA06 removes a
  `tool_reference` to advisor and keeps one to `Bash`.

## Not changed, open
- The request header `advisor-tool-2026-03-01` stays. That it is harmless without the tool is a hypothesis; the first live
  request after a proxy restart shows it (the live proxy runs a frozen copy, so running sessions are unaffected).
- Probes `dev/proxy_instrumentation/p4_blocklist_223_probe.py` and `p7_blocklist_258_probe.py` report failures (`post_strip_set_is_exact`,
  Edit/Write not in the blocklist). They failed the same way before this change; not touched.

## Related: workers forking
Forking was possible because workers of a project without proxy marker ran unproxied. See iterative-dev
`process-docs/worker_spawn/2026-11-06_worker_without_marker_ran_unproxied.md`. `Agent` was already in `TOOL_BLOCKLIST`;
nothing changes in monitor-cc for that.
