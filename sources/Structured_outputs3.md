CLI
ant messages create <<'YAML'
model: claude-opus-4-6
max_tokens: 1024
messages:
  - role: user
    content: Help me plan a trip to Paris departing May 15, 2026
# JSON outputs: structured response format
output_config:
  format:
    type: json_schema
    schema:
      type: object
      properties:
        summary:
          type: string
        next_steps:
          type: array
          items:
            type: string
      required: [summary, next_steps]
      additionalProperties: false
# Strict tool use: guaranteed tool parameters
tools:
  - name: search_flights
    strict: true
    input_schema:
      type: object
      properties:
        destination:
          type: string
        date:
          type: string
          format: date
      required: [destination, date]
      additionalProperties: false
YAML
Important considerations
Grammar compilation and caching
Structured outputs use constrained sampling with compiled grammar artifacts. This introduces some performance characteristics to be aware of:

First request latency: The first time you use a specific schema, there is additional latency while the grammar compiles
Automatic caching: Compiled grammars are cached for 24 hours from last use, making subsequent requests much faster
Cache invalidation: The cache is invalidated if you change:
The JSON schema structure
The set of tools in your request (when using both structured outputs and tool use)
Changing only name or description fields does not invalidate the cache
Prompt modification and token costs
When using structured outputs, Claude automatically receives an additional system prompt explaining the expected output format. This means:

Your input token count is slightly higher
The injected prompt costs you tokens like any other system prompt
Changing the output_config.format parameter will invalidate any prompt cache for that conversation thread
JSON Schema limitations
Structured outputs support standard JSON Schema with some limitations. Both JSON outputs and strict tool use share these limitations.


Supported features

Not supported

Pattern support (regex)
The Python, TypeScript, Ruby, and PHP SDKs can automatically transform schemas with unsupported features by removing them and adding constraints to field descriptions. See SDK-specific methods for details.
Property ordering
When using structured outputs, properties in objects maintain their defined ordering from your schema, with one important caveat: required properties appear first, followed by optional properties.

For example, given this schema:

{
  "type": "object",
  "properties": {
    "notes": { "type": "string" },
    "name": { "type": "string" },
    "email": { "type": "string" },
    "age": { "type": "integer" }
  },
  "required": ["name", "email"],
  "additionalProperties": false
}
The output will order properties as:

name (required, in schema order)
email (required, in schema order)
notes (optional, in schema order)
age (optional, in schema order)
This means the output might look like:

{
  "name": "John Smith",
  "email": "john@example.com",
  "notes": "Interested in enterprise plan",
  "age": 35
}
If property order in the output is important to your application, mark all properties as required, or account for this reordering in your parsing logic.

Invalid outputs
While structured outputs guarantee schema compliance in most cases, there are scenarios where the output may not match your schema:

Refusals (stop_reason: "refusal")

Claude maintains its safety and helpfulness properties even when using structured outputs. If Claude refuses a request for safety reasons:

The response has stop_reason: "refusal"
You'll receive a 200 status code
You'll be billed for the tokens generated
The output may not match your schema because the refusal message takes precedence over schema constraints
Token limit reached (stop_reason: "max_tokens")

If the response is cut off due to reaching the max_tokens limit:
