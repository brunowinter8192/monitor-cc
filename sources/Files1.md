Files API

Copy page

The Files API lets you upload and manage files to use with the Claude API without re-uploading content with each request. This is particularly useful when using the code execution tool to provide inputs (e.g. datasets and documents) and then download outputs (e.g. charts). You can also use the Files API to prevent having to continually re-upload frequently used documents and images across multiple API calls. You can explore the API reference directly, in addition to this guide.

The Files API is in beta. Reach out through the feedback form to share your experience with the Files API.
This feature is not eligible for Zero Data Retention (ZDR). Data is retained according to the feature's standard retention policy.
Supported models
Referencing a file_id in a Messages request is supported in all models that support the given file type. For example, images are supported in all Claude 3+ models, PDFs in all Claude 3.5+ models, and various other file types for the code execution tool in Claude Haiku 4.5 plus all Claude 3.7+ models.

The Files API is currently not supported on Amazon Bedrock or Google Vertex AI.

How the Files API works
The Files API provides a simple create-once, use-many-times approach for working with files:

Upload files to Anthropic's secure storage and receive a unique file_id
Download files that are created from skills or the code execution tool
Reference files in Messages requests using the file_id instead of re-uploading content
Manage your files with list, retrieve, and delete operations
How to use the Files API
To use the Files API, you'll need to include the beta feature header: anthropic-beta: files-api-2025-04-14.
Uploading a file
Upload a file to be referenced in future API calls:

Shell
curl -X POST https://api.anthropic.com/v1/files \
  -H "x-api-key: $ANTHROPIC_API_KEY" \
  -H "anthropic-version: 2023-06-01" \
  -H "anthropic-beta: files-api-2025-04-14" \
  -F "file=@/path/to/document.pdf"
The response from uploading a file will include:

Output
{
  "id": "file_011CNha8iCJcU1wXNR6q4V8w",
  "type": "file",
  "filename": "document.pdf",
  "mime_type": "application/pdf",
  "size_bytes": 1024000,
  "created_at": "2025-01-01T00:00:00Z",
  "downloadable": false
}
Using a file in messages
Once uploaded, reference the file using its file_id:

Shell
curl -X POST https://api.anthropic.com/v1/messages \
  -H "x-api-key: $ANTHROPIC_API_KEY" \
  -H "anthropic-version: 2023-06-01" \
  -H "anthropic-beta: files-api-2025-04-14" \
  -H "content-type: application/json" \
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
          "text": "Please summarize this document for me."
        },
        {
          "type": "document",
          "source": {
            "type": "file",
            "file_id": "$FILE_ID"
          }
        }
      ]
    }
  ]
}
EOF
File types and content blocks
The Files API supports different file types that correspond to different content block types:

File Type	MIME Type	Content Block Type	Use Case
PDF	application/pdf	document	Text analysis, document processing
Plain text	text/plain	document	Text analysis, processing
Images	image/jpeg, image/png, image/gif, image/webp	image	Image analysis, visual tasks
Datasets, others	Varies	container_upload	Analyze data, create visualizations
Working with other file formats
For file types that are not supported as document blocks (.csv, .txt, .md, .docx, .xlsx), convert the files to plain text, and include the content directly in your message:

