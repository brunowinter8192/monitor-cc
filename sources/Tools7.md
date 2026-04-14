# First, upload a file
curl https://api.anthropic.com/v1/files \
    --header "x-api-key: $ANTHROPIC_API_KEY" \
    --header "anthropic-version: 2023-06-01" \
    --header "anthropic-beta: files-api-2025-04-14" \
    --form 'file=@"data.csv"' \

# Then use the file_id with code execution
curl https://api.anthropic.com/v1/messages \
    --header "x-api-key: $ANTHROPIC_API_KEY" \
    --header "anthropic-version: 2023-06-01" \
    --header "anthropic-beta: files-api-2025-04-14" \
    --header "content-type: application/json" \
    --data '{
        "model": "claude-opus-4-6",
        "max_tokens": 4096,
        "messages": [{
            "role": "user",
            "content": [
                {"type": "text", "text": "Analyze this CSV data"},
                {"type": "container_upload", "file_id": "file_abc123"}
            ]
        }],
        "tools": [{
            "type": "code_execution_20250825",
            "name": "code_execution"
        }]
    }'
Retrieve generated files
When Claude creates files during code execution, you can retrieve these files using the Files API:

CLI
# Request code execution that creates files; extract file_ids from tool results
TOOL_RESULT='content.#(type=="bash_code_execution_tool_result")#'
FILE_IDS=$(ant beta:messages create \
  --beta files-api-2025-04-14 \
  --transform "${TOOL_RESULT}.content.content|@flatten|#.file_id" \
  --format yaml \
    --model claude-opus-4-6 \
    --max-tokens 4096 \
    --message '{role: user, content: Create a matplotlib visualization and save it as output.png}' \
    --tool '{type: code_execution_20250825, name: code_execution}'
)

# Download each created file
while IFS= read -r LINE; do
  [[ "$LINE" != "- "* ]] && continue
  FILE_ID="${LINE#- }"
  FILENAME=$(ant beta:files retrieve-metadata \
    --file-id "$FILE_ID" \
    --transform filename --format yaml)
  ant beta:files download \
    --file-id "$FILE_ID" \
    --output "$FILENAME" > /dev/null
  printf 'Downloaded: %s\n' "$FILENAME"
done <<< "$FILE_IDS"
Tool definition
The code execution tool requires no additional parameters:

JSON
{
  "type": "code_execution_20250825",
  "name": "code_execution"
}
When this tool is provided, Claude automatically gains access to two sub-tools:

bash_code_execution: Run shell commands
text_editor_code_execution: View, create, and edit files, including writing code
Response format
The code execution tool can return two types of results depending on the operation:

Bash command response
Output
{
  "type": "server_tool_use",
  "id": "srvtoolu_01B3C4D5E6F7G8H9I0J1K2L3",
  "name": "bash_code_execution",
  "input": {
    "command": "ls -la | head -5"
  }
},
{
  "type": "bash_code_execution_tool_result",
  "tool_use_id": "srvtoolu_01B3C4D5E6F7G8H9I0J1K2L3",
  "content": {
    "type": "bash_code_execution_result",
    "stdout": "total 24\ndrwxr-xr-x 2 user user 4096 Jan 1 12:00 .\ndrwxr-xr-x 3 user user 4096 Jan 1 11:00 ..\n-rw-r--r-- 1 user user  220 Jan 1 12:00 data.csv\n-rw-r--r-- 1 user user  180 Jan 1 12:00 config.json",
    "stderr": "",
    "return_code": 0
  }
}
File operation responses
View file:
