# 2026-09-14 — What this session built and what it never proved

## Scope of this entry

Main session file for this area. The worker-side entries in this area and in
`process-docs/bg_wakeup_id_line/`, `process-docs/click_ui/` and `process-docs/poread/` carry the
implementation detail. This entry records only what the main session decided and what it left open.

## Built, merged, unproven

Four proxy-side or pane-side changes landed on `integration` and then on `main`:

- `accept-encoding: identity` forced on the outbound Messages request, so the streaming probe sees
  uncompressed bytes again. Before the change, 58 of 58 recorded `_response` entries carried a
  compressed `content-encoding` and 0 carried an `answering_model`.
- The auto-backgrounded-on-timeout acknowledgement stripped to a compact form that keeps the task id
  and the output path. Measured 212 occurrences across two recorded sessions, 38,955 characters.
- Per-message and per-thinking-block copy in both proxy panes.
- `poread`, the CLI plus the proxy-side injection that replaces its marker with a file's full content.

Three of the four only take effect for a proxy started after the change, and no such session was
observed end to end before this session ended. The pane copy work needs no proxy and is the only one
in visible use.

## The verification that did not happen, and why

`dev/proxy_instrumentation/post_restart_verification.py` exists and was dry-run against the frozen
pre-change logs in `/tmp/pre_restart_logs/`: claim one contradicted (212 of 212 streamed responses
still compressed, 0 with an answering model), claim two contradicted, claim three missing data. That
is the expected shape before the change takes effect, and it is the script proving it cannot pass
vacuously.

A worker was then spawned to produce the three triggers in its own fresh-proxy session. It never got
there. The auto-backgrounding trigger requires a Bash call that runs past its own ~120 second timeout,
and the first attempt, `sleep 130 && echo done_sleep`, was blocked by this project's own
chained-sleep hook. The session ended before a second attempt produced a verdict.

## Two findings about the setup, not about the code

The trigger for the auto-backgrounding strip is hard to produce deliberately, because the guardrails
that keep an agent from waiting on purpose are exactly what stands in the way. A future verification
of that claim should plan the trigger before the session, not improvise it.

A worker refused a mid-session instruction that told it to forget its previous task, and it named the
reason: an instruction arriving as a plain conversation turn, telling it to discard its standing task,
matches a prompt-injection pattern. It continued its original task instead. The refusal was correct by
its own rules and it cost the session its last attempt. Whoever redirects a worker mid-task should
expect this and phrase a redirect as a new task rather than as a retraction.

## Decided this session, recorded in another area

The boundary between a hard rule and an agent decision was settled in conversation and written to
`process-docs/tool_use_safety/`. `poread` is the instrument that principle produced.
