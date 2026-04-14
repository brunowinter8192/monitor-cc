Code execution tool

Copy page

Run Python and bash code in a sandboxed container to analyze data, generate files, and iterate on solutions.
Claude can analyze data, create visualizations, perform complex calculations, run system commands, create and edit files, and process uploaded files directly within the API conversation. The code execution tool allows Claude to run Bash commands and manipulate files, including writing code, in a secure, sandboxed environment.

Code execution is free when used with web search or web fetch. When web_search_20260209 or web_fetch_20260209 is included in your request, there are no additional charges for code execution tool calls beyond the standard input and output token costs. Standard code execution charges apply when these tools are not included.

Code execution is a core primitive for building high-performance agents. It enables dynamic filtering in web search and web fetch tools, allowing Claude to process results before they reach the context window, improving accuracy while reducing token consumption.

Reach out through the feedback form to share your feedback on this feature.
This feature is not eligible for Zero Data Retention (ZDR). Data is retained according to the feature's standard retention policy.
Model compatibility
The code execution tool is available on the following models:

Model	Tool versions
Claude Opus 4.6 (claude-opus-4-6)	code_execution_20250825, code_execution_20260120
Claude Sonnet 4.6 (claude-sonnet-4-6)	code_execution_20250825, code_execution_20260120
Claude Opus 4.5 (claude-opus-4-5-20251101)	code_execution_20250825, code_execution_20260120
Claude Sonnet 4.5 (claude-sonnet-4-5-20250929)	code_execution_20250825, code_execution_20260120
Claude Haiku 4.5 (claude-haiku-4-5-20251001)	code_execution_20250825
Claude Opus 4.1 (claude-opus-4-1-20250805)	code_execution_20250825
Claude Opus 4 (claude-opus-4-20250514)	code_execution_20250825
Claude Sonnet 4 (claude-sonnet-4-20250514)	code_execution_20250825
Claude Sonnet 3.7 (claude-3-7-sonnet-20250219) (deprecated)	code_execution_20250825
Claude Haiku 3.5 (claude-3-5-haiku-latest) (deprecated)	code_execution_20250825
code_execution_20250825 supports Bash commands and file operations and is available on every model listed above. code_execution_20260120 adds REPL state persistence and programmatic tool calling from within the sandbox, and is available on Opus 4.5+ and Sonnet 4.5+ only. A legacy version code_execution_20250522 (Python only) is also available on the same models as code_execution_20250825; see Upgrade to latest tool version to migrate from it.
Older tool versions are not guaranteed to be backwards-compatible with newer models. Always use the tool version that corresponds to your model version.
Platform availability
Code execution is available on:

Claude API (Anthropic)
Microsoft Azure AI Foundry
Code execution is not currently available on Amazon Bedrock or Google Vertex AI.

For Claude Mythos Preview, code execution is supported on the Claude API and Microsoft Foundry only. It is not available for Mythos Preview on Amazon Bedrock or Google Vertex AI.
Quick start
Here's a simple example that asks Claude to perform a calculation:

Shell
curl https://api.anthropic.com/v1/messages \
    --header "x-api-key: $ANTHROPIC_API_KEY" \
    --header "anthropic-version: 2023-06-01" \
    --header "content-type: application/json" \
    --data '{
        "model": "claude-opus-4-6",
        "max_tokens": 4096,
        "messages": [
            {
                "role": "user",
                "content": "Calculate the mean and standard deviation of [1, 2, 3, 4, 5, 6, 7, 8, 9, 10]"
            }
        ],
        "tools": [{
            "type": "code_execution_20250825",
            "name": "code_execution"
        }]
    }'
How code execution works
When you add the code execution tool to your API request:

Claude evaluates whether code execution would help answer your question
The tool automatically provides Claude with the following capabilities:
Bash commands: Execute shell commands for system operations and package management
File operations: Create, view, and edit files directly, including writing code
Claude can use any combination of these capabilities in a single request
All operations run in a secure sandbox environment
Claude provides results with any generated charts, calculations, or analysis
Using code execution with other execution tools
When you provide code execution alongside client-provided tools that also run code (such as a bash tool or custom REPL), Claude is operating in a multi-computer environment. The code execution tool runs in Anthropic's sandboxed container, while your client-provided tools run in a separate environment that you control. Claude can sometimes confuse these environments, attempting to use the wrong tool or assuming state is shared between them.

To avoid this, add instructions to your system prompt that clarify the distinction:

When multiple code execution environments are available, be aware that:
- Variables, files, and state do NOT persist between different execution environments
- Use the code_execution tool for general-purpose computation in Anthropic's sandboxed environment
- Use client-provided execution tools (e.g., bash) when you need access to the user's local system, files, or data
- If you need to pass results between environments, explicitly include outputs in subsequent tool calls rather than assuming shared state
This is especially important when combining code execution with web search or web fetch, which enable code execution automatically. If your application already provides a client-side shell tool, the automatic code execution creates a second execution environment that Claude needs to distinguish between.

How to use the tool
Upload and analyze your own files
To analyze your own data files (CSV, Excel, images, etc.), upload them via the Files API and reference them in your request:

Using the Files API with Code Execution requires the Files API beta header: "anthropic-beta": "files-api-2025-04-14"
The Python environment can process various file types uploaded via the Files API, including:

CSV
Excel (.xlsx, .xls)
JSON
XML
Images (JPEG, PNG, GIF, WebP)
Text files (.txt, .md, .py, etc)
Upload and analyze files
Upload your file using the Files API
Reference the file in your message using a container_upload content block
Include the code execution tool in your API request
Shell
