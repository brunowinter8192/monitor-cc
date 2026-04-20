{
  "usage": {
    "input_tokens": 412,
    "cache_read_input_tokens": 0,
    "cache_creation_input_tokens": 0,
    "output_tokens": 531,
    "iterations": [
      {
        "type": "message",
        "input_tokens": 412,
        "cache_read_input_tokens": 0,
        "cache_creation_input_tokens": 0,
        "output_tokens": 89
      },
      {
        "type": "advisor_message",
        "model": "claude-opus-4-7",
        "input_tokens": 823,
        "cache_read_input_tokens": 0,
        "cache_creation_input_tokens": 0,
        "output_tokens": 1612
      },
      {
        "type": "message",
        "input_tokens": 1348,
        "cache_read_input_tokens": 412,
        "cache_creation_input_tokens": 0,
        "output_tokens": 442
      }
    ]
  }
}
Top-level usage fields reflect executor tokens only. Advisor tokens are not rolled into the top-level totals because they are billed at a different rate. Iterations with type: "advisor_message" are billed at the advisor model's rates; iterations with type: "message" are billed at the executor model's rates.

The aggregation rules differ by field. Top-level output_tokens is the sum of all executor iterations. Top-level input_tokens and cache_read_input_tokens reflect the first executor iteration only; subsequent executor iterations' inputs are not re-summed because they include prior output tokens. Use usage.iterations for a full per-iteration breakdown when building cost-tracking logic.

Advisor output is typically 400 to 700 text tokens, or 1,400 to 1,800 tokens total including thinking. The cost savings come from the advisor not generating your full final output; the executor does that at its lower rate.

The top-level max_tokens applies to executor output only. It does not bound advisor sub-inference tokens. The advisor's tokens also do not draw from any task budget applied to the executor.

Advisor prompt caching
There are two independent caching layers.

Executor-side caching
The advisor_tool_result block is cacheable like any other content block. A cache_control breakpoint placed after it on a subsequent turn will hit. The executor's prompt always contains the plaintext advice regardless of whether your client received text or encrypted_content, so caching behavior is identical for both result variants.

Advisor-side caching
Set caching on the tool definition to enable prompt caching for the advisor's own transcript across calls within the same conversation:

tools = [
    {
        "type": "advisor_20260301",
        "name": "advisor",
        "model": "claude-opus-4-7",
        "caching": {"type": "ephemeral", "ttl": "5m"},
    }
]
The advisor's prompt on the Nth call is the (N-1)th call's prompt with one more segment appended, so the prefix is stable across calls. With caching enabled, each advisor call writes a cache entry; the next call reads up to that point and pays only for the delta. You'll see cache_read_input_tokens become nonzero on the second and later advisor_message iterations.

When to enable it: The cache write costs more than the reads save when the advisor is called two or fewer times per conversation. Caching breaks even at roughly three advisor calls and improves from there. Enable it for long agent loops; keep it off for short tasks.

Keep it consistent: Set caching once and leave it for the whole conversation. Toggling it off and on mid-conversation causes cache misses.

clear_thinking with a keep value other than "all" shifts the advisor's quoted transcript each turn, causing advisor-side cache misses. This is a cost degradation only; advice quality is unaffected. When extended thinking is enabled without explicit clear_thinking configuration, the API defaults to keep: {type: "thinking_turns", value: 1}, which triggers this behavior. Set keep: "all" to preserve advisor cache stability.
Combining with other tools
The advisor tool composes with other server-side and client-side tools. Add them all to the same tools array:

tools = [
    {
        "type": "web_search_20250305",
        "name": "web_search",
        "max_uses": 5,
    },
    {
        "type": "advisor_20260301",
        "name": "advisor",
        "model": "claude-opus-4-7",
    },
    {
        "name": "run_bash",
        "description": "Run a bash command",
        "input_schema": {
            "type": "object",
            "properties": {"command": {"type": "string"}},
        },
    },
]
The executor can search the web, call the advisor, and use your custom tools in the same turn. The advisor's plan can inform which tools the executor reaches for next.

Feature	Interaction
Batch processing	Supported. usage.iterations is reported per item.
Token counting	Returns the executor's first-iteration input tokens only. For a rough advisor estimate, call count_tokens with model set to the advisor model and the same messages.
Context editing	clear_tool_uses is not yet fully compatible with advisor tool blocks; full support is planned for a follow-up release. With clear_thinking, see the caching warning above.
pause_turn	A dangling advisor call ends the response with stop_reason: "pause_turn" and the server_tool_use block as the last content block. The advisor executes on resumption. See Server tools.
Best practices
Prompting for coding and agent tasks
The advisor tool ships with a built-in description that nudges the executor to call it near the start of complex tasks and when it hits difficulty. For research tasks, no additional prompting is typically needed.

On coding and agent tasks, the advisor produces higher intelligence at similar cost when it reduces total tool calls and conversation length. Two timings drive this improvement:

An early first advisor call, after a few exploratory reads are in the transcript.
For difficult tasks, a final advisor call after file writes and test outputs are in the transcript.
If your agent exposes other planner-like tools (for example, a todo list tool), prompt the model to call the advisor before those tools so the advisor's plan funnels into them. The suggested system prompt below reinforces the early-call pattern; add your own funnel-in sentence pointing at whichever planner tools your agent exposes.

Suggested system prompt for coding tasks
For coding tasks where you want consistent advisor timing and around two to three calls per task, prepend the following blocks to your executor system prompt before any other sentences that mention the advisor. On internal coding evaluations this pattern produced the highest intelligence at near-Sonnet cost.

Timing guidance:

You have access to an `advisor` tool backed by a stronger reviewer model. It takes NO parameters — when you call advisor(), your entire conversation history is automatically forwarded. They see the task, every tool call you've made, every result you've seen.

Call advisor BEFORE substantive work — before writing, before committing to an interpretation, before building on an assumption. If the task requires orientation first (finding files, fetching a source, seeing what's there), do that, then call advisor. Orientation is not substantive work. Writing, editing, and declaring an answer are.

Also call advisor:
- When you believe the task is complete. BEFORE this call, make your deliverable durable: write the file, save the result, commit the change. The advisor call takes time; if the session ends during it, a durable result persists and an unwritten one doesn't.
- When stuck — errors recurring, approach not converging, results that don't fit.
- When considering a change of approach.

On tasks longer than a few steps, call advisor at least once before committing to an approach and once before declaring done. On short reactive tasks where the next action is dictated by tool output you just read, you don't need to keep calling — the advisor adds most of its value on the first call, before the approach crystallizes.
How the executor should treat the advice (place directly after the timing block):

Give the advice serious weight. If you follow a step and it fails empirically, or you have primary-source evidence that contradicts a specific claim (the file says X, the paper states Y), adapt. A passing self-test is not evidence the advice is wrong — it's evidence your test doesn't check what the advice is checking.

If you've already retrieved data pointing one way and the advisor points another: don't silently switch. Surface the conflict in one more advisor call — "I found X, you suggest Y, which constraint breaks the tie?" The advisor saw your evidence but may have underweighted it; a reconcile call is cheaper than committing to the wrong branch.
Trimming advisor output length
Advisor output is the advisor's largest cost driver. To reduce that cost, prepend a single conciseness instruction to the system prompt before any other sentence that mentions the advisor. In internal testing, the following line cut total advisor output tokens by roughly 35 to 45 percent without changing call frequency:

The advisor should respond in under 100 words and use enumerated steps, not explanations.
Pair this with the timing block above for the strongest cost-versus-quality tradeoff.

Pairing with effort settings
For coding tasks, pairing a Sonnet executor at medium effort with an Opus advisor achieves intelligence comparable to Sonnet at default effort, at lower cost. For maximum intelligence, keep the executor at default effort.

Cost control
For conversation-level budgets, count advisor calls client-side. When you reach your cap, remove the advisor tool from tools and strip all advisor_tool_result blocks from your message history to avoid a 400 invalid_request_error.
Enable caching only for conversations where you expect three or more advisor calls.
Limitations
Advisor output does not stream. Expect a pause in the stream while the sub-inference runs.
No built-in conversation-level cap on advisor calls. Track and cap them client-side.
max_tokens applies to executor output only. It does not bound advisor tokens.
Anthropic Priority Tier is honored per model. Priority Tier on the executor model does not extend to the advisor; you need Priority Tier on the advisor model specifically.
