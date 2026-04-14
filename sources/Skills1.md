Using Agent Skills with the API

Copy page

Learn how to use Agent Skills to extend Claude's capabilities through the API.
Agent Skills extend Claude's capabilities through organized folders of instructions, scripts, and resources. This guide shows you how to use both pre-built and custom Skills with the Claude API.

For complete API reference including request/response schemas and all parameters, see:

Skill Management API Reference - CRUD operations for Skills
Skill Versions API Reference - Version management
This feature is not eligible for Zero Data Retention (ZDR). Data is retained according to the feature's standard retention policy.
Quick Links
Get started with Agent Skills
Create your first Skill
Create Custom Skills
Best practices for authoring Skills
Overview
For a deep dive into the architecture and real-world applications of Agent Skills, read the engineering blog post: Equipping agents for the real world with Agent Skills.
Skills integrate with the Messages API through the code execution tool. Whether using pre-built Skills managed by Anthropic or custom Skills you've uploaded, the integration shape is identical: both require code execution and use the same container structure.

Using Skills
Skills integrate identically in the Messages API regardless of source. You specify Skills in the container parameter with a skill_id, type, and optional version, and they execute in the code execution environment.

You can use Skills from two sources:

Aspect	Anthropic Skills	Custom Skills
Type value	anthropic	custom
Skill IDs	Short names: pptx, xlsx, docx, pdf	Generated: skill_01AbCdEfGhIjKlMnOpQrStUv
Version format	Date-based: 20251013 or latest	Epoch timestamp: 1759178010641129 or latest
Management	Pre-built and maintained by Anthropic	Upload and manage via Skills API
Availability	Available to all users	Private to your workspace
Both skill sources are returned by the List Skills endpoint (use the source parameter to filter). The integration shape and execution environment are identical. The only difference is where the Skills come from and how they're managed.

Prerequisites
To use Skills, you need:

Claude API key from the Console
Beta headers:
code-execution-2025-08-25 - Enables code execution (required for Skills)
skills-2025-10-02 - Enables Skills API
files-api-2025-04-14 - For uploading/downloading files to/from container
Code execution tool enabled in your requests
Using Skills in Messages
Container Parameter
Skills are specified using the container parameter in the Messages API. You can include up to 8 Skills per request.

The structure is identical for both Anthropic and custom Skills. Specify the required type and skill_id, and optionally include version to pin to a specific version:

Shell
curl https://api.anthropic.com/v1/messages \
  -H "x-api-key: $ANTHROPIC_API_KEY" \
  -H "anthropic-version: 2023-06-01" \
  -H "anthropic-beta: code-execution-2025-08-25,skills-2025-10-02" \
  -H "content-type: application/json" \
  -d '{
    "model": "claude-opus-4-6",
    "max_tokens": 4096,
    "container": {
      "skills": [
        {
          "type": "anthropic",
          "skill_id": "pptx",
          "version": "latest"
        }
      ]
    },
    "messages": [{
      "role": "user",
      "content": "Create a presentation about renewable energy"
    }],
    "tools": [{
      "type": "code_execution_20250825",
      "name": "code_execution"
    }]
  }'
Downloading Generated Files
When Skills create documents (Excel, PowerPoint, PDF, Word), they return file_id attributes in the response. You must use the Files API to download these files.

How it works:

Skills create files during code execution
Response includes file_id for each created file
Use Files API to download the actual file content
Save locally or process as needed
Example: Creating and downloading an Excel file

