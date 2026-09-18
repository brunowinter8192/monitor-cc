# mcp__plugin_iterative-dev_iterative-dev__dev_sync

**Char count:** 79
**Schema char count:** 247

## Description

Sync dev branch to main without checkout. Uses git update-ref for fast-forward.

## Input Schema

```json
{
  "additionalProperties": false,
  "properties": {
    "project_path": {
      "anyOf": [
        {
          "type": "string"
        },
        {
          "type": "null"
        }
      ],
      "default": null
    }
  },
  "type": "object"
}
```
