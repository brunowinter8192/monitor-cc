Listing Skills
Retrieve all Skills available to your workspace, including both Anthropic pre-built Skills and your custom Skills. Use the source parameter to filter by skill type:

CLI
# List all Skills
ant beta:skills list

# List only custom Skills
ant beta:skills list --source custom
See the List Skills API reference for pagination and filtering options.

Retrieving a Skill
Get details about a specific Skill:

CLI
ant beta:skills retrieve \
  --skill-id skill_01AbCdEfGhIjKlMnOpQrStUv
Deleting a Skill
To delete a Skill, you must first delete all its versions:

CLI
# Step 1: Delete all versions
ant beta:skills:versions list \
  --skill-id skill_01AbCdEfGhIjKlMnOpQrStUv \
  --transform version --format yaml \
  | tr -d '"' \
  | while read -r VERSION; do
      ant beta:skills:versions delete \
        --skill-id skill_01AbCdEfGhIjKlMnOpQrStUv \
        --version "$VERSION" >/dev/null
    done

# Step 2: Delete the Skill
ant beta:skills delete \
  --skill-id skill_01AbCdEfGhIjKlMnOpQrStUv >/dev/null
Attempting to delete a Skill with existing versions returns a 400 error.

Versioning
Skills support versioning to manage updates safely:

Anthropic-Managed Skills:

Versions use date format: 20251013
New versions released as updates are made
Specify exact versions for stability
Custom Skills:

Auto-generated epoch timestamps: 1759178010641129
Use "latest" to always get the most recent version
Create new versions when updating Skill files
CLI
# Create a new version
VERSION_NUMBER=$(ant beta:skills:versions create \
  --skill-id skill_01AbCdEfGhIjKlMnOpQrStUv \
  --file updated_skill/SKILL.md \
  --transform version --format yaml)

# Use specific version
ant beta:messages create \
  --beta code-execution-2025-08-25 \
  --beta skills-2025-10-02 <<YAML
model: claude-opus-4-6
max_tokens: 4096
container:
  skills:
    - type: custom
      skill_id: skill_01AbCdEfGhIjKlMnOpQrStUv
      version: $VERSION_NUMBER
messages:
  - role: user
    content: Use updated Skill
tools:
  - type: code_execution_20250825
    name: code_execution
YAML

# Use latest version
ant beta:messages create \
  --beta code-execution-2025-08-25 \
  --beta skills-2025-10-02 <<'YAML'
model: claude-opus-4-6
max_tokens: 4096
container:
  skills:
    - type: custom
      skill_id: skill_01AbCdEfGhIjKlMnOpQrStUv
      version: latest
messages:
  - role: user
    content: Use latest Skill version
tools:
  - type: code_execution_20250825
    name: code_execution
YAML
See the Create Skill Version API reference for complete details.

How Skills Are Loaded
When you specify Skills in a container:

Metadata Discovery: Claude sees metadata for each Skill (name, description) in the system prompt
File Loading: Skill files are copied into the container at /skills/{directory}/
Automatic Use: Claude automatically loads and uses Skills when relevant to your request
Composition: Multiple Skills compose together for complex workflows
The progressive disclosure architecture ensures efficient context usage: Claude only loads full Skill instructions when needed.

Use Cases
Organizational Skills
Brand & Communications

Apply company-specific formatting (colors, fonts, layouts) to documents
Generate communications following organizational templates
Ensure consistent brand guidelines across all outputs
Project Management

Structure notes with company-specific formats (OKRs, decision logs)
Generate tasks following team conventions
Create standardized meeting recaps and status updates
Business Operations

Create company-standard reports, proposals, and analyses
Execute company-specific analytical procedures
Generate financial models following organizational templates
Personal Skills
Content Creation

