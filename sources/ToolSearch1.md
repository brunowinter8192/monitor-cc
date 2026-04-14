Tool search tool

Copy page

The tool search tool enables Claude to work with hundreds or thousands of tools by dynamically discovering and loading them on-demand. Instead of loading all tool definitions into the context window upfront, Claude searches your tool catalog (including tool names, descriptions, argument names, and argument descriptions) and loads only the tools it needs.

This approach solves two problems that compound quickly as tool libraries scale:

Context bloat: Tool definitions eat into your context budget fast. A typical multi-server setup (GitHub, Slack, Sentry, Grafana, Splunk) can consume ~55k tokens in definitions before Claude does any actual work. Tool search typically reduces this by over 85%, loading only the 3–5 tools Claude actually needs for a given request.
Tool selection accuracy: Claude's ability to correctly pick the right tool degrades significantly once you exceed 30–50 available tools. By surfacing a focused set of relevant tools on demand, tool search keeps selection accuracy high even across thousands of tools.
For background on the scaling challenges that tool search solves, see Advanced tool use. Tool search's on-demand loading is also an instance of the broader just-in-time retrieval principle described in Effective context engineering.
Although this is provided as a server-side tool, you can also implement your own client-side tool search functionality. See Custom tool search implementation for details.

Share feedback on this feature through the feedback form.
This feature qualifies for Zero Data Retention (ZDR) with limited technical retention. See the Data retention section for details on what is retained and why.
On Amazon Bedrock, server-side tool search is available only via the invoke API, not the converse API.
You can also implement client-side tool search by returning tool_reference blocks from your own search implementation.

How tool search works
There are two tool search variants:

Regex (tool_search_tool_regex_20251119): Claude constructs regex patterns to search for tools
BM25 (tool_search_tool_bm25_20251119): Claude uses natural language queries to search for tools
When you enable the tool search tool:

You include a tool search tool (e.g., tool_search_tool_regex_20251119 or tool_search_tool_bm25_20251119) in your tools list
You provide all tool definitions with defer_loading: true for tools that shouldn't be loaded immediately
Claude sees only the tool search tool and any non-deferred tools initially
When Claude needs additional tools, it searches using a tool search tool
The API returns 3-5 most relevant tool_reference blocks
These references are automatically expanded into full tool definitions
Claude selects from the discovered tools and invokes them
This keeps your context window efficient while maintaining high tool selection accuracy.

Quick start
Here's a simple example with deferred tools:

Shell
curl https://api.anthropic.com/v1/messages \
    --header "x-api-key: $ANTHROPIC_API_KEY" \
    --header "anthropic-version: 2023-06-01" \
    --header "content-type: application/json" \
    --data '{
        "model": "claude-opus-4-6",
        "max_tokens": 2048,
        "messages": [
            {
                "role": "user",
                "content": "What is the weather in San Francisco?"
            }
        ],
        "tools": [
            {
                "type": "tool_search_tool_regex_20251119",
                "name": "tool_search_tool_regex"
            },
            {
                "name": "get_weather",
                "description": "Get the weather at a specific location",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "location": {"type": "string"},
                        "unit": {
                            "type": "string",
                            "enum": ["celsius", "fahrenheit"]
                        }
                    },
                    "required": ["location"]
                },
                "defer_loading": true
            },
            {
                "name": "search_files",
                "description": "Search through files in the workspace",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "query": {"type": "string"},
                        "file_types": {
                            "type": "array",
                            "items": {"type": "string"}
                        }
                    },
                    "required": ["query"]
                },
                "defer_loading": true
            }
        ]
    }'
Tool definition
The tool search tool has two variants:

JSON
{
  "type": "tool_search_tool_regex_20251119",
  "name": "tool_search_tool_regex"
}
JSON
{
  "type": "tool_search_tool_bm25_20251119",
  "name": "tool_search_tool_bm25"
}
Regex variant query format: Python regex, NOT natural language
