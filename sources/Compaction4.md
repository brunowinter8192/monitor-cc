The top-level input_tokens and output_tokens do not include compaction iteration usage. They reflect the sum of all non-compaction iterations. To calculate total tokens consumed and billed for a request, sum across all entries in the usage.iterations array.

If you previously relied on usage.input_tokens and usage.output_tokens for cost tracking or auditing, you'll need to update your tracking logic to aggregate across usage.iterations when compaction is enabled. The iterations array is only populated when a new compaction is triggered during the request. Re-applying a previous compaction block incurs no additional compaction cost, and the top-level usage fields remain accurate in that case.
Combining with other features
Server tools
When using server tools (like web search), the compaction trigger is checked at the start of each sampling iteration. Compaction may occur multiple times within a single request depending on your trigger threshold and the amount of output generated.

Token counting
The token counting endpoint (/v1/messages/count_tokens) applies existing compaction blocks in your prompt but does not trigger new compactions. Use it to check your effective token count after previous compactions:

CLI
cat > request.yaml <<'YAML'
model: claude-opus-4-6
messages:
  - role: user
    content: Hello, Claude
context_management:
  edits:
    - type: compact_20260112
YAML

CURRENT=$(ant beta:messages count-tokens \
  --beta compact-2026-01-12 \
  --transform input_tokens --format yaml < request.yaml)

ORIGINAL=$(ant beta:messages count-tokens \
  --beta compact-2026-01-12 \
  --transform context_management.original_input_tokens \
  --format yaml < request.yaml)

printf 'Current tokens: %s\n' "$CURRENT"
printf 'Original tokens: %s\n' "$ORIGINAL"
Examples
Here's a complete example of a long-running conversation with compaction:

CLI
# The CLI handles individual turns; maintain the messages array in the
# calling script. See the SDK tabs for the full chat() loop. Single-turn
# request shape:
ant beta:messages create --beta compact-2026-01-12 \
  --transform 'content.#(type=="text").text' --format yaml <<'YAML'
model: claude-opus-4-6
max_tokens: 4096
messages:
  - role: user
    content: Help me build a Python web scraper
context_management:
  edits:
    - type: compact_20260112
      trigger:
        type: input_tokens
        value: 100000
YAML
Here's an example that uses pause_after_compaction to preserve the prior exchange and the current user message (three messages total) verbatim instead of summarizing them:

CLI
# The CLI handles individual turns; maintain the messages array in the
# calling script. See the SDK tabs for the full chat() loop with
# pause-and-preserve handling. Single-turn request shape:
ant beta:messages create --beta compact-2026-01-12 \
  --transform 'content.#(type=="text").text' --format yaml <<'YAML'
model: claude-opus-4-6
max_tokens: 4096
messages:
  - role: user
    content: Help me build a Python web scraper
context_management:
  edits:
    - type: compact_20260112
      trigger:
        type: input_tokens
        value: 100000
      pause_after_compaction: true
YAML
Current limitations
Same model for summarization: The model specified in your request is used for summarization. There is no option to use a different (for example, cheaper) model for the summary.