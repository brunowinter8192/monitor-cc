Client-side compaction (SDK)
Anthropic recommends server-side compaction over SDK compaction. Server-side compaction handles context management automatically with less integration complexity, better token usage calculation, and no client-side limitations. Use SDK compaction only if you specifically need client-side control over the summarization process.
Compaction is available in the Python, TypeScript, and Ruby SDKs when using the tool_runner method.
Compaction is an SDK feature that automatically manages conversation context by generating summaries when token usage grows too large. Unlike server-side context editing strategies that clear content, compaction instructs Claude to summarize the conversation history, then replaces the full history with that summary. This allows Claude to continue working on long-running tasks that would otherwise exceed the context window.

How compaction works
When compaction is enabled, the SDK monitors token usage after each model response:

Threshold check: The SDK calculates total tokens as input_tokens + cache_creation_input_tokens + cache_read_input_tokens + output_tokens.
Summary generation: When the threshold is exceeded, a summary prompt is injected as a user turn, and Claude generates a structured summary wrapped in <summary></summary> tags.
Context replacement: The SDK extracts the summary and replaces the entire message history with it.
Continuation: The conversation resumes from the summary, with Claude picking up where it left off.
Using compaction
Add compaction_control to your tool_runner call to enable automatic summarization when token usage exceeds the threshold.

CLI
Python
TypeScript
C#
Go
Java
PHP
Ruby
The CLI does not include a tool_runner helper. Use server-side compaction instead, which handles compaction on Anthropic's servers without SDK-side integration.
What happens during compaction
As the conversation grows, the message history accumulates:

Before compaction (approaching 100k tokens):

[
  { "role": "user", "content": "Analyze all files and write a report..." },
  { "role": "assistant", "content": "I'll help. Let me start by reading..." },
  {
    "role": "user",
    "content": [{ "type": "tool_result", "tool_use_id": "...", "content": "..." }]
  },
  { "role": "assistant", "content": "Based on file1.txt, I see..." },
  {
    "role": "user",
    "content": [{ "type": "tool_result", "tool_use_id": "...", "content": "..." }]
  },
  { "role": "assistant", "content": "After analyzing file2.txt..." }
  // ... 50 more exchanges like this ...
]
When tokens exceed the threshold, the SDK injects a summary request and Claude generates a summary. The entire history is then replaced:

After compaction (back to ~2-3k tokens):

[
  {
    "role": "assistant",
    "content": "# Task Overview\nThe user requested analysis of directory files to produce a summary report...\n\n# Current State\nAnalyzed 52 files across 3 subdirectories. Key findings documented in report.md...\n\n# Important Discoveries\n- Configuration files use YAML format\n- Found 3 deprecated dependencies\n- Test coverage at 67%\n\n# Next Steps\n1. Analyze remaining files in /src/legacy\n2. Complete final report sections...\n\n# Context to Preserve\nUser prefers markdown format with executive summary first..."
  }
]
Claude continues working from this summary as if it were the original conversation history.

Configuration options
Parameter	Type	Required	Default	Description
enabled	boolean	Yes	-	Whether to enable automatic compaction
context_token_threshold	number	No	100,000	Token count at which compaction triggers
model	string	No	Same as main model	Model to use for generating summaries
summary_prompt	string	No	See below	Custom prompt for summary generation
Choosing a token threshold
The threshold determines when compaction occurs. A lower threshold means more frequent compactions with smaller context windows. A higher threshold allows more context but risks hitting limits.

Python
# More frequent compaction for memory-constrained scenarios
compaction_control = {"enabled": True, "context_token_threshold": 50000}

# Less frequent compaction when you need more context
compaction_control = {"enabled": True, "context_token_threshold": 150000}
Using a different model for summaries
You can use a faster or cheaper model for generating summaries:

Python
compaction_control = {
    "enabled": True,
    "context_token_threshold": 100000,
    "model": "claude-haiku-4-5",
}
Custom summary prompts
You can provide a custom prompt for domain-specific needs. Your prompt should instruct Claude to wrap its summary in <summary></summary> tags.

Python
compaction_control = {
    "enabled": True,
    "context_token_threshold": 100000,
    "summary_prompt": """Summarize the research conducted so far, including:
- Sources consulted and key findings
- Questions answered and remaining unknowns
- Recommended next steps

Wrap your summary in <summary></summary> tags.""",
}
Default summary prompt
The built-in summary prompt instructs Claude to create a structured continuation summary including:

Task Overview: The user's core request, success criteria, and constraints.
Current State: What has been completed, files modified, and artifacts produced.
Important Discoveries: Technical constraints, decisions made, errors resolved, and failed approaches.
Next Steps: Specific actions needed, blockers, and priority order.
Context to Preserve: User preferences, domain-specific details, and commitments made.
This structure enables Claude to resume work efficiently without losing important context or repeating mistakes.


View full default prompt
Limitations
Server-side tools
Compaction requires special consideration when using server-side tools such as web search or web fetch.
When using server-side tools, the SDK may incorrectly calculate token usage, causing compaction to trigger at the wrong time.

For example, after a web search operation, the API response might show:

Output
{
  "usage": {
    "input_tokens": 63000,
    "cache_read_input_tokens": 270000,
    "output_tokens": 1400
  }
}
The SDK calculates total usage as 63,000 + 270,000 = 333,000 tokens. However, the cache_read_input_tokens value includes accumulated reads from multiple internal API calls made by the server-side tool, not your actual conversation context. Your real context length might only be the 63,000 input_tokens, but the SDK sees 333k and triggers compaction prematurely.
