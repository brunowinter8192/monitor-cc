# Sources

External references used as evidence for pipeline decisions.

| Source | URL | Relevance | Pipeline Steps |
|--------|-----|-----------|----------------|
| tmux man page | github.com/tmux/tmux `tmux.1` | split-window, pane targeting, layout, `-l size%` behavior | pipe01 |
| Claude Code #30973 | github.com/anthropics/claude-code/issues/30973 | InstructionsLoaded hook behavior | pipe03 |
| Claude Code #33275 | github.com/anthropics/claude-code/issues/33275 | InstructionsLoaded session_start bug | pipe03 |
| Claude Code #31017 | github.com/anthropics/claude-code/issues/31017 | InstructionsLoaded /clear behavior | pipe03 |
| Claude Code #12151 | github.com/anthropics/claude-code/issues/12151 | Plugin hook output bug (not affecting us) | pipe03 |
| Claude Code #19377 | github.com/anthropics/claude-code/issues/19377 | paths: YAML array syntax broken (CSV parser bug) | pipe04 |
| Claude Code #33581 | github.com/anthropics/claude-code/issues/33581 | Multiple paths: entries silently fail (same root cause as #19377) | pipe04 |
| Claude Code #16299 | github.com/anthropics/claude-code/issues/16299 | Path-scoped rules load globally (version-dependent) | pipe04 |
| Claude Code #27724 | github.com/anthropics/claude-code/issues/27724 | JSONL format undocumented, changes without changelog | pipe02, pipe04 |
| Claude Code #27361 | github.com/anthropics/claude-code/issues/27361 | Token counts ~2x too low in JSONL | pipe03 |
| Claude Code #33414 | github.com/anthropics/claude-code/issues/33414 | FireHose monitoring feature request | pipe02 |
| unified-cowork JSONL Spec | github.com/yjjoeathome-byte/unified-cowork | Community reverse-engineered Cowork audit.jsonl spec (related format) | pipe02 |
| termshot | github.com/homeport/termshot | ANSI text → PNG rendering (terminal screenshots) | pipe04 |
| claudeoo | github.com/monk1337/claudeoo | SSE stream interceptor for accurate token counts (solves #27361 undercount) | pipe02, pipe03 |
| better-ccusage | github.com/cobra91/better-ccusage | Post-hoc JSONL parser with session block aggregation, multi-provider | pipe02, pipe03 |
| ccusage | github.com/ryoppippi/ccusage | 5h billing block ceiling, session boundary detection, hash-based dedup, dual token naming convention | pipe02, pipe03 |
| hooks-observability | github.com/disler/claude-code-hooks-multi-agent-observability | 12 hook types, universal dispatcher pattern, HTTP+WebSocket real-time, SQLite storage | pipe03, pipe04 |
| claude-hud | github.com/jarrodwatts/claude-hud | CC statusline plugin, native context_window/rate_limits stdin data, transcript caching | pipe02, pipe03, pipe04 |
| Claude-Code-Usage-Monitor | github.com/Maciek-roboblog/Claude-Code-Usage-Monitor | Real-time TUI token monitor (7k stars), Python, P90 session limits | pipe02, pipe03 |
| tokscale | github.com/junhoyeo/tokscale | CLI token tracking with contributions graph, multi-agent support | pipe02, pipe03 |
