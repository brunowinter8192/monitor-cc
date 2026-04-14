# If you still get empty responses after fixing the above:
def handle_empty_response(client, messages):
    response = client.messages.create(
        model="claude-opus-4-6", max_tokens=1024, messages=messages
    )

    # Check if response is empty
    if response.stop_reason == "end_turn" and not response.content:
        # INCORRECT: Don't just retry with the empty response
        # This won't work because Claude already decided it's done

        # CORRECT: Add a continuation prompt in a NEW user message
        messages.append({"role": "user", "content": "Please continue"})

        response = client.messages.create(
            model="claude-opus-4-6", max_tokens=1024, messages=messages
        )

    return response
Best practices:

Never add text blocks immediately after tool results - This teaches Claude to expect user input after every tool use
Don't retry empty responses without modification - Simply sending the empty response back won't help
Use continuation prompts as a last resort - Only if the above fixes don't resolve the issue
max_tokens
Claude stopped because it reached the max_tokens limit specified in your request.

Python
# Request with limited tokens
response = client.messages.create(
    model="claude-opus-4-6",
    max_tokens=10,
    messages=[{"role": "user", "content": "Explain quantum physics"}],
)

if response.stop_reason == "max_tokens":
    # Response was truncated
    print("Response was cut off at token limit")
    # Consider making another request to continue
Incomplete tool use blocks
If Claude's response is cut off due to hitting the max_tokens limit, and the truncated response contains an incomplete tool use block, you'll need to retry the request with a higher max_tokens value to get the full tool use.

CLI
RESPONSE=$(ant messages create --max-tokens 1024 \
  --format jsonl < request.yaml)

# Check if the response was truncated mid tool use
STOP_REASON=$(jq -r '.stop_reason' <<<"$RESPONSE")
LAST_TYPE=$(jq -r '.content[-1].type' <<<"$RESPONSE")
if [ "$STOP_REASON" = "max_tokens" ] && [ "$LAST_TYPE" = "tool_use" ]; then
  # Retry with a higher max_tokens
  ant messages create --max-tokens 4096 < request.yaml
fi
stop_sequence
Claude encountered one of your custom stop sequences.

Python
response = client.messages.create(
    model="claude-opus-4-6",
    max_tokens=1024,
    stop_sequences=["END", "STOP"],
    messages=[{"role": "user", "content": "Generate text until you say END"}],
)

if response.stop_reason == "stop_sequence":
    print(f"Stopped at sequence: {response.stop_sequence}")
tool_use
Claude is calling a tool and expects you to execute it.

For most tool use implementations, we recommend using the tool runner which automatically handles tool execution, result formatting, and conversation management.
Python
from anthropic import Anthropic

client = Anthropic()
weather_tool = {
    "name": "get_weather",
    "description": "Get the current weather in a given location",
    "input_schema": {
        "type": "object",
        "properties": {
            "location": {"type": "string", "description": "City and state"},
        },
        "required": ["location"],
    },
}


def execute_tool(name, tool_input):
    """Execute a tool and return the result."""
    return f"Weather in {tool_input.get('location', 'unknown')}: 72°F"


response = client.messages.create(
    model="claude-sonnet-4-20250514",
    max_tokens=1024,
    tools=[weather_tool],
    messages=[{"role": "user", "content": "What's the weather?"}],
)

if response.stop_reason == "tool_use":
    # Extract and execute the tool
    for content in response.content:
        if content.type == "tool_use":
            result = execute_tool(content.name, content.input)
            # Return result to Claude for final response
pause_turn
Returned when the server-side sampling loop reaches its iteration limit while executing server tools like web search or web fetch. The default limit is 10 iterations per request.

When this happens, the response may contain a server_tool_use block without a corresponding server_tool_result. To let Claude finish processing, continue the conversation by sending the response back as-is.

