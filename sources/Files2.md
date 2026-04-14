Shell
# Example: Reading a text file and sending it as plain text
# Note: For files with special characters, consider base64 encoding
# ...
curl https://api.anthropic.com/v1/messages \
  -H "content-type: application/json" \
  -H "x-api-key: $ANTHROPIC_API_KEY" \
  -H "anthropic-version: 2023-06-01" \
  -d @- <<EOF
{
  "model": "claude-opus-4-6",
  "max_tokens": 1024,
  "messages": [
    {
      "role": "user",
      "content": [
        {
          "type": "text",
          "text": "Here's the document content:\n\n${TEXT_CONTENT}\n\nPlease summarize this document."
        }
      ]
    }
  ]
}
EOF
For .docx files containing images, convert them to PDF format first, then use PDF support to take advantage of the built-in image parsing. This allows using citations from the PDF document.
Document blocks
For PDFs and text files, use the document content block:

{
  "type": "document",
  "source": {
    "type": "file",
    "file_id": "file_011CNha8iCJcU1wXNR6q4V8w"
  },
  "title": "Document Title", // Optional
  "context": "Context about the document", // Optional
  "citations": { "enabled": true } // Optional, enables citations
}
Image blocks
For images, use the image content block:

{
  "type": "image",
  "source": {
    "type": "file",
    "file_id": "file_011CPMxVD3fHLUhvTqtsQA5w"
  }
}
Managing files
List files
Retrieve a list of your uploaded files:

Shell
curl https://api.anthropic.com/v1/files \
  -H "x-api-key: $ANTHROPIC_API_KEY" \
  -H "anthropic-version: 2023-06-01" \
  -H "anthropic-beta: files-api-2025-04-14"
Get file metadata
Retrieve information about a specific file:

Shell
curl "https://api.anthropic.com/v1/files/$FILE_ID" \
  -H "x-api-key: $ANTHROPIC_API_KEY" \
  -H "anthropic-version: 2023-06-01" \
  -H "anthropic-beta: files-api-2025-04-14"
Delete a file
Remove a file from your workspace:

Shell
curl -X DELETE "https://api.anthropic.com/v1/files/$FILE_ID" \
  -H "x-api-key: $ANTHROPIC_API_KEY" \
  -H "anthropic-version: 2023-06-01" \
  -H "anthropic-beta: files-api-2025-04-14"
Downloading a file
Download files that have been created by skills or the code execution tool:

Shell
curl -X GET "https://api.anthropic.com/v1/files/$FILE_ID/content" \
  -H "x-api-key: $ANTHROPIC_API_KEY" \
  -H "anthropic-version: 2023-06-01" \
  -H "anthropic-beta: files-api-2025-04-14" \
  --output downloaded_file.txt
You can only download files that were created by skills or the code execution tool. Files that you uploaded cannot be downloaded.
File storage and limits
Storage limits
Maximum file size: 500 MB per file
Total storage: 500 GB per organization
File lifecycle
Files are scoped to the workspace of the API key. Other API keys can use files created by any other API key associated with the same workspace
Files persist until you delete them
Deleted files cannot be recovered
Files are inaccessible via the API shortly after deletion, but they may persist in active Messages API calls and associated tool uses
Files that users delete will be deleted in accordance with Anthropic's data retention policy.
Data retention
Files uploaded via the Files API are retained until explicitly deleted using the DELETE /v1/files/{file_id} endpoint. Files are stored for reuse across multiple API requests.

For ZDR eligibility across all features, see API and data retention.

Error handling
Common errors when using the Files API include:

File not found (404): The specified file_id doesn't exist or you don't have access to it
Invalid file type (400): The file type doesn't match the content block type (e.g., using an image file in a document block)
Exceeds context window size (400): The file is larger than the context window size (e.g. using a 500 MB plaintext file in a /v1/messages request)
Invalid filename (400): Filename doesn't meet the length requirements (1-255 characters) or contains forbidden characters (<, >, :, ", |, ?, *, \, /, or unicode characters 0-31)
File too large (413): File exceeds the 500 MB limit
Storage limit exceeded (403): Your organization has reached the 500 GB storage limit
Output
{
  "type": "error",
  "error": {
    "type": "invalid_request_error",
    "message": "File not found: file_011CNha8iCJcU1wXNR6q4V8w"
  }
}
Usage and billing
File API operations are free:

Uploading files
Downloading files
Listing files
Getting file metadata
Deleting files
File content used in Messages requests are priced as input tokens. You can only download files created by skills or the code execution tool.

Rate limits
During the beta period:

File-related API calls are limited to approximately 100 requests per minute
Contact us if you need higher limits for your use case
