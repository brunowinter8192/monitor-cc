Tool use with Claude

Copy page

Connect Claude to external tools and APIs. Learn where tools execute and how the agentic loop works.
Tool use lets Claude call functions you define or that Anthropic provides. Claude decides when to call a tool based on the user's request and the tool's description, then returns a structured call that your application executes (client tools) or that Anthropic executes (server tools).

Here's the simplest example using a server tool, where Anthropic handles execution:

Shell
curl https://api.anthropic.com/v1/messages \
  -H "x-api-key: $ANTHROPIC_API_KEY" \
  -H "anthropic-version: 2023-06-01" \
  -H "content-type: application/json" \
  -d '{
    "model": "claude-opus-4-6",
    "max_tokens": 1024,
    "tools": [{"type": "web_search_20260209", "name": "web_search"}],
    "messages": [{"role": "user", "content": "What'\''s the latest on the Mars rover?"}]
  }'
How tool use works
Tools differ primarily by where the code executes. Client tools (including user-defined tools and Anthropic-schema tools like bash and text_editor) run in your application: Claude responds with stop_reason: "tool_use" and one or more tool_use blocks, your code executes the operation, and you send back a tool_result. Server tools (web_search, code_execution, web_fetch, tool_search) run on Anthropic's infrastructure: you see the results directly without handling execution.

For the full conceptual model including the agentic loop and when to choose each approach, see How tool use works.

For connecting to MCP servers, see the MCP connector. For building your own MCP client, see modelcontextprotocol.io.

Guarantee schema conformance with strict tool use

Add strict: true to your tool definitions to ensure Claude's tool calls always match your schema exactly. See Strict tool use.
Tool access is one of the highest-leverage primitives you can give an agent. On benchmarks like LAB-Bench FigQA (scientific figure interpretation) and SWE-bench (real-world software engineering), adding even basic tools produces outsized capability gains, often surpassing human expert baselines.

Tool use examples
For a complete hands-on walkthrough, see the tutorial. For reference examples of individual concepts, see Define tools and Handle tool calls.


What happens when Claude needs more information
Pricing
Tool use requests are priced based on:

The total number of input tokens sent to the model (including in the tools parameter)
The number of output tokens generated
For server-side tools, additional usage-based pricing (e.g., web search charges per search performed)
Client-side tools are priced the same as any other Claude API request, while server-side tools may incur additional charges based on their specific usage.

The additional tokens from tool use come from:

The tools parameter in API requests (tool names, descriptions, and schemas)
tool_use content blocks in API requests and responses
tool_result content blocks in API requests
When you use tools, we also automatically include a special system prompt for the model which enables tool use. The number of tool use tokens required for each model are listed below (excluding the additional tokens listed above). Note that the table assumes at least 1 tool is provided. If no tools are provided, then a tool choice of none uses 0 additional system prompt tokens.

Model	Tool choice	Tool use system prompt token count
Claude Opus 4.6	auto, none
any, tool	346 tokens
313 tokens
Claude Opus 4.5	auto, none
any, tool	346 tokens
313 tokens
Claude Opus 4.1	auto, none
any, tool	346 tokens
313 tokens
Claude Opus 4	auto, none
any, tool	346 tokens
313 tokens
Claude Sonnet 4.6	auto, none
any, tool	346 tokens
313 tokens
Claude Sonnet 4.5	auto, none
any, tool	346 tokens
313 tokens
Claude Sonnet 4	auto, none
any, tool	346 tokens
313 tokens
Claude Sonnet 3.7 (deprecated)	auto, none
any, tool	346 tokens
313 tokens
Claude Haiku 4.5	auto, none
any, tool	346 tokens
313 tokens
Claude Haiku 3.5	auto, none
any, tool	264 tokens
340 tokens
Claude Opus 3 (deprecated)	auto, none
any, tool	530 tokens
281 tokens
Claude Sonnet 3	auto, none
any, tool	159 tokens
235 tokens
Claude Haiku 3	auto, none
any, tool	264 tokens
340 tokens
These token counts are added to your normal input and output tokens to calculate the total cost of a request.

Refer to the models overview table for current per-model prices.

When you send a tool use prompt, just like any other API request, the response will output both input and output token counts as part of the reported usage metrics.