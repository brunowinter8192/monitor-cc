Python
response = client.messages.create(
    model="claude-opus-4-6",
    max_tokens=1024,
    tools=[{"type": "web_search_20250305", "name": "web_search"}],
    messages=[{"role": "user", "content": "Search for latest AI news"}],
)

if response.stop_reason == "pause_turn":
    # Continue the conversation by sending the response back
    messages = [
        {"role": "user", "content": original_query},
        {"role": "assistant", "content": response.content},
    ]
    continuation = client.messages.create(
        model="claude-opus-4-6",
        messages=messages,
        tools=[{"type": "web_search_20250305", "name": "web_search"}],
    )
Your application should handle pause_turn in any agent loop that uses server tools. Simply add the assistant's response to your messages array and make another API request to let Claude continue.
refusal
Claude refused to generate a response due to safety concerns.

Python
response = client.messages.create(
    model="claude-opus-4-6",
    max_tokens=1024,
    messages=[{"role": "user", "content": "[Unsafe request]"}],
)

if response.stop_reason == "refusal":
    # Claude declined to respond
    print("Claude was unable to process this request")
    # Consider rephrasing or modifying the request
If you encounter refusal stop reasons frequently while using Claude Sonnet 4.5 or Opus 4.1, you can try updating your API calls to use Sonnet 4 (claude-sonnet-4-20250514), which has different usage restrictions. Learn more about understanding Sonnet 4.5's API safety filters.
To learn more about refusals triggered by API safety filters for Claude Sonnet 4.5, see Understanding Sonnet 4.5's API Safety Filters.
model_context_window_exceeded
Claude stopped because it reached the model's context window limit. This allows you to request the maximum possible tokens without knowing the exact input size.

Python
# Request with maximum tokens to get as much as possible
response = client.messages.create(
    model="claude-opus-4-6",
    max_tokens=64000,  # Practical non-streaming ceiling (Opus 4.6 supports 128K with streaming)
    messages=[
        {"role": "user", "content": "Large input that uses most of context window..."}
    ],
)

if response.stop_reason == "model_context_window_exceeded":
    # Response hit context window limit before max_tokens
    print("Response reached model's context window limit")
    # The response is still valid but was limited by context window
This stop reason is available by default in Sonnet 4.5 and newer models. For earlier models, use the beta header model-context-window-exceeded-2025-08-26 to enable this behavior.
Best practices for handling stop reasons
1. Always check stop_reason
Make it a habit to check the stop_reason in your response handling logic:

def handle_response(response):
    if response.stop_reason == "tool_use":
        return handle_tool_use(response)
    elif response.stop_reason == "max_tokens":
        return handle_truncation(response)
    elif response.stop_reason == "model_context_window_exceeded":
        return handle_context_limit(response)
    elif response.stop_reason == "pause_turn":
        return handle_pause(response)
    elif response.stop_reason == "refusal":
        return handle_refusal(response)
    else:
        # Handle end_turn and other cases
        return response.content[0].text
2. Handle truncated responses gracefully
When a response is truncated due to token limits or context window:

def handle_truncated_response(response):
    if response.stop_reason in ["max_tokens", "model_context_window_exceeded"]:
        # Option 1: Warn the user about the specific limit
        if response.stop_reason == "max_tokens":
            message = "[Response truncated due to max_tokens limit]"
        else:
            message = "[Response truncated due to context window limit]"
        return f"{response.content[0].text}\n\n{message}"

        # Option 2: Continue generation
        messages = [
            {"role": "user", "content": original_prompt},
            {"role": "assistant", "content": response.content[0].text},
        ]
        continuation = client.messages.create(
            model="claude-opus-4-6",
            max_tokens=1024,
            messages=messages + [{"role": "user", "content": "Please continue"}],
        )
        return response.content[0].text + continuation.content[0].text
3. Implement retry logic for pause_turn
When using server tools, the API may return pause_turn if the server-side sampling loop reaches its iteration limit (default 10). Handle this by continuing the conversation:

def handle_server_tool_conversation(client, user_query, tools, max_continuations=5):
    """
