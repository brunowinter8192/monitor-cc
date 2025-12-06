---
description: Systematic debugging with context gathering, interactive root cause analysis, and user-guided implementation
argument-hint: [observation/error-description]
---

## Problem Observation

User observes: $ARGUMENTS

---

## Step Indicator Rule

**MANDATORY:** Every response in this workflow MUST start with:
`Phase X, Step X/6: [Step-Name]`

---

## Phase 1: Mandatory Clarification + Context Gathering (5 Steps)

### Step 1/6: Mandatory Clarification (FIRST)

**CRITICAL:** BEFORE you analyze anything, make sure the problem itself is 100% clear. (what does the user see and what is bothering him)

**Analyze User Observation for ambiguities:**
- Is it clear WHERE the problem occurs? (Which pane, which output, which mode?)
- Is it clear WHAT exactly the symptom is? (Exact error message, behavior?)
- Is it clear WHEN it occurs? (Always, sometimes, during which tool calls?)

**For EVERY ambiguity: IMMEDIATELY `AskUserQuestion` Multiple Choice:**
- Ask 1 one question at a time
- Examples:
  - "Where exactly do you see the problem?" - Options: Left Pane / Right Pane / Both / UI Mode
  - "What type of content is affected?" - Options: Tool Input / Tool Output / Both / Warnings
  - "Does this always occur?" - Options: Yes, always / Only with specific tools / Only with large outputs

**Only when 100% crystal clear, proceed to Step 2/6: Context Gathering**

### Step 2/6: Context Gathering - Sequential Workflow

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
Prepare: Complete context for Phase 2/3 analysis

**OUTPUT:** Complete context package ready for Phase 2 (Source Research) or Phase 3 (Root Cause)

---

## Phase 2: Source Code Research (Step 3/6)

**MANDATORY for this project.** tmux source is cloned in `repo/`.

**RULE: NEVER guess tmux syntax. Always verify in source.**

### 3.1 Check tmux Source

Bug involves tmux/keybindings/escape sequences? Search `repo/`:

```bash
# Key bindings syntax
grep -r "pattern" repo/key-bindings.c repo/key-string.c

# Config examples
grep -r "pattern" repo/regress/conf/

# Test cases
grep -r "pattern" repo/regress/*.sh
```

**Key files:**
- `key-string.c` - Valid key names (C-, M-, F1-F12, etc.)
- `key-bindings.c` - Default bindings and syntax
- `regress/conf/*.conf` - Real-world usage examples

### 3.2 Document Findings (concise)

```
TMUX SOURCE CHECK
- Verified: [what works]
- Invalid: [what doesn't work + why]
- Source: [file:line]
```

### 3.3 Skip Only If

Pure Python logic bug with no tmux/terminal interaction.

---

## Phase 3: Root Cause Analysis (Step 4/6)

Based on context from Phase 1 (and Phase 2 if applicable), perform direct analysis:

### Step 4/6: Code Analysis

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

**NEXT: Proceed to Phase 4 to validate assumptions before implementing.**

---

## Phase 4: Validate Hypotheses & Get User Decision (Step 5/6)

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

### Step 5/6: Identify Key Assumptions

From Phase 3 analysis, extract assumptions that need validation:
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

## Phase 5: Implementation (Step 6/6)

**Only after user confirms to proceed with the recommended solution.**

### Step 6/6: Implement Fix

Based on validated root cause analysis from Phase 3-4:
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