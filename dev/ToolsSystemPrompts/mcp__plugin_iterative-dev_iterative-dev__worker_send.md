# mcp__plugin_iterative-dev_iterative-dev__worker_send

**Char count:** 31
**Schema char count:** 385

## Description

Send message to running worker.

## Input Schema

```json
{
  "additionalProperties": false,
  "properties": {
    "name": {
      "type": "string"
    },
    "message": {
      "type": "string"
    },
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
  "required": [
    "name",
    "message"
  ],
  "type": "object"
}
```
