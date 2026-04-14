Tool	Error Code	Description
All tools	unavailable	The tool is temporarily unavailable
All tools	execution_time_exceeded	Execution exceeded maximum time limit
All tools	container_expired	Container expired and is no longer available
All tools	invalid_tool_input	Invalid parameters provided to the tool
All tools	too_many_requests	Rate limit exceeded for tool usage
bash	output_file_too_large	Command output exceeded the maximum size
text_editor	file_not_found	File doesn't exist (for view/edit operations)
text_editor	string_not_found	The old_str not found in file (for str_replace)
pause_turn stop reason
The response may include a pause_turn stop reason, which indicates that the API paused a long-running turn. You may provide the response back as-is in a subsequent request to let Claude continue its turn, or modify the content if you wish to interrupt the conversation.

Containers
The code execution tool runs in a secure, containerized environment designed specifically for code execution, with a higher focus on Python.

Runtime environment
Python version: 3.11.12
Operating system: Linux-based container
Architecture: x86_64 (AMD64)
Resource limits
Memory: 5GiB RAM
Disk space: 5GiB workspace storage
CPU: 1 CPU
Networking and security
Internet access: Completely disabled for security
External connections: No outbound network requests permitted
Sandbox isolation: Full isolation from host system and other containers
File access: Limited to workspace directory only
Workspace scoping: Like Files, containers are scoped to the workspace of the API key
Expiration: Containers expire 30 days after creation
Pre-installed libraries
The sandboxed Python environment includes these commonly used libraries:

Data Science: pandas, numpy, scipy, scikit-learn, statsmodels
Visualization: matplotlib, seaborn
File Processing: pyarrow, openpyxl, xlsxwriter, xlrd, pillow, python-pptx, python-docx, pypdf, pdfplumber, pypdfium2, pdf2image, pdfkit, tabula-py, reportlab[pycairo], Img2pdf
Math & Computing: sympy, mpmath
Utilities: tqdm, python-dateutil, pytz, joblib, unzip, unrar, 7zip, bc, rg (ripgrep), fd, sqlite
Container reuse
You can reuse an existing container across multiple API requests by providing the container ID from a previous response. This allows you to maintain created files between requests.

Example
Shell
# First request: Create a file with a random number
curl https://api.anthropic.com/v1/messages \
    --header "x-api-key: $ANTHROPIC_API_KEY" \
    --header "anthropic-version: 2023-06-01" \
    --header "content-type: application/json" \
    --data '{
        "model": "claude-opus-4-6",
        "max_tokens": 4096,
        "messages": [{
            "role": "user",
            "content": "Write a file with a random number and save it to \"/tmp/number.txt\""
        }],
        "tools": [{
            "type": "code_execution_20250825",
            "name": "code_execution"
        }]
    }' > response1.json

# Extract container ID from the response (using jq)
CONTAINER_ID=$(jq -r '.container.id' response1.json)

# Second request: Reuse the container to read the file
curl https://api.anthropic.com/v1/messages \
    --header "x-api-key: $ANTHROPIC_API_KEY" \
    --header "anthropic-version: 2023-06-01" \
    --header "content-type: application/json" \
    --data '{
        "container": "'$CONTAINER_ID'",
        "model": "claude-opus-4-6",
        "max_tokens": 4096,
        "messages": [{
            "role": "user",
            "content": "Read the number from \"/tmp/number.txt\" and calculate its square"
        }],
        "tools": [{
            "type": "code_execution_20250825",
            "name": "code_execution"
        }]
    }'
Streaming
With streaming enabled, you'll receive code execution events as they occur:

event: content_block_start
data: {"type": "content_block_start", "index": 1, "content_block": {"type": "server_tool_use", "id": "srvtoolu_xyz789", "name": "code_execution"}}

// Code execution streamed
event: content_block_delta
data: {"type": "content_block_delta", "index": 1, "delta": {"type": "input_json_delta", "partial_json": "{\"code\":\"import pandas as pd\\ndf = pd.read_csv('data.csv')\\nprint(df.head())\"}"}}

// Pause while code executes

// Execution results streamed
event: content_block_start
data: {"type": "content_block_start", "index": 2, "content_block": {"type": "code_execution_tool_result", "tool_use_id": "srvtoolu_xyz789", "content": {"stdout": "   A  B  C\n0  1  2  3\n1  4  5  6", "stderr": ""}}}
Batch requests
You can include the code execution tool in the Messages Batches API. Code execution tool calls through the Messages Batches API are priced the same as those in regular Messages API requests.

Usage and pricing
Code execution is free when used with web search or web fetch. When web_search_20260209 or web_fetch_20260209 is included in your API request, there are no additional charges for code execution tool calls beyond the standard input and output token costs.

When used without these tools, code execution is billed by execution time, tracked separately from token usage:

Execution time has a minimum of 5 minutes
Each organization receives 1,550 free hours of usage per month
Additional usage beyond 1,550 hours is billed at $0.05 per hour, per container
If files are included in the request, execution time is billed even if the tool is not invoked, due to files being preloaded onto the container
Code execution usage is tracked in the response:

