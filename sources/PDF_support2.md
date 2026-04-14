
# Create a JSON request file using the pdf_base64.txt content
jq -n --rawfile PDF_BASE64 pdf_base64.txt '{
    "model": "claude-opus-4-6",
    "max_tokens": 1024,
    "messages": [{
        "role": "user",
        "content": [{
            "type": "document",
            "source": {
                "type": "base64",
                "media_type": "application/pdf",
                "data": $PDF_BASE64
            }
        },
        {
            "type": "text",
            "text": "What are the key findings in this document?"
        }]
    }]
}' > request.json

# Send the API request using the JSON file
curl https://api.anthropic.com/v1/messages \
  -H "content-type: application/json" \
  -H "x-api-key: $ANTHROPIC_API_KEY" \
  -H "anthropic-version: 2023-06-01" \
  -d @request.json
Option 3: Files API
For PDFs you'll use repeatedly, or when you want to avoid encoding overhead, use the Files API:

Shell
# First, upload your PDF to the Files API
curl -X POST https://api.anthropic.com/v1/files \
  -H "x-api-key: $ANTHROPIC_API_KEY" \
  -H "anthropic-version: 2023-06-01" \
  -H "anthropic-beta: files-api-2025-04-14" \
  -F "file=@document.pdf"

# Then use the returned file_id in your message
curl https://api.anthropic.com/v1/messages \
  -H "content-type: application/json" \
  -H "x-api-key: $ANTHROPIC_API_KEY" \
  -H "anthropic-version: 2023-06-01" \
  -H "anthropic-beta: files-api-2025-04-14" \
  -d '{
    "model": "claude-opus-4-6",
    "max_tokens": 1024,
    "messages": [{
      "role": "user",
      "content": [{
        "type": "document",
        "source": {
          "type": "file",
          "file_id": "file_abc123"
        }
      },
      {
        "type": "text",
        "text": "What are the key findings in this document?"
      }]
    }]
  }'
How PDF support works
When you send a PDF to Claude, the following steps occur:

1
The system extracts the contents of the document.
The system converts each page of the document into an image.
The text from each page is extracted and provided alongside each page's image.
2
Claude analyzes both the text and images to better understand the document.
Documents are provided as a combination of text and images for analysis.
This allows users to ask for insights on visual elements of a PDF, such as charts, diagrams, and other non-textual content.
3
Claude responds, referencing the PDF's contents if relevant.
Claude can reference both textual and visual content when it responds. You can further improve performance by integrating PDF support with:

Prompt caching: To improve performance for repeated analysis.
Batch processing: For high-volume document processing.
Tool use: To extract specific information from documents for use as tool inputs.
Estimate your costs
The token count of a PDF file depends on the total text extracted from the document as well as the number of pages:

Text token costs: Each page typically uses 1,500-3,000 tokens per page depending on content density. Standard API pricing applies with no additional PDF fees.
Image token costs: Since each page is converted into an image, the same image-based cost calculations are applied.
You can use token counting to estimate costs for your specific PDFs.

Optimize PDF processing
Improve performance
Follow these best practices for optimal results:

Place PDFs before text in your requests
Use standard fonts
Ensure text is clear and legible
Rotate pages to proper upright orientation
Use logical page numbers (from PDF viewer) in prompts
Split large PDFs into chunks when needed
Enable prompt caching for repeated analysis
Scale your implementation
For high-volume processing, consider these approaches:

Use prompt caching
Cache PDFs to improve performance on repeated queries:

Shell
# Create a JSON request file using the pdf_base64.txt content
jq -n --rawfile PDF_BASE64 pdf_base64.txt '{
    "model": "claude-opus-4-6",
    "max_tokens": 1024,
    "messages": [{
        "role": "user",
        "content": [{
            "type": "document",
            "source": {
                "type": "base64",
                "media_type": "application/pdf",
                "data": $PDF_BASE64
            },
            "cache_control": {
              "type": "ephemeral"
            }
        },
        {
            "type": "text",
            "text": "Which model has the highest human preference win rates across each use-case?"
        }]
    }]
}' > request.json

