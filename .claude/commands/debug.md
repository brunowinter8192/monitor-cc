---
description: Systematic debugging with context gathering, interactive root cause analysis, and user-guided implementation
argument-hint: [observation/error-description]
---

## Problem Observation

User observes: $ARGUMENTS

---

## Step Indicator Rule

**MANDATORY:** Every response in this workflow MUST start with:
`Super. Step X/5: [Step-Name]`

Steps:
- Step 0/5: Bug vs Feature Detection
- Step 1/5: Mandatory Clarification
- Step 2/5: Context Gathering
- Step 3/5: Root Cause Analysis
- Step 4/5: Validate Hypotheses
- Step 5/5: Implementation

---

## Phase 0: Bug vs Feature Detection (Step 0/5 - MANDATORY FIRST STEP)

**CRITICAL:** Before ANY analysis, determine if this is a BUG or a FEATURE REQUEST.

**Definition:**
- **BUG:** Something that WORKED BEFORE and is now BROKEN, or something that SHOULD work but DOESN'T (error, crash, wrong output, unexpected behavior)
- **FEATURE REQUEST:** Something that NEVER EXISTED, a NEW capability, an ENHANCEMENT, or a CONFIGURATION change

**Detection Questions:**
1. Does user describe something that is BROKEN or MISSING?
2. Is there an ERROR message, CRASH, or WRONG OUTPUT?
3. Did this WORK BEFORE and stopped working?

**MANDATORY:** Use AskUserQuestion to confirm:

```
Question: "Is this a bug (something broken) or a feature request (something new)?"
Options:
- Bug: Something is broken/not working as expected
- Feature: I want new functionality that doesn't exist yet
- Enhancement: Existing feature needs improvement
- Not sure: Need help determining
```

**IF FEATURE/ENHANCEMENT:**
STOP this workflow immediately. Respond:
"This appears to be a feature request, not a bug. The /debug workflow is for fixing broken code.
For new features, please use: /feature [description]
For enhancements, describe what you want to improve and I'll help implement it directly."

**IF BUG:** Proceed to Phase 1.

---

## Phase 1: Mandatory Clarification + Context Gathering (5 Steps)

### Step 1/5: Mandatory Clarification (FIRST)

**CRITICAL:** BEFORE you analyze anything, make sure the problem itself is 100% clear. (what does the user see and what is bothering him)

**Analyze User Observation for ambiguities:**
- Is it clear WHERE the problem occurs? (Which pane, which output, which mode?)
- Is it clear WHAT exactly the symptom is? (Exact error message, behavior?)
- Is it clear WHEN it occurs? (Always, sometimes, during which tool calls?)

**For EVERY ambiguity: IMMEDIATELY `AskUserQuestion` Multiple Choice:**
- Ask 1-4 questions simultaneously
- Examples:
  - "Where exactly do you see the problem?" - Options: Left Pane / Right Pane / Both / UI Mode
  - "What type of content is affected?" - Options: Tool Input / Tool Output / Both / Warnings
  - "Does this always occur?" - Options: Yes, always / Only with specific tools / Only with large outputs

**Only when 100% crystal clear, proceed to Step 2/5: Context Gathering**

### Step 2/5: Context Gathering - Sequential Workflow

**CRITICAL:** Follow this workflow step-by-step. Each step builds on the previous.

**WORKFLOW:**

**Step 2.1: Identify Affected Modules**
Based on user observation, determine which modules are involved

THEN

**Step 2.2: Check Historical Context**
Review bug_fixes/ and not_working/ in root
Look for: similar issues, previous fixes, failed attempts
WHY: Issue may have reappeared or similar fix already tried

THEN

**Step 2.3: Find Relevant Files (max 3-4, focused)**
Use Glob/Grep to locate affected code in src/
Focus on modules identified in Step 2.1

THEN

**Step 2.4: Read LOGS_MAP.md - Match Problem to Workflow Phases**

LOGS_MAP.md contains 83 events across 9 workflow phases

YOUR TASK: Match user's problem to workflow phases
EXTRACT: Relevant log files, primary modules, key tags

EXAMPLE MAPPING:
- Startup/Init: 01_startup.log, 02_initialization.log
- Session discovery: 03_session_discovery.log
- JSONL parsing: 04_file_reading.log, 05_jsonl_parsing.log
- Tool extraction: 06_tool_extraction.log
- Display/routing: 07_display_routing.log
- UI rendering: 08_ui_rendering.log
- Mouse clicks: 09_click_handling.log

WHY: Logs capture runtime errors, state transitions, timing issues
WHEN: ALWAYS for runtime failures, intermittent bugs, state issues

THEN

**Step 2.5: Check Log Files in src/logs/**
Read identified log files for runtime evidence
Look for: error sequences, state transitions, timing patterns

THEN

**Step 2.6: Inspect Raw Data Sources (IF parsing/processing fails)**

WHY: Logs show WHAT happened, raw data shows WHAT WAS PROCESSED
WHEN: If logs show parsing errors, extraction failures, format mismatches, missing data
HOW: Use bash commands to inspect actual data structure

EXAMPLE PATTERNS:
```bash
# Inspect JSONL structure
tail -20 <session.jsonl> | python3 -c "import sys,json; ..."

# Check content block types
tail -1 <file.jsonl> | python3 -c "import sys,json; ..."

# Verify expected data presence
tail -50 <file> | grep -E "expected_pattern" | head -10

# Check CSV/data file structure
head -10 <data.csv> | python3 -c "import sys,csv; ..."
```

CRITICAL: Do this BEFORE analysis for accurate data context

THEN

**Step 2.7: Gather All Evidence**
Collect: Error messages, stack traces, File:Line references
Include: Raw data inspection findings from Step 2.6
Prepare: Complete context for Phase 2 Root Cause Analysis

**OUTPUT:** Complete context package ready for Phase 2 analysis

---

## External Tool/Library Source Code Lookup

**CRITICAL RULE: NEVER guess syntax or behavior of external tools/libraries.**

**WHEN to use:**
- Unknown syntax for external tools (tmux, git, docker, etc.)
- Unclear API behavior of libraries
- Documentation is ambiguous or incomplete
- Multiple syntax options and unsure which is correct

**HOW to do it:**
1. Clone the official repository to `repo/` folder:
   ```bash
   git clone https://github.com/[org]/[repo] /path/to/project/repo
   ```

2. Add `repo/` to `.gitignore`:
   ```
   # External repos (for research)
   repo/
   ```

3. Search the source code for correct syntax:
   - Use Grep to find usage patterns
   - Read test files, examples, default configurations
   - Check `regress/`, `test/`, `examples/` folders

**Example (tmux command syntax):**
```bash
# Clone tmux source
git clone https://github.com/tmux/tmux repo/

# Search for bind-key examples
grep -r "bind.*command-prompt" repo/regress/conf/

# Read key-bindings.c for default bindings
cat repo/key-bindings.c | grep -A5 "bind"
```

**WHY this matters:**
- Source code is the authoritative truth
- Documentation can be outdated or incomplete
- Guessing leads to subtle bugs that are hard to debug
- One source code lookup saves hours of trial-and-error

---

## Phase 2: Root Cause Analysis (Step 3/5)

Based on context from Phase 1, perform direct analysis:

### Step 3/5: Code Analysis

1. **Examine affected modules** identified in Phase 1
2. **Read relevant functions** with focus on File:Line references from logs/errors
3. **Trace execution flow** - follow the code path that leads to the bug
4. **Identify logic errors** - where does actual behavior diverge from expected?

### Log Evidence Correlation

1. **Check relevant log files** from LOGS_MAP.md
2. **Look for patterns:**
   - Error sequences (what happens before/after)
   - State transitions (cache updates, mode changes)
   - Timing issues (race conditions, ordering problems)
   - Data flow anomalies (missing data, format mismatches)

### Formulate Root Cause Hypothesis

Present analysis to user:

```
-----------------------------------------------------------
ROOT CAUSE ANALYSIS
-----------------------------------------------------------

WHAT IS FAILING:
[Precise description of the failure]

WHERE IT FAILS:
File: [module.py:line]
Function: [function_name]

WHY IT FAILS:
[Explanation of the logic error/bug based on code + logs]

LOG EVIDENCE:
- Workflow Phase: [e.g., 06_tool_extraction]
- Key Tags Found: [e.g., TOOL_ORPHAN, EXTRACT_STATS]
- Pattern: [What the logs reveal]

PROPOSED SOLUTION:
[High-level approach to fix - NO implementation yet]

ASSUMPTIONS TO VALIDATE:
[List key assumptions that should be confirmed with user]
```

**NEXT: Proceed to Phase 3 to validate assumptions before implementing.**

---

## Phase 3: Validate Hypotheses & Get User Decision (Step 4/5)

**CRITICAL VALIDATION STEP**

**STOP - DO NOT IMPLEMENT ANYTHING WITHOUT USER CONFIRMATION**

**WHY THIS IS CRITICAL:**
- AI can misinterpret symptoms and implement wrong fixes
- Assumptions about environment/config are often incorrect
- Simple user questions prevent hours of wasted work

**WHAT YOU MUST DO:**
1. Identify ALL assumptions in your root cause hypothesis
2. Use AskUserQuestion to validate EACH assumption
3. Wait for user confirmation before ANY code changes

**EXAMPLES OF FAILURES FROM PREMATURE IMPLEMENTATION:**
- Fixed "parsing error" but problem was actually data format
- Added caching but issue was race condition in existing cache
- Modified display logic but root cause was upstream filtering
- Implemented complex solution when simple config change sufficed

**Remember: One user question NOW saves rebuilding the fix LATER**

---

**MANDATORY:** Use AskUserQuestion tool to validate assumptions BEFORE implementation.

### Step 4/5: Identify Key Assumptions

From Phase 2 analysis, extract assumptions that need validation:
- Environmental facts (how many sessions running, what mode active)
- Timing/frequency (when does issue occur, always vs sometimes)
- Data characteristics (format, size, source)
- Configuration state (settings, flags, parameters)

### Ask Validation Questions

Use AskUserQuestion with multiple choice (2-4 options):

**Example patterns:**

**For session/process claims:**
```
Question: "How many monitor sessions are currently running?"
Options:
- Only one session
- Multiple sessions (2-3)
- Many sessions (4+)
- Not sure
```

**For timing/frequency claims:**
```
Question: "When does the problem occur?"
Options:
- Every time (100%)
- Most of the time (~75%)
- Sometimes (~50%)
- Rarely (~25%)
```

**For configuration claims:**
```
Question: "Which mode/configuration are you using?"
Options:
- Mode A (with X enabled)
- Mode B (with Y enabled)
- Default mode
- Custom configuration
```

### Check Hypothesis Against User Answers

Based on user answers:
- Check if root cause hypothesis is consistent with user's confirmed facts
- If contradictions found, revise hypothesis or investigate further
- If consistent, proceed to honest assessment

**Remember:** Consistency with facts does not equal proof. Multiple explanations can fit the same facts.

### Present Honest Assessment & Recommendation

**CRITICAL:** Root causes and solutions are rarely 100% certain. Be honest about confidence and uncertainty.

```
HONEST ASSESSMENT & RECOMMENDATION
-----------------------------------

CONFIDENCE LEVEL: [X%] - [High 80-95% / Medium 60-80% / Low 40-60%]

Why this confidence level:
[Honest explanation: What makes us confident? What creates uncertainty?]

---

VALIDATED FACTS (from user):
- [Fact 1: User confirmed X]
- [Fact 2: User confirmed Y]
- [Fact 3: User confirmed Z]

---

ROOT CAUSE (best hypothesis):
File: [module.py:line]
Issue: [What we think is wrong]
Why: [Explanation consistent with validated facts]

ALTERNATIVE EXPLANATIONS (if any):
- [Other possible cause 1 - why less likely]
- [Other possible cause 2 - why less likely]

---

RECOMMENDED SOLUTION:
[Detailed fix approach based on best hypothesis]

WHY THIS IS OUR BEST HYPOTHESIS:
1. [Reason 1 - addresses symptoms]
2. [Reason 2 - supported by log evidence]
3. [Reason 3 - consistent with validated environment]

WHAT COULD BE WRONG WITH THIS HYPOTHESIS:
- [Uncertainty 1: What we don't know]
- [Uncertainty 2: What could invalidate this]
- [Risk: What if we're wrong about X]

---

RECOMMENDED APPROACH:
[If confidence < 70%: Suggest additional investigation steps]
[If confidence >= 70%: Recommend implementation with monitoring]

-----------------------------------
USER DECISION
-----------------------------------

Proceed with recommended solution?
- Yes, implement the fix
- No, investigate further: [what to check]
- Different approach: [specify alternative]
```

**CRITICAL: WAIT for user confirmation before proceeding to implementation.**

---

## Phase 4: Implementation (Step 5/5)

**Only after user confirms to proceed with the recommended solution.**

### Step 5/5: Implement Fix

Based on validated root cause analysis from Phase 2-3:
- Apply the proposed fix to production code
- Follow the solution approach from validated recommendation
- Make changes to identified files (File:Line references from analysis)

### Commit Changes

**CRITICAL: ALWAYS commit after implementing the fix.**

---

## Next Steps: Testing & Documentation

**After implementation, user should:**

1. **Test the fix** - Run workflow, check logs, verify bug is resolved
2. **Document results** using `/document-fix` command:
   - If fix works: `/document-fix success`
   - If fix fails: `/document-fix failed`

The `/document-fix` command will create appropriate documentation in either `bug_fixes/` (success) or `not_working/` (failed) folders.

---