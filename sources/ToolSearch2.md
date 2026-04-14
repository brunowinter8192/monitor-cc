
When using tool_search_tool_regex_20251119, Claude constructs regex patterns using Python's re.search() syntax, not natural language queries. Common patterns:

"weather" - matches tool names/descriptions containing "weather"
"get_.*_data" - matches tools like get_user_data, get_weather_data
"database.*query|query.*database" - OR patterns for flexibility
"(?i)slack" - case-insensitive search
Maximum query length: 200 characters
BM25 variant query format: Natural language

When using tool_search_tool_bm25_20251119, Claude uses natural language queries to search for tools.
Deferred tool loading
Mark tools for on-demand loading by adding defer_loading: true:

JSON
{
  "name": "get_weather",
  "description": "Get current weather for a location",
  "input_schema": {
    "type": "object",
    "properties": {
      "location": { "type": "string" },
      "unit": { "type": "string", "enum": ["celsius", "fahrenheit"] }
    },
    "required": ["location"]
  },
  "defer_loading": true
}
Key points:

Tools without defer_loading are loaded into context immediately
Tools with defer_loading: true are only loaded when Claude discovers them via search
The tool search tool itself should never have defer_loading: true
Keep your 3-5 most frequently used tools as non-deferred for optimal performance
Both tool search variants (regex and bm25) search tool names, descriptions, argument names, and argument descriptions.

How deferral works internally: Deferred tools are not included in the system-prompt prefix. When the model discovers a deferred tool through tool search, the tool definition is appended inline as a tool_reference block in the conversation. The prefix is untouched, so prompt caching is preserved. The grammar for strict mode builds from the full toolset, so defer_loading and strict mode compose without grammar recompilation.

Response format
When Claude uses the tool search tool, the response includes new block types:

JSON
{
  "role": "assistant",
  "content": [
    {
      "type": "text",
      "text": "I'll search for tools to help with the weather information."
    },
    {
      "type": "server_tool_use",
      "id": "srvtoolu_01ABC123",
      "name": "tool_search_tool_regex",
      "input": {
        "query": "weather"
      }
    },
    {
      "type": "tool_search_tool_result",
      "tool_use_id": "srvtoolu_01ABC123",
      "content": {
        "type": "tool_search_tool_search_result",
        "tool_references": [{ "type": "tool_reference", "tool_name": "get_weather" }]
      }
    },
    {
      "type": "text",
      "text": "I found a weather tool. Let me get the weather for San Francisco."
    },
    {
      "type": "tool_use",
      "id": "toolu_01XYZ789",
      "name": "get_weather",
      "input": { "location": "San Francisco", "unit": "fahrenheit" }
    }
  ],
  "stop_reason": "tool_use"
}
Understanding the response
server_tool_use: Indicates Claude is invoking the tool search tool
tool_search_tool_result: Contains the search results with a nested tool_search_tool_search_result object
tool_references: Array of tool_reference objects pointing to discovered tools
tool_use: Claude invoking the discovered tool
The tool_reference blocks are automatically expanded into full tool definitions before being shown to Claude. You don't need to handle this expansion yourself. It happens automatically in the API as long as you provide all matching tool definitions in the tools parameter.

MCP integration
For configuring mcp_toolset with defer_loading, see MCP connector.

Custom tool search implementation
You can implement your own tool search logic (e.g., using embeddings or semantic search) by returning tool_reference blocks from a custom tool. When Claude calls your custom search tool, return a standard tool_result with tool_reference blocks in the content array:

JSON
{
  "type": "tool_result",
  "tool_use_id": "toolu_your_tool_id",
  "content": [{ "type": "tool_reference", "tool_name": "discovered_tool_name" }]
}
Every tool referenced must have a corresponding tool definition in the top-level tools parameter with defer_loading: true. This approach lets you use more sophisticated search algorithms while maintaining compatibility with the tool search system.
