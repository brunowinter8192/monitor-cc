Context editing

Copy page

Automatically manage conversation context as it grows with context editing.
This feature is eligible for Zero Data Retention (ZDR). When your organization has a ZDR arrangement, data sent through this feature is not stored after the API response is returned.
Overview
For most use cases, server-side compaction is the primary strategy for managing context in long-running conversations. The strategies on this page are useful for specific scenarios where you need more fine-grained control over what content is cleared.
Context editing allows you to selectively clear specific content from conversation history as it grows. Beyond optimizing costs and staying within limits, this is about actively curating what Claude sees: context is a finite resource with diminishing returns, and irrelevant content degrades model focus. Context editing gives you fine-grained runtime control over that curation. For the broader principles behind context management, see Effective context engineering. This page covers:

Tool result clearing - Best for agentic workflows with heavy tool use where old tool results are no longer needed
Thinking block clearing - For managing thinking blocks when using extended thinking, with options to preserve recent thinking for context continuity
Client-side SDK compaction - An SDK-based alternative for summary-based context management (server-side compaction is generally preferred)
Approach	Where it runs	Strategies	How it works
Server-side	API	Tool result clearing (clear_tool_uses_20250919)
Thinking block clearing (clear_thinking_20251015)	Applied before the prompt reaches Claude. Clears specific content from conversation history. Each strategy can be configured independently.
Client-side	SDK	Compaction	Available in Python, TypeScript, and Ruby SDKs when using tool_runner. Generates a summary and replaces full conversation history. See Client-side compaction below.
Server-side strategies
Context editing is in beta with support for tool result clearing and thinking block clearing. To enable it, use the beta header context-management-2025-06-27 in your API requests.

Share feedback on this feature through the feedback form.
Tool result clearing
The clear_tool_uses_20250919 strategy clears tool results when conversation context grows beyond your configured threshold. This is particularly useful for agentic workflows with heavy tool use. Older tool results (like file contents or search results) are no longer needed once Claude has processed them.

When activated, the API automatically clears the oldest tool results in chronological order. The API replaces each cleared result with placeholder text so Claude knows it was removed. By default, only tool results are cleared. You can optionally clear both tool results and tool calls (the tool use parameters) by setting clear_tool_inputs to true.

Thinking block clearing
The clear_thinking_20251015 strategy manages thinking blocks in conversations when extended thinking is enabled. This strategy gives you control over thinking preservation: you can choose to keep more thinking blocks to maintain reasoning continuity, or clear them more aggressively to save context space.

Default behavior: When extended thinking is enabled without configuring the clear_thinking_20251015 strategy, the API automatically keeps only the thinking blocks from the last assistant turn (equivalent to keep: {type: "thinking_turns", value: 1}).

To maximize cache hits, preserve all thinking blocks by setting keep: "all".
An assistant conversation turn may include multiple content blocks (e.g. when using tools) and multiple thinking blocks (e.g. with interleaved thinking).

Context editing happens server-side
Context editing is applied server-side before the prompt reaches Claude. Your client application maintains the full, unmodified conversation history. You do not need to sync your client state with the edited version. Continue managing your full conversation history locally as you normally would.

Context editing and prompt caching
Context editing's interaction with prompt caching varies by strategy:

Tool result clearing: Invalidates cached prompt prefixes when content is cleared. To account for this, clear enough tokens to make the cache invalidation worthwhile. Use the clear_at_least parameter to ensure a minimum number of tokens is cleared each time. You'll incur cache write costs each time content is cleared, but subsequent requests can reuse the newly cached prefix.
Thinking block clearing: When thinking blocks are kept in context (not cleared), the prompt cache is preserved, enabling cache hits and reducing input token costs. When thinking blocks are cleared, the cache is invalidated at the point where clearing occurs. Configure the keep parameter based on whether you want to prioritize cache performance or context window availability.
Supported models
Context editing is available on all supported Claude models.

Tool result clearing usage
The simplest way to enable tool result clearing is to specify only the strategy type. All other configuration options use their default values:

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
                "content": "Search for recent developments in AI"
            }
        ],
        "tools": [
            {
                "type": "web_search_20250305",
                "name": "web_search"
            }
        ],
        "context_management": {
            "edits": [
                {"type": "clear_tool_uses_20250919"}
            ]
        }
    }'
Advanced configuration
You can customize the tool result clearing behavior with additional parameters:
