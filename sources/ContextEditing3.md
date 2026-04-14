YAML
Configuration options for tool result clearing
Configuration option	Default	Description
trigger	100,000 input tokens	Defines when the context editing strategy activates. Once the prompt exceeds this threshold, clearing will begin. You can specify this value in either input_tokens or tool_uses.
keep	3 tool uses	Defines how many recent tool use/result pairs to keep after clearing occurs. The API removes the oldest tool interactions first, preserving the most recent ones.
clear_at_least	None	Ensures a minimum number of tokens is cleared each time the strategy activates. If the API can't clear at least the specified amount, the strategy will not be applied. This helps determine if context clearing is worth breaking your prompt cache.
exclude_tools	None	List of tool names whose tool uses and results should never be cleared. Useful for preserving important context.
clear_tool_inputs	false	Controls whether the tool call parameters are cleared along with the tool results. By default, only the tool results are cleared while keeping Claude's original tool calls visible.
Context editing response
You can see which context edits were applied to your request using the context_management response field, along with helpful statistics about the content and input tokens cleared.

Output
{
  "id": "msg_013Zva2CMHLNnXjNJJKqJ2EF",
  "type": "message",
  "role": "assistant",
  "content": [
    // ...
  ],
  "usage": {
    // ...
  },
  "context_management": {
    "applied_edits": [
      // When using `clear_thinking_20251015`
      {
        "type": "clear_thinking_20251015",
        "cleared_thinking_turns": 3,
        "cleared_input_tokens": 15000
      },
      // When using `clear_tool_uses_20250919`
      {
        "type": "clear_tool_uses_20250919",
        "cleared_tool_uses": 8,
        "cleared_input_tokens": 50000
      }
    ]
  }
}
For streaming responses, the context edits will be included in the final message_delta event:

Streaming Response
{
  "type": "message_delta",
  "delta": {
    "stop_reason": "end_turn",
    "stop_sequence": null
  },
  "usage": {
    "output_tokens": 1024
  },
  "context_management": {
    "applied_edits": [
      // ...
    ]
  }
}
Token counting
The token counting endpoint supports context management, allowing you to preview how many tokens your prompt will use after context editing is applied.

Shell
curl https://api.anthropic.com/v1/messages/count_tokens \
    --header "x-api-key: $ANTHROPIC_API_KEY" \
    --header "anthropic-version: 2023-06-01" \
    --header "content-type: application/json" \
    --header "anthropic-beta: context-management-2025-06-27" \
    --data '{
        "model": "claude-opus-4-6",
        "messages": [
            {
                "role": "user",
                "content": "Continue our conversation..."
            }
        ],
        "tools": [],
        "context_management": {
            "edits": [
                {
                    "type": "clear_tool_uses_20250919",
                    "trigger": {
                        "type": "input_tokens",
                        "value": 30000
                    },
                    "keep": {
                        "type": "tool_uses",
                        "value": 5
                    }
                }
            ]
        }
    }'
Output
{
  "input_tokens": 25000,
  "context_management": {
    "original_input_tokens": 70000
  }
}
The response shows both the final token count after context management is applied (input_tokens) and the original token count before any clearing occurred (original_input_tokens).

Using with the Memory Tool
Context editing can be combined with the memory tool. When your conversation context approaches the configured clearing threshold, Claude receives an automatic warning to preserve important information. This enables Claude to save tool results or context to its memory files before they're cleared from the conversation history.

This combination allows you to:

Preserve important context: Claude can write essential information from tool results to memory files before those results are cleared
Maintain long-running workflows: Enable agentic workflows that would otherwise exceed context limits by offloading information to persistent storage
Access information on demand: Claude can look up previously cleared information from memory files when needed, rather than keeping everything in the active context window
For example, in a file editing workflow where Claude performs many operations, Claude can summarize completed changes to memory files as the context grows. When tool results are cleared, Claude retains access to that information through its memory system and can continue working effectively.

To use both features together, enable them in your API request:

CLI
ant beta:messages create --beta context-management-2025-06-27 <<'YAML'
model: claude-opus-4-6
max_tokens: 4096
messages:
  - role: user
    content: Hello
tools:
  - type: memory_20250818
    name: memory
context_management:
  edits:
    - type: clear_tool_uses_20250919
YAML
For the full memory tool reference including commands and examples, see Memory tool.

