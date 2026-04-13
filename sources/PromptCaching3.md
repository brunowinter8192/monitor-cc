4096 tokens for Claude Mythos Preview, Claude Opus 4.6, and Claude Opus 4.5
2048 tokens for Claude Sonnet 4.6
1024 tokens for Claude Sonnet 4.5, Claude Opus 4.1, Claude Opus 4, Claude Sonnet 4, and Claude Sonnet 3.7 (deprecated)
4096 tokens for Claude Haiku 4.5
2048 tokens for Claude Haiku 3.5 (deprecated) and Claude Haiku 3
Shorter prompts cannot be cached, even if marked with cache_control. Any requests to cache fewer than this number of tokens will be processed without caching, and no error is returned. To verify whether a prompt was cached, check the response usage fields: if both cache_creation_input_tokens and cache_read_input_tokens are 0, the prompt was not cached (likely because it did not meet the minimum length requirement).

If your prompt falls just short of the minimum for the model you are using, expanding the cached content to reach the threshold is often worthwhile. Cache reads cost significantly less than uncached input tokens, so reaching the minimum can reduce costs for frequently reused prompts.

For concurrent requests, note that a cache entry only becomes available after the first response begins. If you need cache hits for parallel requests, wait for the first response before sending subsequent requests.

Currently, "ephemeral" is the only supported cache type, which by default has a 5-minute lifetime.

What can be cached
Most blocks in the request can be cached. This includes:

Tools: Tool definitions in the tools array
System messages: Content blocks in the system array
Text messages: Content blocks in the messages.content array, for both user and assistant turns
Images & Documents: Content blocks in the messages.content array, in user turns
Tool use and tool results: Content blocks in the messages.content array, in both user and assistant turns
Each of these elements can be cached, either automatically or by marking them with cache_control.

What cannot be cached
While most request blocks can be cached, there are some exceptions:

Thinking blocks cannot be cached directly with cache_control. However, thinking blocks CAN be cached alongside other content when they appear in previous assistant turns. When cached this way, they DO count as input tokens when read from cache.
Sub-content blocks (like citations) themselves cannot be cached directly. Instead, cache the top-level block.

In the case of citations, the top-level document content blocks that serve as the source material for citations can be cached. This allows you to use prompt caching with citations effectively by caching the documents that citations will reference.
Empty text blocks cannot be cached.
What invalidates the cache
Modifications to cached content can invalidate some or all of the cache.

As described in Structuring your prompt, the cache follows the hierarchy: tools → system → messages. Changes at each level invalidate that level and all subsequent levels.

The following table shows which parts of the cache are invalidated by different types of changes. ✘ indicates that the cache is invalidated, while ✓ indicates that the cache remains valid.

What changes	Tools cache	System cache	Messages cache	Impact
Tool definitions	✘	✘	✘	Modifying tool definitions (names, descriptions, parameters) invalidates the entire cache
Web search toggle	✓	✘	✘	Enabling/disabling web search modifies the system prompt
Citations toggle	✓	✘	✘	Enabling/disabling citations modifies the system prompt
Speed setting	✓	✘	✘	Switching between speed: "fast" and standard speed invalidates system and message caches
Tool choice	✓	✓	✘	Changes to tool_choice parameter only affect message blocks
Images	✓	✓	✘	Adding/removing images anywhere in the prompt affects message blocks
Thinking parameters	✓	✓	✘	Changes to extended thinking settings (enable/disable, budget) affect message blocks
Non-tool results passed to extended thinking requests	✓	✓	✘	When non-tool results are passed in requests while extended thinking is enabled, all previously-cached thinking blocks are stripped from context, and any messages in context that follow those thinking blocks are removed from the cache. For more details, see Caching with thinking blocks.
Tracking cache performance
Monitor cache performance using these API response fields, within usage in the response (or message_start event if streaming):

cache_creation_input_tokens: Number of tokens written to the cache when creating a new entry.
cache_read_input_tokens: Number of tokens retrieved from the cache for this request.
input_tokens: Number of input tokens which were not read from or used to create a cache (that is, tokens after the last cache breakpoint).
Understanding the token breakdown

The input_tokens field represents only the tokens that come after the last cache breakpoint in your request - not all the input tokens you sent.

To calculate total input tokens:

total_input_tokens = cache_read_input_tokens + cache_creation_input_tokens + input_tokens
Spatial explanation:

cache_read_input_tokens = tokens before breakpoint already cached (reads)
cache_creation_input_tokens = tokens before breakpoint being cached now (writes)
input_tokens = tokens after your last breakpoint (not eligible for cache)
Example: If you have a request with 100,000 tokens of cached content (read from cache), 0 tokens of new content being cached, and 50 tokens in your user message (after the cache breakpoint):

cache_read_input_tokens: 100,000
cache_creation_input_tokens: 0
input_tokens: 50
Total input tokens processed: 100,050 tokens
This is important for understanding both costs and rate limits, as input_tokens will typically be much smaller than your total input when using caching effectively.
Caching with thinking blocks
When using extended thinking with prompt caching, thinking blocks have special behavior:

Automatic caching alongside other content: While thinking blocks cannot be explicitly marked with cache_control, they get cached as part of the request content when you make subsequent API calls with tool results. This commonly happens during tool use when you pass thinking blocks back to continue the conversation.

Input token counting: When thinking blocks are read from cache, they count as input tokens in your usage metrics. This is important for cost calculation and token budgeting.

Cache invalidation patterns:

Cache remains valid when only tool results are provided as user messages
Cache gets invalidated when non-tool-result user content is added, causing all previous thinking blocks to be stripped
This caching behavior occurs even without explicit cache_control markers
For more details on cache invalidation, see What invalidates the cache.

Example with tool use:

Request 1: User: "What's the weather in Paris?"
Response: [thinking_block_1] + [tool_use block 1]

Request 2:
User: ["What's the weather in Paris?"],
Assistant: [thinking_block_1] + [tool_use block 1],
User: [tool_result_1, cache=True]
Response: [thinking_block_2] + [text block 2]
# Request 2 caches its request content (not the response)
# The cache includes: user message, thinking_block_1, tool_use block 1, and tool_result_1
