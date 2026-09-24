# INFRASTRUCTURE
from typing import List

# FUNCTIONS

def get_message_content(message: dict) -> List[dict]:
    content = message.get('message', {}).get('content', [])
    if isinstance(content, list):
        return content
    return []

def is_tool_use(block: dict) -> bool:
    return block.get('type') == 'tool_use'
