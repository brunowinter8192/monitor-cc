Prompt caching

Copy page

Prompt caching optimizes your API usage by allowing resuming from specific prefixes in your prompts. This significantly reduces processing time and costs for repetitive tasks or prompts with consistent elements.

This feature is eligible for Zero Data Retention (ZDR). When your organization has a ZDR arrangement, data sent through this feature is not stored after the API response is returned.
There are two ways to enable prompt caching:

Automatic caching: Add a single cache_control field at the top level of your request. The system automatically applies the cache breakpoint to the last cacheable block and moves it forward as conversations grow. Best for multi-turn conversations where the growing message history should be cached automatically.
Explicit cache breakpoints: Place cache_control directly on individual content blocks for fine-grained control over exactly what gets cached.
The simplest way to start is with automatic caching:

Shell
curl https://api.anthropic.com/v1/messages \
  -H "content-type: application/json" \
  -H "x-api-key: $ANTHROPIC_API_KEY" \
  -H "anthropic-version: 2023-06-01" \
  -d '{
    "model": "claude-opus-4-6",
    "max_tokens": 1024,
    "cache_control": {"type": "ephemeral"},
    "system": "You are an AI assistant tasked with analyzing literary works. Your goal is to provide insightful commentary on themes, characters, and writing style.",
    "messages": [
      {
        "role": "user",
        "content": "Analyze the major themes in Pride and Prejudice."
      }
    ]
  }'
With automatic caching, the system caches all content up to and including the last cacheable block. On subsequent requests with the same prefix, cached content is reused automatically.

How prompt caching works
When you send a request with prompt caching enabled:

The system checks if a prompt prefix, up to a specified cache breakpoint, is already cached from a recent query.
If found, it uses the cached version, reducing processing time and costs.
Otherwise, it processes the full prompt and caches the prefix once the response begins.
This is especially useful for:

Prompts with many examples
Large amounts of context or background information
Repetitive tasks with consistent instructions
Long multi-turn conversations
By default, the cache has a 5-minute lifetime. The cache is refreshed for no additional cost each time the cached content is used.

If you find that 5 minutes is too short, Anthropic also offers a 1-hour cache duration at additional cost.

For more information, see 1-hour cache duration.
Prompt caching caches the full prefix

Prompt caching references the entire prompt - tools, system, and messages (in that order) up to and including the block designated with cache_control.
Pricing
Prompt caching introduces a new pricing structure. The table below shows the price per million tokens for each supported model:

Model	Base Input Tokens	5m Cache Writes	1h Cache Writes	Cache Hits & Refreshes	Output Tokens
Claude Opus 4.6	$5 / MTok	$6.25 / MTok	$10 / MTok	$0.50 / MTok	$25 / MTok
Claude Opus 4.5	$5 / MTok	$6.25 / MTok	$10 / MTok	$0.50 / MTok	$25 / MTok
Claude Opus 4.1	$15 / MTok	$18.75 / MTok	$30 / MTok	$1.50 / MTok	$75 / MTok
Claude Opus 4	$15 / MTok	$18.75 / MTok	$30 / MTok	$1.50 / MTok	$75 / MTok
Claude Sonnet 4.6	$3 / MTok	$3.75 / MTok	$6 / MTok	$0.30 / MTok	$15 / MTok
Claude Sonnet 4.5	$3 / MTok	$3.75 / MTok	$6 / MTok	$0.30 / MTok	$15 / MTok
Claude Sonnet 4	$3 / MTok	$3.75 / MTok	$6 / MTok	$0.30 / MTok	$15 / MTok
Claude Sonnet 3.7 (deprecated)	$3 / MTok	$3.75 / MTok	$6 / MTok	$0.30 / MTok	$15 / MTok
Claude Haiku 4.5	$1 / MTok	$1.25 / MTok	$2 / MTok	$0.10 / MTok	$5 / MTok
Claude Haiku 3.5	$0.80 / MTok	$1 / MTok	$1.6 / MTok	$0.08 / MTok	$4 / MTok
Claude Opus 3 (deprecated)	$15 / MTok	$18.75 / MTok	$30 / MTok	$1.50 / MTok	$75 / MTok
Claude Haiku 3	$0.25 / MTok	$0.30 / MTok	$0.50 / MTok	$0.03 / MTok	$1.25 / MTok
The table above reflects the following pricing multipliers for prompt caching:

5-minute cache write tokens are 1.25 times the base input tokens price
1-hour cache write tokens are 2 times the base input tokens price
Cache read tokens are 0.1 times the base input tokens price
These multipliers stack with other pricing modifiers such as the Batch API discount and data residency. See pricing for full details.
Supported models
Prompt caching (both automatic and explicit) is supported on all active Claude models.

Automatic caching
Automatic caching is the simplest way to enable prompt caching. Instead of placing cache_control on individual content blocks, add a single cache_control field at the top level of your request body. The system automatically applies the cache breakpoint to the last cacheable block.

Shell
curl https://api.anthropic.com/v1/messages \
  -H "content-type: application/json" \
  -H "x-api-key: $ANTHROPIC_API_KEY" \
  -H "anthropic-version: 2023-06-01" \
  -d '{
    "model": "claude-opus-4-6",
    "max_tokens": 1024,
    "cache_control": {"type": "ephemeral"},
    "system": "You are a helpful assistant that remembers our conversation.",
    "messages": [
      {"role": "user", "content": "My name is Alex. I work on machine learning."},
      {"role": "assistant", "content": "Nice to meet you, Alex! How can I help with your ML work today?"},
      {"role": "user", "content": "What did I say I work on?"}
    ]
  }'
How automatic caching works in multi-turn conversations
With automatic caching, the cache point moves forward automatically as conversations grow. Each new request caches everything up to the last cacheable block, and previous content is read from cache.