Adaptive thinking

Copy page

Let Claude dynamically determine when and how much to use extended thinking with adaptive thinking mode.
This feature is eligible for Zero Data Retention (ZDR). When your organization has a ZDR arrangement, data sent through this feature is not stored after the API response is returned.
Adaptive thinking is the recommended way to use extended thinking with Claude Opus 4.7, Claude Opus 4.6, and Claude Sonnet 4.6, and is the default mode on Claude Mythos Preview (where it auto-applies whenever thinking is unset). Instead of manually setting a thinking token budget, adaptive thinking lets Claude dynamically determine when and how much to use extended thinking based on the complexity of each request. On Claude Opus 4.7, adaptive thinking is the only supported thinking mode; manual thinking: {type: "enabled", budget_tokens: N} is no longer accepted.

Adaptive thinking can drive better performance than extended thinking with a fixed budget_tokens for many workloads, especially bimodal tasks and long-horizon agentic workflows. No beta header is required.

If your workload requires predictable latency or precise control over thinking costs, extended thinking with budget_tokens is still functional on Claude Opus 4.6 and Claude Sonnet 4.6 but is deprecated and no longer recommended. See the warning below.
Supported models
Adaptive thinking is supported on the following models:

Claude Mythos Preview (claude-mythos-preview), adaptive thinking is the default; thinking: {type: "disabled"} is not supported
Claude Opus 4.7 (claude-opus-4-7), adaptive thinking is the only supported thinking mode. Thinking is off unless you explicitly set thinking: {type: "adaptive"} in your request; manual thinking: {type: "enabled"} is rejected with a 400 error.
Claude Opus 4.6 (claude-opus-4-6)
Claude Sonnet 4.6 (claude-sonnet-4-6)
thinking.type: "enabled" and budget_tokens are deprecated on Opus 4.6 and Sonnet 4.6 and will be removed in a future model release. Use thinking.type: "adaptive" with the effort parameter instead. Existing budget_tokens configurations are still functional but no longer recommended; plan to migrate.

Older models (Sonnet 4.5, Opus 4.5, etc.) do not support adaptive thinking and require thinking.type: "enabled" with budget_tokens.
How adaptive thinking works
In adaptive mode, thinking is optional for the model. Claude evaluates the complexity of each request and determines whether and how much to use extended thinking. At the default effort level (high), Claude almost always thinks. At lower effort levels, Claude may skip thinking for simpler problems.

Adaptive thinking also automatically enables interleaved thinking. This means Claude can think between tool calls, making it especially effective for agentic workflows.

How to use adaptive thinking
Set thinking.type to "adaptive" in your API request:

Shell
CLI
Python
TypeScript
C#
Go
Java
PHP
Ruby
curl https://api.anthropic.com/v1/messages \
     --header "x-api-key: $ANTHROPIC_API_KEY" \
     --header "anthropic-version: 2023-06-01" \
     --header "content-type: application/json" \
     --data \
'{
    "model": "claude-opus-4-7",
    "max_tokens": 16000,
    "thinking": {
        "type": "adaptive"
    },
    "messages": [
        {
            "role": "user",
            "content": "Explain why the sum of two even numbers is always even."
        }
    ]
}'
Adaptive thinking with the effort parameter
You can combine adaptive thinking with the effort parameter to guide how much thinking Claude does. The effort level acts as soft guidance for Claude's thinking allocation:

Effort level	Thinking behavior
max	Claude always thinks with no constraints on thinking depth. Available on Claude Mythos Preview, Claude Opus 4.7, Claude Opus 4.6, and Claude Sonnet 4.6.
xhigh	Claude always thinks deeply with extended exploration. Available on Claude Opus 4.7.
high (default)	Claude always thinks. Provides deep reasoning on complex tasks.
medium	Claude uses moderate thinking. May skip thinking for very simple queries.
low	Claude minimizes thinking. Skips thinking for simple tasks where speed matters most.
Shell
CLI
Python
TypeScript
C#
Go
Java
PHP
Ruby
curl https://api.anthropic.com/v1/messages \
     --header "x-api-key: $ANTHROPIC_API_KEY" \
     --header "anthropic-version: 2023-06-01" \
     --header "content-type: application/json" \
     --data \
'{
    "model": "claude-opus-4-7",
    "max_tokens": 16000,
    "thinking": {
        "type": "adaptive"
    },
    "output_config": {
        "effort": "medium"
    },
    "messages": [
        {
            "role": "user",
            "content": "What is the capital of France?"
        }
    ]
}'
Streaming with adaptive thinking
Adaptive thinking works seamlessly with streaming. Thinking blocks are streamed via thinking_delta events just like manual thinking mode:

