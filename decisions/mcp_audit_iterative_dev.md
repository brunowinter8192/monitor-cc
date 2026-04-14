# iterative-dev MCP Tool Audit for Opus

Source: `/Users/brunowinter2000/Documents/ai/Meta/blank`
Scan date: 2026-04-14

Schema sizes measured from `src/proxy/schemas/iterative-dev/` (exact char counts from schema JSON files).
"Used every session" based on SKILL.md mandatory section + core IMPLEMENT phase workflow.

---

## Tool Inventory

| Tool Name | server.py line | LOC | Purpose | Schema (chars) | Used every session? | Execution-critical? | CLI equivalent | Decision |
|---|---|---|---|---|---|---|---|---|
| `bead_list` | 91 | 7 | List open/closed beads | 545 | **yes** (mandatory start) | no | `bd list -s open` | CONVERT |
| `bead_show` | 100 | 10 | Show bead + comments (2 bd calls, merged) | 498 | frequent | no | `bd show <id> && bd comments <id>` | CONVERT |
| `bead_create` | 112 | 14 | Create bead with title/desc/labels | 865 | occasional | no | `bd --repo <p> create --title ... --description ...` | CONVERT |
| `bead_comment` | 128 | 9 | Add comment to bead | 552 | occasional | no | `bd comments add <id> <text>` | CONVERT |
| `bead_close` | 139 | 8 | Close bead with reason | 373 | occasional | no | `bd close <id> --reason=<r>` | CONVERT |
| `worker_list` | 151 | 8 | List active tmux workers | 421 | yes | no | `source tmux_spawn.sh && worker_list <path>` | CONVERT |
| `worker_status` | 161 | 9 | Check idle/busy status of one worker | 506 | yes | no | `source tmux_spawn.sh && worker_status <name> <path>` | CONVERT |
| `worker_capture` | 172 | 23 | Capture pane output; optional tail-N | 925 | yes | no | `source tmux_spawn.sh && worker_capture <n> "" <p>; tail -n N <file>` | CONVERT |
| `worker_send` | 197 | 27 | Send multi-line message to worker via env var | 578 | yes | **yes** | n/a — shell-escape safety | **KEEP** |
| `worker_spawn` | 226 | 65 | Atomic: worktree + settings copy + venv symlink + tmux spawn | 716 | yes | **yes** | n/a — multi-step with early-exit rollback | **KEEP** |
| `worker_merge` | 293 | 27 | git log preview + git merge | 556 | yes | no | `git log dev..<name> --oneline && git merge <name>` | CONVERT |
| `worker_kill` | 322 | 29 | tmux kill + worktree remove + branch delete | 545 | occasional | no | 3 sequential bash commands (order matters, no rollback either way) | CONVERT |
| `dev_sync` | 353 | 47 | FF-safe dev→main without checkout via git update-ref | 465 | yes (session end) | **yes** | n/a — ff check + main/master fallback + no-checkout atomic | **KEEP** |
| `prompt` | 439 | 45 | External LLM via NVIDIA NIM (model aliases, file I/O) | 1330 | occasional | no | `curl` + env var for api key | CONVERT |
| `eval_list_agents` | 488 | 10 | List subagent JSONL files for a session | 561 | occasional | no | `python3 -m src.pipeline.list_agents <path>` | CONVERT |
| `eval_extract` | 500 | 21 | Convert agent JSONL → markdown summary | 546 | occasional | no | `python3 -m src.pipeline.jsonl_to_md <path> <out>` | CONVERT |
| `git_check` | 535 | 4 | Pre-commit: auto-stage with skip patterns + diff summary | 328 | **yes** (every commit) | **yes** | n/a — auto-staging logic in check.py is non-trivial | **KEEP** |
| `git_commit` | 541 | 11 | `git -C <path> commit -m <msg>` | 379 | yes | no | `git -C <path> commit -m <msg>` | CONVERT |
| `git_push` | 554 | 20 | push with `-u origin <branch>` fallback | 305 | yes | no | `git -C <p> push \|\| git -C <p> push -u origin $(git branch --show-current)` | CONVERT |
| `git_post` | 576 | 4 | Post-commit: `git status --short` check | 317 | yes | no | `git -C <path> status --short` | CONVERT |
| `git_sync` | 582 | 18 | Run `plugin-sync.sh <name> <path>` for plugin repos | 324 | occasional (plugin repos only) | no | `<plugin_dir>/plugin-sync.sh <name> <path>` | CONVERT |
| `activate_plugin` | 634 | 13 | Append plugin to active_plugins.json | 647 | occasional | no | `python3 -c "import json; p=open(...); ..."` or jq | CONVERT |
| `deactivate_plugin` | 649 | 13 | Remove plugin from active_plugins.json | 629 | occasional | no | same — jq / python one-liner | CONVERT |
| `list_active_plugins` | 664 | 8 | Read active_plugins.json | 447 | occasional | no | `cat <project>/.claude/active_plugins.json` | CONVERT |

**Total schema size (all 24 tools):** 13,358 chars  
**Schema size after conversion (4 KEEP tools):** 2,087 chars  
**Savings per request:** 11,271 chars ≈ 2,800 tokens  
**At 100 requests/session:** ~280,000 tokens saved

---

## Recommendations per Tool

### KEEP as MCP

**`worker_send`** — KEEP (execution-critical, every session)  
Message is passed via env var (`_WORKER_MSG`) to avoid shell escaping. Worker instructions routinely contain newlines, triple backticks, and embedded shell commands. Without the env-var trick, a bash-interpolated send-keys call on any code-containing message would corrupt the input. There is no safe bash equivalent for arbitrary-content multi-line messages.

**`worker_spawn`** — KEEP (execution-critical, every session)  
Runs 5 steps atomically with early-exit on failure: (1) branch collision check, (2) `git worktree add -b`, (3) `settings.local.json` copy, (4) `venv` symlink, (5) tmux spawn. Each step is a failure point; the MCP tool provides ordered error reporting. Replicating this in a bash heredoc is possible but fragile — one quoting issue in the tmux spawn command would silently mis-spawn the worker with the wrong prompt.

**`dev_sync`** — KEEP (execution-critical, every session end)  
Enforces fast-forward check (`git merge-base --is-ancestor`) before `git update-ref`. Without the ff check, calling `update-ref` on a non-ancestor dev HEAD would silently lose main's commits. Additionally handles main/master fallback. The no-checkout design (session stays on dev) is specifically what this tool provides — a naive `git checkout main && git merge dev && git checkout dev` is a poor substitute because it moves HEAD.

**`git_check`** — KEEP (execution-critical, every commit)  
Runs `src/git/check.py --auto-stage`. The auto-staging logic in check.py has skip patterns (venv/, .venv/, node_modules/) and classifies staged/unstaged/untracked with a formatted diff summary used directly as commit message material. The complexity is in check.py (~100 lines), not the MCP wrapper. A bash equivalent would need to replicate all of that.

---

### CONVERT to Skill + CLI

#### Bead Group

**`bead_list`** — CONVERT  
CLI: `bd list -s open` (or `bd --db <repo>/.beads/dolt list -s open` for non-default repo).  
Called exactly once per session at start. Schema ships every request — 545 chars × 100 requests = 54,500 chars wasted for one call.

**Skill draft (`skills/bead/SKILL.md`):**
```
# Bead CLI Skill
Session start: run `bd list -s open` — read open beads.
Non-default repo: `bd --db <path>/.beads/dolt list -s open`
```

---

**`bead_show`** — CONVERT  
CLI: `bd show <id> && echo "--- COMMENTS ---" && bd comments <id>`  
Two bd calls, no state. The MCP tool just merges the output.

---

**`bead_create`** — CONVERT  
CLI: `bd --repo <project_path> create --title "<title>" --type task --description "<desc>"` (add `--labels` if needed).  
Flag note: create uses `--repo`, other bd commands use `--db`.

---

**`bead_comment`** — CONVERT  
CLI: `bd comments add <id> "<text>"`

---

**`bead_close`** — CONVERT  
CLI: `bd close <id> --reason="<reason>"`

**Consolidated skill draft for all bead ops:**
```
# Bead CLI Skill

Session start: `bd list -s open`
Show bead:    `bd show <id> && echo "---" && bd comments <id>`
Create bead:  `bd --repo <project_path> create --title "..." --type task --description "..."`
Add comment:  `bd comments add <id> "text"`
Close bead:   `bd close <id> --reason="reason"`
Non-default repo (all except create): `bd --db <path>/.beads/dolt <cmd>`
```

---

#### Worker Group (non-critical)

**`worker_list`** — CONVERT  
CLI: `PLUGIN="~/.claude/plugins/cache/brunowinter-plugins/iterative-dev/1.0.0"; source "$PLUGIN/src/spawn/tmux_spawn.sh" && worker_list "<project_path>"`

**`worker_status`** — CONVERT  
CLI: `source "$PLUGIN/src/spawn/tmux_spawn.sh" && worker_status "<name>" "<project_path>"`

**`worker_capture`** — CONVERT  
CLI: `source "$PLUGIN/src/spawn/tmux_spawn.sh" && worker_capture "<name>" "" "<path>" && tail -n <N> <output_file>`  
Note: the MCP tool's `tail` param is a convenience — two bash commands replicate it.

**`worker_merge`** — CONVERT  
CLI: `git -C <path> log dev..<name> --oneline && git -C <path> merge <name>`

**`worker_kill`** — CONVERT  
CLI:  
```bash
tmux kill-session -t "worker-$(basename <path>)-<name>" 2>/dev/null
git -C <path> worktree remove --force .claude/worktrees/<name>
git -C <path> branch -d <name>
```
Note: session name pattern is `worker-<basename(project_path)>-<name>`.

**Consolidated skill draft (`skills/worker-cli/SKILL.md`):**
```
# Worker CLI Skill
PLUGIN=~/.claude/plugins/cache/brunowinter-plugins/iterative-dev/1.0.0

List workers:   source "$PLUGIN/src/spawn/tmux_spawn.sh" && worker_list "<project_path>"
Check status:   source "$PLUGIN/src/spawn/tmux_spawn.sh" && worker_status "<name>" "<path>"
Capture output: source "$PLUGIN/src/spawn/tmux_spawn.sh" && worker_capture "<name>" "" "<path>"
  Read tail:    tail -n 50 <output_file>
Merge worker:   git -C <path> log dev..<name> --oneline && git -C <path> merge <name>
Kill worker:
  tmux kill-session -t "worker-$(basename <path>)-<name>" 2>/dev/null
  git -C <path> worktree remove --force .claude/worktrees/<name>
  git -C <path> branch -d <name>
```

---

#### Git Group (non-critical)

**`git_commit`** — CONVERT  
CLI: `git -C <repo_path> commit -m "<message>"`  
The MCP tool is a one-liner wrapper. Schema cost 379 chars × 100 requests = 37,900 chars wasted.

**`git_push`** — CONVERT  
CLI: `git -C <p> push || git -C <p> push -u origin $(git -C <p> branch --show-current)`

**`git_post`** — CONVERT  
CLI: `git -C <path> status --short` — if empty, working tree is clean.

**`git_sync`** — CONVERT  
CLI: `~/.claude/plugins/cache/brunowinter-plugins/iterative-dev/1.0.0/plugin-sync.sh <name> <repo_path>`  
Only relevant for plugin repos (check: `.claude-plugin/plugin.json` exists).

**Consolidated skill draft (`skills/git-cli/SKILL.md`):**
```
# Git CLI Skill (non-check operations)
PLUGIN=~/.claude/plugins/cache/brunowinter-plugins/iterative-dev/1.0.0

Commit:    git -C <path> commit -m "<message>"
Push:      git -C <p> push || git -C <p> push -u origin $(git -C <p> branch --show-current)
Post-check: git -C <path> status --short   (empty = clean)
Plugin sync (plugin repos only): $PLUGIN/plugin-sync.sh <plugin_name> <repo_path>
```

---

#### Plugin Group

**`activate_plugin`** — CONVERT  
CLI: `python3 -c "import json,os; p='<project>/.claude/active_plugins.json'; os.makedirs(os.path.dirname(p),exist_ok=True); d=json.load(open(p)) if os.path.exists(p) else {'plugins':['iterative-dev']}; d['plugins'].append('<name>') if '<name>' not in d['plugins'] else None; json.dump(d,open(p,'w'),indent=2)"`

Simpler with jq: `jq '.plugins += ["<name>"] | .plugins |= unique' <project>/.claude/active_plugins.json | sponge <project>/.claude/active_plugins.json`

**`deactivate_plugin`** — CONVERT  
CLI (jq): `jq '.plugins -= ["<name>"]' <project>/.claude/active_plugins.json | sponge <project>/.claude/active_plugins.json`

**`list_active_plugins`** — CONVERT  
CLI: `cat <project>/.claude/active_plugins.json`

**Skill draft (`skills/plugin-cli/SKILL.md`):**
```
# Plugin Activation CLI Skill
Requires jq installed.

List:       cat <project>/.claude/active_plugins.json
Activate:   jq '.plugins += ["<name>"] | .plugins |= unique' <project>/.claude/active_plugins.json | sponge <project>/.claude/active_plugins.json
Deactivate: jq '.plugins -= ["<name>"]' <project>/.claude/active_plugins.json | sponge <project>/.claude/active_plugins.json

Default file if missing: {"plugins": ["iterative-dev"]}
```

---

#### LLM Proxy

**`prompt`** — CONVERT (schema: 1,330 chars — largest single tool)  
CLI (curl):
```bash
curl -s -X POST https://integrate.api.nvidia.com/v1/chat/completions \
  -H "Authorization: Bearer $NVIDIA_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"model":"mistralai/mistral-small-3.1-24b-instruct-2503","messages":[{"role":"user","content":"<text>"}],"max_tokens":4096}' \
  | python3 -c "import sys,json; print(json.load(sys.stdin)['choices'][0]['message']['content'])"
```

**Skill draft (`skills/llm-prompt/SKILL.md`):**
```
# LLM Prompt Skill (NVIDIA NIM)

Default model: mistralai/mistral-small-3.1-24b-instruct-2503 (alias: mistral)
Medium model:  mistralai/mistral-medium-3-instruct (alias: mistral-medium)
Large model:   mistralai/mistral-large-3-675b-instruct-2512 (default if no alias)
Llama:         meta/llama-3.3-70b-instruct
Gemma:         google/gemma-3-27b-it

Simple prompt:
curl -s -X POST https://integrate.api.nvidia.com/v1/chat/completions \
  -H "Authorization: Bearer $NVIDIA_API_KEY" \
  -H "Content-Type: application/json" \
  -d "{\"model\":\"<model_id>\",\"messages\":[{\"role\":\"user\",\"content\":\"<text>\"}],\"max_tokens\":4096,\"temperature\":0.15}" \
  | python3 -c "import sys,json; print(json.load(sys.stdin)['choices'][0]['message']['content'])"

With input file: prepend file content to text.
With output file: redirect curl output to file before jq extraction.
```

---

#### Eval Group

**`eval_list_agents`** — CONVERT  
CLI: `cd <plugin_root> && python3 -m src.pipeline.list_agents <project_path>`  
Occasional — used for post-session analysis, not part of core workflow.

**`eval_extract`** — CONVERT  
CLI: `cd <plugin_root> && python3 -m src.pipeline.jsonl_to_md <jsonl_path> /tmp/out.md`  
Or for specific tool calls: `python3 -m src.pipeline.extract_calls <jsonl_path> <call_numbers>`

**Skill draft (`skills/eval-cli/SKILL.md`):**
```
# Eval CLI Skill
PLUGIN=~/.claude/plugins/cache/brunowinter-plugins/iterative-dev/1.0.0

List subagents: cd $PLUGIN && python3 -m src.pipeline.list_agents <project_path>
Extract JSONL:  cd $PLUGIN && python3 -m src.pipeline.jsonl_to_md <jsonl_path> /tmp/eval_out.md
Extract calls:  cd $PLUGIN && python3 -m src.pipeline.extract_calls <jsonl_path> <call_nums>
```

---

## Summary

- **Total tools registered:** 24
- **KEEP for Opus:** 4 (`worker_send`, `worker_spawn`, `dev_sync`, `git_check`)
- **CONVERT to Skill + CLI:** 20

**Schema reduction:**
- Before: 13,358 chars per request
- After: 2,087 chars per request
- Saved: 11,271 chars ≈ **2,800 tokens per request**
- At 100 requests/session: **~280,000 tokens saved**

---

### Honest Ranking

**3 tools Opus would miss most if removed:**

1. `worker_send` — no safe bash alternative for multi-line code-containing messages; one quoting failure silently corrupts a worker mid-session
2. `worker_spawn` — the 5-step atomic setup (worktree + settings + venv + tmux) is where sessions start; a partial failure here leaves orphaned branches
3. `git_check` — the auto-staging logic with skip patterns is genuinely useful; without it Opus would need to manually `git add` specific files every commit

**3 tools that are pure bash wrappers:**

1. `git_commit` — literally `git -C <path> commit -m <msg>` with no additional logic
2. `bead_list` — literally `bd list -s open`; the only nod to complexity is the optional `--db` flag for non-default repos
3. `git_post` — literally `git -C <path> status --short`; 4 LOC in server.py confirms this

---

## Out of Scope

- No changes to `blank/` source code
- No audit of github-research, RAG, searxng, arxiv, or reddit plugins
- No implementation — plan only
