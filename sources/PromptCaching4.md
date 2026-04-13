
Request 3:
User: ["What's the weather in Paris?"],
Assistant: [thinking_block_1] + [tool_use block 1],
User: [tool_result_1, cache=True],
Assistant: [thinking_block_2] + [text block 2],
User: [Text response, cache=True]
# Non-tool-result user block causes all thinking blocks to be ignored
# This request is processed as if thinking blocks were never present
When a non-tool-result user block is included, it designates a new assistant loop and all previous thinking blocks are removed from context.

For more detailed information, see the extended thinking documentation.

Cache storage and sharing
Starting February 5, 2026, prompt caching will use workspace-level isolation instead of organization-level isolation. Caches will be isolated per workspace, ensuring data separation between workspaces within the same organization. This change applies to the Claude API and Azure AI Foundry (preview); Amazon Bedrock and Google Vertex AI will maintain organization-level cache isolation. If you use multiple workspaces, review your caching strategy to account for this change.
Organization Isolation: Caches are isolated between organizations. Different organizations never share caches, even if they use identical prompts.
Exact Matching: Cache hits require 100% identical prompt segments, including all text and images up to and including the block marked with cache control.
Output Token Generation: Prompt caching has no effect on output token generation. The response you receive will be identical to what you would get if prompt caching was not used.
Best practices for effective caching
To optimize prompt caching performance:

Start with automatic caching for multi-turn conversations. It handles breakpoint management automatically.
Use explicit block-level breakpoints when you need to cache different sections with different change frequencies.
Cache stable, reusable content like system instructions, background information, large contexts, or frequent tool definitions.
Place cached content at the prompt's beginning for best performance.
Use cache breakpoints strategically to separate different cacheable prefix sections.
Place the breakpoint on the last block that stays identical across requests. For a prompt with a static prefix and a varying suffix (timestamps, per-request context, the incoming message), that is the end of the prefix, not the varying block.
Regularly analyze cache hit rates and adjust your strategy as needed.
Optimizing for different use cases
Tailor your prompt caching strategy to your scenario:

Conversational agents: Reduce cost and latency for extended conversations, especially those with long instructions or uploaded documents.
Coding assistants: Improve autocomplete and codebase Q&A by keeping relevant sections or a summarized version of the codebase in the prompt.
Large document processing: Incorporate complete long-form material including images in your prompt without increasing response latency.
Detailed instruction sets: Share extensive lists of instructions, procedures, and examples to fine-tune Claude's responses. Developers often include an example or two in the prompt, but with prompt caching you can get even better performance by including 20+ diverse examples of high quality answers.
Agentic tool use: Enhance performance for scenarios involving multiple tool calls and iterative code changes, where each step typically requires a new API call.
Talk to books, papers, documentation, podcast transcripts, and other longform content: Bring any knowledge base alive by embedding the entire document(s) into the prompt, and letting users ask it questions.
Troubleshooting common issues
If experiencing unexpected behavior:

Ensure cached sections are identical across calls. For explicit breakpoints, verify that cache_control markers are in the same locations
Check that calls are made within the cache lifetime (5 minutes by default)
Verify that tool_choice and image usage remain consistent between calls
Validate that you are caching at least the minimum number of tokens for the model you are using (see Cache limitations). Length-based caching failures are silent: the request succeeds but both cache_creation_input_tokens and cache_read_input_tokens will be 0
Confirm your breakpoint is on a block that stays identical across requests. Cache writes happen only at the breakpoint, and if that block changes (timestamps, per-request context, the incoming message), the prefix hash never matches. The lookback does not find stable content behind the breakpoint; it only finds entries that earlier requests wrote at their own breakpoints
Verify that the keys in your tool_use content blocks have stable ordering as some languages (for example, Swift, Go) randomize key order during JSON conversion, breaking caches
Changes to tool_choice or the presence/absence of images anywhere in the prompt will invalidate the cache, requiring a new cache entry to be created. For more details on cache invalidation, see What invalidates the cache.
1-hour cache duration
If you find that 5 minutes is too short, Anthropic also offers a 1-hour cache duration at additional cost.

To use the extended cache, include ttl in the cache_control definition like this:

"cache_control": {
  "type": "ephemeral",
  "ttl": "1h"
}
The response will include detailed cache information like the following:

Output
{
  "usage": {
    "input_tokens": 2048,
    "cache_read_input_tokens": 1800,
    "cache_creation_input_tokens": 248,
    "output_tokens": 503,

    "cache_creation": {
      "ephemeral_5m_input_tokens": 456,
      "ephemeral_1h_input_tokens": 100
    }
  }
}
Note that the current cache_creation_input_tokens field equals the sum of the values in the cache_creation object.

When to use the 1-hour cache
If you have prompts that are used at a regular cadence (that is, system prompts that are used more frequently than every 5 minutes), continue to use the 5-minute cache, since this will continue to be refreshed at no additional charge.

The 1-hour cache is best used in the following scenarios:

When you have prompts that are likely used less frequently than 5 minutes, but more frequently than every hour. For example, when an agentic side-agent will take longer than 5 minutes, or when storing a long chat conversation with a user and you generally expect that user may not respond in the next 5 minutes.
When latency is important and your follow up prompts may be sent beyond 5 minutes.
When you want to improve your rate limit utilization, since cache hits are not deducted against your rate limit.
The 5-minute and 1-hour cache behave the same with respect to latency. You will generally see improved time-to-first-token for long documents.
Mixing different TTLs
You can use both 1-hour and 5-minute cache controls in the same request, but with an important constraint: Cache entries with longer TTL must appear before shorter TTLs (that is, a 1-hour cache entry must appear before any 5-minute cache entries).

When mixing TTLs, the API determines three billing locations in your prompt:

Position A: The token count at the highest cache hit (or 0 if no hits).
Position B: The token count at the highest 1-hour cache_control block after A (or equals A if none exist).
Position C: The token count at the last cache_control block.
If B and/or C are larger than A, they will necessarily be cache misses, because A is the highest cache hit.
You'll be charged for:

Cache read tokens for A.
1-hour cache write tokens for (B - A).
5-minute cache write tokens for (C - B).
Here are 3 examples. This depicts the input tokens of 3 requests, each of which has different cache hits and cache misses. Each has a different calculated pricing, shown in the colored boxes, as a result. Mixing TTLs Diagram
