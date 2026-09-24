# Pane flicker — orchestrator notes (2026-09-24)

Orchestrator-side record for the `pane_flicker` area: what the user observed, which decisions came from the chat, and what was left open. The implementation details, tests and numbers are in the two worker entries of this area.

## User observations that shaped the fix

- The tokens pane and the proxy pane flickered "again", after earlier sessions had discussed it. No process-docs entry existed for flicker before this area was created; the only earlier documented flicker case is the 2026-04-29 tracemalloc overhead in the proxy pane (area `pipeline`), which was ruled out here because `MONITOR_CC_RAM_AUDIT` was not set.
- Flicker appeared only once a session had accumulated many messages.
- Flicker appeared only while the mouse moved over the pane. With the mouse still there was none. This pointed at the hover path: every motion event rebuilt the whole document and cleared the screen.
- The user always hovers across several rows, so "skip the redraw when the hover row did not change" was rejected by the user as useless.
- The user's own formulation of the fix: finished turns never change, so they must not be recomputed ("this is our session so far, whatever happens, it stays like that").
- After the first live verification the user reported white blocks flashing for under a second in random rows while hovering. That was the terminal cursor walking through the in-place overwrite (tmux 3.6a paints it mid-frame). Hiding the cursor fixed it; second live verification passed.

## tmux

- 2026-09-24: `brew upgrade tmux` 3.6a -> 3.7c, with the user's consent. Both use PROTOCOL_VERSION 8, so the new client talks to the old running server without problems.
- tmux accepts synchronized output (DECSET 2026) from applications only since 3.7 (CHANGES 3.6b -> 3.7; fixes in 3.7b and 3.8). The panes already emit the 2026 wrap, but it has no effect until the tmux SERVER is restarted on 3.7c. As of 2026-09-24 the server was still 3.6a; the restart kills every tmux session (monitor, workers, mains in tmux) and was left to the user.

## Open

- The warnings, workers, gpu and news panes still clear the whole screen before every frame (`\033[2J\033[3J\033[H`). They were out of scope. The same hover flicker can appear there once they carry enough content (hypothesis, not observed).
