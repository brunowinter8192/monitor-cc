
Workarounds:

Use the token counting endpoint to get accurate context length
Avoid compaction when using server-side tools extensively
Tool use edge cases
When the SDK triggers compaction while a tool use response is pending, it removes the tool use block from the message history before generating the summary. Claude will re-issue the tool call after resuming from the summary if still needed.

Monitoring compaction
Understanding when compaction triggers helps you tune thresholds and verify expected behavior.

Python
TypeScript
C#
Go
Java
PHP
Ruby
The Python SDK logs compaction events at the INFO level. Enable the anthropic.lib.tools logger:

Python
import logging

logging.basicConfig(level=logging.INFO)
logging.getLogger("anthropic.lib.tools").setLevel(logging.INFO)

# Logs will show:
# INFO: Token usage 105000 has exceeded the threshold of 100000. Performing compaction.
# INFO: Compaction complete. New token usage: 2500
When to use compaction
Good use cases:

Long-running agent tasks that process many files or data sources
Research workflows that accumulate large amounts of information
Multi-step tasks with clear, measurable progress
Tasks that produce artifacts (files, reports) that persist outside the conversation
Less ideal use cases:

Tasks requiring precise recall of early conversation details
Workflows using server-side tools extensively
Tasks that need to maintain exact state across many variables