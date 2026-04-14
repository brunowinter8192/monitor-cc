Compaction

Copy page

Server-side context compaction for managing long conversations that approach context window limits.
This feature is eligible for Zero Data Retention (ZDR). When your organization has a ZDR arrangement, data sent through this feature is not stored after the API response is returned.
Server-side compaction is the recommended strategy for managing context in long-running conversations and agentic workflows. It handles context management automatically with minimal integration work.
Compaction extends the effective context length for long-running conversations and tasks by automatically summarizing older context when approaching the context window limit. This isn't just about staying under a token cap. As conversations get longer, models struggle to maintain focus across the full history. Compaction keeps the active context focused and performant by replacing stale content with concise summaries.

For a deeper look at why long contexts degrade and how compaction helps, see Effective context engineering.
This is ideal for:

Chat-based, multi-turn conversations where you want users to use one chat for a long period of time
Task-oriented prompts that require a lot of follow-up work (often tool use) that may exceed the context window
Compaction is in beta. Include the beta header compact-2026-01-12 in your API requests to use this feature.
Supported models
Compaction is supported on the following models:

Claude Mythos Preview (claude-mythos-preview)
Claude Opus 4.6 (claude-opus-4-6)
Claude Sonnet 4.6 (claude-sonnet-4-6)
How compaction works
When compaction is enabled, Claude automatically summarizes your conversation when it approaches the configured token threshold. The API:

Detects when input tokens exceed your specified trigger threshold.
Generates a summary of the current conversation.
Creates a compaction block containing the summary.
Continues the response with the compacted context.
On subsequent requests, append the response to your messages. The API automatically drops all message blocks prior to the compaction block, continuing the conversation from the summary.

Flow diagram showing the compaction process: when input tokens exceed the trigger threshold, Claude generates a summary in a compaction block and continues the response with the compacted context
Basic usage
Enable compaction by adding the compact_20260112 strategy to context_management.edits in your Messages API request.

Shell
curl https://api.anthropic.com/v1/messages \
     --header "x-api-key: $ANTHROPIC_API_KEY" \
     --header "anthropic-version: 2023-06-01" \
     --header "anthropic-beta: compact-2026-01-12" \
     --header "content-type: application/json" \
     --data \
'{
    "model": "claude-opus-4-6",
    "max_tokens": 4096,
    "messages": [
        {
            "role": "user",
            "content": "Help me build a website"
        }
    ],
    "context_management": {
        "edits": [
            {
                "type": "compact_20260112"
            }
        ]
    }
}'
Parameters
Parameter	Type	Default	Description
type	string	Required	Must be "compact_20260112"
trigger	object	150,000 tokens	When to trigger compaction. Must be at least 50,000 tokens.
pause_after_compaction	boolean	false	Whether to pause after generating the compaction summary
instructions	string	null	Custom summarization prompt. Completely replaces the default prompt when provided.
Trigger configuration
Configure when compaction triggers using the trigger parameter:

CLI
ant beta:messages create --beta compact-2026-01-12 <<'YAML'
model: claude-opus-4-6
max_tokens: 4096
messages:
  - role: user
    content: Hello, Claude
context_management:
  edits:
    - type: compact_20260112
      trigger:
        type: input_tokens
        value: 150000
YAML
Custom summarization instructions
By default, compaction uses the following summarization prompt:

You have written a partial transcript for the initial task above. Please write a summary of the transcript. The purpose of this summary is to provide continuity so you can continue to make progress towards solving the task in a future context, where the raw history above may not be accessible and will be replaced with this summary. Write down anything that would be helpful, including the state, next steps, learnings etc. You must wrap your summary in a <summary></summary> block.
You can provide custom instructions via the instructions parameter to replace this prompt entirely. Custom instructions don't supplement the default; they completely replace it:

CLI
ant beta:messages create --beta compact-2026-01-12 <<'YAML'
model: claude-opus-4-6
max_tokens: 4096
messages:
  - role: user
    content: Hello, Claude
context_management:
  edits:
    - type: compact_20260112
      instructions: >-
        Focus on preserving code snippets, variable names, and
        technical decisions.
YAML
Pausing after compaction
Use pause_after_compaction to pause the API after generating the compaction summary. This allows you to add additional content blocks (such as preserving recent messages or specific instruction-oriented messages) before the API continues with the response.
