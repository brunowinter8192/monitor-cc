
The response has stop_reason: "max_tokens"
The output may be incomplete and not match your schema
Retry with a higher max_tokens value to get the complete structured output
Schema complexity limits
Structured outputs work by compiling your JSON schemas into a grammar that constrains Claude's output. More complex schemas produce larger grammars that take longer to compile. To protect against excessive compilation times, the API enforces several complexity limits.

Explicit limits
The following limits apply to all requests with output_config.format or strict: true:

Limit	Value	Description
Strict tools per request	20	Maximum number of tools with strict: true. Non-strict tools don't count toward this limit.
Optional parameters	24	Total optional parameters across all strict tool schemas and JSON output schemas. Each parameter not listed in required counts toward this limit.
Parameters with union types	16	Total parameters that use anyOf or type arrays (e.g., "type": ["string", "null"]) across all strict schemas. These are especially expensive because they create exponential compilation cost.
These limits apply to the combined total across all strict schemas in a single request. For example, if you have 4 strict tools with 6 optional parameters each, you'll reach the 24-parameter limit even though no single tool seems complex.
Additional internal limits
Beyond the explicit limits above, there are additional internal limits on the compiled grammar size. These limits exist because schema complexity doesn't reduce to a single dimension: features like optional parameters, union types, nested objects, and number of tools interact with each other in ways that can make the compiled grammar disproportionately large.

When these limits are exceeded, you'll receive a 400 error with the message "Schema is too complex for compilation." These errors mean the combined complexity of your schemas exceeds what can be efficiently compiled, even if each individual limit above is satisfied. As a final stop-gap, the API also enforces a compilation timeout of 180 seconds. Schemas that pass all explicit checks but produce very large compiled grammars may hit this timeout.

Tips for reducing schema complexity
If you're hitting complexity limits, try these strategies in order:

Mark only critical tools as strict. If you have many tools, reserve it for tools where schema violations cause real problems, and rely on Claude's natural adherence for simpler tools.
Reduce optional parameters. Make parameters required where possible. Each optional parameter roughly doubles a portion of the grammar's state space. If a parameter always has a reasonable default, consider making it required and having Claude provide that default explicitly.
Simplify nested structures. Deeply nested objects with optional fields compound the complexity. Flatten structures where possible.
Split into multiple requests. If you have many strict tools, consider splitting them across separate requests or sub-agents.
For persistent issues with valid schemas, contact support with your schema definition.

Data retention
Prompts and responses are processed with ZDR when using structured outputs. However, the JSON schema itself is temporarily cached for up to 24 hours since last use for optimization purposes. No prompt or response data is retained beyond the API response.

Structured outputs are HIPAA eligible, but PHI must not be included in JSON schema definitions. The API compiles JSON schemas into grammars that are cached separately from message content, and these cached schemas do not receive the same PHI protections as prompts and responses. Do not include PHI in schema property names, enum values, const values, or pattern regular expressions. PHI should only appear in message content (prompts and responses), where it is protected under HIPAA safeguards.

For ZDR and HIPAA eligibility across all features, see API and data retention.

Feature compatibility
Works with:

Batch processing: Process structured outputs at scale with 50% discount
Token counting: Count tokens without compilation
Streaming: Stream structured outputs like normal responses
Combined usage: Use JSON outputs (output_config.format) and strict tool use (strict: true) together in the same request
Incompatible with:

Citations: Citations require interleaving citation blocks with text, which conflicts with strict JSON schema constraints. Returns 400 error if citations enabled with output_config.format.
Message Prefilling: Incompatible with JSON outputs