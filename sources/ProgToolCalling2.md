
{
  "type": "tool_use",
  "id": "toolu_abc123",
  "name": "query_database",
  "input": { "sql": "<sql>" },
  "caller": { "type": "direct" }
}
Programmatic invocation:

{
  "type": "tool_use",
  "id": "toolu_xyz789",
  "name": "query_database",
  "input": { "sql": "<sql>" },
  "caller": {
    "type": "code_execution_20260120",
    "tool_id": "srvtoolu_abc123"
  }
}
The tool_id references the code execution tool that made the programmatic call.

Container lifecycle
Programmatic tool calling uses the same containers as code execution:

Container creation: A new container is created for each session unless you reuse an existing one
Expiration: Containers have a 30-day maximum lifetime and are cleaned up after 4.5 minutes of idle time
Container ID: Returned in responses via the container field
Reuse: Pass the container ID to maintain state across requests
When a tool is called programmatically and the container is waiting for your tool result, you must respond before the container expires. Monitor the expires_at field. If the container expires, Claude may treat the tool call as timed out and retry it.
Example workflow
Here's how a complete programmatic tool calling flow works:

Step 1: Initial request
Send a request with code execution and a tool that allows programmatic calling. To enable programmatic calling, add the allowed_callers field to your tool definition.

Provide detailed descriptions of your tool's output format in the tool description. If you specify that the tool returns JSON, Claude attempts to deserialize and process the result in code. The more detail you provide about the output schema, the better Claude can handle the response programmatically.
The request shape is identical to the Quick start example: include code_execution in your tools list, add allowed_callers: ["code_execution_20260120"] to any tool you want Claude to invoke from code, and send your user message.

Step 2: API response with tool call
Claude writes code that calls your tool. The API pauses and returns:

Output
{
  "role": "assistant",
  "content": [
    {
      "type": "text",
      "text": "I'll query the purchase history and analyze the results."
    },
    {
      "type": "server_tool_use",
      "id": "srvtoolu_abc123",
      "name": "code_execution",
      "input": {
        "code": "results = await query_database('<sql>')\ntop_customers = sorted(results, key=lambda x: x['revenue'], reverse=True)[:5]\nprint(f'Top 5 customers: {top_customers}')"
      }
    },
    {
      "type": "tool_use",
      "id": "toolu_def456",
      "name": "query_database",
      "input": { "sql": "<sql>" },
      "caller": {
        "type": "code_execution_20260120",
        "tool_id": "srvtoolu_abc123"
      }
    }
  ],
  "container": {
    "id": "container_xyz789",
    "expires_at": "2025-01-15T14:30:00Z"
  },
  "stop_reason": "tool_use"
}
Step 3: Provide tool result
Include the full conversation history plus your tool result:

CLI
ant messages create <<'YAML'
model: claude-opus-4-6
max_tokens: 4096
container: container_xyz789
messages:
  - role: user
    content: >-
      Query customer purchase history from the last quarter and identify our
      top 5 customers by revenue
  - role: assistant
    content:
      - type: text
        text: I'll query the purchase history and analyze the results.
      - type: server_tool_use
        id: srvtoolu_abc123
        name: code_execution
        input:
          code: "..."
      - type: tool_use
        id: toolu_def456
        name: query_database
        input:
          sql: "<sql>"
        caller:
          type: code_execution_20260120
          tool_id: srvtoolu_abc123
  - role: user
    content:
      - type: tool_result
        tool_use_id: toolu_def456
        content: >-
          [{"customer_id": "C1", "revenue": 45000}, {"customer_id": "C2",
          "revenue": 38000}, ...]
tools: [...]
YAML
Step 4: Next tool call or completion
The code execution continues and processes the results. If additional tool calls are needed, repeat Step 3 until all tool calls are satisfied.
