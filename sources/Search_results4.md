# Claude might respond and call a tool to search for pricing
# Then you provide tool results with more search results
Combining with other content types
Both methods support mixing search results with other content:

from anthropic.types import SearchResultBlockParam, TextBlockParam

# In tool results
tool_result = [
    SearchResultBlockParam(
        type="search_result",
        source="https://docs.company.com/guide",
        title="User Guide",
        content=[TextBlockParam(type="text", text="Configuration details...")],
        citations={"enabled": True},
    ),
    TextBlockParam(
        type="text", text="Additional context: This applies to version 2.0 and later."
    ),
]

# In top-level content
user_content = [
    SearchResultBlockParam(
        type="search_result",
        source="https://research.com/paper",
        title="Research Paper",
        content=[TextBlockParam(type="text", text="Key findings...")],
        citations={"enabled": True},
    ),
    {
        "type": "image",
        "source": {"type": "url", "url": "https://example.com/chart.png"},
    },
    TextBlockParam(
        type="text", text="How does the chart relate to the research findings?"
    ),
]
Cache control
Add cache control for better performance:

{
  "type": "search_result",
  "source": "https://docs.company.com/guide",
  "title": "User Guide",
  "content": [{ "type": "text", "text": "..." }],
  "cache_control": {
    "type": "ephemeral"
  }
}
Citation control
By default, citations are disabled for search results. You can enable citations by explicitly setting the citations configuration:

{
  "type": "search_result",
  "source": "https://docs.company.com/guide",
  "title": "User Guide",
  "content": [{ "type": "text", "text": "Important documentation..." }],
  "citations": {
    "enabled": true // Enable citations for this result
  }
}
When citations.enabled is set to true, Claude includes citation references when using information from the search result. This enables:

Natural citations for your custom RAG applications
Source attribution when interfacing with proprietary knowledge bases
Web search-quality citations for any custom tool that returns search results
If the citations field is omitted, citations are disabled by default.

Citations are all-or-nothing: either all search results in a request must have citations enabled, or all must have them disabled. Mixing search results with different citation settings results in an error. If you need to disable citations for some sources, you must disable them for all search results in that request.
Best practices
For tool-based search (Method 1)
Dynamic content: Use for real-time searches and dynamic RAG applications
Error handling: Return appropriate messages when searches fail
Result limits: Return only the most relevant results to avoid context overflow
For top-level search (Method 2)
Pre-fetched content: Use when you already have search results
Batch processing: Ideal for processing multiple search results at once
Testing: Great for testing citation behavior with known content
General best practices
Structure results effectively

Use clear, permanent source URLs
Provide descriptive titles
Break long content into logical text blocks
Maintain consistency

Use consistent source formats across your application
Ensure titles accurately reflect content
Keep formatting consistent
Handle errors gracefully

def search_with_fallback(query):
    try:
        results = perform_search(query)
        if not results:
            return {"type": "text", "text": "No results found."}
        return format_as_search_results(results)
    except Exception as e:
        return {"type": "text", "text": f"Search error: {str(e)}"}
Limitations
Search result content blocks are available on Claude API, Amazon Bedrock, and Google Cloud's Vertex AI
Only text content is supported within search results (no images or other media)
The content array must contain at least one text block
