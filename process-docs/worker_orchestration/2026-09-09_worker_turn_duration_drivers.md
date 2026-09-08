# Worker turn duration — measured drivers, 2026-09-09

Two trading-project worker sessions from 2026-09-06 (`k-ratio`, `reldist-power`) were measured with
the `duallog turns` command built for this purpose (see `process-docs/dual_log_cli/` for the
command's own entries). The question was why a worker turn ran for tens of minutes: model
generation, shell commands, or token intake.

## Method

A turn runs from a typed prompt (orchestrator via `worker-cli send`) to the model's idle text
reply. Per request, the proxy's forwarded log gives the send time and CC's transcript gives the
stream-end time and output tokens, joined by request id. Model time = send → stream end, summed
over the turn. Tool time = stream end → next send, summed. The proxy's own `_response` timestamp
is first-byte time and unusable for this split.

## Findings

`reldist-power`, turn 1 (the turn the original observation came from; the 32m38s figure was a
mid-turn reading):

| duration | model | tool | requests | output tokens |
|---|---|---|---|---|
| 41m27s | 20m23s | 21m04s | 77 | 102,389 |

The tool half is two runs of one script: `15_reldist_power_study.py`, REQ 42 at 9m42s and REQ 59
at 9m44s (the script itself reports `Runtime: 9.7 min`), plus one 68 s call. Every other tool call
in the turn took under 10 s.

The model half is concentrated in four requests: REQ 24, a `Write` of a 43.5k-char study script
(3m56s, 30,097 tokens); REQ 15, a `Bash` preceded by long thinking (3m29s, 19,684 tokens); REQ 20
(1m38s, 9,611 tokens); REQ 70, a `Write` (1m02s, 5,909 tokens). Those four are 10m05s of the
20m23s. The remaining 73 requests average about 8 s each.

`k-ratio`, 20 turns, longest turn 8:

| duration | model | tool | requests | output tokens |
|---|---|---|---|---|
| 11m33s | 9m18s | 2m15s | 58 | 57,070 |

Across all 20 k-ratio turns, tool time never exceeded 2m23s per turn and no single tool call
exceeded 27 s; model time dominated every turn there.

## Conclusion

Two independent drivers, both real, neither dominant in general:

- A long-running analysis script inside a `Bash` call adds its full runtime to the turn. In
  reldist-power that was 19.5 minutes from two runs of the same study.
- Large generated artifacts add minutes of pure generation: a 30k-token `Write` cost close to four
  minutes on its own. Output-token volume, not intake, is the model-side driver; cache-read intake
  (CR ~270k–300k in that session) did not show up as time.

Token intake was ruled out as a driver: the requests with the largest CR were the fast ones.
