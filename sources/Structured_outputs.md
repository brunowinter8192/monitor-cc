Structured outputs

Copy page

Get validated JSON results from agent workflows
Structured outputs constrain Claude's responses to follow a specific schema, ensuring valid, parseable output for downstream processing. Structured outputs provide two complementary features:

JSON outputs (output_config.format): Get Claude's response in a specific JSON format
Strict tool use (strict: true): Guarantee schema validation on tool names and inputs
You can use these features independently or together in the same request.

Structured outputs are generally available on the Claude API and Amazon Bedrock for Claude Mythos Preview, Claude Opus 4.6, Claude Sonnet 4.6, Claude Sonnet 4.5, Claude Opus 4.5, and Claude Haiku 4.5. Structured outputs are in beta on Microsoft Foundry. Structured outputs are not supported on Google Cloud's Vertex AI for Claude Mythos Preview.
This feature qualifies for Zero Data Retention (ZDR) with limited technical retention. See the Data retention section for details on what is retained and why.
Migrating from beta? The output_format parameter has moved to output_config.format, and beta headers are no longer required. The old beta header (structured-outputs-2025-11-13) and output_format parameter will continue working for a transition period. See code examples below for the updated API shape.
Why use structured outputs
Without structured outputs, Claude can generate malformed JSON responses or invalid tool inputs that break your applications. Even with careful prompting, you may encounter:

Parsing errors from invalid JSON syntax
Missing required fields
Inconsistent data types
Schema violations requiring error handling and retries
Structured outputs guarantee schema-compliant responses through constrained decoding:

Always valid: No more JSON.parse() errors
Type safe: Guaranteed field types and required fields
Reliable: No retries needed for schema violations
JSON outputs
JSON outputs control Claude's response format, ensuring Claude returns valid JSON matching your schema. Use JSON outputs when you need to:

Control Claude's response format
Extract data from images or text
Generate structured reports
Format API responses
Quick start
Shell
curl https://api.anthropic.com/v1/messages \
  -H "content-type: application/json" \
  -H "x-api-key: $ANTHROPIC_API_KEY" \
  -H "anthropic-version: 2023-06-01" \
  -d '{
    "model": "claude-opus-4-6",
    "max_tokens": 1024,
    "messages": [
      {
        "role": "user",
        "content": "Extract the key information from this email: John Smith (john@example.com) is interested in our Enterprise plan and wants to schedule a demo for next Tuesday at 2pm."
      }
    ],
    "output_config": {
      "format": {
        "type": "json_schema",
        "schema": {
          "type": "object",
          "properties": {
            "name": {"type": "string"},
            "email": {"type": "string"},
            "plan_interest": {"type": "string"},
            "demo_requested": {"type": "boolean"}
          },
          "required": ["name", "email", "plan_interest", "demo_requested"],
          "additionalProperties": false
        }
      }
    }
  }'
Response format: Valid JSON matching your schema in response.content[0].text

Output
{
  "name": "John Smith",
  "email": "john@example.com",
  "plan_interest": "Enterprise",
  "demo_requested": true
}
How it works
1
Define your JSON schema
Create a JSON schema that describes the structure you want Claude to follow. The schema uses standard JSON Schema format with some limitations (see JSON Schema limitations).
2
Add the output_config.format parameter
Include the output_config.format parameter in your API request with type: "json_schema" and your schema definition.
3
Parse the response
Claude's response is valid JSON matching your schema, returned in response.content[0].text.
Working with JSON outputs in SDKs
The SDKs provide helpers that make it easier to work with JSON outputs, including schema transformation, automatic validation, and integration with popular schema libraries.

The Python SDK's client.messages.parse() still accepts output_format as a convenience parameter and translates it to output_config.format internally. Other SDKs require output_config directly. The examples below show the SDK helper syntax.
Using native schema definitions
Instead of writing raw JSON schemas, you can use familiar schema definition tools in your language:
