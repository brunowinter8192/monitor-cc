
The tool_search_tool_result format shown in the Response format section is the server-side format used internally by Anthropic's built-in tool search. For custom client-side implementations, always use the standard tool_result format with tool_reference content blocks as shown above.
For a complete example using embeddings, see the tool search with embeddings cookbook.

Error handling
The tool search tool is not compatible with tool use examples. If you need to provide examples of tool usage, use standard tool calling without tool search.
HTTP errors (400 status)
These errors prevent the request from being processed:

All tools deferred:

{
  "type": "error",
  "error": {
    "type": "invalid_request_error",
    "message": "All tools have defer_loading set. At least one tool must be non-deferred."
  }
}
Missing tool definition:

{
  "type": "error",
  "error": {
    "type": "invalid_request_error",
    "message": "Tool reference 'unknown_tool' has no corresponding tool definition"
  }
}
Tool result errors (200 status)
Errors during tool execution return a 200 response with error information in the body:

JSON
{
  "type": "tool_result",
  "tool_use_id": "srvtoolu_01ABC123",
  "content": {
    "type": "tool_search_tool_result_error",
    "error_code": "invalid_pattern"
  }
}
Error codes:

too_many_requests: Rate limit exceeded for tool search operations
invalid_pattern: Malformed regex pattern
pattern_too_long: Pattern exceeds 200 character limit
unavailable: Tool search service temporarily unavailable
Common mistakes

400 Error: All tools are deferred

400 Error: Missing tool definition

Claude doesn't find expected tools
Prompt caching
For how defer_loading preserves prompt caching, see Tool use with prompt caching.

The system automatically expands tool_reference blocks throughout the entire conversation history, so Claude can reuse discovered tools in subsequent turns without re-searching.

Streaming
With streaming enabled, you'll receive tool search events as part of the stream:

event: content_block_start
data: {"type": "content_block_start", "index": 1, "content_block": {"type": "server_tool_use", "id": "srvtoolu_xyz789", "name": "tool_search_tool_regex"}}

// Search query streamed
event: content_block_delta
data: {"type": "content_block_delta", "index": 1, "delta": {"type": "input_json_delta", "partial_json": "{\"query\":\"weather\"}"}}

// Pause while search executes

// Search results streamed
event: content_block_start
data: {"type": "content_block_start", "index": 2, "content_block": {"type": "tool_search_tool_result", "tool_use_id": "srvtoolu_xyz789", "content": {"type": "tool_search_tool_search_result", "tool_references": [{"type": "tool_reference", "tool_name": "get_weather"}]}}}

// Claude continues with discovered tools
Batch requests
You can include the tool search tool in the Messages Batches API. Tool search operations through the Messages Batches API are priced the same as those in regular Messages API requests.

Data retention
Server-side tool search (tool_search tool) indexes and stores tool catalog data (tool names, descriptions, and argument metadata) beyond the immediate API response; this catalog data is retained according to Anthropic's standard retention policy. Custom client-side tool search implementations that use the standard Messages API are fully ZDR-eligible.

For ZDR eligibility across all features, see API and data retention.

Limits and best practices
Limits
Maximum tools: 10,000 tools in your catalog
Search results: Returns 3-5 most relevant tools per search
Pattern length: Maximum 200 characters for regex patterns
Model support: Claude Mythos Preview, Sonnet 4.0+, Opus 4.0+ only (no Haiku)
When to use tool search
Good use cases:

10+ tools available in your system
Tool definitions consuming >10k tokens
Experiencing tool selection accuracy issues with large tool sets
Building MCP-powered systems with multiple servers (200+ tools)
Tool library growing over time
When traditional tool calling might be better:

Less than 10 tools total
All tools are frequently used in every request
Very small tool definitions (<100 tokens total)
Optimization tips
Keep 3-5 most frequently used tools as non-deferred
Write clear, descriptive tool names and descriptions
Use consistent namespacing in tool names: prefix by service or resource (e.g., github_, slack_) so that search queries naturally surface the right tool group
Use semantic keywords in descriptions that match how users describe tasks
Add a system prompt section describing available tool categories: "You can search for tools to interact with Slack, GitHub, and Jira"
Monitor which tools Claude discovers to refine descriptions
Usage
Tool search tool usage is tracked in the response usage object:

JSON
{
  "usage": {
    "input_tokens": 1024,
    "output_tokens": 256,
    "server_tool_use": {
      "tool_search_requests": 2
    }
  }
}