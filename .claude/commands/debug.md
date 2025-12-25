---
description: Systematic debugging with context gathering, interactive root cause analysis, and user-guided implementation
argument-hint: [observation/error-description]
---

## Problem Observation

User observes: $ARGUMENTS

---

## Step Indicator Rule

**MANDATORY:** Every response in this workflow MUST start with:
`Phase X, Step Y: [Name]`

Example: `Phase 1, Step 3: Find Files`

---

## Phase 1: Context Gathering

### Step 1: Clarification

**CRITICAL:** Make sure the problem is 100% clear before any analysis.

**Check for ambiguities:**
- WHERE does the problem occur? (Which pane, which output, which mode?)
- WHAT exactly is the symptom? (Exact error message, behavior?)
- WHEN does it occur? (Always, sometimes, during which tool calls?)

**For EVERY ambiguity:** Use AskUserQuestion (one question at a time)

**Only when 100% clear, proceed to Step 2**

### Step 2: Historical Context

Review `bug_fixes/` and `not_working/` in root
- Look for: similar issues, previous fixes, failed attempts
- WHY: Issue may have reappeared or similar fix already tried

### Step 3: Find Files

**Goal:** Narrow down to specific code causing the bug.

1. Use Glob/Grep to locate affected modules in `src/`
2. Read identified files, trace execution flow
3. Pinpoint the exact function(s) where behavior diverges from expected

**Output:** List of `file.py:line` references where bug likely originates

### Step 4: Check Monitor Logs

1. Read LOGS_MAP.md to identify relevant workflow phase
2. Read tail of corresponding log files in `src/logs/`
3. Note any error patterns, state transitions, or timing issues

### Step 5: Inspect Claude Code JSONL

**SINGLE SOURCE OF TRUTH:** Claude Code writes JSONL files to `~/.claude/projects/`.
These files are the only data source the monitor parses.

WHY: src/logs/ shows what the monitor DID. JSONL shows what Claude Code PRODUCED.
WHEN: Parsing errors, extraction failures, missing tool calls, format mismatches

**Location:** `~/.claude/projects/<encoded-path>/*.jsonl`

```bash
# Find active session files
ls -lt ~/.claude/projects/*/*.jsonl | head -5

# Inspect recent JSONL entries
tail -20 <session.jsonl> | python3 -c "import sys,json; [print(json.loads(l).get('type','?')) for l in sys.stdin]"

# Check tool_use/tool_result structure
tail -50 <file.jsonl> | grep -E "tool_use|tool_result" | head -10
```

### Step 6: Source Research (if tmux-related)

**Skip if:** Pure Python logic bug with no tmux/terminal interaction.

If bug involves tmux/keybindings/escape sequences, search `repo/`:

```bash
grep -r "pattern" repo/key-bindings.c repo/key-string.c
grep -r "pattern" repo/regress/conf/
```

Document findings:
```
TMUX SOURCE CHECK
- Verified: [what works]
- Invalid: [what doesn't work + why]
- Source: [file:line]
```

### PHASE 1 REPORT (MANDATORY)

```
PHASE 1 COMPLETE: Context Gathering
====================================

PROBLEM UNDERSTANDING:
[Summary of clarified problem]

HISTORICAL CONTEXT:
[Relevant bug_fixes/ or not_working/ findings, or "None found"]

AFFECTED MODULES:
[List of identified files with line references]

LOG EVIDENCE:
[Relevant log files and key findings]

CLAUDE CODE JSONL:
[Raw data inspection results, or "Not inspected (not needed)"]

TMUX SOURCE (if applicable):
[Verified syntax, invalid patterns, source references, or "Not applicable"]
```

---

**🛑 STOP** - Ask the user if he wants to proceed to Phase 2 or if he has remarks based on the summary or if there are more things to clarify
     **CRITICAL** if the user does not clearly state in his response the he wants to proceed to Phase 2, dont go. Make sure the user is satisfied with the Phase 1 results. 

---

## Phase 2: Root Cause Analysis

**Goal:** Compare IS-STATE vs SHOULD-STATE (both from Phase 1) to identify root cause.

### Step 1: Compare Behavior

- Current code behavior (IS-STATE from Phase 1)
- Expected behavior (SHOULD-STATE from Phase 1 source research)
- Where do they diverge?

### Step 2: Formulate Hypothesis

```
ROOT CAUSE
==========
File: [module.py:line]
Function: [function_name]
Issue: [What's wrong]
Why: [Logic error explanation]
```

### Step 3: Validate (if needed)

If assumptions are unclear, use AskUserQuestion to confirm key facts.

### Step 4: Present Fix Approach

```
PROPOSED FIX
============
[Concrete fix approach with file:line references]

WHY THIS WORKS
==============
[Explanation of why this solution fixes the root cause]
[Why this approach was chosen over alternatives]
```

---

**🛑 STOP** - Ask the user if he wants to proceed to Phase 3 or if he has remarks based on the summary or if there are more things to clarify
     **CRITICAL** if the user does not clearly state in his response the he wants to proceed to Phase 3, go back to Step 1 and execute again from there

---

## Phase 3: Write Plan + Exit

### Step 1: Write to System Plan File

Write fix plan to the system-provided plan file (path from Plan Mode system message).

### Step 2: Exit Plan Mode

Call ExitPlanMode

---

## Phase 4: Implementation

1. Implement the fix
2. Commit changes

---

## Phase 5: Documentation

**After user confirms fix works:**

### Step 1: Failure Analysis (ONLY for failed fixes)

Use AskUserQuestion with 4 multiple choice questions:

1. **What happened when you tested?**
   - Same problem persists
   - Problem got worse
   - Partially fixed
   - Different problem now

2. **Specific symptoms:**
   - Nothing displays/renders
   - Error messages or crashes
   - Works but with side effects
   - Same symptoms as before

3. **Compared to BEFORE fix:**
   - Exactly the same
   - Worse (regression)
   - Slightly better but broken
   - Different symptoms

4. **Side effects observed?**
   - Critical (blocks other functionality)
   - Minor (cosmetic/performance)
   - None observed
   - Not tested yet

### Step 2: Generate Documentation

**For SUCCESS:** `bug_fixes/[name]_YYYYMMDD_HHMMSS.md`

```markdown
# [Short Bug Title]

**Date:** YYYY-MM-DD HH:MM

## Problem
[How it manifested - 2-3 sentences]

## Root Cause
[What caused it - 2-3 sentences]

## Fix
[How it was fixed - File:Line references]
```

**For FAILED:** `not_working/[name]_YYYYMMDD_HHMMSS_failed.md`

```markdown
# [Short Bug Title] - FAILED FIX ATTEMPT

**Date:** YYYY-MM-DD HH:MM

## Problem
[How it manifested]

## Attempted Fix
[What was tried - File:Line references]

**Theory:** [Why this approach was expected to work]

## Why It Failed

**Observed:** [From Step 1 answers]
**Symptoms:** [Specific symptoms]
**Hypothesis:** [Technical explanation]
**Confidence:** [X%] - [High/Medium/Low]
**Uncertain about:** [What needs investigation]

## Next Steps
[Other approaches to try]
```

### Step 3: Write File

Generate timestamp, create descriptive filename, write to appropriate folder.
