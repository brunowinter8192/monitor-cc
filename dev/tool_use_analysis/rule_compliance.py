#!/usr/bin/env python3
"""Match tool_use/tool_result pairs from Proxy JSONL files against strict prohibitions
in tool-use.md. Pattern-centric (not Hard-Rule-number-centric) — covers Hard Rules,
Tool-Specific Reference, and CLI safety rules (Worker / Git / RAG).

Input:  src/logs/api_requests_*.jsonl (one or more paths, positional args)
Output: rule compliance report (--output FILE or stdout)
"""

# INFRASTRUCTURE
import argparse
import glob as _glob
import json
import os
import re
import sys
from collections import defaultdict
from datetime import datetime
from pathlib import Path

INPUT_PREVIEW_CHARS = 120
ERROR_PREVIEW_CHARS = 300

# Diagnostic-chain segment commands that return non-zero on a "normal correct case"
_RULE11_DIAG_RE = re.compile(r'(^|&&|\|\|)\s*('
                             r'grep\b[^&|]*|'
                             r'ls\s+[^-&|][^&|]*|'
                             r'wc\s+-l\s+[^&|]+|'
                             r'find\s+[^&|]+|'
                             r'\[\s+-[fd]\s+[^&|]+\s+\]|'
                             r'test\s+-[fd]\s+[^&|]+'
                             r')\s*&&')
# Trivial read-only commands that must not run in background
_BG_TRIVIAL_RE = re.compile(r'^(grep|cat|ls|wc|git\s+status|head|tail)\b')
# Rule 3 — file-target extensions (signal that grep is scoped, not broad)
_FILE_EXTENSIONS = {'.py', '.md', '.sh', '.json', '.ts', '.jsonl', '.txt',
                    '.yaml', '.yml', '.toml', '.cfg', '.ini', '.js', '.go', '.rs'}


# SIGNATURES (each returns (matched: bool, evidence: str|None))

# Rule 2 — No Bash heredoc for file creation (cat > file << EOF; not >> which is append)
def _sig_cat_heredoc(pair):
    if pair['tool_name'] != 'Bash':
        return False, None
    cmd = pair['input_full'].get('command', '')
    if re.search(r'cat\s*(?!>)>\s*\S+\s*<<\s*[\'"]?EOF', cmd):
        return True, cmd[:INPUT_PREVIEW_CHARS]
    return False, None


# Rule 3 — Recursive grep without --include= on broad directory target
# Refined: parse each segment separately, check grep flags BEFORE the pattern arg,
# guard against quoted-string FPs by tokenizing per logical segment.
def _sig_broad_grep(pair):
    if pair['tool_name'] != 'Bash':
        return False, None
    cmd = pair['input_full'].get('command', '')
    segments = re.split(r'[;]|&&|\|\|', cmd)
    for seg in segments:
        tokens = seg.split()
        if 'grep' not in tokens:
            continue
        gi = tokens.index('grep')
        has_r = False
        has_include = False
        # Inspect flags between 'grep' and the first non-flag token (the pattern)
        pattern_idx = None
        for i, tok in enumerate(tokens[gi + 1:], start=gi + 1):
            if tok.startswith('--include='):
                has_include = True
                continue
            if tok.startswith('--'):
                if tok == '--recursive':
                    has_r = True
                continue
            if tok.startswith('-') and len(tok) > 1:
                if 'r' in tok[1:]:
                    has_r = True
                continue
            pattern_idx = i
            break
        if not has_r or has_include:
            continue
        # Last non-flag positional arg after the pattern is the target
        positionals = [t for t in tokens[(pattern_idx or gi) + 1:] if not t.startswith('-')]
        target = positionals[-1] if positionals else None
        if target:
            ext = os.path.splitext(target)[1].lower()
            if ext in _FILE_EXTENSIONS:
                continue
            # Glob like *.py or **/*.md → file-scoped intent
            if '*' in target and '.' in target:
                continue
        return True, seg.strip()[:INPUT_PREVIEW_CHARS]
    return False, None


# Rule 6 — Parallel Bash cancelled by runtime
def _sig_parallel_bash(pair):
    if not pair['is_error']:
        return False, None
    if 'Cancelled: parallel tool call' in pair['error_text']:
        return True, pair['error_text'][:INPUT_PREVIEW_CHARS]
    return False, None


# Rule 9 — Read before Edit/Write (retroactive: error string only)
def _sig_read_before_edit(pair):
    if not pair['is_error']:
        return False, None
    if 'File has not been read yet' in pair['error_text']:
        return True, pair['error_text'][:INPUT_PREVIEW_CHARS]
    return False, None


# Rule 10 — Branch-name ambiguity (git fatal: ambiguous argument)
def _sig_git_ambiguous(pair):
    if pair['tool_name'] != 'Bash' or not pair['is_error']:
        return False, None
    if 'fatal: ambiguous argument' in pair['error_text']:
        return True, pair['error_text'][:INPUT_PREVIEW_CHARS]
    return False, None


# Rule 11 — Diagnostic Bash chain with && where left segment may exit non-zero
# Heuristic — known FP risk on legitimate prereq chains (mkdir && cd && build).
def _sig_diag_chain(pair):
    if pair['tool_name'] != 'Bash':
        return False, None
    cmd = pair['input_full'].get('command', '')
    if '&&' not in cmd:
        return False, None
    if _RULE11_DIAG_RE.search(cmd):
        return True, cmd[:INPUT_PREVIEW_CHARS]
    return False, None


# Rule 12 — sleep forbidden (canonical form sleep N && echo done + bg=True is allowed)
def _sig_sleep_noncanonical(pair):
    if pair['tool_name'] != 'Bash':
        return False, None
    cmd = pair['input_full'].get('command', '')
    if not re.search(r'\bsleep\s+\d', cmd):
        return False, None
    if (re.fullmatch(r'sleep\s+\d+(?:\.\d+)?\s*&&\s*echo\s+done', cmd.strip())
            and pair['input_full'].get('run_in_background')):
        return False, None
    return True, cmd[:INPUT_PREVIEW_CHARS]


# Rule 13 — .claire/ typo in tool_input only (NOT error_text — quoting the typo in
# follow-up grep/sed/cat output would self-contaminate the violation count).
def _sig_claire_typo(pair):
    if pair['tool_name'] in ('Read', 'Write', 'Edit'):
        fp = pair['input_full'].get('file_path', '')
        if '.claire/' in fp:
            return True, fp[:INPUT_PREVIEW_CHARS]
    if pair['tool_name'] == 'Bash':
        cmd = pair['input_full'].get('command', '')
        if '.claire/' in cmd:
            return True, cmd[:INPUT_PREVIEW_CHARS]
    return False, None


# Rule 13 same-class — `..letter` double-dot path typo (two dots immediately followed by lowercase letter)
def _sig_double_dot(pair):
    pat = re.compile(r'(?:^|/|\s|=)\.\.[a-z]')
    if pair['tool_name'] in ('Read', 'Write', 'Edit'):
        fp = pair['input_full'].get('file_path', '')
        if pat.search(fp):
            return True, fp[:INPUT_PREVIEW_CHARS]
    if pair['tool_name'] == 'Bash':
        cmd = pair['input_full'].get('command', '')
        if pat.search(cmd):
            return True, cmd[:INPUT_PREVIEW_CHARS]
    return False, None


# Rule 14 — Trivial read-only command run in background unnecessarily
def _sig_bg_trivial(pair):
    if pair['tool_name'] != 'Bash':
        return False, None
    if not pair['input_full'].get('run_in_background'):
        return False, None
    cmd = pair['input_full'].get('command', '').strip()
    if _BG_TRIVIAL_RE.match(cmd):
        return True, cmd[:INPUT_PREVIEW_CHARS]
    return False, None


# Rule 4 sub — `./venv/bin/python script.py` without `> /tmp/file.md 2>&1` redirect
def _sig_venv_python_no_redirect(pair):
    if pair['tool_name'] != 'Bash':
        return False, None
    cmd = pair['input_full'].get('command', '')
    if not re.search(r'\.?\.?/?venv/bin/python\s+\S+\.py\b', cmd):
        return False, None
    # Any file redirect (> or >>) → fine
    if re.search(r'>\s*\S+', cmd):
        return False, None
    return True, cmd[:INPUT_PREVIEW_CHARS]


# Edit — noop edit (old_string == new_string)
def _sig_noop_edit(pair):
    if pair['tool_name'] != 'Edit':
        return False, None
    inp = pair['input_full']
    old = inp.get('old_string', None)
    new = inp.get('new_string', None)
    if isinstance(old, str) and isinstance(new, str) and old == new:
        return True, f'old_string == new_string ({len(old)} chars)'
    return False, None


# Edit — line-number prefix (`\d+\t`) in old_string or new_string
def _sig_edit_prefix(pair):
    if pair['tool_name'] != 'Edit':
        return False, None
    inp = pair['input_full']
    for field in ('old_string', 'new_string'):
        val = inp.get(field, '')
        if isinstance(val, str) and re.match(r'^\s*\d+\t', val):
            return True, f'{field}={val[:60]!r}'
    return False, None


# Read — directory path (CC-native error or hook block)
def _sig_read_directory(pair):
    if pair['tool_name'] != 'Read' or not pair['is_error']:
        return False, None
    err = pair['error_text'].lower()
    if ('cannot read directories' in err
            or 'is a directory' in err
            or 'blocked: read on directory' in err):
        return True, pair['input_full'].get('file_path', '')[:INPUT_PREVIEW_CHARS]
    return False, None


# Read — oversize file (>256KB or >25k tokens)
def _sig_read_oversize(pair):
    if pair['tool_name'] != 'Read' or not pair['is_error']:
        return False, None
    err = pair['error_text']
    if ('exceeds maximum allowed size' in err
            or 'exceeds maximum allowed tokens' in err
            or 'BLOCKED: Read on oversize' in err):
        return True, pair['input_full'].get('file_path', '')[:INPUT_PREVIEW_CHARS]
    return False, None


# Worker safety — `pkill -f` or `ps ... | grep ... | kill` (cmdline-substring kill)
def _sig_dangerous_kill(pair):
    if pair['tool_name'] != 'Bash':
        return False, None
    cmd = pair['input_full'].get('command', '')
    if re.search(r'\bpkill\s+(?:-[^\s]*\s+)*-f\b', cmd):
        return True, cmd[:INPUT_PREVIEW_CHARS]
    if re.search(r'\bps\b.+\|.+\bgrep\b.+\|.+\bkill\b', cmd):
        return True, cmd[:INPUT_PREVIEW_CHARS]
    return False, None


# Git safety — `git ... commit ... --amend`
def _sig_git_amend(pair):
    if pair['tool_name'] != 'Bash':
        return False, None
    cmd = pair['input_full'].get('command', '')
    if re.search(r'\bgit\b[^|;&]*\bcommit\b[^|;&]*--amend\b', cmd):
        return True, cmd[:INPUT_PREVIEW_CHARS]
    return False, None


# Git safety — `git ... push ... --force` or `-f`
def _sig_git_force_push(pair):
    if pair['tool_name'] != 'Bash':
        return False, None
    cmd = pair['input_full'].get('command', '')
    if re.search(r'\bgit\b[^|;&]*\bpush\b[^|;&]*(?:--force\b|--force-with-lease\b)', cmd):
        return True, cmd[:INPUT_PREVIEW_CHARS]
    if re.search(r'\bgit\b[^|;&]*\bpush\b[^|;&]*\s-f\b', cmd):
        return True, cmd[:INPUT_PREVIEW_CHARS]
    return False, None


# Git safety — `--no-verify` (skip hooks on commit/push)
def _sig_git_no_verify(pair):
    if pair['tool_name'] != 'Bash':
        return False, None
    cmd = pair['input_full'].get('command', '')
    if re.search(r'\bgit\b[^|;&]*\b(commit|push)\b[^|;&]*--no-verify\b', cmd):
        return True, cmd[:INPUT_PREVIEW_CHARS]
    return False, None


# Git safety — `git config` modification (exclude read-only variants)
def _sig_git_config_modify(pair):
    if pair['tool_name'] != 'Bash':
        return False, None
    cmd = pair['input_full'].get('command', '')
    m = re.search(r'\bgit\b(?:\s+-C\s+\S+)?\s+config\b([^|;&]*)', cmd)
    if not m:
        return False, None
    rest = m.group(1)
    if re.search(r'\s--(list|get|get-all|get-regexp|show-origin|show-scope|show-keys)\b', rest):
        return False, None
    return True, cmd[:INPUT_PREVIEW_CHARS]


# Git safety — `git ... commit ... --allow-empty`
def _sig_git_empty_commit(pair):
    if pair['tool_name'] != 'Bash':
        return False, None
    cmd = pair['input_full'].get('command', '')
    if re.search(r'\bgit\b[^|;&]*\bcommit\b[^|;&]*--allow-empty\b', cmd):
        return True, cmd[:INPUT_PREVIEW_CHARS]
    return False, None


# RAG safety — direct `llama-server` start (must go through rag-cli)
def _sig_rag_llama_direct(pair):
    if pair['tool_name'] != 'Bash':
        return False, None
    cmd = pair['input_full'].get('command', '')
    if 'rag-cli' in cmd:
        return False, None
    if re.search(r'\bllama-server\b', cmd):
        return True, cmd[:INPUT_PREVIEW_CHARS]
    return False, None


# PATTERNS — single source of truth for all detection.
#
# Field meaning:
#   id:        unique pattern identifier
#   category:  hard-rule | tool-ref | cli-safety | hygiene
#   rule_num:  numbered Rule from `## Hard Rules` (optional cross-ref)
#   title:     display title
#   source:    location in tool-use.md
#   class:     hooked | hookable | hookable-heur | session-state |
#              multi-call | runtime-only | meta
#   hook:      hook filename (if class=hooked)
#   sig:       signature function (None = no static detection)
#   note:      one-line description

PATTERNS = [
    # --- Hard Rules (numbered) ---
    {'id': 'rule-01-python-iteration', 'category': 'hard-rule', 'rule_num': 1,
     'title': 'Python: heredoc for one-shot vs Write+Edit for iteration',
     'source': 'tool-use.md § Rule 1', 'class': 'meta', 'hook': None, 'sig': None,
     'note': 'Iteration-intent judgment'},
    {'id': 'rule-02-cat-heredoc', 'category': 'hard-rule', 'rule_num': 2,
     'title': 'No Bash heredoc for file creation',
     'source': 'tool-use.md § Rule 2', 'class': 'hookable', 'hook': None, 'sig': _sig_cat_heredoc,
     'note': 'cat > file << EOF (use Write tool)'},
    {'id': 'rule-03-broad-grep', 'category': 'hard-rule', 'rule_num': 3,
     'title': 'Recursive grep without --include= on broad target',
     'source': 'tool-use.md § Rule 3', 'class': 'hooked', 'hook': 'block_broad_grep.py',
     'sig': _sig_broad_grep, 'note': 'broad-scope directory scan'},
    {'id': 'rule-04-verbose-context', 'category': 'hard-rule', 'rule_num': 4,
     'title': 'Verbose output → file, signal output → context',
     'source': 'tool-use.md § Rule 4', 'class': 'meta', 'hook': None, 'sig': None,
     'note': 'Output noise-vs-signal judgment'},
    {'id': 'rule-05-stop-after-2-fails', 'category': 'hard-rule', 'rule_num': 5,
     'title': 'Stop after 2 failed tool calls',
     'source': 'tool-use.md § Rule 5', 'class': 'session-state', 'hook': None, 'sig': None,
     'note': 'Failure-history across calls'},
    {'id': 'rule-06-parallel-bash', 'category': 'hard-rule', 'rule_num': 6,
     'title': 'Parallel Bash tool_use blocks',
     'source': 'tool-use.md § Rule 6', 'class': 'runtime-only', 'hook': None,
     'sig': _sig_parallel_bash, 'note': 'CC dispatches in parallel; PreToolUse fires per-block'},
    {'id': 'rule-07-tool-failure', 'category': 'hard-rule', 'rule_num': 7,
     'title': 'Tool failure → immediate action',
     'source': 'tool-use.md § Rule 7', 'class': 'meta', 'hook': None, 'sig': None,
     'note': 'Failure-response judgment'},
    {'id': 'rule-08-persisted-output', 'category': 'hard-rule', 'rule_num': 8,
     'title': '<persisted-output> blocks: grep the full file',
     'source': 'tool-use.md § Rule 8', 'class': 'meta', 'hook': None, 'sig': None,
     'note': 'Reading-behavior on persisted-output'},
    {'id': 'rule-09-read-before-edit', 'category': 'hard-rule', 'rule_num': 9,
     'title': 'Read before Edit/Write',
     'source': 'tool-use.md § Rule 9', 'class': 'session-state', 'hook': None,
     'sig': _sig_read_before_edit, 'note': 'Read-state per file across calls'},
    {'id': 'rule-10-git-ambiguous', 'category': 'hard-rule', 'rule_num': 10,
     'title': 'Branch-name ambiguity in repos with same-named dirs',
     'source': 'tool-use.md § Rule 10', 'class': 'hookable', 'hook': None,
     'sig': _sig_git_ambiguous, 'note': 'git diff <name> when dir <name>/ exists'},
    {'id': 'rule-11-diag-and-chain', 'category': 'hard-rule', 'rule_num': 11,
     'title': 'Diagnostic Bash chain with && instead of ;',
     'source': 'tool-use.md § Rule 11', 'class': 'hookable-heur', 'hook': None,
     'sig': _sig_diag_chain, 'note': 'FP risk on legitimate prereq chains'},
    {'id': 'rule-12-sleep-noncanonical', 'category': 'hard-rule', 'rule_num': 12,
     'title': 'sleep N && X (non-canonical orchestration timer)',
     'source': 'tool-use.md § Rule 12', 'class': 'hooked', 'hook': 'block_chained_sleep.py',
     'sig': _sig_sleep_noncanonical, 'note': 'only sleep N && echo done is allowed'},
    {'id': 'rule-13-claire-typo', 'category': 'hard-rule', 'rule_num': 13,
     'title': '.claire/ typo in worktree path',
     'source': 'tool-use.md § Rule 13', 'class': 'hookable', 'hook': None,
     'sig': _sig_claire_typo, 'note': 'tokenizer typo of .claude/'},
    {'id': 'rule-13-double-dot', 'category': 'hard-rule', 'rule_num': 13,
     'title': '..letter double-dot path typo',
     'source': 'tool-use.md § Rule 13 (same-class)', 'class': 'hookable', 'hook': None,
     'sig': _sig_double_dot, 'note': '..claude/ etc. — two dots followed by lowercase letter'},
    {'id': 'rule-14-bg-trivial', 'category': 'hard-rule', 'rule_num': 14,
     'title': 'Trivial read-only command run_in_background=True',
     'source': 'tool-use.md § Rule 14', 'class': 'hooked',
     'hook': 'block_unauthorized_background.py', 'sig': _sig_bg_trivial,
     'note': 'grep/cat/ls/wc/git status etc. must be foreground'},
    {'id': 'rule-15-zsh-quoting', 'category': 'hard-rule', 'rule_num': 15,
     'title': 'zsh quoting for repeated path calls',
     'source': 'tool-use.md § Rule 15', 'class': 'multi-call', 'hook': None, 'sig': None,
     'note': 'requires comparing path usage across calls'},
    {'id': 'rule-16-cd-drift', 'category': 'hard-rule', 'rule_num': 16,
     'title': 'cd-drift across Bash calls',
     'source': 'tool-use.md § Rule 16', 'class': 'multi-call', 'hook': None, 'sig': None,
     'note': 'requires tracking cwd across calls'},

    # --- Tool-Specific Reference ---
    {'id': 'tool-edit-noop', 'category': 'tool-ref', 'rule_num': None,
     'title': 'Edit with identical old_string and new_string',
     'source': 'tool-use.md § Edit (Noop edit)', 'class': 'hooked',
     'hook': 'block_noop_edit.py', 'sig': _sig_noop_edit,
     'note': 'CC rejects with "No changes to make"'},
    {'id': 'tool-edit-prefix-line', 'category': 'tool-ref', 'rule_num': None,
     'title': 'Edit with `\\d+\\t` line-number prefix in old/new_string',
     'source': 'tool-use.md § Edit (Indentation)', 'class': 'hookable', 'hook': None,
     'sig': _sig_edit_prefix, 'note': 'cat -n prefix must be stripped before Edit'},
    {'id': 'tool-read-directory', 'category': 'tool-ref', 'rule_num': None,
     'title': 'Read tool on directory path',
     'source': 'tool-use.md § Read (Directories)', 'class': 'hooked',
     'hook': 'block_read_directory.py', 'sig': _sig_read_directory,
     'note': 'Read cannot read directories — use ls'},
    {'id': 'tool-read-oversize', 'category': 'tool-ref', 'rule_num': None,
     'title': 'Read on file > 256KB / > 25k tokens',
     'source': 'tool-use.md § Read (256KB / 25k-token limit)', 'class': 'hooked',
     'hook': 'block_read_oversize.py', 'sig': _sig_read_oversize,
     'note': 'use grep + offset/limit Read instead'},
    {'id': 'tool-write-md-readme', 'category': 'tool-ref', 'rule_num': None,
     'title': 'Write *.md/README files without explicit user request',
     'source': 'tool-use.md § Write (No docs)', 'class': 'meta', 'hook': None, 'sig': None,
     'note': 'requires user-intent classification'},

    # --- CLI Safety (Worker / Git / RAG) ---
    {'id': 'cli-worker-kill-substring', 'category': 'cli-safety', 'rule_num': None,
     'title': 'pkill -f / ps|grep|kill (cmdline-substring kills workers)',
     'source': 'tool-use.md § Worker CLI (May-12 session)', 'class': 'hooked',
     'hook': 'block_dangerous_kill.py', 'sig': _sig_dangerous_kill,
     'note': 'kills worker processes whose prompt text contains the pattern'},
    {'id': 'cli-git-amend', 'category': 'cli-safety', 'rule_num': None,
     'title': 'git commit --amend',
     'source': 'tool-use.md § Git CLI § Safety Protocol', 'class': 'hookable', 'hook': None,
     'sig': _sig_git_amend, 'note': 'never amend existing commits'},
    {'id': 'cli-git-force-push', 'category': 'cli-safety', 'rule_num': None,
     'title': 'git push --force (and --force-with-lease, -f)',
     'source': 'tool-use.md § Git CLI § Safety Protocol', 'class': 'hookable', 'hook': None,
     'sig': _sig_git_force_push, 'note': 'never force push'},
    {'id': 'cli-git-no-verify', 'category': 'cli-safety', 'rule_num': None,
     'title': 'git --no-verify (skip hooks)',
     'source': 'tool-use.md § Git CLI § Safety Protocol', 'class': 'hookable', 'hook': None,
     'sig': _sig_git_no_verify, 'note': 'never skip hooks'},
    {'id': 'cli-git-config-modify', 'category': 'cli-safety', 'rule_num': None,
     'title': 'git config (modify, not --list/--get)',
     'source': 'tool-use.md § Git CLI § Safety Protocol', 'class': 'hookable', 'hook': None,
     'sig': _sig_git_config_modify, 'note': 'never modify git config'},
    {'id': 'cli-git-empty-commit', 'category': 'cli-safety', 'rule_num': None,
     'title': 'git commit --allow-empty',
     'source': 'tool-use.md § Git CLI § Safety Protocol', 'class': 'hookable', 'hook': None,
     'sig': _sig_git_empty_commit, 'note': 'never create empty commits'},
    {'id': 'cli-rag-llama-direct', 'category': 'cli-safety', 'rule_num': None,
     'title': 'llama-server direct start (bypass rag-cli)',
     'source': 'tool-use.md § RAG CLI § Rules', 'class': 'hookable', 'hook': None,
     'sig': _sig_rag_llama_direct, 'note': 'use rag-cli server start <preset>'},
    {'id': 'cli-rag-kill-gpu', 'category': 'cli-safety', 'rule_num': None,
     'title': 'kill GPU process outside rag-cli',
     'source': 'tool-use.md § RAG CLI § Rules', 'class': 'meta', 'hook': None, 'sig': None,
     'note': 'requires PID-to-process classification'},

    # --- Hygiene (Rule 4 sub-bullets) ---
    {'id': 'hygiene-venv-no-redirect', 'category': 'hygiene', 'rule_num': 4,
     'title': './venv/bin/python script.py without `> /tmp/file.md 2>&1` redirect',
     'source': 'tool-use.md § Rule 4 (sub)', 'class': 'hookable', 'hook': None,
     'sig': _sig_venv_python_no_redirect, 'note': 'noisy script output pollutes context'},
]

CATEGORY_ORDER = ['hard-rule', 'tool-ref', 'cli-safety', 'hygiene']
CLASS_ORDER = ['hooked', 'hookable', 'hookable-heur', 'session-state',
               'multi-call', 'runtime-only', 'meta']


# ORCHESTRATOR

def rule_compliance_workflow(proxy_paths, output_path):
    events_by_log = {}
    for path in proxy_paths:
        events_by_log[path] = _load_proxy(path)

    tool_uses = {}
    tool_results = {}
    for path, events in events_by_log.items():
        label = _log_label(path)
        _collect_tool_uses(events, label, tool_uses)
        _collect_tool_results(events, tool_results)

    pairs = _build_pairs(tool_uses, tool_results)
    violations, uncategorized = _run_signatures(pairs)
    report = _build_report(proxy_paths, events_by_log, tool_uses, pairs,
                           violations, uncategorized)
    _write_output(report, output_path)


# FUNCTIONS

# Load proxy JSONL — only entries with raw_payload
def _load_proxy(path):
    events = []
    with open(path, encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                d = json.loads(line)
            except json.JSONDecodeError:
                continue
            if d.get('raw_payload') is None:
                continue
            d['_path'] = path
            events.append(d)
    return events


# Build session label from log filename (opus / worker:<name>)
def _log_label(path):
    base = os.path.basename(path)
    if base.startswith('api_requests_worker_'):
        name = base.replace('api_requests_worker_', '').rsplit('_', 1)[0]
        return f'worker:{name}'
    if base.startswith('api_requests_opus_'):
        return 'opus'
    return base


# Collect all tool_use blocks — deduped by id, stores full input dict
def _collect_tool_uses(events, label, out):
    for ev in events:
        ts = ev.get('timestamp', '')
        for msg in ev.get('raw_payload', {}).get('messages', []):
            content = msg.get('content', [])
            if not isinstance(content, list):
                continue
            for blk in content:
                if not isinstance(blk, dict) or blk.get('type') != 'tool_use':
                    continue
                bid = blk.get('id', '')
                if not bid or bid in out:
                    continue
                inp = blk.get('input', {})
                inp_str = json.dumps(inp)
                out[bid] = {
                    'name': blk.get('name', ''),
                    'input_full': inp,
                    'input_preview': inp_str[:INPUT_PREVIEW_CHARS],
                    'ts': ts,
                    'label': label,
                }


# Collect all tool_result blocks — deduped by tool_use_id
def _collect_tool_results(events, out):
    for ev in events:
        for msg in ev.get('raw_payload', {}).get('messages', []):
            content = msg.get('content', [])
            if not isinstance(content, list):
                continue
            for blk in content:
                if not isinstance(blk, dict) or blk.get('type') != 'tool_result':
                    continue
                tid = blk.get('tool_use_id', '')
                if not tid or tid in out:
                    continue
                raw_c = blk.get('content', '')
                text = raw_c if isinstance(raw_c, str) else json.dumps(raw_c)
                out[tid] = {'is_error': bool(blk.get('is_error', False)), 'text': text}


# Join tool_use + tool_result into unified pair dicts — ALL tool_uses included
def _build_pairs(tool_uses, tool_results):
    pairs = []
    for bid, tu in tool_uses.items():
        tr = tool_results.get(bid, {})
        pairs.append({
            'bid': bid,
            'tool_name': tu['name'],
            'label': tu['label'],
            'ts': tu['ts'],
            'input_full': tu['input_full'],
            'input_preview': tu['input_preview'],
            'is_error': tr.get('is_error', False),
            'error_text': tr.get('text', ''),
        })
    pairs.sort(key=lambda x: (x['label'], x['ts']))
    return pairs


# Run all signatures against each pair — violations by pattern id + uncategorized failures
def _run_signatures(pairs):
    violations = defaultdict(list)
    uncategorized = []
    for pair in pairs:
        matched = []
        for pat in PATTERNS:
            sig = pat.get('sig')
            if sig is None:
                continue
            hit, evidence = sig(pair)
            if hit:
                matched.append(pat['id'])
                violations[pat['id']].append({
                    'pattern_id': pat['id'],
                    'tool_name': pair['tool_name'],
                    'label': pair['label'],
                    'ts': pair['ts'],
                    'input_preview': pair['input_preview'],
                    'error_text': pair['error_text'],
                    'evidence': evidence or '',
                })
        if pair['is_error'] and not matched:
            uncategorized.append(pair)
    return violations, uncategorized


# Render full Markdown compliance report
def _build_report(proxy_paths, events_by_log, tool_uses, pairs, violations, uncategorized):
    now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    L = [f'# Rule Compliance Analysis — {now}', '', '## Source JSONLs', '']
    total_tu = len(tool_uses)
    for path in proxy_paths:
        label = _log_label(path)
        tu_count = sum(1 for tu in tool_uses.values() if tu['label'] == label)
        L.append(f'- `{os.path.basename(path)}` ({len(events_by_log.get(path, []))} events, '
                 f'{tu_count} tool_use) — `{label}`')

    total_fail = sum(1 for p in pairs if p['is_error'])
    patterns_with_sig = sum(1 for p in PATTERNS if p.get('sig'))
    patterns_violated = sum(1 for p in PATTERNS if violations.get(p['id']))
    L += ['', '## Summary', '',
          f'- Total tool_use blocks: {total_tu}',
          f'- Failures (is_error=True): {total_fail}',
          f'- Patterns checked (with signature): {patterns_with_sig} / {len(PATTERNS)}',
          f'- Patterns with violations: {patterns_violated}',
          f'- Uncategorized failures: {len(uncategorized)}', '']

    # Coverage Overview
    L += ['## Coverage Overview', '',
          '| Category | Total | Hooked | Hookable | Hookable-Heur | Other |',
          '|----------|-------|--------|----------|---------------|-------|']
    for cat in CATEGORY_ORDER:
        cat_pats = [p for p in PATTERNS if p['category'] == cat]
        if not cat_pats:
            continue
        cnt = {c: sum(1 for p in cat_pats if p['class'] == c) for c in CLASS_ORDER}
        other = sum(cnt[c] for c in CLASS_ORDER
                    if c not in ('hooked', 'hookable', 'hookable-heur'))
        L.append(f'| {cat} | {len(cat_pats)} | {cnt["hooked"]} | {cnt["hookable"]} | '
                 f'{cnt["hookable-heur"]} | {other} |')
    L.append('')

    L += ['Live hooks (in `src/hooks/`):', '']
    for pat in PATTERNS:
        if pat['class'] == 'hooked' and pat.get('hook'):
            vc = len(violations.get(pat['id'], []))
            L.append(f'- `{pat["hook"]}` — {pat["title"]} ({vc} violations in this log set)')
    L.append('')

    L += ['Hook migration candidates (hookable, no hook yet):', '']
    for pat in PATTERNS:
        if pat['class'] == 'hookable' and not pat.get('hook'):
            vc = len(violations.get(pat['id'], []))
            L.append(f'- `{pat["id"]}` — {pat["title"]} ({vc} violations) — {pat["source"]}')
    L.append('')

    L += ['Not statically detectable from a single PreToolUse payload:', '']
    for pat in PATTERNS:
        if pat['class'] in ('session-state', 'multi-call', 'runtime-only', 'meta'):
            L.append(f'- `{pat["id"]}` ({pat["class"]}) — {pat["title"]}')
    L.append('')

    # Per-Pattern Compliance (grouped by category)
    L += ['## Per-Pattern Compliance', '']
    for cat in CATEGORY_ORDER:
        cat_pats = [p for p in PATTERNS if p['category'] == cat]
        if not cat_pats:
            continue
        L += [f'### {cat}', '',
              '| ID | Title | Class | Hook | Violations | Sample |',
              '|----|-------|-------|------|------------|--------|']
        for pat in cat_pats:
            cls = pat['class']
            hook_cell = f'`{pat["hook"]}`' if pat.get('hook') else '—'
            title = pat['title'][:55]
            if not pat.get('sig'):
                L.append(f'| {pat["id"]} | {title} | {cls} | {hook_cell} | — | *(no signature)* |')
                continue
            vlist = violations.get(pat['id'], [])
            if vlist:
                v0 = vlist[0]
                sample = (f'`{v0["tool_name"]}` '
                          f'{v0["evidence"][:30].replace(chr(10), " ").replace("|", "｜")}')
                L.append(f'| {pat["id"]} | {title} | {cls} | {hook_cell} | '
                         f'⚠ {len(vlist)} | {sample} |')
            else:
                L.append(f'| {pat["id"]} | {title} | {cls} | {hook_cell} | ✅ 0 | — |')
        L.append('')

    # Violations Detail
    L += ['## Violations Detail', '']
    any_v = False
    for cat in CATEGORY_ORDER:
        cat_pats = [p for p in PATTERNS if p['category'] == cat]
        cat_violated = [p for p in cat_pats if violations.get(p['id'])]
        if not cat_violated:
            continue
        L += [f'### {cat}', '']
        for pat in cat_violated:
            any_v = True
            vlist = violations[pat['id']]
            L += [f'#### `{pat["id"]}` — {pat["title"]}', '',
                  f'> {pat["note"]} ({pat["source"]})', '',
                  f'**Violations ({len(vlist)}):**', '']
            for i, v in enumerate(vlist, 1):
                ts = _format_ts_local(v['ts'])
                L += [f'**[{i}] {v["label"]} — {ts} — {v["tool_name"]}**', '']
                if v['input_preview']:
                    L.append(f'- Input: `{v["input_preview"]}`')
                if v['evidence'] and v['evidence'] != v['input_preview']:
                    L.append(f'- Evidence: `{v["evidence"][:120]}`')
                if v['error_text']:
                    err = v['error_text'][:ERROR_PREVIEW_CHARS].replace('\n', ' ')
                    L.append(f'- Error: `{err}`')
                else:
                    L.append('- Error: *(call succeeded — input-based violation)*')
                L.append('')
            L += ['---', '']
    if not any_v:
        L += ['*No violations detected.*', '', '---', '']

    # Hook Coverage Gaps (most actionable section)
    L += ['## Hook Coverage Gaps', '',
          'Patterns with ≥ 1 violation in this log set AND no live hook AND '
          'class ∈ {hookable, hookable-heur}:', '']
    gaps = [p for p in PATTERNS
            if p['class'] in ('hookable', 'hookable-heur')
            and not p.get('hook')
            and violations.get(p['id'])]
    if gaps:
        for pat in sorted(gaps, key=lambda x: -len(violations[x['id']])):
            vc = len(violations[pat['id']])
            tag = ' [heuristic]' if pat['class'] == 'hookable-heur' else ''
            L.append(f'- **{pat["id"]}**{tag} — {vc} violations — {pat["title"]}')
    else:
        L.append('*No hook gaps in this log set.*')
    L.append('')

    # Uncategorized failures
    L += ['## Uncategorized Failures', '']
    if uncategorized:
        L.append(f'{len(uncategorized)} failure(s) not matched by any pattern — '
                 f'candidates for new signatures.')
        L.append('')
        for i, p in enumerate(uncategorized, 1):
            ts = _format_ts_local(p['ts'])
            L += [f'### [{i}] {p["tool_name"]} — {p["label"]} — {ts}', '']
            if p['input_preview']:
                L.append(f'- Input: `{p["input_preview"]}`')
            L.append(f'- Error: `{p["error_text"][:ERROR_PREVIEW_CHARS].replace(chr(10), " ")}`')
            L.append('')
    else:
        L += ['*All failures matched at least one pattern.*', '']

    return '\n'.join(L)


# Convert UTC ISO timestamp to local HH:MM:SS
def _format_ts_local(ts_str):
    if not ts_str:
        return '?'
    try:
        dt = datetime.fromisoformat(ts_str.replace('Z', '+00:00'))
        return dt.astimezone().strftime('%H:%M:%S')
    except Exception:
        return ts_str[:19]


# Write report to file or stdout
def _write_output(content, path):
    if path:
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        with open(path, 'w', encoding='utf-8') as f:
            f.write(content)
        print(f'Report written to: {path}', file=sys.stderr)
    else:
        print(content)


def _parse_args():
    p = argparse.ArgumentParser(
        description='Match proxy JSONL tool calls against strict prohibitions in tool-use.md.'
    )
    p.add_argument('proxy_jsonl', nargs='*',
                   help='Path(s) to Proxy JSONL file(s) under src/logs/')
    p.add_argument('--input-glob', default=None, metavar='GLOB',
                   help='Glob pattern (e.g. "src/logs/api_requests_*.jsonl"); '
                        'expanded in addition to positional paths')
    p.add_argument('--output', default=None, metavar='FILE',
                   help='Output markdown file path (default: stdout)')
    return p.parse_args()


if __name__ == '__main__':
    args = _parse_args()
    paths = list(args.proxy_jsonl)
    if args.input_glob:
        paths.extend(sorted(_glob.glob(os.path.expanduser(args.input_glob))))
    paths = sorted(set(paths))
    if not paths:
        sys.exit('ERROR: no JSONL paths provided (positional or --input-glob)')
    rule_compliance_workflow(paths, args.output)
