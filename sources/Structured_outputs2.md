
Python: Pydantic models with client.messages.parse()
TypeScript: Zod schemas with zodOutputFormat() or typed JSON Schema literals with jsonSchemaOutputFormat()
Java: Plain Java classes with automatic schema derivation via outputConfig(Class<T>)
Ruby: Anthropic::BaseModel classes with output_config: {format: Model}
PHP: Classes implementing StructuredOutputModel with outputConfig: ['format' => MyClass::class]
CLI, C#, Go: Raw JSON schemas passed via output_config
CLI
{ read -r _ NAME; read -r _ EMAIL; } < <(
  ant messages create \
    --transform 'content.0.text|@fromstr|{name,email}' --format yaml <<'YAML'
model: claude-opus-4-6
max_tokens: 1024
messages:
  - role: user
    content: >-
      Extract the key information from this email: John Smith
      (john@example.com) is interested in our Enterprise plan and wants
      to schedule a demo for next Tuesday at 2pm.
output_config:
  format:
    type: json_schema
    schema:
      type: object
      properties:
        name: {type: string}
        email: {type: string}
        plan_interest: {type: string}
        demo_requested: {type: boolean}
      required: [name, email, plan_interest, demo_requested]
      additionalProperties: false
YAML
)
printf '%s (%s)\n' "$NAME" "$EMAIL"
SDK-specific methods
Each SDK provides helpers that make working with structured outputs easier. See individual SDK pages for full details.

CLI
Python
TypeScript
C#
Go
Java
PHP
Ruby
Raw JSON schemas via heredoc body

The CLI passes raw JSON schemas as a YAML heredoc body. Use the GJSON @fromstr modifier with --transform to parse the JSON string returned in content[0].text and project specific fields.

ant messages create \
  --transform 'content.0.text|@fromstr|{name,email}' \
  --format yaml <<'YAML'
model: claude-opus-4-6
max_tokens: 1024
messages:
  - role: user
    content: >-
      Extract contact info: John Smith, john@example.com,
      interested in the Pro plan
output_config:
  format:
    type: json_schema
    schema:
      type: object
      properties:
        name: {type: string}
        email: {type: string}
        plan_interest: {type: string}
      required: [name, email, plan_interest]
      additionalProperties: false
YAML
Output
name: John Smith
email: john@example.com
How SDK transformation works
The Python, TypeScript, Ruby, and PHP SDKs automatically transform schemas with unsupported features:

Remove unsupported constraints (e.g., minimum, maximum, minLength, maxLength)
Update descriptions with constraint info (e.g., "Must be at least 100"), when the constraint is not directly supported with structured outputs
Add additionalProperties: false to all objects
Filter string formats to supported list only
Validate responses against your original schema (with all constraints)
This means Claude receives a simplified schema, but your code still enforces all constraints through validation.

Example: A Pydantic field with minimum: 100 becomes a plain integer in the sent schema, but the SDK updates the description to "Must be at least 100" and validates the response against the original constraint.

Common use cases

Data extraction

Classification

API response formatting
Strict tool use
For enforcing JSON Schema compliance on tool inputs with grammar-constrained sampling, see Strict tool use.

Using both features together
JSON outputs and strict tool use solve different problems and work together:

JSON outputs control Claude's response format (what Claude says)
Strict tool use validates tool parameters (how Claude calls your functions)
When combined, Claude can call tools with guaranteed-valid parameters AND return structured JSON responses. This is useful for agentic workflows where you need both reliable tool calls and structured final outputs.

