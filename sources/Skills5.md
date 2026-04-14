Custom document templates
Specialized formatting and styling
Domain-specific content generation
Data Analysis

Custom data processing pipelines
Specialized visualization templates
Industry-specific analytical methods
Development & Automation

Code generation templates
Testing frameworks
Deployment workflows
Example: Financial Modeling
Combine Excel and custom DCF analysis Skills:

Shell
# Create custom DCF analysis Skill
DCF_SKILL=$(curl -X POST "https://api.anthropic.com/v1/skills" \
  -H "x-api-key: $ANTHROPIC_API_KEY" \
  -H "anthropic-version: 2023-06-01" \
  -H "anthropic-beta: skills-2025-10-02" \
  -F "display_title=DCF Analysis" \
  -F "files[]=@dcf_skill/SKILL.md;filename=dcf_skill/SKILL.md")

DCF_SKILL_ID=$(echo "$DCF_SKILL" | jq -r '.id')

# Use with Excel to create financial model
curl https://api.anthropic.com/v1/messages \
  -H "x-api-key: $ANTHROPIC_API_KEY" \
  -H "anthropic-version: 2023-06-01" \
  -H "anthropic-beta: code-execution-2025-08-25,skills-2025-10-02" \
  -H "content-type: application/json" \
  -d "{
    \"model\": \"claude-opus-4-6\",
    \"max_tokens\": 4096,
    \"container\": {
      \"skills\": [
        {
          \"type\": \"anthropic\",
          \"skill_id\": \"xlsx\",
          \"version\": \"latest\"
        },
        {
          \"type\": \"custom\",
          \"skill_id\": \"$DCF_SKILL_ID\",
          \"version\": \"latest\"
        }
      ]
    },
    \"messages\": [{
      \"role\": \"user\",
      \"content\": \"Build a DCF valuation model for a SaaS company with the attached financials\"
    }],
    \"tools\": [{
      \"type\": \"code_execution_20250825\",
      \"name\": \"code_execution\"
    }]
  }"
Limits and Constraints
Request Limits
Maximum Skills per request: 8
Maximum Skill upload size: 30 MB (all files combined)
YAML frontmatter requirements:
name: Maximum 64 characters, lowercase letters/numbers/hyphens only, no XML tags, no reserved words
description: Maximum 1024 characters, non-empty, no XML tags
Environment Constraints
Skills run in the code execution container with these limitations:

No network access - Cannot make external API calls
No runtime package installation - Only pre-installed packages available
Isolated environment - Each request gets a fresh container
See the code execution tool documentation for available packages.

Best Practices
When to Use Multiple Skills
Combine Skills when tasks involve multiple document types or domains:

Good use cases:

Data analysis (Excel) + presentation creation (PowerPoint)
Report generation (Word) + export to PDF
Custom domain logic + document generation
Avoid:

Including unused Skills (impacts performance)
Version Management Strategy
For production:

# Pin to specific versions for stability
container = {
    "skills": [
        {
            "type": "custom",
            "skill_id": "skill_01AbCdEfGhIjKlMnOpQrStUv",
            "version": "1759178010641129",  # Specific version
        }
    ]
}
For development:

# Use latest for active development
container = {
    "skills": [
        {
            "type": "custom",
            "skill_id": "skill_01AbCdEfGhIjKlMnOpQrStUv",
            "version": "latest",  # Always get newest
        }
    ]
}
Prompt Caching Considerations
When using prompt caching, note that changing the Skills list in your container breaks the cache:

Shell
# First request creates cache
curl https://api.anthropic.com/v1/messages \
  -H "x-api-key: $ANTHROPIC_API_KEY" \
  -H "anthropic-version: 2023-06-01" \
  -H "anthropic-beta: code-execution-2025-08-25,skills-2025-10-02,prompt-caching-2024-07-31" \
  -H "content-type: application/json" \
  -d '{
    "model": "claude-opus-4-6",
    "max_tokens": 4096,
    "container": {
      "skills": [
        {"type": "anthropic", "skill_id": "xlsx", "version": "latest"}
      ]
    },
    "messages": [{"role": "user", "content": "Analyze sales data"}],
    "tools": [{"type": "code_execution_20250825", "name": "code_execution"}]
  }'
