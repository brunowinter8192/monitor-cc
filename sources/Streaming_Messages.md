Streaming Messages

Copy page

When creating a Message, you can set "stream": true to incrementally stream the response using server-sent events (SSE).

Streaming with SDKs
The Python and TypeScript SDKs offer multiple ways of streaming. The PHP SDK provides streaming via createStream(). The Python SDK allows both sync and async streams. See the documentation in each SDK for details.

CLI
ant messages create --stream --format jsonl \
  --model claude-opus-4-6 \
  --max-tokens 1024 \
  --message '{role: user, content: "Hello"}' \
  | while IFS= read -r event; do
      [[ $event == *'"text_delta"'* ]] || continue
      text=${event#*'"text":"'}
      printf '%b' "${text%\"*}"
    done
Get the final message without handling events
If you don't need to process text as it arrives, the SDKs provide a way to use streaming under the hood while returning the complete Message object, identical to what .create() returns. This is especially useful for requests with large max_tokens values, where the SDKs require streaming to avoid HTTP timeouts.

CLI
# The ant CLI's --stream flag emits one event per line and does not
# accumulate into a final Message. For long generations, stream the
# raw events:
ant messages create --stream --format jsonl <<'YAML'
model: claude-opus-4-6
max_tokens: 128000
messages:
  - role: user
    content: Write a detailed analysis...
YAML
The .stream() call keeps the HTTP connection alive with server-sent events, then .get_final_message() (Python) or .finalMessage() (TypeScript) accumulates all events and returns the complete Message object. In Go, you call message.Accumulate(event) inside the stream loop to build the same complete Message. In Java, use MessageAccumulator.create() and call accumulator.accumulate(event) on each event. In Ruby, call .accumulated_message on the stream. In the PHP SDK, you iterate over stream events manually to accumulate the response.

Event types
Each server-sent event includes a named event type and associated JSON data. Each event uses an SSE event name (e.g. event: message_stop), and includes the matching event type in its data.

Each stream uses the following event flow:

message_start: contains a Message object with empty content.
A series of content blocks, each of which have a content_block_start, one or more content_block_delta events, and a content_block_stop event. Each content block has an index that corresponds to its index in the final Message content array.
One or more message_delta events, indicating top-level changes to the final Message object.
A final message_stop event.
The token counts shown in the usage field of the message_delta event are cumulative.
Ping events
Event streams may also include any number of ping events.

Error events
The API may occasionally send errors in the event stream. For example, during periods of high usage, you may receive an overloaded_error, which would normally correspond to an HTTP 529 in a non-streaming context:

Example error
event: error
data: {"type": "error", "error": {"type": "overloaded_error", "message": "Overloaded"}}
Other events
In accordance with the versioning policy, new event types may be added, and your code should handle unknown event types gracefully.

Content block delta types
Each content_block_delta event contains a delta of a type that updates the content block at a given index.

Text delta
A text content block delta looks like:

Text delta
event: content_block_delta
data: {"type": "content_block_delta","index": 0,"delta": {"type": "text_delta", "text": "ello frien"}}
Input JSON delta
The deltas for tool_use content blocks correspond to updates for the input field of the block. To support maximum granularity, the deltas are partial JSON strings, whereas the final tool_use.input is always an object.

You can accumulate the string deltas and parse the JSON once you receive a content_block_stop event, by using a library like Pydantic to do partial JSON parsing, or by using the SDKs, which provide helpers to access parsed incremental values.

A tool_use content block delta looks like:

Input JSON delta
event: content_block_delta
data: {"type": "content_block_delta","index": 1,"delta": {"type": "input_json_delta","partial_json": "{\"location\": \"San Fra"}}}
Note: Current models only support emitting one complete key and value property from input at a time. As such, when using tools, there may be delays between streaming events while the model is working. Once an input key and value are accumulated, they are emitted as multiple content_block_delta events with chunked partial json so that the format can automatically support finer granularity in future models.

Thinking delta
When using extended thinking with streaming enabled, you'll receive thinking content via thinking_delta events. These deltas correspond to the thinking field of the thinking content blocks.

For thinking content, a special signature_delta event is sent just before the content_block_stop event. This signature is used to verify the integrity of the thinking block.

When display: "omitted" is set on the thinking configuration, no thinking_delta events are sent. The thinking block opens, receives a single signature_delta, and closes. See Controlling thinking display.

A typical thinking delta looks like:

Thinking delta
event: content_block_delta
data: {"type": "content_block_delta", "index": 0, "delta": {"type": "thinking_delta", "thinking": "I need to find the GCD of 1071 and 462 using the Euclidean algorithm.\n\n1071 = 2 × 462 + 147"}}
The signature delta looks like:

Signature delta
event: content_block_delta
data: {"type": "content_block_delta", "index": 0, "delta": {"type": "signature_delta", "signature": "EqQBCgIYAhIM1gbcDa9GJwZA2b3hGgxBdjrkzLoky3dl1pkiMOYds..."}}
Full HTTP Stream response
Use the client SDKs when using streaming mode. However, if you are building a direct API integration, you need to handle these events yourself.