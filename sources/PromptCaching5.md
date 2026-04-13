
Prompt caching examples
To help you get started with prompt caching, the prompt caching cookbook provides detailed examples and best practices.

The following code snippets showcase various prompt caching patterns. These examples demonstrate how to implement caching in different scenarios, helping you understand the practical applications of this feature:


Large context caching example

Caching tool definitions

Continuing a multi-turn conversation

Putting it all together: Multiple cache breakpoints
Data retention
Prompt caching (both automatic and explicit) is ZDR eligible. Anthropic does not store the raw text of your prompts or Claude's responses.

KV (key-value) cache representations and cryptographic hashes of cached content are held in memory only and are not stored at rest. Cached entries have a minimum lifetime of 5 minutes (standard) or 60 minutes (extended), after which they are promptly, though not immediately, deleted. Cache entries are isolated between organizations.

For ZDR eligibility across all features, see API and data retention.

FAQ

Do I need multiple cache breakpoints or is one at the end sufficient?
In most cases, a single cache breakpoint at the end of your static content is sufficient. Cache writes happen only at the block you mark. Place it on the last block that stays identical across requests, and every subsequent request reads that same entry. If a later block varies per request (a timestamp, the incoming message), keep the breakpoint before it, on the last stable block.

You only need multiple breakpoints if:

A growing conversation pushes your breakpoint 20 or more blocks past the last cache write, putting the prior entry outside the lookback window
You want to cache sections that update at different frequencies independently
You need explicit control over what gets cached for cost optimization
Example: If you have system instructions (rarely change) and RAG context (changes daily), you might use two breakpoints to cache them separately.

Do cache breakpoints add extra cost?
No, cache breakpoints themselves are free. You only pay for:

Writing content to cache (25% more than base input tokens for 5-minute TTL)
Reading from cache (10% of base input token price)
Regular input tokens for uncached content
The number of breakpoints doesn't affect pricing - only the amount of content cached and read matters.

How do I calculate total input tokens from the usage fields?
The usage response includes three separate input token fields that together represent your total input:

total_input_tokens = cache_read_input_tokens + cache_creation_input_tokens + input_tokens
cache_read_input_tokens: Tokens retrieved from cache (everything before cache breakpoints that was cached)
cache_creation_input_tokens: New tokens being written to cache (at cache breakpoints)
input_tokens: Tokens after the last cache breakpoint that aren't cached
Important: input_tokens does NOT represent all input tokens - only the portion after your last cache breakpoint. If you have cached content, input_tokens will typically be much smaller than your total input.

Example: With a 200k token document cached and a 50 token user question:

cache_read_input_tokens: 200,000
cache_creation_input_tokens: 0
input_tokens: 50
Total: 200,050 tokens
This breakdown is critical for understanding both your costs and rate limit usage. See Tracking cache performance for more details.

What is the cache lifetime?
The cache's default minimum lifetime (TTL) is 5 minutes. This lifetime is refreshed each time the cached content is used.

If you find that 5 minutes is too short, Anthropic also offers a 1-hour cache TTL.

How many cache breakpoints can I use?
You can define up to 4 cache breakpoints (using cache_control parameters) in your prompt.

Is prompt caching available for all models?
Prompt caching is supported on all active Claude models.

How does prompt caching work with extended thinking?
Cached system prompts and tools will be reused when thinking parameters change. However, thinking changes (enabling/disabling or budget changes) will invalidate previously cached prompt prefixes with messages content.

For more details on cache invalidation, see What invalidates the cache.

For more on extended thinking, including its interaction with tool use and prompt caching, see the extended thinking documentation.

How do I enable prompt caching?
The easiest way is to add "cache_control": {"type": "ephemeral"} at the top level of your request body (automatic caching). Alternatively, include at least one cache_control breakpoint on individual content blocks (explicit cache breakpoints).

Can I use prompt caching with other API features?
Yes, prompt caching can be used alongside other API features like tool use and vision capabilities. However, changing whether there are images in a prompt or modifying tool use settings will break the cache.

For more details on cache invalidation, see What invalidates the cache.

How does prompt caching affect pricing?
Prompt caching introduces a new pricing structure where cache writes cost 25% more than base input tokens, while cache hits cost only 10% of the base input token price.

Can I manually clear the cache?
Currently, there's no way to manually clear the cache. Cached prefixes automatically expire after a minimum of 5 minutes of inactivity.

How can I track the effectiveness of my caching strategy?
You can monitor cache performance using the cache_creation_input_tokens and cache_read_input_tokens fields in the API response.

What can break the cache?
See What invalidates the cache for more details on cache invalidation, including a list of changes that require creating a new cache entry.

How does prompt caching handle privacy and data separation?
Prompt caching is designed with strong privacy and data separation measures: