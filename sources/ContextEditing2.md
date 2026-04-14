
Shell
curl https://api.anthropic.com/v1/messages \
    --header "x-api-key: $ANTHROPIC_API_KEY" \
    --header "anthropic-version: 2023-06-01" \
    --header "content-type: application/json" \
    --header "anthropic-beta: context-management-2025-06-27" \
    --data '{
        "model": "claude-opus-4-6",
        "max_tokens": 4096,
        "messages": [
            {
                "role": "user",
                "content": "Create a simple command line calculator app using Python"
            }
        ],
        "tools": [
            {
                "type": "text_editor_20250728",
                "name": "str_replace_based_edit_tool",
                "max_characters": 10000
            },
            {
                "type": "web_search_20250305",
                "name": "web_search",
                "max_uses": 3
            }
        ],
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
                        "value": 3
                    },
                    "clear_at_least": {
                        "type": "input_tokens",
                        "value": 5000
                    },
                    "exclude_tools": ["web_search"]
                }
            ]
        }
    }'
Thinking block clearing usage
Enable thinking block clearing to manage context and prompt caching effectively when extended thinking is enabled:

Shell
curl https://api.anthropic.com/v1/messages \
    --header "x-api-key: $ANTHROPIC_API_KEY" \
    --header "anthropic-version: 2023-06-01" \
    --header "content-type: application/json" \
    --header "anthropic-beta: context-management-2025-06-27" \
    --data '{
        "model": "claude-opus-4-6",
        "max_tokens": 16000,
        "messages": [{"role": "user", "content": "Hello"}],
        "thinking": {
            "type": "enabled",
            "budget_tokens": 10000
        },
        "context_management": {
            "edits": [
                {
                    "type": "clear_thinking_20251015",
                    "keep": {
                        "type": "thinking_turns",
                        "value": 2
                    }
                }
            ]
        }
    }'
Configuration options for thinking block clearing
The clear_thinking_20251015 strategy supports the following configuration:

Configuration option	Default	Description
keep	{type: "thinking_turns", value: 1}	Defines how many recent assistant turns with thinking blocks to preserve. Use {type: "thinking_turns", value: N} where N must be > 0 to keep the last N turns, or "all" to keep all thinking blocks.
Example configurations:

Keep thinking blocks from the last 3 assistant turns:

{
  "type": "clear_thinking_20251015",
  "keep": {
    "type": "thinking_turns",
    "value": 3
  }
}
Keep all thinking blocks (maximizes cache hits):

{
  "type": "clear_thinking_20251015",
  "keep": "all"
}
Combining strategies
You can use both thinking block clearing and tool result clearing together:

When using multiple strategies, the clear_thinking_20251015 strategy must be listed first in the edits array.
CLI
ant beta:messages create --beta context-management-2025-06-27 <<'YAML'
model: claude-opus-4-6
max_tokens: 16000
thinking:
  type: enabled
  budget_tokens: 10000
messages:
  - role: user
    content: Hello
tools:
  - type: web_search_20250305
    name: web_search
context_management:
  edits:
    - type: clear_thinking_20251015
      keep:
        type: thinking_turns
        value: 2
    - type: clear_tool_uses_20250919
      trigger:
        type: input_tokens
        value: 50000
      keep:
        type: tool_uses
        value: 5
