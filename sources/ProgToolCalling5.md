
Token counting for programmatic tool calls: Tool results from programmatic invocations do not count toward your input/output token usage. Only the final code execution result and Claude's response count.
Best practices
Tool design
Provide detailed output descriptions: Since Claude deserializes tool results in code, clearly document the format (JSON structure, field types, etc.)
Return structured data: JSON or other easily parseable formats work best for programmatic processing
Keep responses concise: Return only necessary data to minimize processing overhead
When to use programmatic calling
Good use cases:

Processing large datasets where you only need aggregates or summaries
Multi-step workflows with 3+ dependent tool calls
Operations requiring filtering, sorting, or transformation of tool results
Tasks where intermediate data shouldn't influence Claude's reasoning
Parallel operations across many items (e.g., checking 50 endpoints)
Less ideal use cases:

Single tool calls with simple responses
Tools that need immediate user feedback
Very fast operations where code execution overhead would outweigh the benefit
Performance optimization
Reuse containers when making multiple related requests to maintain state
Batch similar operations in a single code execution when possible
Troubleshooting
Common issues
"Tool not allowed" error

Verify your tool definition includes "allowed_callers": ["code_execution_20260120"]
Container expiration

Ensure you respond to tool calls before the container idles out (4.5 minutes of inactivity; 30-day hard maximum)
Monitor the expires_at field in responses
Consider implementing faster tool execution
Tool result not parsed correctly

Ensure your tool returns string data that Claude can deserialize
Provide clear output format documentation in your tool description
Debugging tips
Log all tool calls and results to track the flow
Check the caller field to confirm programmatic invocation
Monitor container IDs to ensure proper reuse
Test tools independently before enabling programmatic calling
Why programmatic tool calling works
Claude's training includes extensive exposure to code, making it effective at reasoning through and chaining function calls. When tools are presented as callable functions within a code execution environment, Claude can leverage this strength to:

Reason naturally about tool composition: Chain operations and handle dependencies as naturally as writing any Python code
Process large results efficiently: Filter down large tool outputs, extract only relevant data, or write intermediate results to files before returning summaries to the context window
Reduce latency significantly: Eliminate the overhead of re-sampling Claude between each tool call in multi-step workflows
This approach enables workflows that would be impractical with traditional tool use (such as processing files over 1M tokens) by allowing Claude to work with data programmatically rather than loading everything into the conversation context.

Alternative implementations
Programmatic tool calling is a generalizable pattern that can be implemented outside of Anthropic's managed code execution. Here's an overview of the approaches:

Client-side direct execution
Provide Claude with a code execution tool and describe what functions are available in that environment. When Claude invokes the tool with code, your application executes it locally where those functions are defined.

Advantages:

Simple to implement with minimal re-architecting
Full control over the environment and instructions
Disadvantages:

Executes untrusted code outside of a sandbox
Tool invocations can be vectors for code injection
Use when: Your application can safely execute arbitrary code, you want a simple solution, and Anthropic's managed offering doesn't fit your needs.

Self-managed sandboxed execution
Same approach from Claude's perspective, but code runs in a sandboxed container with security restrictions (e.g., no network egress). If your tools require external resources, you'll need a protocol for executing tool calls outside the sandbox.

Advantages:

Safe programmatic tool calling on your own infrastructure
Full control over the execution environment
Disadvantages:

Complex to build and maintain
Requires managing both infrastructure and inter-process communication
Use when: Security is critical and Anthropic's managed solution doesn't fit your requirements.

Anthropic-managed execution
Anthropic's programmatic tool calling is a managed version of sandboxed execution with an opinionated Python environment tuned for Claude. Anthropic handles container management, code execution, and secure tool invocation communication.

Advantages:

Safe and secure by default
Easy to enable with minimal configuration
Environment and instructions optimized for Claude
Consider using Anthropic's managed solution if you're using the Claude API.

Data retention
Programmatic tool calling is built on the code execution infrastructure and uses the same sandbox containers. Container data, including execution artifacts and outputs, is retained for up to 30 days.

For ZDR eligibility across all features, see API and data retention.