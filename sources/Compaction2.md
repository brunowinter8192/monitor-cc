
When enabled, the API returns a message with the compaction stop reason after generating the compaction block:

CLI
ant beta:messages create --beta compact-2026-01-12 \
  --transform '{stop_reason,content}' --format jsonl <<'YAML' > resp.json
model: claude-opus-4-6
max_tokens: 4096
messages:
  - role: user
    content: "Hello, Claude"
context_management:
  edits:
    - type: compact_20260112
      pause_after_compaction: true
YAML

# Check if compaction triggered a pause
if grep -q '"stop_reason":"compaction"' resp.json; then
  # Response contains only the compaction block
  RESP=$(cat resp.json)
  CONTENT="${RESP#*\"content\":}"
  printf '%s' "${CONTENT%\}}" > content.json

  # Continue the request
  ant beta:messages create --beta compact-2026-01-12 <<YAML > /dev/null
model: claude-opus-4-6
max_tokens: 4096
messages:
  - role: user
    content: "Hello, Claude"
  - role: assistant
    content: $(cat content.json)
context_management:
  edits:
    - type: compact_20260112
YAML
fi
Enforcing a total token budget
When a model works on long tasks with many tool-use iterations, total token consumption can grow significantly. You can combine pause_after_compaction with a compaction counter to estimate cumulative usage and gracefully wrap up the task once a budget is reached:

Python
client = anthropic.Anthropic()
messages = [{"role": "user", "content": "Hello, Claude"}]
TRIGGER_THRESHOLD = 100_000
TOTAL_TOKEN_BUDGET = 3_000_000
n_compactions = 0

response = client.beta.messages.create(
    betas=["compact-2026-01-12"],
    model="claude-opus-4-6",
    max_tokens=4096,
    messages=messages,
    context_management={
        "edits": [
            {
                "type": "compact_20260112",
                "trigger": {"type": "input_tokens", "value": TRIGGER_THRESHOLD},
                "pause_after_compaction": True,
            }
        ]
    },
)

if response.stop_reason == "compaction":
    n_compactions += 1
    messages.append({"role": "assistant", "content": response.content})

    # Estimate total tokens consumed; prompt wrap-up if over budget
    if n_compactions * TRIGGER_THRESHOLD >= TOTAL_TOKEN_BUDGET:
        messages.append(
            {
                "role": "user",
                "content": "Please wrap up your current work and summarize the final state.",
            }
        )
Working with compaction blocks
When compaction is triggered, the API returns a compaction block at the start of the assistant response.

A long-running conversation may result in multiple compactions. The last compaction block reflects the final state of the prompt, replacing content prior to it with the generated summary.

Output
{
  "content": [
    {
      "type": "compaction",
      "content": "Summary of the conversation: The user requested help building a web scraper..."
    },
    {
      "type": "text",
      "text": "Based on our conversation so far..."
    }
  ]
}
Passing compaction blocks back
You must pass the compaction block back to the API on subsequent requests to continue the conversation with the shortened prompt. The simplest approach is to append the entire response content to your messages:

