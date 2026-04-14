
The citation blocks generated in responses cannot be cached directly, but the source documents they reference can be cached. To optimize performance, apply cache_control to your top-level document content blocks.

Shell
curl https://api.anthropic.com/v1/messages \
     --header "x-api-key: $ANTHROPIC_API_KEY" \
     --header "anthropic-version: 2023-06-01" \
     --header "content-type: application/json" \
     --data '{
    "model": "claude-opus-4-6",
    "max_tokens": 1024,
    "messages": [
        {
            "role": "user",
            "content": [
                {
                    "type": "document",
                    "source": {
                        "type": "text",
                        "media_type": "text/plain",
                        "data": "This is a very long document with thousands of words..."
                    },
                    "citations": {"enabled": true},
                    "cache_control": {"type": "ephemeral"}
                },
                {
                    "type": "text",
                    "text": "What does this document say about API features?"
                }
            ]
        }
    ]
}'
In this example:

The document content is cached using cache_control on the document block
Citations are enabled on the document
Claude can generate responses with citations while benefiting from cached document content
Subsequent requests using the same document will benefit from the cached content
Document Types
Choosing a document type
Three document types are supported for citations. Documents can be provided directly in the message (base64, text, or URL) or uploaded via the Files API and referenced by file_id:

Type	Best for	Chunking	Citation format
Plain text	Simple text documents, prose	Sentence	Character indices (0-indexed)
PDF	PDF files with text content	Sentence	Page numbers (1-indexed)
Custom content	Lists, transcripts, special formatting, more granular citations	No additional chunking	Block indices (0-indexed)
.csv, .xlsx, .docx, .md, and .txt files are not supported as document blocks. Convert these to plain text and include directly in message content. See Working with other file formats.
Plain text documents
Plain text documents are automatically chunked into sentences. You can provide them inline or by reference with their file_id:

Inline text
Files API
{
    "type": "document",
    "source": {
        "type": "text",
        "media_type": "text/plain",
        "data": "Plain text content...",
    },
    "title": "Document Title",  # optional
    "context": "Context about the document that will not be cited from",  # optional
    "citations": {"enabled": True},
}

Example plain text citation
PDF documents
PDF documents can be provided as base64-encoded data or by file_id. PDF text is extracted and chunked into sentences. As image citations are not yet supported, PDFs that are scans of documents and do not contain extractable text will not be citable.

Base64
Files API
{
    "type": "document",
    "source": {
        "type": "base64",
        "media_type": "application/pdf",
        "data": base64_encoded_pdf_data,
    },
    "title": "Document Title",  # optional
    "context": "Context about the document that will not be cited from",  # optional
    "citations": {"enabled": True},
}

Example PDF citation
Custom content documents
Custom content documents give you control over citation granularity. No additional chunking is done and chunks are provided to the model according to the content blocks provided.

{
    "type": "document",
    "source": {
        "type": "content",
        "content": [
            {"type": "text", "text": "First chunk"},
            {"type": "text", "text": "Second chunk"},
        ],
    },
    "title": "Document Title",  # optional
    "context": "Context about the document that will not be cited from",  # optional
    "citations": {"enabled": True},
}

