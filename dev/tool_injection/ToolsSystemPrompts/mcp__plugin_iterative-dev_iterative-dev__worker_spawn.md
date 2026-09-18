# mcp__plugin_iterative-dev_iterative-dev__worker_spawn

**Char count:** 46
**Schema char count:** 497

## Description

Spawn worker with optional worktree isolation.

## Input Schema

```json
{
  "additionalProperties": false,
  "properties": {
    "name": {
      "type": "string"
    },
    "prompt_file": {
      "type": "string"
    },
    "project_path": {
      "type": "string"
    },
    "model": {
      "default": "sonnet",
      "enum": [
        "sonnet",
        "opus"
      ],
      "type": "string"
    },
    "worktree": {
      "default": true,
      "type": "boolean"
    }
  },
  "required": [
    "name",
    "prompt_file",
    "project_path"
  ],
  "type": "object"
}
```
