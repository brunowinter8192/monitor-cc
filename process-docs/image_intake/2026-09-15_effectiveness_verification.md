# 2026-09-15 — Verifying that the 50,000-byte poread ceiling and the un-blocked Read tool are actually in effect

Main session, no worker, no source code changed. This entry records a pure verification run against
the live system. Two earlier changes in this area and in `process-docs/poread/` had established their
values in source; the open question was whether a running session actually experiences them. The
answer for the session measured here is yes, on all three counts, with the measurements below.

## Why "in source" was not the same question as "in effect"

The mechanism carries the same four marker constants (`POREAD_MAX_BYTES`, `POREAD_HASH_LEN`,
`POREAD_MARKER_PREFIX`, `POREAD_NOTICE`) in two hand-maintained copies, and neither copy is what
actually executes:

- The `poread` CLI is reached through `~/.local/bin/poread`, a symlink to
  `Meta/iterative-dev/bin/poread`. That wrapper does NOT run the repo's source. It runs
  `python3 -m src.poread_cli` from `$CLAUDE_PLUGIN_ROOT`, defaulting to
  `~/.claude/plugins/cache/brunowinter-plugins/iterative-dev/1.0.0`. So the plugin cache, not the
  source repo, decides what ceiling the CLI enforces.
- The proxy does not run `monitor-cc/src/proxy/` either. At startup it copies the package into
  `src/logs/.proxy_live_<session_id>/proxy/` and `mitmdump -s` loads
  `src/logs/.proxy_addon_live_<session_id>.py`, whose sys.path bootstrap points into that snapshot.
  The snapshot is frozen at proxy start time. A proxy started before a change keeps serving the old
  code for its whole lifetime.
- `TOOL_BLOCKLIST` is a third case. The snapshot's `proxy/tools.py` does not import it from the
  snapshot at all; it inserts `$MONITOR_CC_ROOT/src` on sys.path and imports `constants` from the
  LIVE repo. But the import happens once, at proxy start, so the value is still frozen at start
  time even though the file it came from is the live one.

Three delivery paths, three independent chances for a source-correct value never to reach a running
session. That is what this verification was about.

## What the environment looked like at measurement time

Three `mitmdump` processes were alive: port 8080 started Tue 2026-09-15 14:04, port 8081 started
Mon 2026-09-14 14:45, port 8082 started Tue 2026-09-15 13:43. The session doing the measuring used
`ANTHROPIC_BASE_URL=http://localhost:8080`, i.e. the 14:04 proxy, snapshot id
`25c51a2e_57782_1789473857`. Verification was deliberately scoped to that one proxy on the user's
instruction. The 8081 proxy from 2026-09-14 14:45 was NOT checked and is the obvious candidate for
carrying pre-change code, since the Read-unblock commit `2eceaf55` is dated 2026-09-14 19:44 —
about five hours after that proxy started. Anyone hitting stale poread or missing-Read behavior
should check the proxy's start time first.

## Static side, all four checks passed

- `src/proxy/inject_poread.py:9` in the repo: `POREAD_MAX_BYTES = 50_000`.
- The 14:04 snapshot's own `proxy/inject_poread.py`: identical, `50_000`.
- `Meta/iterative-dev/src/poread_cli/__main__.py` and the plugin-cache copy at
  `~/.claude/plugins/cache/brunowinter-plugins/iterative-dev/1.0.0/src/poread_cli/__main__.py`:
  `diff` reports the two files byte-identical, and both carry `50_000`. So the published half and
  the source half had not drifted.
- The four constants compared line-by-line between the proxy snapshot and the plugin cache: same
  ceiling, same hash length, same `'<poread-export '` prefix, same two-line notice sentence
  ("The file's full content will arrive automatically on the next turn — do not read this file
  again until then."). This is the drift that fails silently, so it was compared literally rather
  than assumed.
- `src/constants.py`'s `TOOL_BLOCKLIST` ends `"SendFeedback", "ListAgents", "Edit", "Write"` — no
  `Read`. Commit `2eceaf55` is dated 2026-09-14 19:44 +0200, before the 14:04 proxy start, so the
  frozen import picked up the post-change value.

## Live side, the CLI ceiling

Two files built on the exact boundary: `/tmp/po_under.txt` at 49,999 bytes and `/tmp/po_over.txt`
at 50,001 bytes, both filled with `x`.

- `poread /tmp/po_under.txt` exited 0 and printed the marker plus the notice:
  `<poread-export path="/private/tmp/po_under.txt" bytes="49999" sha256="5a4a05dddd82373b"/>`.
- `poread /tmp/po_over.txt` exited 1 and printed no marker, only
  `poread: /private/tmp/po_over.txt is 50001 bytes, over the 50000-byte poread ceiling — refusing
  to export; no truncated or partial export is produced`.

A two-byte span across the boundary separates accept from refuse, so the number in force is exactly
50,000 and not a nearby value.

## Live side, the proxy refusing an over-ceiling marker

This needed care, because a refusal alone does not say WHICH check refused. `inject_poread.py`
rejects on several grounds — over-ceiling size, hash mismatch, vanished file, block not exactly
marker-plus-notice — and a sloppy probe proves nothing about the ceiling specifically.

First attempt used a hand-crafted marker with `bytes="50001"` and a deliberately fake hash
`0123456789abcdef`, emitted alone in its own Bash call so the tool_result block was nothing but
marker plus notice. The forwarded payload kept the marker verbatim and contained no `x` run from
the file, so no injection happened. But the fake hash makes this ambiguous: the hash check could
have been the one that fired.

Second attempt removed the ambiguity. The real truncated sha256 of `/tmp/po_over.txt` was computed
(`a6ef35e156d996bb`) and a marker minted with the true size and the true hash, again alone in its
block. Result in
`src/logs/dual_log/api_requests_opus_monitor_cc_1789473857_forwarded.jsonl`: the marker string
`a6ef35e156d996bb` was still present unexpanded and no `x` run appeared anywhere in the payload.
With path, size and hash all correct, the only remaining reason to refuse is the ceiling. That is
the proxy-side half of the issue's goal, demonstrated rather than reasoned about.

The counter-proof that the mechanism was alive at all, rather than dead in a way that would refuse
everything: `poread /tmp/po_under.txt` run alone in its own Bash call DID expand, and the agent
received the header line `--- poread: /private/tmp/po_under.txt (49999B) ---` followed by all
49,999 bytes. Expansion works at 49,999 and is refused at 50,001, through the same proxy, minutes
apart.

Side note worth knowing before repeating this: that counter-proof pulls the whole file into the
measuring agent's own context. 49,999 bytes of filler is a real cost paid for one boolean. Use a
file whose content you would not mind reading, or accept the burn.

## Live side, Read in the forwarded tools array

`api_requests_opus_monitor_cc_1789473857_forwarded.jsonl` stores tools as a delta, not as a full
array on every request — the first request's `tools_delta` is `{}` and `counts.tools` is 0, so
looking for a `tools` key finds nothing and means nothing. The full set appears in the
`tools_delta` of request index 2 as a positional map: `"0"` Bash, `"1"` Read, `"2"` Skill. Read is
present, forwarded, and its `description` plus every per-parameter schema `description` are `""` —
the expected effect of `content_strip.py::_strip_tool_descriptions`, which blanks descriptions on
every forwarded tool. So the post-blocklist forwarded set for this session is exactly
`{Bash, Read, Skill}`.

## What was not established

The stderr diagnostic `[proxy_addon] poread: marker declares ...B, over the ...B ceiling` was never
captured. `/tmp/monitor_cc_error.log` (the path in `src/pane_error_log.py`) had not been written
since 14:04, and `tmux list-panes -a` showed no pane running mitmdump, so the proxy's stderr had no
reachable sink from the measuring session. The refusal is therefore proven by absence of expansion
in the forwarded log plus elimination of the other refusal grounds, not by reading the message the
code prints. Anyone who wants the message itself has to find where that proxy's stderr goes first.
