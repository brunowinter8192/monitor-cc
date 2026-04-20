
Result variants
The advisor_tool_result.content field is a discriminated union. Which variant you receive depends on the advisor model:

Variant	Fields	Returned when
advisor_result	text	The advisor model returns plaintext (for example, Claude Opus 4.7).
advisor_redacted_result	encrypted_content	The advisor model returns encrypted output.
With advisor_result, the text field contains human-readable advice. With advisor_redacted_result, the encrypted_content field contains an opaque blob that you cannot read; on the next turn, the server decrypts it and renders the plaintext into the executor's prompt.

In both cases, round-trip the content verbatim on subsequent turns. If you switch advisor models mid-conversation, branch on content.type to handle both shapes.

Error results
If the advisor call fails, the result carries an error:

{
  "type": "advisor_tool_result",
  "tool_use_id": "srvtoolu_abc123",
  "content": {
    "type": "advisor_tool_result_error",
    "error_code": "overloaded"
  }
}
The executor sees the error and continues without further advice. The request itself does not fail.

error_code	Meaning
max_uses_exceeded	The request reached the max_uses cap set on the tool definition. Further advisor calls in the same request return this error.
too_many_requests	The advisor sub-inference was rate-limited.
overloaded	The advisor sub-inference hit capacity limits.
prompt_too_long	The transcript exceeded the advisor model's context window.
execution_time_exceeded	The advisor sub-inference timed out.
unavailable	Any other advisor failure.
Advisor rate limits draw from the same per-model bucket as direct calls to the advisor model. A rate limit on the advisor appears as too_many_requests inside the tool result; a rate limit on the executor fails the whole request with HTTP 429.

Multi-turn conversations
Pass the full assistant content, including advisor_tool_result blocks, back to the API on subsequent turns:

import anthropic

client = anthropic.Anthropic()

tools = [
    {
        "type": "advisor_20260301",
        "name": "advisor",
        "model": "claude-opus-4-7",
    }
]

messages = [
    {
        "role": "user",
        "content": "Build a concurrent worker pool in Go with graceful shutdown.",
    }
]

response = client.beta.messages.create(
    model="claude-sonnet-4-6",
    max_tokens=4096,
    betas=["advisor-tool-2026-03-01"],
    tools=tools,
    messages=messages,
)

# Append the full response content, including any advisor_tool_result blocks
messages.append({"role": "assistant", "content": response.content})

# Continue the conversation
messages.append({"role": "user", "content": "Now add a max-in-flight limit of 10."})

response = client.beta.messages.create(
    model="claude-sonnet-4-6",
    max_tokens=4096,
    betas=["advisor-tool-2026-03-01"],
    tools=tools,
    messages=messages,
)
If you omit the advisor tool from tools on a follow-up turn while the message history still contains advisor_tool_result blocks, the API returns a 400 invalid_request_error.

The advisor tool has no built-in conversation-level cap. To limit advisor calls across a conversation, count them client-side. When you reach your ceiling, remove the advisor tool from your tools array and strip all advisor_tool_result blocks from your message history to avoid a 400 invalid_request_error.
Streaming
The advisor sub-inference does not stream. The executor's stream pauses while the advisor runs, then the full result arrives in a single event.

The server_tool_use block with name: "advisor" signals that an advisor call is starting. The pause begins when that block closes (content_block_stop). During the pause, the stream is quiet except for standard SSE ping keepalives emitted roughly every 30 seconds; short advisor calls may show no pings.

When the advisor finishes, the advisor_tool_result arrives fully formed in a single content_block_start event (no deltas). Executor output then resumes streaming.

A message_delta event follows with the updated usage.iterations array reflecting the advisor's token counts.

Usage and billing
Advisor calls run as a separate sub-inference billed at the advisor model's rates. Usage is reported in the usage.iterations[] array:

