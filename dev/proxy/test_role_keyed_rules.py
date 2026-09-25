#!/usr/bin/env python3

# INFRASTRUCTURE
import json
import shutil
import sys
import os
import tempfile
from contextlib import contextmanager
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_ROOT / 'src'))
sys.path.insert(0, str(_ROOT))
from dev.refactoring.live_log_isolation import isolate_monitor_root

_ROOT_SANDBOX = isolate_monitor_root("test_role_keyed_rules_")


from src.proxy import rules_config
from src.proxy.rules_config import _load_system2_rules
from src.proxy.rules import apply_modification_rules
from dev.refactoring.strand_runner import strand_workflow

_FILES = {
    'global/g1.md': 'GLOBAL-ONE',
    'global/g2.md': 'GLOBAL-TWO',
    'main/m1.md': 'MAIN-ONE',
    'main/m2.md': 'MAIN-TWO',
    'worker/w1.md': 'WORKER-ONE',
    'opus/o1.md': 'LEGACY-OPUS-ONE',
}

GLOBAL_TEXT = 'GLOBAL-ONE\n\nGLOBAL-TWO'
MAIN_TEXT = GLOBAL_TEXT + '\n\nMAIN-ONE\n\nMAIN-TWO'
WORKER_TEXT = GLOBAL_TEXT + '\n\nWORKER-ONE'

_FULL_CONFIG = {
    'system2_rules': {
        'global': {'files': ['global/g1.md', 'global/g2.md']},
        'main': {'files': ['main/m1.md', 'main/m2.md']},
        'worker': {'files': ['worker/w1.md']},
        'opus': {'files': ['opus/o1.md']},
        'projects': {},
        'exclude_projects': [],
    }
}

_STRANDS = [
    'strand_role_selection',
    'strand_model_family_is_not_the_key',
    'strand_haiku_short_circuit',
    'strand_degraded_configs',
    'strand_exclude_projects_under_both_roles',
    'strand_end_to_end_system2',
]

# ORCHESTRATOR

def test_role_keyed_rules_workflow() -> int:
    return strand_workflow(globals(), __file__, _STRANDS, title='test_role_keyed_rules')

# FUNCTIONS

def check(name, condition, detail=""):
    if not condition:
        print(f"  FAIL  {name}" + (f": {detail}" if detail != "" else ""))
        raise AssertionError(name)
    print(f"  PASS  {name}")
    return True

@contextmanager
def _rules_dir():
    tmp = Path(tempfile.mkdtemp(prefix='role_rules_test_'))
    try:
        yield tmp
    finally:
        shutil.rmtree(tmp, ignore_errors=True)

def install_config(config: dict, tmp: Path) -> None:
    for rel, body in _FILES.items():
        p = tmp / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(body, encoding='utf-8')
    (tmp / 'proxy_rules.json').write_text(json.dumps(config), encoding='utf-8')
    rules_config._SHARED_RULES_DIR = tmp
    rules_config._PROXY_RULES_CONFIG = tmp / 'proxy_rules.json'
    rules_config._config_cache[0] = None
    rules_config._file_cache.clear()


def mk_payload() -> dict:
    return {
        'model': 'claude-opus-4-6',
        'system': [
            {'type': 'text', 'text': 'block0'},
            {'type': 'text', 'text': "You are Claude Code, Anthropic's official CLI for Claude."},
            {'type': 'text', 'text': 'ORIGINAL-SYS2'},
            {'type': 'text', 'text': 'block3'},
        ],
        'messages': [{'role': 'user', 'content': 'hello'}],
        'tools': [],
    }

def strand_role_selection():
    with _rules_dir() as tmp:
        install_config(_FULL_CONFIG, tmp)

        check('main context -> global + main',
              _load_system2_rules('opus', '', 'main') == MAIN_TEXT,
              repr(_load_system2_rules('opus', '', 'main')))
        check('worker:<name> context -> global + worker',
              _load_system2_rules('opus', '', 'worker:rule-injection') == WORKER_TEXT,
              repr(_load_system2_rules('opus', '', 'worker:rule-injection')))
        check('worker name with underscores still matches prefix',
              _load_system2_rules('sonnet', '', 'worker:rule_injection_2') == WORKER_TEXT)
        check('empty context -> main (documented default)',
              _load_system2_rules('opus', '', '') == MAIN_TEXT)
        check('omitted context (3-arg call) -> main',
              _load_system2_rules('opus', '') == MAIN_TEXT)
        check('None context -> main, no crash (tt_delta_skip_replay passes None)',
              _load_system2_rules('opus', '', None) == MAIN_TEXT)
        check('non-worker junk context -> main',
              _load_system2_rules('opus', '', 'workerish') == MAIN_TEXT)

def strand_model_family_is_not_the_key():
    with _rules_dir() as tmp:
        install_config(_FULL_CONFIG, tmp)
        check('opus-family WORKER gets worker rules (the bug this fixes)',
              _load_system2_rules('opus', '', 'worker:w1') == WORKER_TEXT)
        check('sonnet-family MAIN gets main rules (inverse of the bug)',
              _load_system2_rules('sonnet', '', 'main') == MAIN_TEXT)
        check('legacy "opus" config key is never read (no fallback)',
              'LEGACY-OPUS-ONE' not in _load_system2_rules('opus', '', 'main'))

def strand_haiku_short_circuit():
    with _rules_dir() as tmp:
        install_config(_FULL_CONFIG, tmp)
        check('haiku + main context -> empty', _load_system2_rules('haiku', '', 'main') == '')
        check('haiku + worker context -> empty', _load_system2_rules('haiku', '', 'worker:w1') == '')
        check('haiku + absent context -> empty', _load_system2_rules('haiku', '') == '')

def strand_degraded_configs():
    with _rules_dir() as tmp:
        no_main = {'system2_rules': {'global': {'files': ['global/g1.md', 'global/g2.md']},
                                     'worker': {'files': ['worker/w1.md']}}}
        install_config(no_main, tmp)
        check('config without "main" key -> global files only, no crash',
              _load_system2_rules('opus', '', 'main') == GLOBAL_TEXT,
              repr(_load_system2_rules('opus', '', 'main')))
        check('config without "main" key -> worker role unaffected',
              _load_system2_rules('opus', '', 'worker:w1') == WORKER_TEXT)

        no_worker = {'system2_rules': {'global': {'files': ['global/g1.md']},
                                       'main': {'files': ['main/m1.md']}}}
        install_config(no_worker, tmp)
        check('config without "worker" key -> global files only for a worker',
              _load_system2_rules('opus', '', 'worker:w1') == 'GLOBAL-ONE')

        install_config({}, tmp)
        check('config without system2_rules at all -> empty, no crash',
              _load_system2_rules('opus', '', 'main') == '')

        missing_file = {'system2_rules': {'global': {'files': ['global/g1.md', 'global/nope.md']},
                                          'main': {'files': ['main/m1.md']}}}
        install_config(missing_file, tmp)
        check('missing rule file on disk is skipped, rest still concatenated',
              _load_system2_rules('opus', '', 'main') == 'GLOBAL-ONE\n\nMAIN-ONE')

def strand_exclude_projects_under_both_roles():
    with _rules_dir() as tmp:
        excl = json.loads(json.dumps(_FULL_CONFIG))
        excl['system2_rules']['exclude_projects'] = ['/tmp/excluded_proj']
        install_config(excl, tmp)
        check('excluded project -> empty for main',
              _load_system2_rules('opus', '/tmp/excluded_proj/sub', 'main') == '')
        check('excluded project -> empty for worker',
              _load_system2_rules('opus', '/tmp/excluded_proj/sub', 'worker:w1') == '')
        check('non-excluded project unaffected',
              _load_system2_rules('opus', '/tmp/other_proj', 'main') == MAIN_TEXT)

def strand_end_to_end_system2():
    with _rules_dir() as tmp:
        install_config(_FULL_CONFIG, tmp)

        mod, *_ = apply_modification_rules(mk_payload(), 'opus', '', 'main')
        check('e2e: main context lands main rules in system[2]',
              mod['system'][2]['text'] == MAIN_TEXT, repr(mod['system'][2]['text']))

        mod, *_ = apply_modification_rules(mk_payload(), 'opus', '', 'worker:rule-injection')
        check('e2e: worker context lands worker rules in system[2] on an OPUS-family request',
              mod['system'][2]['text'] == WORKER_TEXT, repr(mod['system'][2]['text']))

        mod, *_ = apply_modification_rules(mk_payload(), 'sonnet', '', 'main')
        check('e2e: main context on a SONNET-family request still lands main rules',
              mod['system'][2]['text'] == MAIN_TEXT, repr(mod['system'][2]['text']))

        mod, *_ = apply_modification_rules(mk_payload(), 'haiku', '', 'main')
        check('e2e: haiku inside a main session lands "." in system[2]',
              mod['system'][2]['text'] == '.', repr(mod['system'][2]['text']))

        mod, *_ = apply_modification_rules(mk_payload(), 'opus', '')
        check('e2e: caller omitting worker_context lands main rules',
              mod['system'][2]['text'] == MAIN_TEXT)

if __name__ == '__main__':
    sys.exit(test_role_keyed_rules_workflow())
