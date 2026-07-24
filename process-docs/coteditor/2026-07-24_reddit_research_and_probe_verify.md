# Reddit Research (NOT FOUND) + Interactive Probe Verify — 2026-07-24

## Context

Continuation of the CotEditor drag-selection space-jump investigation. User re-reported
the symptom with a sharper trigger description than earlier records: the jump happens
while selecting text with the LEFT MOUSE BUTTON HELD and dragging, and it happens
OFTEN — a marked change from the earlier "sporadic, not reproducible on demand" state.
Working hypothesis at this point (unproven): Mission Control's edge-drag space switch
fires because the drag-selection carries the pressed-button cursor to the screen edge.

## Reddit Research — NOT FOUND

Searched Reddit for community evidence of the phenomenon before committing to a
measurement probe. Pipeline: subreddit discovery → indexing → RAG retrieval over the
indexed posts.

- Index runs (3): two broad runs over r/MacOS, r/mac, r/osx, r/applehelp with queries
  "desktop switches when dragging text selection" (232 new chunks) and "Mission Control
  auto switch spaces edge drag" (45 new chunks); one deep-dive in r/MacOS with
  "switches space while selecting text mouse drag edge" (47 posts, 175 new chunks).
- Retrieval queries (4): drag-selection phrasing, edge-drag phrasing, the
  `workspaces-edge-delay` defaults key directly, and a broad space-switch phrasing.

Result: zero relevant hits. All retrieved threads concern OTHER space-switch triggers —
Dock app activation, fullscreen mode, multi-monitor jumps, auto-rearrange of Spaces.
No thread describes a space switch during text selection with a held mouse button, and
the hidden Dock edge-delay defaults key did not surface in any indexed post. Absence of
evidence here does not refute the edge-drag hypothesis (indexing covers only the most
relevant posts per subreddit), but it left the hypothesis without community backing —
which is why the decision fell on a direct measurement probe instead of further source
hunting.

## Interactive Probe Verify (orchestrator-side)

The logging probe `dev/coteditor/07_space_jump_probe.py` (built in this session's
worker milestone) had one verification gap the worker could not close headlessly: a
REAL active-Space change while the probe runs. Closed interactively on 2026-07-24:

- Probe started under the venv python; two Space switches simulated via
  `osascript` ctrl+arrow key events while the probe polled.
- Both jumps were captured: `space 4 -> 5` and `space 5 -> 4`, each with a full rolling
  buffer dump (33 and 50 samples) containing all fields — timestamp (ms), mouse x/y,
  at_edge flag, left_down state, space ID, frontmost app.
- SIGINT shutdown clean in a separate run (start/stop markers both present, process
  exited).

As of 2026-07-24 the probe was left running in the background on the user's machine
(log under `dev/coteditor/07_reports/`), armed to capture the next real CotEditor
drag-selection jump. The discriminating readout for the hypothesis: at the jump moment,
is `left_down=True` AND `at_edge=True` in the buffered samples.

## Sources

- `dev/coteditor/07_space_jump_probe.py`
- `dev/coteditor/07_reports/` (probe logs)
