Task budgets

Copy page

Give Claude an advisory token budget for the full agentic loop to help the model self-regulate on long agentic tasks with task budgets.
This feature is eligible for Zero Data Retention (ZDR). When your organization has a ZDR arrangement, data sent through this feature is not stored after the API response is returned.
Task budgets let you tell Claude how many tokens it has for a full agentic loop, including thinking, tool calls, tool results, and output. The model sees a running countdown and uses it to prioritize work and finish gracefully as the budget is consumed.

Task budgets are in public beta on Claude Opus 4.7. Set the task-budgets-2026-03-13 beta header to opt in.
When to use task budgets
Task budgets work best for agentic workflows where Claude makes multiple tool calls and decisions before finalizing its output to await the next human response. Use them when:

You want Claude to self-regulate token spend on long-horizon tasks.
You have a predictable per-task cost or latency ceiling to enforce.
You want the model to finish gracefully (summarize findings, report progress) as it approaches the budget rather than cutting off mid-action.
Task budgets complement the effort parameter: effort controls how thoroughly Claude reasons about each step, while task budgets cap the total work Claude can do across an agentic loop.

Setting a task budget
Add task_budget to output_config and include the beta header:

Shell
CLI
Python
TypeScript
Go
Java
C#
PHP
Ruby
curl https://api.anthropic.com/v1/messages \
    --header "x-api-key: $ANTHROPIC_API_KEY" \
    --header "anthropic-version: 2023-06-01" \
    --header "anthropic-beta: task-budgets-2026-03-13" \
    --header "content-type: application/json" \
    --data '{
        "model": "claude-opus-4-7",
        "max_tokens": 128000,
        "messages": [{
            "role": "user",
            "content": "Review the codebase and propose a refactor plan."
        }],
        "output_config": {
            "effort": "high",
            "task_budget": {"type": "tokens", "total": 64000}
        }
    }'
The task_budget object has three fields:

type: always "tokens".
total: the number of tokens Claude can spend across the agentic loop, including thinking, tool calls, tool results, and output.
remaining (optional): the budget remainder carried over from a prior request. Defaults to total when omitted.
How the budget countdown works
Claude sees a budget-countdown marker injected server-side throughout the conversation. The marker shows how many tokens remain in the current agentic loop and updates as the model generates thinking, tool calls, and output, and as it processes tool results. Claude uses this signal to pace itself and finish gracefully as the budget is consumed.

The countdown reflects tokens Claude has processed in the current agentic loop, not tokens you resend between turns. If your client sends the full conversation history on every follow-up request, your client-side token count may differ from the budget Claude is tracking. If you also decrement remaining while resending full history, the model sees an under-reported budget and the countdown drops faster than it should, causing Claude to wrap up earlier than the budget actually allows. Set a generous budget and let the model self-regulate against the countdown rather than trying to mirror it client-side.
Worked example: budget counting across turns
The task budget counts what Claude sees (thinking, tool calls and results, and text), not what's in your request payload. In an agentic loop your client resends the full conversation on every request, so the payload grows turn over turn, but the budget only decrements by the tokens Claude sees this turn.

Consider a loop with task_budget: {type: "tokens", total: 100000} and a single bash tool.

Turn 1. You send the initial request:

{
  "messages": [
    { "role": "user", "content": "Audit this repo for security issues and report findings." }
  ]
}
Claude thinks, then emits a tool call and stops with stop_reason: "tool_use":

{
  "role": "assistant",
  "content": [
    {
      "type": "thinking",
      "thinking": "I'll start by listing dependencies to look for known-vulnerable packages..."
    },
    {
      "type": "tool_use",
      "id": "toolu_01",
      "name": "bash",
      "input": { "command": "cat package.json && npm audit --json" }
    }
  ]
}
Suppose this assistant turn (thinking plus the tool call) totals 5,000 generated tokens. The countdown Claude saw during generation ended near remaining ≈ 95,000.

Turn 2. Your client executes the tool, then resends the full history with the tool result appended:

{
  "messages": [
    { "role": "user", "content": "Audit this repo for security issues and report findings." },
    {
      "role": "assistant",
      "content": [
        { "type": "thinking", "thinking": "I'll start by listing dependencies..." },
        {
          "type": "tool_use",
          "id": "toolu_01",
          "name": "bash",
          "input": { "command": "cat package.json && npm audit --json" }
        }
      ]
    },
    {
      "role": "user",
      "content": [
        {
          "type": "tool_result",
          "tool_use_id": "toolu_01",
          "content": "<2,800 tokens of npm audit output>"
        }
      ]
    }
  ]
}
The resent turn-1 user and assistant messages are not counted again, but the 2,800-token tool result is new content Claude sees this turn and counts against the budget. Claude spends another 4,000 tokens on thinking and a second tool call (grep -rn "eval(" src/). The countdown ends near remaining ≈ 88,200.

Turn 3. Full history resent again with the second tool result (1,200 tokens of grep output) appended. Claude writes a 6,000-token final findings report and stops with stop_reason: "end_turn". remaining ≈ 81,000.
