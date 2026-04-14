{
  "type": "code_execution_tool_result",
  "tool_use_id": "srvtoolu_xyz789",
  "content": {
    "type": "code_execution_result",
    "stdout": "Analysis complete. Top 5 customers identified from 847 total records.",
    "stderr": "",
    "return_code": 0,
    "content": []
  }
}
Error handling
Common errors
Error	Description	Solution
invalid_tool_input	Tool input doesn't match schema	Validate your tool's input_schema
tool_not_allowed	Tool doesn't allow the requested caller type	Check allowed_callers includes the right contexts
missing_beta_header	Required beta header not provided (Bedrock and Vertex AI only; programmatic tool calling is GA on the first-party Claude API)	Add the required beta headers to your request
Container expiration during tool call
If your tool takes too long to respond, the code execution receives a TimeoutError. Claude sees this in stderr and typically retries:

{
  "type": "code_execution_tool_result",
  "tool_use_id": "srvtoolu_abc123",
  "content": {
    "type": "code_execution_result",
    "stdout": "",
    "stderr": "TimeoutError: Calling tool ['query_database'] timed out.",
    "return_code": 0,
    "content": []
  }
}
To prevent timeouts:

Monitor the expires_at field in responses
Implement timeouts for your tool execution
Consider breaking long operations into smaller chunks
Tool execution errors
If your tool returns an error:

{
  "type": "tool_result",
  "tool_use_id": "toolu_abc123",
  "content": "Error: Query timeout - table lock exceeded 30 seconds"
}
Claude's code receives this error and can handle it appropriately.

Constraints and limitations
Feature incompatibilities
Structured outputs: Tools with strict: true are not supported with programmatic calling
Tool choice: You cannot force programmatic calling of a specific tool via tool_choice
Parallel tool use: disable_parallel_tool_use: true is not supported with programmatic calling
Tool restrictions
The following tools cannot currently be called programmatically, but support may be added in future releases:

Tools provided by an MCP connector
Message formatting restrictions
When responding to programmatic tool calls, there are strict formatting requirements:

Tool result only responses: If there are pending programmatic tool calls waiting for results, your response message must contain only tool_result blocks. You cannot include any text content, even after the tool results.

Invalid - Cannot include text when responding to programmatic tool calls:

{
  "role": "user",
  "content": [
    {
      "type": "tool_result",
      "tool_use_id": "toolu_01",
      "content": "[{\"customer_id\": \"C1\", \"revenue\": 45000}]"
    },
    { "type": "text", "text": "What should I do next?" }
  ]
}
Valid - Only tool results when responding to programmatic tool calls:

{
  "role": "user",
  "content": [
    {
      "type": "tool_result",
      "tool_use_id": "toolu_01",
      "content": "[{\"customer_id\": \"C1\", \"revenue\": 45000}]"
    }
  ]
}
This restriction only applies when responding to programmatic (code execution) tool calls. For regular client-side tool calls, you can include text content after tool results.

Rate limits
Programmatic tool calls are subject to the same rate limits as regular tool calls. Each tool call from code execution counts as a separate invocation.

Validate tool results before use
When implementing user-defined tools that will be called programmatically:

Tool results are returned as strings: They can contain any content, including code snippets or executable commands that may be processed by the execution environment.
Validate external tool results: If your tool returns data from external sources or accepts user input, be aware of code injection risks if the output will be interpreted or executed as code.
Token efficiency
Programmatic tool calling can significantly reduce token consumption:

Tool results from programmatic calls are not added to Claude's context - only the final code output is
Intermediate processing happens in code - filtering, aggregation, etc. don't consume model tokens
Multiple tool calls in one code execution - reduces overhead compared to separate model turns
For example, calling 10 tools directly uses ~10x the tokens of calling them programmatically and returning a summary.

Usage and pricing
Programmatic tool calling uses the same pricing as code execution. See the code execution pricing for details.
