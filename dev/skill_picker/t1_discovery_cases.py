# INFRASTRUCTURE
import json
import shutil
import tempfile
from pathlib import Path

from dev.skill_picker.t1_fixtures import _REAL_SHAPED_FULL, _Logs, _imp, _make_claude_dir, _make_plugin, _make_project, _skill_md, _write

# FUNCTIONS

def _case_discovery_plugins() -> str:
    sd = _imp('skill_discovery')
    root = Path(tempfile.mkdtemp(prefix='skillpicker_'))
    claude = _make_claude_dir(root)
    with _Logs(sd) as logs:
        skills = sd.discover_skills_workflow('', claude)
    full = sorted(s.full for s in skills)
    assert full == sorted(_REAL_SHAPED_FULL), f'full names {full}'
    assert all(s.source == 'plugin' for s in skills)
    assert not any('off-plugin' in s.full for s in skills), 'disabled plugin listed'
    assert logs == [], f'a plugin with neither manifest nor skills/ directory must be skipped silently, logs {logs}'
    shutil.rmtree(root)
    return '8 plugin skills, disabled plugin absent, pyright-like plugin (no manifest, no skills/ directory) skipped without a log line'

def _case_discovery_manifest_missing() -> str:
    sd = _imp('skill_discovery')
    root = Path(tempfile.mkdtemp(prefix='skillpicker_'))
    claude = root / 'dotclaude'
    with_dir = claude / 'plugins' / 'cache' / 'withdir'
    _skill_md(with_dir / 'skills' / 'some-skill' / 'SKILL.md', 'some-skill')
    bare = claude / 'plugins' / 'cache' / 'bare'
    (bare).mkdir(parents=True)
    _write(bare / 'README.md', 'no manifest, no skills')
    _write(claude / 'settings.json', json.dumps({'enabledPlugins': {'withdir@m': True, 'bare@m': True}}))
    ent = lambda p: [{'scope': 'user', 'installPath': str(p)}]
    _write(claude / 'plugins' / 'installed_plugins.json', json.dumps({'plugins': {
        'withdir@m': ent(with_dir), 'bare@m': ent(bare)}}))
    with _Logs(sd) as logs:
        skills = sd.discover_skills_workflow('', claude)
    assert skills == [], f'skills {skills}'
    assert logs == [('skill', 'FAILED plugin=withdir@m reason=manifest_missing')], f'logs {logs}'
    shutil.rmtree(root)
    return f'no manifest + skills/ directory -> {logs[0][1]}; no manifest + no skills/ directory -> skipped silently'

def _case_discovery_tripwires() -> str:
    sd = _imp('skill_discovery')
    root = Path(tempfile.mkdtemp(prefix='skillpicker_'))
    claude = root / 'dotclaude'
    noarr = _make_plugin(claude, 'noarr', {'name': 'noarr'}, {})
    noname = _make_plugin(claude, 'noname', {'skills': ['./skills/x/']}, {'skills/x': 'x'})
    missing = _make_plugin(claude, 'miss', {'name': 'miss', 'skills': ['./skills/gone/', './skills/here/']},
                           {'skills/here': None})
    default_only = _make_plugin(claude, 'defonly', {'name': 'defonly'}, {'skills/hidden': 'hidden'})
    _write(claude / 'settings.json', json.dumps({'enabledPlugins': {
        'noarr@m': True, 'noname@m': True, 'miss@m': True, 'defonly@m': True, 'ghost@m': True}}))
    ent = lambda p: [{'scope': 'user', 'installPath': str(p)}]
    _write(claude / 'plugins' / 'installed_plugins.json', json.dumps({'plugins': {
        'noarr@m': ent(noarr), 'noname@m': ent(noname), 'miss@m': ent(missing), 'defonly@m': ent(default_only)}}))
    with _Logs(sd) as logs:
        skills = sd.discover_skills_workflow('', claude)
    assert [s.full for s in skills] == ['miss:here'], f'skills {[s.full for s in skills]}'
    msgs = sorted(m for _, m in logs)
    want = sorted([
        'FAILED plugin=defonly@m reason=no_skills_array',
        'FAILED plugin=ghost@m reason=not_installed',
        'FAILED plugin=miss@m reason=skill_file_missing entry=./skills/gone/',
        'FAILED plugin=noarr@m reason=no_skills_array',
        'FAILED plugin=noname@m reason=manifest_name_missing',
    ])
    assert msgs == want, f'logs {msgs}'
    broken = root / 'broken'
    _write(broken / 'settings.json', '{not json')
    with _Logs(sd) as logs2:
        assert sd.discover_skills_workflow('', broken) == []
    assert len(logs2) == 1 and 'settings_unreadable' in logs2[0][1], logs2
    shutil.rmtree(root)
    return 'no skills array (also for a plugin with only a default skills/ folder), no name, missing skill file, not installed, unreadable settings: each logged FAILED and skipped'

def _case_discovery_names() -> str:
    sd = _imp('skill_discovery')
    root = Path(tempfile.mkdtemp(prefix='skillpicker_'))
    claude = root / 'dotclaude'
    plug = _make_plugin(claude, 'p', {'name': 'realname', 'skills': [
        './skills/dirA/', './skills/dirB/', './skills/dirC/']},
        {'skills/dirA': 'labelA', 'skills/dirB': '', 'skills/dirC': None})
    _write(plug / 'skills' / 'dirD' / 'SKILL.md', '# no frontmatter at all\n')
    manifest = json.loads((plug / '.claude-plugin' / 'plugin.json').read_text())
    manifest['skills'].append('./skills/dirD/')
    _write(plug / '.claude-plugin' / 'plugin.json', json.dumps(manifest))
    _write(claude / 'settings.json', json.dumps({'enabledPlugins': {'keyprefix@m': True}}))
    _write(claude / 'plugins' / 'installed_plugins.json', json.dumps({'plugins': {
        'keyprefix@m': [{'scope': 'local', 'projectPath': '/x', 'installPath': '/nonexistent'},
                        {'scope': 'user', 'installPath': str(plug)}]}}))
    with _Logs(sd):
        skills = sd.discover_skills_workflow('', claude)
    got = [(s.short, s.full) for s in skills]
    assert got == [('labelA', 'realname:labelA'), ('dirB', 'realname:dirB'),
                   ('dirC', 'realname:dirC'), ('dirD', 'realname:dirD')], f'got {got}'
    shutil.rmtree(root)
    return f'plugin name from manifest (not key), frontmatter name else dir name, user scope entry preferred: {got}'

def _case_discovery_project_personal() -> str:
    sd = _imp('skill_discovery')
    root = Path(tempfile.mkdtemp(prefix='skillpicker_'))
    claude = _make_claude_dir(root)
    _skill_md(claude / 'skills' / 'mine' / 'SKILL.md', 'Pretty Label')
    general = _make_project(root, 'general', {'penny': 'penny', 'wise2627-tracker': 'wise2627-tracker', 'x-dir': 'Different Label'})
    (Path(general) / '.claude' / 'skills' / 'no-skill-file').mkdir()
    other = _make_project(root, 'other', {})
    with _Logs(sd):
        in_general = sd.discover_skills_workflow(general, claude)
        in_other = sd.discover_skills_workflow(other, claude)
        in_none = sd.discover_skills_workflow('', claude)
    proj = [(s.short, s.full) for s in in_general if s.source == 'project']
    assert proj == [('penny', 'penny'), ('wise2627-tracker', 'wise2627-tracker'), ('x-dir', 'x-dir')], f'project {proj}'
    pers = [(s.short, s.full) for s in in_general if s.source == 'personal']
    assert pers == [('mine', 'mine')], f'personal {pers} (synced folder without SKILL.md must not appear)'
    assert not any(s.source == 'project' for s in in_other), 'project skills leaked into another project'
    assert not any(s.source == 'project' for s in in_none)
    assert [s.source for s in in_general] == ['project'] * 3 + ['personal'] + ['plugin'] * 8, 'group order'
    shutil.rmtree(root)
    return f'project {proj}; personal {pers}; other project and empty cwd see no project skills; order project, personal, plugin'
