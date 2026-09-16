# INFRASTRUCTURE

_LAUNCH_ACK = (
    "Command running in background with ID: bg_01ABC. "
    "Output is being written to: /tmp/output_01ABC.txt. "
    "You will be notified when it completes. "
    "To check interim output, use Read on that file path."
)

_EXPECTED_REPLACEMENT = (
    "Command is running in the background. Do NOT check, poll, or read its output — "
    "just wait until it finishes (you will get a completion notice).\n"
    "Output: /tmp/output_01ABC.txt\n"
    "ID: bg_01ABC\n"
)

_COMPLETION_NOTIF = 'Background command "sleep 30" failed with exit code 143'

_FP_LARGE = (
    "RAG search results (hybrid, 5 hits):\n\n"
    "[1] decisions/strip_bg_launch_ack.md (score 0.92)\n"
    "    The strip was added because every CC 2.1.176 session emitted a\n"
    "    'Command running in background with ID: <id>' ack immediately\n"
    "    after bash tool invocations. These acks polluted the context window.\n\n"
    "[2] src/proxy/strip_bg_launch_ack.py (score 0.88)\n"
    "    Marker constant: 'running in background with ID'. Anchored prefix:\n"
    "    'Command running in background with ID:'. The strip ONLY fires\n"
    "    when text.lstrip().startswith(prefix), not substring-anywhere.\n\n"
    "[3] dev/proxy_176_bg_launch_ack_tests.py (score 0.85)\n"
    "    Unit suite. Tests: tool_result string, text block, list content,\n"
    "    str message, non-matching, completion notification, assistant.\n\n"
    "Query: 'running in background with ID strip anchored prefix fix'\n"
    "Collection: monitor-cc-docs | Mode: hybrid | k=5\n"
)

_FP_USER_STR = (
    "I pasted this output from the terminal:\n"
    "  running in background with ID: bxab0pzvo. Output is being written to ...\n"
    "Does the proxy strip this? I want it preserved."
)

_FP_TEXT_BLOCK_TEXT = (
    "The following phrase appears in the decision file:\n"
    "'Command running in background with ID: <id>' — this is the ack prefix.\n"
    "It is quoted here for documentation purposes."
)

_FP_LIST_SUB_TEXT = (
    "Tool output (read file dev/proxy_176_bg_launch_ack_tests.py):\n"
    "Line 28: _LAUNCH_ACK = 'Command running in background with ID: bg_01ABC. '\n"
    "Line 33-35: fixture for completion notification.\n"
)

_LAUNCH_ACK_W2 = (
    "Command was manually backgrounded by user with ID: bsxpatpam. "
    "Output is being written to: /tmp/output_w2.txt"
)

_EXPECTED_REPLACEMENT_W2 = (
    "Command is running in the background. Do NOT check, poll, or read its output — "
    "just wait until it finishes (you will get a completion notice).\n"
    "Output: /tmp/output_w2.txt\n"
    "ID: bsxpatpam\n"
)

_FP_W2_MID_CONTENT = (
    "RAG search results (hybrid, 3 hits):\n\n"
    "[1] decisions/strip_bg_launch_ack.md (score 0.90)\n"
    "    Wording 2 marker: 'backgrounded by user with ID'. Anchored prefix:\n"
    "    'Command was manually backgrounded by user with ID:'. Fires only when\n"
    "    text.lstrip().startswith(prefix), not substring-anywhere.\n\n"
    "[2] Example quoted transcript:\n"
    "    'Command was manually backgrounded by user with ID: bxab0pzvo. Output is being written to ...'\n"
    "    — pasted here for documentation purposes, must not be replaced.\n"
)


_LAUNCH_ACK_W3 = (
    "Command did not complete within its 120s timeout and was moved to the background (ID: "
    "b1mahby4a). Output is being written to: /private/tmp/claude-501/"
    "-Users-brunowinter2000-Documents-ai-monitor-cc/d7b0d213-0c28-4e53-baf8-c11fa7838f0b/"
    "tasks/b1mahby4a.output. You will be notified when it completes. To check interim output, "
    "use Read on that file path.\n"
    "Session cwd remains /Users/brunowinter2000/Documents/ai/monitor-cc; directory changes made "
    "by the backgrounded command do not apply to subsequent commands."
)

_EXPECTED_REPLACEMENT_W3 = (
    "Command exceeded its timeout and was moved to the background. Do NOT check, poll, or read "
    "its output — just wait until it finishes (you will get a completion notice).\n"
    "Output: /private/tmp/claude-501/-Users-brunowinter2000-Documents-ai-monitor-cc/"
    "d7b0d213-0c28-4e53-baf8-c11fa7838f0b/tasks/b1mahby4a.output\n"
    "ID: b1mahby4a\n"
)

_FP_W3_MID_CONTENT = (
    "RAG search results (hybrid, 3 hits):\n\n"
    "[1] decisions/strip_bg_launch_ack.md (score 0.91)\n"
    "    Wording 3 marker: 'moved to the background (ID'. Anchored prefix:\n"
    "    'Command did not complete within its'. Fires only when\n"
    "    text.lstrip().startswith(prefix), not substring-anywhere.\n\n"
    "[2] Example quoted transcript:\n"
    "    'Command did not complete within its 60s timeout and was moved to the background "
    "(ID: bxab0pzvo). Output is being written to ...'\n"
    "    — pasted here for documentation purposes, must not be replaced.\n"
)
