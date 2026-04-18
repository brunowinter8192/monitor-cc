
Use adaptive thinking for workloads that require agentic behavior such as multi-step tool use, complex coding tasks, and long-horizon agent loops. Older models use manual thinking mode with budget_tokens.

You can guide Claude's thinking behavior:

Example prompt
After receiving tool results, carefully reflect on their quality and determine optimal next steps before proceeding. Use your thinking to plan and iterate based on this new information, and then take the best next action.
The triggering behavior for adaptive thinking is promptable. If you find the model thinking more often than you'd like, which can happen with large or complex system prompts, add guidance to steer it:

Sample prompt
Extended thinking adds latency and should only be used when it will meaningfully improve answer quality - typically for problems that require multi-step reasoning. When in doubt, respond directly.
If you are migrating from extended thinking with budget_tokens, replace your thinking configuration and move budget control to effort:

Before (extended thinking, older models):

Python
client.messages.create(
    model="claude-sonnet-4-5-20250929",
    max_tokens=64000,
    thinking={"type": "enabled", "budget_tokens": 32000},
    messages=[{"role": "user", "content": "..."}],
)
After (adaptive thinking):

Python
client.messages.create(
    model="claude-opus-4-7",
    max_tokens=64000,
    thinking={"type": "adaptive"},
    output_config={"effort": "high"},  # or "max", "xhigh", "medium", "low"
    messages=[{"role": "user", "content": "..."}],
)
If you are not using extended thinking, no changes are required. Thinking is off by default when you omit the thinking parameter.

Prefer general instructions over prescriptive steps. A prompt like "think thoroughly" often produces better reasoning than a hand-written step-by-step plan. Claude's reasoning frequently exceeds what a human would prescribe.
Multishot examples work with thinking. Use <thinking> tags inside your few-shot examples to show Claude the reasoning pattern. It will generalize that style to its own extended thinking blocks.
Manual CoT as a fallback. When thinking is off, you can still encourage step-by-step reasoning by asking Claude to think through the problem. Use structured tags like <thinking> and <answer> to cleanly separate reasoning from the final output.
Ask Claude to self-check. Append something like "Before you finish, verify your answer against [test criteria]." This catches errors reliably, especially for coding and math.
When extended thinking is disabled, Claude Opus 4.5 is particularly sensitive to the word "think" and its variants. Consider using alternatives like "consider," "evaluate," or "reason through" in those cases.
For more information on thinking capabilities, see Extended thinking and Adaptive thinking.
Agentic systems
Long-horizon reasoning and state tracking
Claude's latest models excel at long-horizon reasoning tasks with exceptional state tracking capabilities. Claude maintains orientation across extended sessions by focusing on incremental progress, making steady advances on a few things at a time rather than attempting everything at once. This capability especially emerges over multiple context windows or task iterations, where Claude can work on a complex task, save the state, and continue with a fresh context window.

Context awareness and multi-window workflows
Claude 4.6 and Claude 4.5 models feature context awareness, enabling the model to track its remaining context window (i.e. "token budget") throughout a conversation. This enables Claude to execute tasks and manage context more effectively by understanding how much space it has to work.

Managing context limits:

If you are using Claude in an agent harness that compacts context or allows saving context to external files (like in Claude Code), consider adding this information to your prompt so Claude can behave accordingly. Otherwise, Claude may sometimes naturally try to wrap up work as it approaches the context limit. Below is an example prompt:

Sample prompt
Your context window will be automatically compacted as it approaches its limit, allowing you to continue working indefinitely from where you left off. Therefore, do not stop tasks early due to token budget concerns. As you approach your token budget limit, save your current progress and state to memory before the context window refreshes. Always be as persistent and autonomous as possible and complete tasks fully, even if the end of your budget is approaching. Never artificially stop any task early regardless of the context remaining.
The memory tool pairs naturally with context awareness for seamless context transitions.

Multi-context window workflows
For tasks spanning multiple context windows:

Use a different prompt for the very first context window: Use the first context window to set up a framework (write tests, create setup scripts), then use future context windows to iterate on a todo-list.
Have the model write tests in a structured format: Ask Claude to create tests before starting work and keep track of them in a structured format (e.g., tests.json). This leads to better long-term ability to iterate. Remind Claude of the importance of tests: "It is unacceptable to remove or edit tests because this could lead to missing or buggy functionality."
Set up quality of life tools: Encourage Claude to create setup scripts (e.g., init.sh) to gracefully start servers, run test suites, and linters. This prevents repeated work when continuing from a fresh context window.
Starting fresh vs compacting: When a context window is cleared, consider starting with a brand new context window rather than using compaction. Claude's latest models are extremely effective at discovering state from the local filesystem. In some cases, you may want to take advantage of this over compaction. Be prescriptive about how it should start:

"Call pwd; you can only read and write files in this directory."
"Review progress.txt, tests.json, and the git logs."
"Manually run through a fundamental integration test before moving on to implementing new features."
Provide verification tools: As the length of autonomous tasks grows, Claude needs to verify correctness without continuous human feedback. Tools like Playwright MCP server or computer use capabilities for testing UIs are helpful.
Encourage complete usage of context: Prompt Claude to efficiently complete components before moving on:
Sample prompt
This is a very long task, so it may be beneficial to plan out your work clearly. It's encouraged to spend your entire output context working on the task - just make sure you don't run out of context with significant uncommitted work. Continue working systematically until you have completed this task.
State management best practices
Use structured formats for state data: When tracking structured information (like test results or task status), use JSON or other structured formats to help Claude understand schema requirements
Use unstructured text for progress notes: Freeform progress notes work well for tracking general progress and context
Use git for state tracking: Git provides a log of what's been done and checkpoints that can be restored. Claude's latest models perform especially well in using git to track state across multiple sessions.
Emphasize incremental progress: Explicitly ask Claude to keep track of its progress and focus on incremental work

Example: State tracking
Balancing autonomy and safety
Without guidance, Claude Opus 4.6 may take actions that are difficult to reverse or affect shared systems, such as deleting files, force-pushing, or posting to external services. If you want Claude Opus 4.6 to confirm before taking potentially risky actions, add guidance to your prompt:

Sample prompt
Consider the reversibility and potential impact of your actions. You are encouraged to take local, reversible actions like editing files or running tests, but for actions that are hard to reverse, affect shared systems, or could be destructive, ask the user before proceeding.

Examples of actions that warrant confirmation:
- Destructive operations: deleting files or branches, dropping database tables, rm -rf
- Hard to reverse operations: git push --force, git reset --hard, amending published commits
- Operations visible to others: pushing code, commenting on PRs/issues, sending messages, modifying shared infrastructure

When encountering obstacles, do not use destructive actions as a shortcut. For example, don't bypass safety checks (e.g. --no-verify) or discard unfamiliar files that may be in-progress work.
Research and information gathering
Claude's latest models demonstrate exceptional agentic search capabilities and can find and synthesize information from multiple sources effectively. For optimal research results:

Provide clear success criteria: Define what constitutes a successful answer to your research question
Encourage source verification: Ask Claude to verify information across multiple sources
For complex research tasks, use a structured approach:
Sample prompt for complex research
Search for this information in a structured way. As you gather data, develop several competing hypotheses. Track your confidence levels in your progress notes to improve calibration. Regularly self-critique your approach and plan. Update a hypothesis tree or research notes file to persist information and provide transparency. Break down this complex research task systematically.
This structured approach allows Claude to find and synthesize virtually any piece of information and iteratively critique its findings, no matter the size of the corpus.

Subagent orchestration
Claude's latest models demonstrate significantly improved native subagent orchestration capabilities. These models can recognize when tasks would benefit from delegating work to specialized subagents and do so proactively without requiring explicit instruction.
