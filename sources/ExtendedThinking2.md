You're still charged for the full thinking tokens. Omitting reduces latency, not cost.
If you pass thinking blocks back in multi-turn conversations, pass them unchanged. The server decrypts the signature to reconstruct the original thinking for prompt construction (see Preserving thinking blocks). Any text you place in the thinking field of a round-tripped omitted block is ignored.
display is invalid with thinking.type: "disabled" (there is nothing to display).
When using thinking.type: "adaptive" and the model skips thinking for a simple request, no thinking block is produced regardless of display.
The signature field is identical whether display is "summarized" or "omitted". Switching display values between turns in a conversation is supported.
On Claude Mythos Preview, display defaults to "omitted". The examples in this section pass display explicitly so they apply to all models, but on Mythos Preview you can leave it unset and receive the same behavior. To receive summarized thinking on Mythos Preview, set display: "summarized" explicitly.
Automated pipelines that never surface thinking content to end users can skip the overhead of receiving thinking tokens over the wire. Latency-sensitive applications get the same reasoning quality without waiting for thinking text to stream before the final response begins.

Shell
CLI
Python
TypeScript
C#
Go
Java
PHP
Ruby
Shell
curl https://api.anthropic.com/v1/messages \
     --header "x-api-key: $ANTHROPIC_API_KEY" \
     --header "anthropic-version: 2023-06-01" \
     --header "content-type: application/json" \
     --data \
'{
    "model": "claude-sonnet-4-6",
    "max_tokens": 16000,
    "thinking": {
        "type": "enabled",
        "budget_tokens": 10000,
        "display": "omitted"
    },
    "messages": [
        {
            "role": "user",
            "content": "What is 27 * 453?"
        }
    ]
}'
When display: "omitted" is set, the response contains thinking blocks with an empty thinking field:

Output
{
  "content": [
    {
      "type": "thinking",
      "thinking": "",
      "signature": "EosnCkYICxIMMb3LzNrMu..."
    },
    {
      "type": "text",
      "text": "The answer is 12,231."
    }
  ]
}
When streaming with display: "omitted", no thinking_delta events are emitted; see Streaming thinking below for the event sequence.

Streaming thinking
You can stream extended thinking responses using server-sent events (SSE).

When streaming is enabled for extended thinking, you receive thinking content via thinking_delta events.

When display: "omitted" is set, no thinking_delta events are emitted. See Controlling thinking display.

For more documentation on streaming via the Messages API, see Streaming Messages.

Here's how to handle streaming with thinking:

Shell
CLI
Python
TypeScript
C#
Go
Java
PHP
Ruby
Try in Console
curl https://api.anthropic.com/v1/messages \
     --header "x-api-key: $ANTHROPIC_API_KEY" \
     --header "anthropic-version: 2023-06-01" \
     --header "content-type: application/json" \
     --data \
'{
    "model": "claude-sonnet-4-6",
    "max_tokens": 16000,
    "stream": true,
    "thinking": {
        "type": "enabled",
        "budget_tokens": 10000
    },
    "messages": [
        {
            "role": "user",
            "content": "What is the greatest common divisor of 1071 and 462?"
        }
    ]
}'
Example streaming output:
