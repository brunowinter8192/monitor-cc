# INFRASTRUCTURE
import importlib
import sys
from datetime import datetime
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_ROOT))

from dev.session_launcher.test_env import isolate_home

_REAL_CLAUDE_DIR = Path.home() / '.claude'
_REPORT = Path(__file__).resolve().parent / 'md' / 'p1_real_discovery.md'
_CWDS = (
    '/Users/brunowinter2000/Documents/general',
    '/Users/brunowinter2000/Documents/ai/monitor-cc',
)

# ORCHESTRATOR

def main() -> None:
    home = isolate_home()
    sd = importlib.import_module('src.menubar.skill_discovery')
    log_mod = importlib.import_module('src.menubar.menubar_log')
    sections = [_section(sd, cwd) for cwd in _CWDS]
    log_text = log_mod.MENUBAR_LOG.read_text() if log_mod.MENUBAR_LOG.exists() else '(no log lines)'
    text = _build_report(sections, log_text)
    _REPORT.parent.mkdir(parents=True, exist_ok=True)
    _REPORT.write_text(text, encoding='utf-8')
    print(text)

# FUNCTIONS

def _section(sd, cwd: str) -> str:
    skills = sd.discover_skills_workflow(cwd, _REAL_CLAUDE_DIR)
    lines = [f'### cwd {cwd}', '', '| short | inserted text | source |', '|---|---|---|']
    for s in skills:
        lines.append(f'| {s.short} | Aktiviere den Skill {s.full}. | {s.source} |')
    lines.append('')
    return '\n'.join(lines)

def _build_report(sections, log_text: str) -> str:
    head = ['# p1_real_discovery report', '', f'- time: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}',
            f'- read-only against {_REAL_CLAUDE_DIR}; HOME is isolated so log lines go to a temp file, nothing is typed anywhere', '']
    tail = ['## Log lines the picker wrote during these discoveries (temp log)', '', '```', log_text.rstrip(), '```', '']
    return '\n'.join(head + sections + tail)

if __name__ == '__main__':
    main()
