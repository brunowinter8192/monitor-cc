Building with extended thinking

Copy page

This feature is eligible for Zero Data Retention (ZDR). When your organization has a ZDR arrangement, data sent through this feature is not stored after the API response is returned.
Extended thinking gives Claude enhanced reasoning capabilities for complex tasks, while providing varying levels of transparency into its step-by-step thought process before it delivers its final answer.

For Claude Opus 4.7 and later models, use adaptive thinking (thinking: {type: "adaptive"}) with the effort parameter. Manual extended thinking (thinking: {type: "enabled", budget_tokens: N}) is no longer supported on Claude Opus 4.7 or later models and returns a 400 error. For Claude Opus 4.6 and Claude Sonnet 4.6, adaptive thinking is also recommended; the manual configuration is still functional on these models but is deprecated and will be removed in a future model release.
Supported models
Manual extended thinking (thinking: {type: "enabled", budget_tokens: N}) is supported on all current Claude models except Claude Opus 4.7 and later models, where it is no longer accepted and returns a 400 error. A few models have mode-specific behavior:

Claude Opus 4.7 (claude-opus-4-7) and later models: manual extended thinking is no longer supported. Use adaptive thinking (thinking: {type: "adaptive"}) with the effort parameter instead.
Claude Mythos Preview: adaptive thinking is the default; thinking: {type: "enabled", budget_tokens: N} is also accepted. thinking: {type: "disabled"} is not supported, and display defaults to "omitted" rather than returning thinking content. Pass display: "summarized" to receive summaries.
Claude Opus 4.6 (claude-opus-4-6): adaptive thinking recommended; manual mode (type: "enabled") is deprecated but still functional.
Claude Sonnet 4.6 (claude-sonnet-4-6): adaptive thinking recommended; manual mode (type: "enabled") with interleaved mode is deprecated but still functional.
API behavior differs across Claude Sonnet 3.7 and Claude 4 models, but the API shapes remain exactly the same.

For more information, see Differences in thinking across model versions.
How extended thinking works
When extended thinking is turned on, Claude creates thinking content blocks where it outputs its internal reasoning. Claude incorporates insights from this reasoning before crafting a final response.

The API response includes thinking content blocks, followed by text content blocks.

Here's an example of the default response format:

{
  "content": [
    {
      "type": "thinking",
      "thinking": "Let me analyze this step by step...",
      "signature": "WaUjzkypQ2mUEVM36O2TxuC06KN8xyfbJwyem2dw3URve/op91XWHOEBLLqIOMfFG/UvLEczmEsUjavL...."
    },
    {
      "type": "text",
      "text": "Based on my analysis..."
    }
  ]
}
For more information about the response format of extended thinking, see the Messages API Reference.

How to use extended thinking
Here is an example of using extended thinking in the Messages API:

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
    "model": "claude-sonnet-4-6",
    "max_tokens": 16000,
    "thinking": {
        "type": "enabled",
        "budget_tokens": 10000
    },
    "messages": [
        {
            "role": "user",
            "content": "Are there an infinite number of prime numbers such that n mod 4 == 3?"
        }
    ]
}'
To turn on extended thinking, add a thinking object, with the type parameter set to enabled and the budget_tokens to a specified token budget for extended thinking. For Claude Opus 4.6 and Claude Sonnet 4.6, use type: "adaptive" instead. See Adaptive thinking for details. While type: "enabled" with budget_tokens is still functional on these models, it is deprecated and will be removed in a future release.

The budget_tokens parameter determines the maximum number of tokens Claude is allowed to use for its internal reasoning process. In Claude 4 and later models, this limit applies to full thinking tokens, and not to the summarized output. Larger budgets can improve response quality by enabling more thorough analysis for complex problems, although Claude may not use the entire budget allocated, especially at ranges above 32k.

budget_tokens is deprecated on Claude Opus 4.6 and Claude Sonnet 4.6 and will be removed in a future model release. Use adaptive thinking with the effort parameter to control thinking depth instead.
Claude Mythos Preview, Claude Opus 4.7, and Claude Opus 4.6 support up to 128k output tokens. Claude Sonnet 4.6 and Claude Haiku 4.5 support up to 64k. See the models overview for limits on legacy models. On the Message Batches API, the output-300k-2026-03-24 beta header raises the output limit to 300k for Opus 4.7, Opus 4.6, and Sonnet 4.6.
budget_tokens must be set to a value less than max_tokens. However, when using interleaved thinking with tools, you can exceed this limit as the token limit becomes your entire context window.

Summarized thinking
With extended thinking enabled, the Messages API for Claude 4 models returns a summary of Claude's full thinking process. Summarized thinking provides the full intelligence benefits of extended thinking, while preventing misuse. This is the default behavior on Claude 4 models when the display field on the thinking configuration is unset or set to "summarized". On Claude Opus 4.7 and Claude Mythos Preview, display defaults to "omitted" instead, so you must set display: "summarized" explicitly to receive summarized thinking.

Here are some important considerations for summarized thinking:

You're charged for the full thinking tokens generated by the original request, not the summary tokens.
The billed output token count will not match the count of tokens you see in the response.
On Claude 4 models, the first few lines of thinking output are more verbose, providing detailed reasoning that's particularly helpful for prompt engineering purposes. Claude Mythos Preview summarizes from the first token, so its thinking blocks do not show this verbose preamble.
As Anthropic seeks to improve the extended thinking feature, summarization behavior is subject to change.
Summarization preserves the key ideas of Claude's thinking process with minimal added latency, enabling a streamable user experience and easy migration from Claude Sonnet 3.7 to Claude 4 and later models.
Summarization is processed by a different model than the one you target in your requests. The thinking model does not see the summarized output.
Claude Sonnet 3.7 continues to return full thinking output.

In rare cases where you need access to full thinking output for Claude 4 models, contact our sales team.
Controlling thinking display
The display field on the thinking configuration controls how thinking content is returned in API responses. It accepts two values:

"summarized": Thinking blocks contain summarized thinking text. See Summarized thinking for details. This is the default on Claude Opus 4.6, Claude Sonnet 4.6, and earlier Claude 4 models.
"omitted": Thinking blocks are returned with an empty thinking field. The signature field still carries the encrypted full thinking for multi-turn continuity (see Thinking encryption). This is the default on Claude Opus 4.7 and Claude Mythos Preview.
Setting display: "omitted" is useful when your application doesn't surface thinking content to users. The primary benefit is faster time-to-first-text-token when streaming: The server skips streaming thinking tokens entirely and delivers only the signature, so the final text response begins streaming sooner.

No SDK currently includes display in its type definitions. The Python SDK forwards unrecognized dict keys to the API at runtime; passing display in the thinking dict works transparently. The TypeScript SDK requires a type assertion. The C#, Go, Java, PHP, and Ruby SDKs require a direct HTTP request until native support lands.
Here are some important considerations for omitted thinking:

