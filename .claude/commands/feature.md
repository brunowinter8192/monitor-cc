---
description: Iterative feature implementation with exploration, planning, and approval gates
argument-hint: [feature-description]
---

## Feature Request

User wants to implement: $ARGUMENTS

---

# Workflow

## Phase 0: Clarify Feature Requirements

**CRITICAL:** Before launching any subagent, you MUST understand exactly what the user wants.

**Analyze $ARGUMENTS for ambiguities:**
- What exactly should this feature do? (Clear functionality description?)
- Where should it be used? (Which part of the workflow?)
- What are the inputs/outputs? (Data flow clear?)
- How should it interact with existing code? (Integration points?)
- Are there any constraints or requirements? (Performance, format, compatibility?)

**For EVERY ambiguity: IMMEDIATELY use `AskUserQuestion`**

Ask 1-4 multiple choice questions to clarify:

**Example questions:**

**If functionality unclear:**
```
Question: "What should this feature do exactly?"
Options:
- Process data and store results
- Display information to user
- Monitor/track changes in real-time
- Transform/convert existing data
```

**If integration unclear:**
```
Question: "Where in the workflow should this feature run?"
Options:
- At startup (before main workflow)
- During main processing (part of workflow loop)
- On-demand (user triggers manually)
- Continuously in background
```

**If scope unclear:**
```
Question: "What is the scope of this feature?"
Options:
- Minimal - Single focused function
- Moderate - Small module with 3-5 functions
- Extensive - Full module with multiple responsibilities
- Just exploring - Not sure yet, need suggestions
```

**Only when 100% crystal clear, proceed to Phase 1: Exploration**

**Why this matters:**
- Subagent will be prompted based on YOUR understanding
- Wrong understanding = wrong exploration = wrong implementation
- One question NOW saves rebuilding entire feature LATER

---

## Phase 1: Exploration

**CRITICAL:**
- Use explore-specialist to understand the codebase broadly
- Focus on finding: existing patterns, relevant modules, similar features, architectural conventions

Launch Task tool with these parameters:
- description: "explore codebase for feature context"
- subagent_type: "explore-specialist"
- model: "haiku"
- prompt: Include the feature description ($ARGUMENTS) and exploration goals

**Prompt content for explore-specialist:**

```
## Feature to Implement
$ARGUMENTS

## Exploration Goals
1. Find existing modules that handle similar functionality
2. Identify architectural patterns used in the codebase
3. Locate where this feature would logically fit (new module vs extend existing)
4. Check for relevant dependencies or cross-module interactions
5. Review CLAUDE.md and src/DOCS.md for project structure

## Output Required
- Relevant files with File:Line references
- Similar patterns already in use
- Recommended location for implementation
- Architectural considerations
```

---

## Phase 2: Location & Architecture Proposal

After receiving the exploration report:

### 2.1 Analyze Findings
Based on exploration results, determine:
- Should this be a new module in src/ or extend existing module?
- Which existing modules will be affected?
- What cross-module dependencies are needed?

### 2.2 Present Proposal to User

**Location Recommendation:**
```
IMPLEMENTATION LOCATION
=======================

Recommended Approach: [New Module | Extend Existing]

[If New Module:]
- File: src/[module_name].py
- Reason: [Why new module is justified]
- Integrates with: [List affected modules with File:Line]

[If Extend Existing:]
- File: src/[existing_module].py
- Functions to add: [List new function signatures]
- Reason: [Why extending is better than new module]

Affected Files:
- src/[file1].py:[line] - [what changes]
- src/[file2].py:[line] - [what changes]
- workflow.py:[line] - [what changes if entry point affected]
```

**Architectural Approach:**
- Follows existing patterns: [describe patterns from exploration]
- CLAUDE.md compliance: [3-section structure, logging to src/logs/, etc.]
- Cross-module interaction: [how modules will call each other]

### 2.3 Wait for User Approval

**CRITICAL:** WAIT for explicit user confirmation before proceeding.

Ask: "Should I proceed with this location and approach?"

User might want to:
- Choose different location
- Adjust architectural approach
- Ask questions about the proposal

---

## Phase 3: Source Code Research

**Only after Phase 2 approval AND when external tools/libraries are involved.**

**CRITICAL RULE: NEVER guess syntax or behavior of external tools/libraries.**

### 3.1 Identify External Dependencies

From the architecture proposal, identify:
- External CLI tools (tmux, git, docker, etc.)
- Third-party libraries with unclear APIs
- System calls or escape sequences
- Anything where documentation might be incomplete

### 3.2 Clone and Research

For each unknown external dependency:

1. **Clone official repository:**
   ```bash
   git clone https://github.com/[org]/[repo] /path/to/project/repo
   ```

2. **Ensure repo/ is in .gitignore:**
   ```
   # External repos (for research)
   repo/
   ```

3. **Search source code for correct syntax:**
   - Use Grep to find usage patterns
   - Read test files in `regress/`, `test/`, `examples/`
   - Check default configurations
   - Find the authoritative implementation

### 3.3 Document Findings

Present verified syntax to user:
```
SOURCE CODE RESEARCH
====================

Tool/Library: [name]
Repository: [github URL]

Verified Syntax:
- [specific syntax found in source]
- [format/protocol details]

Source References:
- [file.c:line] - [what it shows]
- [file.c:line] - [what it shows]
```

### 3.4 Skip Conditions

This phase can be SKIPPED if:
- Feature uses only Python standard library
- All APIs are well-known and documented
- No external CLI tools involved
- No escape sequences or protocols involved

**If skipping, state: "Phase 3 skipped - no external dependencies requiring source lookup"**

---

## Phase 4: Implementation Planning

**Only after Phase 3 approval (or skip).**

### 4.1 Create Detailed Implementation Plan

Break down the feature into specific tasks following CLAUDE.md structure:

```
IMPLEMENTATION PLAN
===================

[If New Module: src/[module_name].py]

INFRASTRUCTURE Section:
- Import statements: [list required imports]
- Constants: [list any constants needed]
- Logging setup:
  - Log file: src/logs/[workflow_phase].log (follow LOGS_MAP.md numbering)
  - Check LOGS_MAP.md to identify which workflow phase this module belongs to
  - If new workflow phase: Add to LOGS_MAP.md with events, tags, colors
  - If existing phase: Consider which events need logging (use existing tags)

ORCHESTRATOR Section:
- Function: [orchestrator_function_name]([parameters])
- Calls in sequence:
  1. [function_1]() - [purpose]
  2. [function_2]() - [purpose]
  3. [function_3]() - [purpose]

FUNCTIONS Section:
1. [function_1_name]([params]) -> [return_type]
   Purpose: [what it does]
   Logic: [brief description]

2. [function_2_name]([params]) -> [return_type]
   Purpose: [what it does]
   Logic: [brief description]

3. [function_3_name]([params]) -> [return_type]
   Purpose: [what it does]
   Logic: [brief description]

[If Extending Existing Module:]

Modifications to src/[existing_module].py:

INFRASTRUCTURE Updates:
- Add imports: [list new imports]
- Add constants: [list new constants]

ORCHESTRATOR Updates:
- [Modify existing orchestrator OR keep unchanged]

FUNCTIONS to Add:
[Same function breakdown as above]

---

Cross-Module Changes:
- src/[module1].py:[line] - [change description]
- workflow.py:[line] - [change description if needed]

---

CLAUDE.md Compliance Checklist:
[x] All code in src/ directory
[x] 3-section structure (INFRASTRUCTURE, ORCHESTRATOR, FUNCTIONS)
[x] No emojis in production code
[x] Logging to src/logs/[module].log instead of console prints
[x] Function header comments (1 line, WHAT not HOW)
[x] No inline comments inside function bodies
[x] Cross-module imports with comments: "# From [module].py: [purpose]"
```

### 4.2 Wait for User Approval

**CRITICAL:** WAIT for explicit user confirmation before implementing.

Present the plan and ask: "Should I implement this feature according to the plan?"

User might want to:
- Adjust function breakdown
- Change implementation details
- Add/remove functionality
- Modify cross-module interactions

---

## Phase 5: Implementation

**Only after Phase 4 approval.**

### 5.1 Execute Implementation

Follow the approved plan step-by-step:

1. **Create/Modify Module File(s)**
   - Write INFRASTRUCTURE section first
   - Write ORCHESTRATOR section (calls only, no logic)
   - Write FUNCTIONS section (ordered by call sequence)
   - Include function header comments (1 line each)
   - Add cross-module import comments where needed

2. **Update Cross-Module Dependencies**
   - Modify affected files (orchestrators that need to call new functions)
   - Add imports with proper comments
   - Update workflow.py if entry point affected

3. **Create Debug/Test Script**
   - File: src/debug/test_[feature_name].py
   - Include test cases from plan
   - Use emojis allowed in debug scripts

4. **Test the Implementation**
   - Run debug script to verify functionality
   - Check that feature works as expected
   - Fix any issues found

### 5.2 Report Implementation Status

After implementation:

IMPLEMENTATION COMPLETE
=======================

Files Created/Modified:
[x] src/[new_module].py - [brief description]
[x] src/[changed_module].py:[lines] - [what changed]

---

**IMPORTANT NOTES:**

1. **Approval Gates:** This command has up to 4 approval gates:
   - After Phase 2 (location/architecture)
   - After Phase 3 (source code research) - if applicable
   - After Phase 4 (implementation plan)
   - After Phase 5 (implementation complete)

2. **Iterative Process:** User can request changes at any approval gate. Be flexible.

3. **CLAUDE.md Compliance:** Every implementation MUST follow project standards strictly.

4. **Cross-Module Awareness:** Always consider how new feature integrates with existing modules.

5. **Documentation Sync:** Keep DOCS.md in sync with code changes immediately.
