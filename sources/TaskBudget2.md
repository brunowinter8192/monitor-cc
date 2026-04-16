
Putting the three turns side by side makes the distinction between payload size and budget spend explicit:

Turn	Request payload (approx. input tokens you sent)	Tokens counted against budget this turn	Budget remaining after
1	~20	5,000 (thinking + tool_use)	~95,000
2	~7,800 (turn 1 history + tool result)	6,800 (2,800 tool result + 4,000 thinking and tool_use)	~88,200
3	~13,000 (full history + second tool result)	7,200 (1,200 tool result + 6,000 text)	~81,000
Total	~20,820 sent across requests	19,000 counted against budget	—
Your client sent the turn-1 user message three times and the turn-1 assistant message twice, but each was counted once. The budget spent 19,000 of 100,000 tokens, even though the cumulative payload your client transmitted was larger and the prompt-cached input on turns 2 and 3 was larger still.

Carrying a budget across compaction with remaining
If your agentic loop compacts or rewrites context between requests (for example, by summarizing earlier turns), the server has no memory of how much budget was spent before compaction. Pass remaining on the next request so the countdown continues from where you left off rather than resetting to total:

Python
TypeScript
Go
Java
C#
PHP
Ruby
output_config = {
    "effort": "high",
    "task_budget": {
        "type": "tokens",
        "total": 128000,
        "remaining": 128000 - tokens_spent_so_far,
    },
}
For loops that resend the full uncompacted history on every turn, omit remaining and let the server track the countdown.

Task budgets are advisory, not enforced
Task budgets are a soft hint, not a hard cap. Claude may occasionally exceed the budget if it is in the middle of an action that would be more disruptive to interrupt than to finish. The enforced limit on total output tokens is still max_tokens, which truncates the response with stop_reason: "max_tokens" when reached.

For a hard cap on cost or latency, combine task budgets with a reasonable max_tokens value:

Use task_budget to give Claude a target to pace against.
Use max_tokens as the absolute ceiling that prevents runaway generation.
Because task_budget spans the full agentic loop (potentially many requests) while max_tokens caps each individual request, the two values are independent; one is not required to be at or below the other.

A budget that is too small for the task can cause refusal-like behavior. When Claude sees a budget that is clearly insufficient for the work being asked (for example, a 20,000-token budget for a multi-hour agentic coding task), it may decline to attempt the task at all, scope it down aggressively, or stop early with a partial result rather than start work it cannot finish. If you observe unexpected refusals or premature stops after setting a budget, raise the budget before debugging other parameters. Size budgets against your actual task-length distribution rather than a fixed default; see Choosing a budget.
Choosing a budget
The right budget depends on how much work your agentic loop currently does. Rather than guessing, measure your existing token usage first and then tune from there.

Measure your current usage
Run a representative sample of tasks without task_budget set and record the total tokens Claude spends per task. For an agentic loop, sum usage.output_tokens plus thinking and tool-result tokens across every request in the loop:

Python
TypeScript
def run_task_and_count_tokens(messages: list) -> int:
    """Runs an agentic loop to completion and returns total tokens spent."""
    total_spend = 0
    while True:
        response = client.beta.messages.create(
            model="claude-opus-4-7",
            max_tokens=128000,
            messages=messages,
            tools=tools,
            betas=["task-budgets-2026-03-13"],
        )
        # Count what Claude generated this turn (output covers text + thinking + tool calls).
        # Tool-result tokens also count against the budget; add the token count of the
        # tool_result blocks you append below if you want client-side tracking to match
        # the server-side countdown.
        total_spend += response.usage.output_tokens
        if response.stop_reason == "end_turn":
            return total_spend
        # Append the assistant turn and your tool results, then continue the loop.
        messages += [
            {"role": "assistant", "content": response.content},
            {"role": "user", "content": run_tools(response.content)},
        ]
Run this across a representative set of tasks and record the distribution. Start with the p99 of your per-task token spend to understand how providing the model with a task budget may modify the model's behavior, then test up or down as needed.

The minimum accepted task_budget.total is 20,000 tokens; values below the minimum return a 400 error.

Interaction with other parameters
max_tokens: Orthogonal to task budgets. max_tokens is a hard per-request cap on generated tokens, while task_budget is an advisory cap across the full agentic loop (potentially spanning many requests). At xhigh or max effort, set max_tokens to at least 64k to give Claude room to think and act on each request.
Effort: Effort controls how deeply Claude reasons per step. Task budgets control how much total work Claude does across an agentic loop. The two are complementary: effort tunes depth, task budgets tune breadth.
Adaptive thinking: Task budgets include thinking tokens in the count, so adaptive thinking naturally scales down as the budget depletes.
Prompt caching: The budget-countdown marker is injected server-side per turn, so it does not match across requests. If your client decrements task_budget.remaining on each follow-up request, the changed value invalidates any cache prefix that contains it. To preserve caching, set the budget once on the initial request and let the model self-regulate against the server-side countdown rather than mutating the budget client-side.
Feature support
Model	Support
Claude Opus 4.7	Public beta (set task-budgets-2026-03-13 header)
Claude Opus 4.6	Not supported
Claude Sonnet 4.6	Not supported
Claude Haiku 4.5	Not supported
Task budgets are not supported on Claude Code or Cowork surfaces at launch. Use task budgets directly via the Messages API on Claude Opus 4.7.