# t1_skill_picker report

- every case ran in its own subprocess with an isolated HOME, all cases in parallel
- nothing in this test types into a terminal or opens a menu

| case | result | detail |
|---|---|---|
| applescript | PASS | script exact, no send key/activate/focus/System Events, quoting escaped, osacompile (compile only, nothing executed) rc=0 |
| controller | PASS | no cwd -> FAILED and no menu; menu popped at the button bottom-left with the controller as target; choice inserts for the clicked row; missing choice -> FAILED |
| discovery_manifest_missing | PASS | no manifest + skills/ directory -> FAILED plugin=withdir@m reason=manifest_missing; no manifest + no skills/ directory -> skipped silently |
| discovery_names | PASS | plugin name from manifest (not key), frontmatter name else dir name, user scope entry preferred: [('labelA', 'realname:labelA'), ('dirB', 'realname:dirB'), ('dirC', 'realname:dirC'), ('dirD', 'realname:dirD')] |
| discovery_plugins | PASS | 8 plugin skills, disabled plugin absent, pyright-like plugin (no manifest, no skills/ directory) skipped without a log line |
| discovery_project_personal | PASS | project [('penny', 'penny'), ('wise2627-tracker', 'wise2627-tracker'), ('x-dir', 'x-dir')]; personal [('mine', 'mine')]; other project and empty cwd see no project skills; order project, personal, plugin |
| discovery_tripwires | PASS | no skills array (also for a plugin with only a default skills/ folder), no name, missing skill file, not installed, unreadable settings: each logged FAILED and skipped |
| grid | PASS | 7 columns, skill button on both main rows right after mon with matching tag, cwd_map {1: '/tmp/alpha', 3: '/tmp/beta'}, worker row column 6 empty |
| insert_paths | PASS | no terminal id: FAILED cwd=/p/x skill=gh-cli:gh-cli-search stage=terminal_id no_terminal_id | rc=1: FAILED cwd=/p/x skill=gh-cli:gh-cli-search stage=osascript rc=1 stderr=not allowed | timeout: FAILED cwd=/p/x skill=gh-cli:gh-cli-search stage=osascript TimeoutExpired('osascript', 5) | success: one osascript call, OK cwd=/p/x skill=gh-cli:gh-cli-search stage=osascript terminal=T9 osascript_ms=0 |
| insert_text | PASS | 10 inserted texts exact, e.g. 'Aktiviere den Skill iterative-dev:iterative-dev-doccheck.' |
| isolation | PASS | CLAUDE_DIR=<home>/.claude and MENUBAR_LOG under the isolated home; discovery log line landed there |
| menu | PASS | titles ['penny', 'sep', 'mine', 'sep', 'a', 'b'], represented full names ['penny', 'mine', 'p:a', 'p:b'], empty list -> one disabled "no skills" |

RESULT: PASS