# INFRASTRUCTURE
import re

# Recognizable command prefixes for Section 6 wrapper name generation (skip if absent)
# echo excluded: second token is always quoted content, never a meaningful subcommand
KNOWN_PREFIXES = frozenset({
    'worker-cli', 'git', 'bd', 'ls', 'cat', 'python3', 'python',
    'head', 'grep', 'jq', 'find',
})

# FUNCTIONS

# Classify wrapper complexity from signature features
def _classify_complexity(sig, tool):
    if tool == 'Bash':
        # Heredoc / inline Python → structural (use Write+script instead)
        if '<<' in sig or "python3 << '" in sig or 'python3 -c' in sig:
            return 'structural'
        if any(op in sig for op in ('|', '&&', '||')):
            return 'medium'
        if 'bd ' in sig or '<BEAD_ID>' in sig:
            return 'medium'
    return 'trivial'


# Derive proposed wrapper name from signature tokens and tool
def _derive_wrapper_name(sig, tool):
    # Skip past shell variable assignments (VAR=... or VAR=$(...)
    s = re.sub(r'^[A-Z_][A-Z0-9_]*=\S*\s*', '', sig).strip()
    tokens = s.split()
    if not tokens:
        return f'{tool.lower()}-wrapper'
    first = tokens[0].lower().rstrip('/').split('(')[0]  # strip shell subshell openers
    # Remove placeholder markers from name
    first = re.sub(r'[<>\$"\']', '', first).strip('-').strip()
    if not first:
        return f'{tool.lower()}-wrapper'
    for alias in ('./venv/bin/python', './venv/bin/python3', 'python3', 'python'):
        if first == alias:
            first = 'python'
            break
    if first == 'worker-cli' and len(tokens) > 1:
        return f'worker-{tokens[1]}'
    # Only extract subcmd for tools with actual meaningful subcommands (not content-bearing tokens)
    if first in ('git', 'bd', 'grep', 'find', 'jq') and len(tokens) > 1:
        subcmd = re.sub(r'[<>\$"\']', '', tokens[1]).strip('-').strip()
        if subcmd and not subcmd.startswith('<'):
            return f'{first}-{subcmd}'
    return f'{first}-wrapper'


# Extract first recognizable command token from a normalized signature
def _first_command_token(sig):
    s = re.sub(r'^[A-Z_][A-Z0-9_]*=\S*\s*', '', sig).strip()
    tokens = s.split()
    if not tokens:
        return ''
    first = tokens[0].lower().rstrip('/').split('(')[0]
    first = re.sub(r'[<>\$"\']', '', first).strip('-').strip()
    for alias in ('./venv/bin/python', './venv/bin/python3'):
        if first == alias:
            return 'python3'
    return first


# Build the ranked, deduped wrapper-candidate list (score-weighted by complexity)
def _build_wrapper_candidates(waste_groups, failed_groups):
    WEIGHT = {'trivial': 1, 'medium': 2, 'structural': 4}
    candidates = []

    # ct tools already absent from waste_groups; also skip any residual worker_send entries
    SKIP_TOOLS = {'Write', 'Edit', 'mcp__plugin_iterative-dev_iterative-dev__worker_send'}
    for (tool, sig), g in waste_groups.items():
        if g['total_input'] < 100:
            continue
        if tool in SKIP_TOOLS:
            continue
        # Skip candidates whose first command token is not in known prefixes (garbage names)
        if _first_command_token(sig) not in KNOWN_PREFIXES:
            continue
        cplx  = _classify_complexity(sig, tool)
        name  = _derive_wrapper_name(sig, tool)
        score = g['total_input'] / WEIGHT[cplx]
        candidates.append({'name': name, 'sig': sig, 'tool': tool,
                           'count': g['count'], 'total_input': g['total_input'],
                           'complexity': cplx, 'score': score, 'is_failure': False})

    for (tool, sig, etype), g in failed_groups.items():
        if _first_command_token(sig) not in KNOWN_PREFIXES:
            continue
        cplx  = 'structural' if etype in ('tool-unavailable', 'parallel-cancel') else 'medium'
        name  = _derive_wrapper_name(sig, tool) + '-fix'
        score = g['total_input'] / WEIGHT[cplx]
        candidates.append({'name': name, 'sig': sig, 'tool': tool,
                           'count': g['count'], 'total_input': g['total_input'],
                           'complexity': cplx, 'score': score, 'is_failure': True,
                           'error_type': etype})

    seen: dict = {}
    for c in candidates:
        if c['name'] not in seen or c['score'] > seen[c['name']]['score']:
            seen[c['name']] = c
    return sorted(seen.values(), key=lambda x: -x['score'])[:8]
