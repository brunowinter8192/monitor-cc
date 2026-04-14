Search results

Copy page

Enable natural citations for RAG applications by providing search results with source attribution
This feature is eligible for Zero Data Retention (ZDR). When your organization has a ZDR arrangement, data sent through this feature is not stored after the API response is returned.
Search result content blocks enable natural citations with proper source attribution, bringing web search-quality citations to your custom applications. This feature is particularly powerful for RAG (Retrieval-Augmented Generation) applications where you need Claude to cite sources accurately.

The search results feature is available on the following models:

Claude Opus 4.6 (claude-opus-4-6)
Claude Sonnet 4.6 (claude-sonnet-4-6)
Claude Sonnet 4.5 (claude-sonnet-4-5-20250929)
Claude Opus 4.5 (claude-opus-4-5-20251101)
Claude Opus 4.1 (claude-opus-4-1-20250805)
Claude Opus 4 (claude-opus-4-20250514)
Claude Sonnet 4 (claude-sonnet-4-20250514)
Claude Sonnet 3.7 (deprecated) (claude-3-7-sonnet-20250219)
Claude Haiku 4.5 (claude-haiku-4-5-20251001)
Claude Haiku 3.5 (deprecated) (claude-3-5-haiku-20241022)
Key benefits
Natural citations - Achieve the same citation quality as web search for any content
Flexible integration - Use in tool returns for dynamic RAG or as top-level content for pre-fetched data
Proper source attribution - Each result includes source and title information for clear attribution
No document workarounds needed - Eliminates the need for document-based workarounds
Consistent citation format - Matches the citation quality and format of Claude's web search functionality
How it works
Search results can be provided in two ways:

From tool calls - Your custom tools return search results, enabling dynamic RAG applications
As top-level content - You provide search results directly in user messages for pre-fetched or cached content
In both cases, Claude can automatically cite information from the search results with proper source attribution.

Search result schema
Search results use the following structure:

{
  "type": "search_result",
  "source": "https://example.com/article", // Required: Source URL or identifier
  "title": "Article Title", // Required: Title of the result
  "content": [
    // Required: Array of text blocks
    {
      "type": "text",
      "text": "The actual content of the search result..."
    }
  ],
  "citations": {
    // Optional: Citation configuration
    "enabled": true // Enable/disable citations for this result
  }
}
Required fields
Field	Type	Description
type	string	Must be "search_result"
source	string	The source URL or identifier for the content
title	string	A descriptive title for the search result
content	array	An array of text blocks containing the actual content
Optional fields
Field	Type	Description
citations	object	Citation configuration with enabled boolean field
cache_control	object	Cache control settings (e.g., {"type": "ephemeral"})
Each item in the content array must be a text block with:

type: Must be "text"
text: The actual text content (non-empty string)
Method 1: Search results from tool calls
The most powerful use case is returning search results from your custom tools. This enables dynamic RAG applications where tools fetch and return relevant content with automatic citations.

Example: Knowledge base tool
Python
from anthropic.types import (
    MessageParam,
    TextBlockParam,
    SearchResultBlockParam,
    ToolResultBlockParam,
)

client = Anthropic()

# Define a knowledge base search tool
knowledge_base_tool = {
    "name": "search_knowledge_base",
    "description": "Search the company knowledge base for information",
    "input_schema": {
        "type": "object",
        "properties": {"query": {"type": "string", "description": "The search query"}},
        "required": ["query"],
    },
}
