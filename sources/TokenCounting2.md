
Thinking blocks from previous assistant turns are ignored and do not count toward your input tokens
Current assistant turn thinking does count toward your input tokens
Shell
curl https://api.anthropic.com/v1/messages/count_tokens \
    --header "x-api-key: $ANTHROPIC_API_KEY" \
    --header "content-type: application/json" \
    --header "anthropic-version: 2023-06-01" \
    --data '{
      "model": "claude-sonnet-4-6",
      "thinking": {
        "type": "enabled",
        "budget_tokens": 16000
      },
      "messages": [
        {
          "role": "user",
          "content": "Are there an infinite number of prime numbers such that n mod 4 == 3?"
        },
        {
          "role": "assistant",
          "content": [
            {
              "type": "thinking",
              "thinking": "This is a nice number theory question. Lets think about it step by step...",
              "signature": "EuYBCkQYAiJAgCs1le6/Pol5Z4/JMomVOouGrWdhYNsH3ukzUECbB6iWrSQtsQuRHJID6lWV..."
            },
            {
              "type": "text",
              "text": "Yes, there are infinitely many prime numbers p such that p mod 4 = 3..."
            }
          ]
        },
        {
          "role": "user",
          "content": "Can you write a formal proof?"
        }
      ]
    }'
Output
{ "input_tokens": 88 }
Count tokens in messages with PDFs
Token counting supports PDFs with the same limitations as the Messages API.
Shell
curl https://api.anthropic.com/v1/messages/count_tokens \
    --header "x-api-key: $ANTHROPIC_API_KEY" \
    --header "content-type: application/json" \
    --header "anthropic-version: 2023-06-01" \
    --data @- <<EOF
{
  "model": "claude-opus-4-6",
  "messages": [{
    "role": "user",
    "content": [
      {
        "type": "document",
        "source": {
          "type": "base64",
          "media_type": "application/pdf",
          "data": "$PDF_BASE64"
        }
      },
      {
        "type": "text",
        "text": "Please summarize this document."
      }
    ]
  }]
}
EOF
Output
{ "input_tokens": 2188 }
Pricing and rate limits
Token counting is free to use but subject to requests per minute rate limits based on your usage tier. If you need higher limits, contact sales through the Claude Console.

Usage tier	Requests per minute (RPM)
1	100
2	2,000
3	4,000
4	8,000
Token counting and message creation have separate and independent rate limits. Usage of one does not count against the limits of the other.
FAQ

Does token counting use prompt caching?
