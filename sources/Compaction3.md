CLI
ant beta:messages create --beta compact-2026-01-12 \
  --transform content --format jsonl <<'YAML' > content.json
model: claude-opus-4-6
max_tokens: 4096
messages:
  - role: user
    content: Hello, Claude
context_management:
  edits:
    - type: compact_20260112
YAML

# After receiving a response with a compaction block, append it as the
# assistant turn and continue the conversation
ant beta:messages create --beta compact-2026-01-12 <<YAML
model: claude-opus-4-6
max_tokens: 4096
messages:
  - role: user
    content: Hello, Claude
  - role: assistant
    content: $(cat content.json)
  - role: user
    content: Now add error handling
context_management:
  edits:
    - type: compact_20260112
YAML
When the API receives a compaction block, all content blocks before it are ignored. You can either:

Keep the original messages in your list and let the API handle removing the compacted content
Manually drop the compacted messages and only include the compaction block onwards
Streaming
When streaming responses with compaction enabled, you'll receive a content_block_start event when compaction begins. The compaction block streams differently from text blocks. You'll receive a content_block_start event, followed by a single content_block_delta with the complete summary content (no intermediate streaming), and then a content_block_stop event.

CLI
ant beta:messages create --stream --format jsonl \
  --beta compact-2026-01-12 <<'YAML'
model: claude-opus-4-6
max_tokens: 4096
messages:
  - role: user
    content: Hello, Claude
context_management:
  edits:
    - type: compact_20260112
YAML
Prompt caching
Compaction works well with prompt caching. You can add a cache_control breakpoint on compaction blocks to cache the summarized content. The original compacted content is ignored.

{
  "role": "assistant",
  "content": [
    {
      "type": "compaction",
      "content": "[summary text]",
      "cache_control": { "type": "ephemeral" }
    },
    {
      "type": "text",
      "text": "Based on our conversation..."
    }
  ]
}
Maximizing cache hits with system prompts
When compaction occurs, the summary becomes new content that needs to be written to the cache. Without additional cache breakpoints, this would also invalidate any cached system prompt, requiring it to be re-cached along with the compaction summary.

To maximize cache hit rates, add a cache_control breakpoint at the end of your system prompt. This keeps the system prompt cached separately from the conversation, so when compaction occurs:

The system prompt cache remains valid and is read from cache
Only the compaction summary needs to be written as a new cache entry
CLI
ant beta:messages create --beta compact-2026-01-12 <<'YAML'
model: claude-opus-4-6
max_tokens: 4096
system:
  - type: text
    text: You are a helpful coding assistant...
    cache_control:
      type: ephemeral
messages:
  - role: user
    content: Hello, Claude
context_management:
  edits:
    - type: compact_20260112
YAML
This approach is particularly beneficial for long system prompts, as they remain cached even across multiple compaction events throughout a conversation.

Understanding usage
Compaction requires an additional sampling step, which contributes to rate limits and billing. The API returns detailed usage information in the response:

Output
{
  "usage": {
    "input_tokens": 23000,
    "output_tokens": 1000,
    "iterations": [
      {
        "type": "compaction",
        "input_tokens": 180000,
        "output_tokens": 3500
      },
      {
        "type": "message",
        "input_tokens": 23000,
        "output_tokens": 1000
      }
    ]
  }
}
The iterations array shows usage for each sampling iteration. When compaction occurs, you'll see a compaction iteration followed by the main message iteration. The top-level input_tokens and output_tokens match the message iteration exactly in this example because there is only one non-compaction iteration. The final iteration's token counts reflect the effective context size after compaction.

