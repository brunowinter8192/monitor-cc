"usage": {
  "input_tokens": 105,
  "output_tokens": 239,
  "server_tool_use": {
    "code_execution_requests": 1
  }
}
Upgrade to latest tool version
By upgrading to code-execution-2025-08-25, you get access to file manipulation and Bash capabilities, including code in multiple languages. There is no price difference.

What's changed
Component	Legacy	Current
Beta header	code-execution-2025-05-22	code-execution-2025-08-25
Tool type	code_execution_20250522	code_execution_20250825
Capabilities	Python only	Bash commands, file operations
Response types	code_execution_result	bash_code_execution_result, text_editor_code_execution_result
Backward compatibility
All existing Python code execution continues to work exactly as before
No changes required to existing Python-only workflows
Upgrade steps
To upgrade, update the tool type in your API requests:

- "type": "code_execution_20250522"
+ "type": "code_execution_20250825"
Review response handling (if parsing responses programmatically):

The previous blocks for Python execution responses will no longer be sent
Instead, new response types for Bash and file operations will be sent (see Response Format section)
Programmatic tool calling
For running tools inside the code execution container, see Programmatic tool calling.

Data retention
Code execution runs in server-side sandbox containers. Container data, including execution artifacts, uploaded files, and outputs, is retained for up to 30 days. This retention applies to all data processed within the container environment. Files that code execution creates in the Files API (retrievable via client.beta.files.download()) persist until explicitly deleted.

For ZDR eligibility across all features, see API and data retention.

Using code execution with Agent Skills
The code execution tool enables Claude to use Agent Skills. Skills are modular capabilities consisting of instructions, scripts, and resources that extend Claude's functionality.

Learn more in the Agent Skills documentation and Agent Skills API guide.