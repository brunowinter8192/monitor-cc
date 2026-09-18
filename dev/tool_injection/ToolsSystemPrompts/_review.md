# Tool Description Review (Phase B)

## Summary

- **Total chars in tool descriptions:** 16,669
- **sys[3] chars:** 3,066
- **Grand total analyzed:** 19,735
- **Chars to strip (REDUNDANT + KNOWN):** ~15,800
- **Chars to keep/migrate:** ~3,935
- **Reduction: ~80%**

Bash dominates: 10,435 chars (63% of all tool descriptions), strips at 96% — driven by the
duplicated Git/PR workflow section. Skill resists hardest (24% strip); its behavioral constraints
are not duplicated anywhere else and are genuine load-bearing content. sys[3]: 100% strip confirmed.

---

## Per-Tool Analysis

### Bash (10,435 chars)

#### REDUNDANT

**Block: "# Committing changes with git"** (~5,800 chars)
Full step-by-step workflow: parallel git status/diff/log calls, staging, commit with Co-Author
HEREDOC, post-commit git status check, push with `-u` fallback. Includes specific `gc` wrapper
syntax and MCP git_check pre-check step.
- Already in: `~/.claude/CLAUDE.md`, section **"Git Commit Workflow"** — verbatim overlap. Same
  gc wrapper, same git_check MCP pre-commit step, same push pattern (`-u origin $(branch --show-current)`),
  same commit message format rules (single-line `-m` default, HEREDOC only for breaking changes),
  same "NEVER amend" / "NEVER force push" safety rules.
- Verdict: strip

**Block: "# Creating pull requests"** (~2,000 chars)
`gh pr create` workflow with HEREDOC body, PR title character limit, git log analysis steps,
parallel branch-check commands.
- Already in: `~/.claude/CLAUDE.md`, section **"Creating pull requests"** — verbatim overlap,
  including the HEREDOC body format example and Summary + Test plan structure.
- Verdict: strip

**Block: "# Other common operations"** (~80 chars)
"View comments on a Github PR: gh api repos/foo/bar/pulls/123/comments"
- Already in: `~/.claude/CLAUDE.md`, section **"Creating pull requests"** (same line at end of PR section).
- Verdict: strip

**Block: Instructions > "For git commands" sub-rules** (~300 chars)
"Prefer to create a new commit rather than amending... Never skip hooks (--no-verify)... Never
run force push to main/master..."
- Already in: `~/.claude/CLAUDE.md`, section **"Git Commit Workflow"** > "Rules" subsection —
  identical bullet list.
- Verdict: strip

**Block: Instructions > "Never prepend `cd` to git command"** (~150 chars)
"never prepend `cd <current-directory>` to a `git` command — `git` already operates on the
current working tree, and the compound triggers a permission prompt."
- Already in: `~/.claude/CLAUDE.md`, section **"Git Commit Workflow"** > "CLI Commands" table
  (same rationale stated explicitly in table note column).
- Verdict: strip

**Block: Instructions > `run_in_background` guidance** (~330 chars)
"Only use this if you don't need the result immediately... you will be notified when it finishes...
Do not retry failing commands in a sleep loop..."
- Already in: `~/.claude/CLAUDE.md`, section **"Avoid unnecessary sleep commands"** (under
  "Communication > Announce & Execute"): same instructions — "use run_in_background for long-running
  commands", "no sleep needed", "do not poll", sleep-loop prohibition.
- Verdict: strip

**Block: Instructions > "When issuing multiple commands" (parallel vs && vs ;)** (~250 chars)
"If commands are independent → multiple Bash tool calls in parallel. Dependent → single Bash call
with &&. Sequential but ok if fail → ;. DO NOT use newlines to separate commands."
- Already in: `~/.claude/CLAUDE.md` system instructions (verbatim — these rules appear in the
  active system prompt).
- Verdict: strip

**Block: "IMPORTANT: Avoid using find, grep, cat, head, tail, sed, awk, or echo"** (~620 chars)
The tool-redirection mapping (Glob/Grep/Read/Edit/Write instead of Bash equivalents).
- `grep` / `rg` → use Grep tool: already in `tool-usage.md`, section **"Grep Scope Hygiene"**
  ("Prefer the Grep tool over bash `grep -rn` for code search").
- `echo >` / `cat << 'EOF' >` → Write tool: already in `tool-usage.md`, section
  **"No Bash for File Creation"**.
- `cat`/`head`/`tail` → Read: KNOWN (baseline model training on Claude Code).
- `find` → Glob: KNOWN.
- Verdict: strip

#### KNOWN

**Opening + working directory behavior** (~170 chars)
"Executes a given bash command and returns its output. The working directory persists between
commands, but shell state does not..."
- Baseline model knowledge. Not a source of behavioral failures in bash_deepdive evidence.
- Verdict: strip

**Instructions > "ls before creating new directories"** (~130 chars)
"If your command will create new directories or files, first use this tool to run `ls` to verify
the parent directory exists and is the correct location."
- Baseline model knowledge. Zero failures attributable to missing this instruction in 214 analyzed
  long Bash calls.
- Verdict: strip

**Instructions > "Always quote file paths that contain spaces"** (~90 chars)
- Baseline shell knowledge.
- Verdict: strip

**Instructions > "DO NOT use newlines to separate commands"** (~60 chars)
- Baseline shell knowledge (tool_use serialization constraint).
- Verdict: strip

#### KEEP

**Timeout specification** (~145 chars)
"You may specify an optional timeout in milliseconds (up to 600000ms / 10 minutes). By default,
your command will timeout after 120000ms (2 minutes)."
- Concrete parameter behavior. Not in any of our rules. Needed when running builds, crawls, or
  long test suites that exceed the 2-minute default silently.
- Migration target: `skills/tool-use/SKILL.md` → new section **"Parameter reference"**

**Bash KEEP total: ~145 chars. Strip: ~10,290 (98%)**

---

### Edit (1,094 chars)

#### KNOWN / REDUNDANT

**Opening** (~42 chars): "Performs exact string replacements in files." — KNOWN.

**"ALWAYS prefer editing existing files; NEVER write new files unless explicitly required"** (~100 chars)
- KNOWN (trained behavior; Write description also states "Prefer Edit for existing files").
- Verdict: strip

**Emoji rule** (~95 chars): "Only use emojis if the user explicitly requests it."
- REDUNDANT: duplicate of Write's emoji rule; behavioral style covered by `~/.claude/CLAUDE.md`,
  section **"Communication"** (communication style guidance).
- Verdict: strip

#### KEEP

**"Must Read before Edit; tool will error if not"** (~153 chars)
"You must use your `Read` tool at least once in the conversation before editing. This tool will
error if you attempt an edit without reading the file."
- Enforced failure mode. Keeps model from attempting blind edits.

**"Preserve exact indentation after line number prefix; format is: line number + tab"** (~318 chars)
"When editing text from Read tool output, ensure you preserve the exact indentation (tabs/spaces)
as it appears AFTER the line number prefix. The line number prefix format is: line number + tab.
Everything after that is the actual file content to match. Never include any part of the line
number prefix in old_string or new_string."
- Non-obvious format detail. Source of frequent Edit failures when ignored — old_string matches
  fail because the model includes the "42\t" prefix in the match string.

**"Edit FAIL if `old_string` not unique; use replace_all or more context"** (~207 chars)
"The edit will FAIL if `old_string` is not unique in the file. Either provide a larger string with
more surrounding context to make it unique or use `replace_all` to change every instance of
`old_string`."
- Concrete error condition with two explicit remedies. Not elsewhere.

**"Use `replace_all` for rename-across-file"** (~170 chars)
"Use `replace_all` for replacing and renaming strings across the file. This parameter is useful if
you want to rename a variable for instance."
- Capability that the tool name doesn't imply.

**Edit KEEP total: ~848 chars. Strip: ~246 (22%)**

Note: Edit resists stripping — description is almost entirely concrete behavioral constraints
with real failure modes. 22% strip is honest for this tool.

---

### Glob (371 chars)

#### KNOWN

All content except mtime sort: "Fast file pattern matching tool", "works with any codebase size",
"Supports glob patterns like `**/*.js` or `src/**/*.ts`", "Use this tool when you need to find
files by name patterns", "When you are doing an open ended search that may require multiple rounds
of globbing and grepping, use the Agent tool instead." — all baseline model knowledge.
- Verdict: strip (~311 chars)

#### KEEP

**"Returns matching file paths sorted by modification time"** (~60 chars)
- Non-obvious sort behavior. Affects which file is first when multiple match — relevant for
  "find most recent log" patterns. Without this, model might assume alphabetical order.
- Migration target: `skills/tool-use/SKILL.md` → note under Rule 6 "Grep/Glob gunshot"

**Glob KEEP total: ~60 chars. Strip: ~311 (84%)**

---

### Grep (866 chars)

#### REDUNDANT

**"ALWAYS use Grep for search tasks. NEVER invoke `grep` or `rg` as a Bash command"** (~75 chars)
- Already in: `tool-usage.md`, section **"Grep Scope Hygiene — Always Restrict When Searching Source"**
  ("Prefer the Grep tool over bash `grep -rn` for code search").
- Verdict: strip

#### KNOWN

**"A powerful search tool built on ripgrep"** (~40 chars) — KNOWN.
**"Supports full regex syntax (e.g., `log.*Error`, `function\s+\w+`)"** (~50 chars) — KNOWN
(model knows ripgrep regex from training).
**"Filter files with glob parameter (e.g. `*.js`) or type parameter (e.g., `js`, `py`)"** (~80 chars)
— KNOWN (ripgrep standard options).
**Output modes: content / files_with_matches / count** (~130 chars) — KNOWN (model knows ripgrep
output modes from training).
**"Use Agent tool for open-ended searches requiring multiple rounds"** (~60 chars) — KNOWN/irrelevant
(Agent tool not in our standard tool set).
- Verdict: strip all (~360 chars)

#### KEEP

**"Pattern syntax: Uses ripgrep — literal braces need escaping (use `interface\{\}` to find
`interface{}` in Go code)"** (~100 chars)
- Non-obvious gotcha. rg vs grep brace escaping differs. Without this, model generates patterns
  that silently match nothing on Go/TypeScript code.
- Migration target: `skills/tool-use/SKILL.md` → new section **"Grep gotchas"**

**"Multiline matching: By default patterns match within single lines only. For cross-line patterns
like `struct \{[\s\S]*?field`, use `multiline: true`"** (~110 chars)
- Non-default parameter. Without the explicit flag, cross-line patterns silently fail.
- Migration target: `skills/tool-use/SKILL.md` → new section **"Grep gotchas"**

**Grep KEEP total: ~210 chars. Strip: ~656 (76%)**

---

### Read (1,779 chars)

#### KNOWN / REDUNDANT

**Opening + "access any file on machine" + "path is valid" assumption** (~210 chars) — KNOWN.
**"`file_path` must be absolute, not relative"** (~72 chars) — KNOWN (enforced; model knows).
**"Only read what you need for larger files"** (~115 chars) — KNOWN/NUANCE → strip (no failure evidence).
**"Regularly asked to read screenshots; ALWAYS use this tool; works with temp paths"** (~195 chars)
— NUANCE → strip (nice to have; not a source of documented failures).
**"Do NOT re-read a file you just edited to verify — Edit/Write would have errored"** (~143 chars)
— NUANCE → strip (correct but "nice to have"; failure would be visible immediately).
**"It is okay to read a file that does not exist; an error will be returned"** (~72 chars) — KNOWN.

#### KEEP

**"Reads up to 2000 lines by default"** (~76 chars)
- Concrete limit. Without knowing this, model doesn't know when to use `offset`/`limit` parameters
  for large files — it gets truncated output and may not realize it.

**"Results returned using cat -n format, with line numbers starting at 1"** (~72 chars)
- Critical for Edit compatibility. Edit's `old_string` must NOT include the line number prefix.
  This rule explains the format that KEEP item in Edit's description references.

**"Can read images (PNG, JPG, etc.) — presented visually as multimodal LLM"** (~162 chars)
- Non-obvious capability. Not all tasks assume screenshot reading is possible.

**"PDF reading: large PDFs (>10 pages) MUST provide `pages` parameter; reading without it will
fail; max 20 pages per request"** (~240 chars)
- Enforced failure mode. Without this, model submits large PDFs without `pages` param and gets an
  error; not recoverable by the tool silently.

**"Can read Jupyter notebooks (.ipynb) — returns all cells with outputs, combining code, text,
and visualizations"** (~140 chars)
- Non-obvious capability. Not inferrable from tool name.

**"Can only read files, not directories; use ls via Bash for directory listing"** (~104 chars)
- Concrete limitation. Without this, model may attempt Read on a directory path and get a confusing error.

**"If you read a file that exists but has empty contents, you will receive a system reminder
warning in place of file contents"** (~120 chars)
- Unusual behavior. Without this, model misinterprets the warning as actual file content and reasons
  incorrectly about it.

**Read KEEP total: ~914 chars. Strip: ~865 (49%)**

Note: Read description is denser than it looks — most content is concrete capability/limitation
info. 49% strip is the honest ceiling without losing genuinely useful constraints.

---

### Skill (1,315 chars)

#### KNOWN

**Opening description** (~185 chars): "Execute a skill within the main conversation... When users ask
you to perform tasks, check if any of the available skills match. Skills provide specialized
capabilities and domain knowledge." — KNOWN.
**"Available skills are listed in system-reminder messages in the conversation"** (~75 chars) — model
knows where skills are listed.
- Verdict: strip (~260 chars)

#### KEEP (all behavioral constraints — none duplicated elsewhere)

**"Slash command or `/<something>` = skill invocation → use this tool"** (~115 chars)
Maps user syntax to tool dispatch. Not in any rule or system block.

**"Set `skill` to exact name (no leading slash). For plugin-namespaced skills, use `plugin:skill` form."** (~155 chars)
Syntax rules including namespace form for our MCP-backed skills (e.g. `iterative-dev:worker_spawn`).

**"`args` to pass optional arguments"** (~37 chars): Capability note.

**"Only invoke a skill that appears in the system-reminder list or user explicitly typed as `/<name>`.
Never guess or invent a skill name from training data."** (~195 chars)
- Strict constraint. Critical — prevents hallucinated skill invocations based on Claude Code
  training knowledge. The "from training data" qualifier is precise and necessary.

**"BLOCKING REQUIREMENT: invoke Skill tool BEFORE generating any other response about the task"** (~148 chars)
- Ordering constraint. Not in any rule. Without this, model generates a partial response before
  the skill loads, causing the skill content to be ignored.

**"NEVER mention a skill without actually calling this tool"** (~55 chars)
- Behavioral constraint. Prevents dead references in text output.

**"Do not invoke a skill that is already running"** (~47 chars)
- State constraint. Prevents re-entry loops.

**"Do not use this tool for built-in CLI commands (like /help, /clear, etc.)"** (~74 chars)
- Scope constraint. Without this, model might try Skill("help") on built-in slash commands.

**"If you see a `<command-name>` tag in the current conversation turn, the skill has ALREADY been
loaded — follow the instructions directly instead of calling this tool again"** (~167 chars)
- Anti-double-invocation signal. Without this, model re-invokes a skill that's already active.

**Skill KEEP total: ~993 chars. Strip: ~322 (24%)**

Skill resists stripping by design — its entire value is behavioral constraints that exist nowhere
else. Do not push further.

---

### Write (618 chars)

#### KNOWN

**Opening** (~38 chars): "Writes a file to the local filesystem." — KNOWN.
**"Will overwrite the existing file if there is one at the provided path"** (~82 chars) — KNOWN.

#### REDUNDANT

**Emoji rule** (~95 chars): "Only use emojis if the user explicitly requests it. Avoid writing emojis to files unless asked."
- Duplicate of Edit's emoji rule; covered by `~/.claude/CLAUDE.md`, section **"Communication"**
  style guidance.
- Verdict: strip

#### KEEP

**"If existing file, MUST use Read tool first; tool will fail if not"** (~145 chars)
"If this is an existing file, you MUST use the Read tool first to read the file's contents. This
tool will fail if you did not read the file first."
- Enforced failure mode. Prevents blind overwrites and the associated data loss.

**"Prefer Edit for existing files — only sends diff. Use Write only for new files or complete
rewrites."** (~140 chars)
- Not in any rule. High-value choice criterion: Edit is more token-efficient (diff only) vs Write
  (sends full content). Model has no other source for this guidance.
- Migration target: `skills/tool-use/SKILL.md` → new section **"Write vs Edit"**

**"NEVER create `*.md` or README files unless explicitly requested by the User"** (~95 chars)
- Behavioral constraint. Prevents unsolicited documentation generation. Not in our rules.

**Write KEEP total: ~380 chars. Strip: ~238 (39%)**

---

### MCP Tools (4 tools, 191 chars total)

All KEEP. Already minimal; no redundancy possible.

| Tool | Description | Verdict |
|------|-------------|---------|
| dev_sync | "Sync dev branch to main without checkout. Uses git update-ref for fast-forward." | KEEP — opaque git operation; description is load-bearing |
| git_check | "Pre-commit check with auto-staging." | KEEP |
| worker_send | "Send message to running worker." | KEEP |
| worker_spawn | "Spawn worker with optional worktree isolation." | KEEP |

---

### sys[3] (3,066 chars)

#### "# Text output" section (~900 chars) — REDUNDANT

Full text: "Assume users can't see most tool calls or thinking — only your text output. Before your
first tool call, state in one sentence what you're about to do..." + rules on updates, end-of-turn
summary, brevity, response length matching task.

- Already in: `~/.claude/CLAUDE.md`, section **"Text output (does not apply to tool calls)"** —
  verbatim duplicate. Same opening sentence, same "one sentence per update" rule, same "end-of-turn:
  one or two sentences" rule.
- Verdict: strip

#### "# Language" section + length limits (~450 chars) — REDUNDANT

"Always respond in deutsch. Use deutsch for all explanations... Maintain full orthographic
correctness... Length limits: keep text between tool calls to ≤25 words. Keep final responses
to ≤100 words unless the task requires more detail."

- Already in: `~/.claude/CLAUDE.md`, section **"Language"** — verbatim duplicate, including the
  length limit sub-section.
- Verdict: strip

#### "# Environment" section (~1,716 chars) — Trade-off analysis

User has signaled 99% strip intent. Verification by field:

| Field | Content | Load-bearing? | Would model behave differently without it? |
|-------|---------|---------------|-------------------------------------------|
| Primary working directory | `/Users/brunowinter2000/Documents/ai/Monitor_CC` | Weak | No — model can `pwd`; path appears in project CLAUDE.md and tool context implicitly |
| Is a git repository: true | — | None | No — model assumes dev projects are git repos; would try git commands either way |
| Platform: darwin | — | Mild | Yes for platform-specific commands: `gstat` vs `stat`, BSD `date` format, `brew` vs `apt`. Without this, model might generate Linux commands that fail on macOS. However: (a) failure is visible immediately, (b) user corrects within 1-2 turns, (c) not flagged as failure source in any session forensics |
| Shell: zsh | — | Minimal | Rarely — zsh array syntax differs from bash, but bash-compatible commands work for 95% of use cases |
| OS Version: Darwin 24.6.0 | macOS 15.x | None | No — version-specific command differences are negligible |
| Model name + ID | claude-opus-4-7[1m] | None | No — model knows what it is from training. Never changes behavior based on own model ID |
| Knowledge cutoff | January 2026 | None | No — model knows its own cutoff from training |
| Model family IDs | Opus/Sonnet/Haiku model ID strings | Low | Only when building AI applications. Irrelevant in Monitor_CC dev sessions |
| Claude Code availability | "CLI, desktop app, web app, IDE extensions" | None | No — KNOWN |
| Fast mode info | "uses Claude Opus 4.6 with faster output..." | None | No — operational detail irrelevant during sessions |

**Assessment of 99% strip:**

The only non-trivial trade-off is `Platform: darwin` (~20 chars). Without it, the model may
generate Linux-compatible commands that fail on macOS (`stat` without `-f`, `date -d`, etc.).
Mitigation path: the model adapts within 1-2 tool calls once the error surfaces. Cost of sending:
~1,716 chars per request (all 11 fields, most with zero load-bearing value) to gain ~20 chars
of genuinely useful context. Net: strip is correct.

**sys[3] KEEP: 0 chars. Strip: 3,066 (100%). 99% claim: CONFIRMED.**

---

## Migration Candidates (Summary)

| Block | Source tool | KEEP chars | Migration target in SKILL.md |
|-------|-------------|-----------|------------------------------|
| Timeout spec (max 600000ms; default 120000ms) | Bash | ~145 | New section **"Parameter reference"** |
| Glob: mtime sort behavior | Glob | ~60 | Note under Rule 6 "Grep/Glob gunshot" |
| Grep: literal brace escaping for Go/TS | Grep | ~100 | New section **"Grep gotchas"** |
| Grep: multiline mode flag | Grep | ~110 | New section **"Grep gotchas"** |
| Read: 2000-line default limit + offset/limit params | Read | ~76 | Note under Rule 4 "Don't re-issue near-identical commands" |
| Write: Edit-over-Write preference + why | Write | ~140 | New section **"Write vs Edit"** |

Non-migration KEEP (stays in tool descriptions; no duplication value from migrating):
- Edit: Read-before-edit, indentation format, old_string uniqueness, replace_all (~848 chars)
- Read: cat-n format, image/PDF/Jupyter capabilities, dirs limitation, empty warning (~838 chars)
- Skill: all constraints (~993 chars)
- MCP tools: all descriptions (191 chars)
- Write: MUST Read first, no-md rule (~240 chars)

---

## Skill vs Rule Consolidation Notes (Input for Phase C)

### Duplication 1 — Inline Python Heredoc Rule

| Source | Section | Core rule | Chars |
|--------|---------|-----------|-------|
| `skills/tool-use/SKILL.md` | Rule 1 "NEVER inline Python heredoc for analysis" | "python3 << 'EOF' ... EOF is #1 waster. Write to /tmp/, then run. Hard cap: python3 -c ≤300 chars." | ~450 |
| `tool-usage.md` | "Tool_Use Input Hygiene — NO Inline Python Heredocs" | Same rule, broader framing: 4 alternatives (prefer jq, write script, shell vars, pipeline), concrete failure example (context 40%→18%), the "15-line test" | ~900 |

**These say the same thing.** `tool-usage.md` is more authoritative: has empirical failure evidence,
jq alternative, and "the test" heuristic. `SKILL.md` adds only the 300-char hard cap for `-c` mode
— that is the only non-redundant addition.

Recommendation for Phase C: make `tool-usage.md` canonical, import the 300-char cap into it,
remove Rule 1 from `SKILL.md`.

### Duplication 2 — File Creation via Bash

| Source | Section | Core rule | Chars |
|--------|---------|-----------|-------|
| `skills/tool-use/SKILL.md` | Rule 7 "Multi-line echo → Write" | "multi-line echo/cat heredoc → Write tool. Single-line echo append for config/log is fine." | ~120 |
| `tool-usage.md` | "No Bash for File Creation" | "NEVER use `cat > file << 'EOF'` or `echo >`. Always use Write tool." + rationale (heredocs can leak shell context) | ~200 |

**Different granularity.** SKILL.md allows single-line echo appends; `tool-usage.md` says NEVER.
SKILL.md's nuance is probably correct (single-line echo for log/config is fine).

Recommendation for Phase C: consolidate under `tool-usage.md` with SKILL.md's nuance preserved:
add "Single-line echo append to existing files is acceptable" clause.
