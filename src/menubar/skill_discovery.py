# INFRASTRUCTURE
import json
from pathlib import Path
from typing import List, NamedTuple

from .menubar_log import log_menubar

CLAUDE_DIR = Path.home() / '.claude'

_SKILL_FILE = 'SKILL.md'
_MANIFEST_PATH = Path('.claude-plugin') / 'plugin.json'
_SOURCE_PROJECT = 'project'
_SOURCE_PERSONAL = 'personal'
_SOURCE_PLUGIN = 'plugin'

class Skill(NamedTuple):
    short: str
    full: str
    source: str

# ORCHESTRATOR

def discover_skills_workflow(cwd: str, claude_dir: Path = CLAUDE_DIR) -> List[Skill]:
    project = _project_skills(cwd)
    personal = _dir_skills(claude_dir / 'skills', _SOURCE_PERSONAL)
    plugin = _plugin_skills(claude_dir)
    return project + personal + plugin

# FUNCTIONS

class PluginProblem(Exception):
    pass

def _dir_skills(skills_root: Path, source: str) -> List[Skill]:
    if not skills_root.is_dir():
        return []
    return [Skill(d.name, d.name, source)
            for d in sorted(skills_root.iterdir())
            if d.is_dir() and (d / _SKILL_FILE).is_file()]

def _project_skills(cwd: str) -> List[Skill]:
    if not cwd:
        return []
    return _dir_skills(Path(cwd) / '.claude' / 'skills', _SOURCE_PROJECT)

def _read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding='utf-8'))

def _enabled_plugin_keys(claude_dir: Path) -> List[str]:
    try:
        enabled = _read_json(claude_dir / 'settings.json').get('enabledPlugins', {})
    except Exception as exc:
        log_menubar('skill', f'FAILED settings_unreadable detail={exc!r}')
        return []
    return sorted(key for key, on in enabled.items() if on is True)

def _plugin_skills(claude_dir: Path) -> List[Skill]:
    keys = _enabled_plugin_keys(claude_dir)
    if not keys:
        return []
    try:
        installed = _read_json(claude_dir / 'plugins' / 'installed_plugins.json').get('plugins', {})
    except Exception as exc:
        log_menubar('skill', f'FAILED installed_plugins_unreadable detail={exc!r}')
        return []
    skills: List[Skill] = []
    for key in keys:
        skills.extend(_skills_of_plugin_logged(key, installed))
    return skills

def _skills_of_plugin_logged(key: str, installed: dict) -> List[Skill]:
    try:
        return _skills_of_plugin(key, installed)
    except PluginProblem as problem:
        log_menubar('skill', f'FAILED plugin={key} reason={problem}')
    except Exception as exc:
        log_menubar('skill', f'FAILED plugin={key} reason=unexpected detail={exc!r}')
    return []

def _install_path(key: str, installed: dict) -> Path:
    entries = installed.get(key) or []
    if not entries:
        raise PluginProblem('not_installed')
    user_entries = [e for e in entries if e.get('scope') == 'user']
    return Path((user_entries or entries)[0]['installPath'])

def _skills_of_plugin(key: str, installed: dict) -> List[Skill]:
    install_path = _install_path(key, installed)
    manifest_file = install_path / _MANIFEST_PATH
    if not manifest_file.is_file():
        if (install_path / 'skills').is_dir():
            raise PluginProblem('manifest_missing')
        return []
    manifest = _read_json(manifest_file)
    plugin_name = manifest.get('name')
    if not plugin_name:
        raise PluginProblem('manifest_name_missing')
    entries = manifest.get('skills')
    if not isinstance(entries, list):
        raise PluginProblem('no_skills_array')
    skills = []
    for entry in entries:
        skill_file = (install_path / entry / _SKILL_FILE).resolve()
        if not skill_file.is_file():
            log_menubar('skill', f'FAILED plugin={key} reason=skill_file_missing entry={entry}')
            continue
        short = _frontmatter_name(skill_file) or skill_file.parent.name
        skills.append(Skill(short, f'{plugin_name}:{short}', _SOURCE_PLUGIN))
    return skills

def _frontmatter_name(skill_file: Path) -> str:
    lines = skill_file.read_text(encoding='utf-8', errors='replace').splitlines()
    if not lines or lines[0].strip() != '---':
        return ''
    for line in lines[1:]:
        if line.strip() == '---':
            return ''
        if line.startswith('name:'):
            return line[len('name:'):].strip().strip('"\'')
    return ''
