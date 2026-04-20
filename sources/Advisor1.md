Advisor tool

Copy page

Pair a faster executor model with a higher-intelligence advisor model that provides strategic guidance mid-generation.
The advisor tool lets a faster, lower-cost executor model consult a higher-intelligence advisor model mid-generation for strategic guidance. The advisor reads the full conversation, produces a plan or course correction (typically 400 to 700 text tokens, 1,400 to 1,800 tokens total including thinking), and the executor continues with the task.

This pattern fits long-horizon agentic workloads (coding agents, computer use, multi-step research pipelines) where most turns are mechanical but having an excellent plan is crucial. You get close to advisor-solo quality while the bulk of token generation happens at executor-model rates.

The advisor tool is in beta. Include the beta header advisor-tool-2026-03-01 in your requests. To request access or share feedback, contact your Anthropic account team.
This feature is eligible for Zero Data Retention (ZDR). When your organization has a ZDR arrangement, data sent through this feature is not stored after the API response is returned.
When to use it
Early benchmarks show meaningful gains for these configurations:

You currently use Sonnet on complex tasks: Add Opus as the advisor for a quality lift at similar or lower total cost.
You currently use Haiku and want a step up in intelligence: Add Opus as the advisor. Expect higher cost than Haiku alone, but lower than switching the executor to a larger model.
Results are task-dependent. Evaluate on your own workload.

The advisor is a weaker fit for single-turn Q&A (nothing to plan), pure pass-through model pickers where your users already choose their own cost and quality tradeoff, or workloads where every turn genuinely requires the advisor model's full capability.

Model compatibility
The executor model (the top-level model field) and the advisor model (the model field inside the tool definition) must form a valid pair. The advisor must be at least as capable as the executor.

Executor models	Advisor models
Claude Haiku 4.5 (claude-haiku-4-5-20251001)	Claude Opus 4.7 (claude-opus-4-7)
Claude Sonnet 4.6 (claude-sonnet-4-6)	Claude Opus 4.7 (claude-opus-4-7)
Claude Opus 4.6 (claude-opus-4-6)	Claude Opus 4.7 (claude-opus-4-7)
Claude Opus 4.7 (claude-opus-4-7)	Claude Opus 4.7 (claude-opus-4-7)
If you request an invalid pair, the API returns a 400 invalid_request_error naming the unsupported combination.

Platform availability
The advisor tool is available in beta on the Claude API (Anthropic).

Quick start
cURL
CLI
Python
TypeScript
C#
Go
PHP
Ruby
client = anthropic.Anthropic()

response = client.beta.messages.create(
    model="claude-sonnet-4-6",
    max_tokens=4096,
    betas=["advisor-tool-2026-03-01"],
    tools=[
        {
            "type": "advisor_20260301",
            "name": "advisor",
            "model": "claude-opus-4-7",
        }
    ],
    messages=[
        {
            "role": "user",
            "content": "Build a concurrent worker pool in Go with graceful shutdown.",
        }
    ],
)

print(response)
How it works
When you add the advisor tool to your tools array, the executor model decides when to call it, just like any other tool. When the executor invokes the advisor:

The executor emits a server_tool_use block with name: "advisor" and an empty input. The executor signals timing; the server supplies context.
Anthropic runs a separate inference pass on the advisor model server-side, passing the executor's full transcript. The advisor sees the system prompt, all tool definitions, all prior turns, and all prior tool results.
The advisor's response returns to the executor as an advisor_tool_result block.
The executor continues generating, informed by the advice.
All of this happens inside a single /v1/messages request. No extra round trips on your side.

The advisor itself runs without tools and without context management. Its thinking blocks are dropped before the result returns; only the advice text reaches the executor.

Tool parameters
Parameter	Type	Default	Description
type	string	required	Must be "advisor_20260301".
name	string	required	Must be "advisor".
model	string	required	The advisor model ID, such as "claude-opus-4-7". Billed at this model's rates for the sub-inference.
max_uses	integer	unlimited	Maximum number of advisor calls allowed in a single request. Once the executor reaches this cap, further advisor calls return an advisor_tool_result_error with error_code: "max_uses_exceeded" and the executor continues without further advice. This is a per-request cap, not a per-conversation cap; see Cost control for conversation-level limits.
caching	object | null	null (off)	Enables prompt caching for the advisor's own transcript across calls within a conversation. See Advisor prompt caching.
The caching object has the shape {"type": "ephemeral", "ttl": "5m" | "1h"}. Unlike cache_control on content blocks, this is not a breakpoint marker; it is an on/off switch. The server decides where cache boundaries go.

Response structure
Successful advisor call
When the advisor is invoked, a server_tool_use block is followed by an advisor_tool_result block in the assistant's content:

{
  "role": "assistant",
  "content": [
    {
      "type": "text",
      "text": "Let me consult the advisor on this."
    },
    {
      "type": "server_tool_use",
      "id": "srvtoolu_abc123",
      "name": "advisor",
      "input": {}
    },
    {
      "type": "advisor_tool_result",
      "tool_use_id": "srvtoolu_abc123",
      "content": {
        "type": "advisor_result",
        "text": "Use a channel-based coordination pattern. The tricky part is draining in-flight work during shutdown: close the input channel first, then wait on a WaitGroup..."
      }
    },
    {
      "type": "text",
      "text": "Here's the implementation. I'm using a channel-based coordination pattern to avoid writer starvation..."
    }
  ]
}
The server_tool_use.input is always empty. The server constructs the advisor's view from the full transcript automatically; nothing the executor puts in input reaches the advisor.
