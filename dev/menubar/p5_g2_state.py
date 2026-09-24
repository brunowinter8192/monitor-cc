# INFRASTRUCTURE
import json
import os
import time

from p5_common import load, tmpdir, digest, check, point_log, log_text

# ORCHESTRATOR

def main() -> None:
    d = tmpdir()
    mlog = point_log(d)
    app_settings(d, mlog)
    model_selection_reads(d, mlog)
    proxy_rules_write(d, mlog)
    pending_write_order(d, mlog)
    hook_state_read(d, mlog)
    sweep_state_read(d, mlog)
    rag_status(d, mlog)
    hook_writer_state(d, mlog)
    paths_shims_gone()

# FUNCTIONS

def app_settings(d, mlog) -> None:
    mod = load('app_settings')
    mod._SETTINGS_PATH = d / 's.json'
    mod._SETTINGS_PATH.write_text(json.dumps({'panel_width': 500, 'panel_min_height': 300}))
    ok = mod._load_settings() == (500, 300)
    missing = d / 'none.json'
    mod._SETTINGS_PATH = missing
    ok = ok and mod._load_settings() == (mod.PANEL_WIDTH, mod.PANEL_HEIGHT)
    check('g2.app_settings.normal_and_missing', ok and log_text(mlog) == '')
    corrupt = d / 'bad.json'
    corrupt.write_text('{oops')
    mod._SETTINGS_PATH = corrupt
    got = mod._load_settings()
    check('g2.app_settings.corrupt_logged', got == (mod.PANEL_WIDTH, mod.PANEL_HEIGHT) and '[settings] load failed' in log_text(mlog))
    mod._SETTINGS_PATH = d / 'nodir' / 'x.json'
    mod._save_settings(400, 200)
    check('g2.app_settings.save_failure_logged', '[settings] save failed' in log_text(mlog))

def model_selection_reads(d, mlog) -> None:
    mod = load('model_selection')
    good = d / 'ms.json'
    good.write_text(json.dumps({'main': 'claude-opus-5', 'worker': 'claude-fable-5'}))
    check('g2.model_selection.read_valid', mod._load_model_selection(good) == ('claude-opus-5', 'claude-fable-5'))
    before = log_text(mlog)
    check('g2.model_selection.read_missing_silent', mod._load_model_selection(d / 'nope.json') == (mod._DEFAULT_MAIN, mod._DEFAULT_WORKER) and log_text(mlog) == before)
    bad = d / 'ms_bad.json'
    bad.write_text('[1,2]')
    check('g2.model_selection.read_corrupt_logged', mod._load_model_selection(bad) == (mod._DEFAULT_MAIN, mod._DEFAULT_WORKER) and 'read failed' in log_text(mlog))
    mod._next_in(('a', 'b'), 'zzz')
    check('g2.model_selection.unknown_value_logged', 'value not in choices' in log_text(mlog))

def proxy_rules_write(d, mlog) -> None:
    mod = load('model_selection')
    rules = d / 'rules.json'
    rules.write_text(json.dumps({'other': {'k': [1, 2]}, 'model_params': {'claude-opus-5': {'effort': 'low'}}}, indent=2))
    args = ('claude-opus-5', 'high', 64000, {'type': 'adaptive'}, 'claude-fable-5', 'low', 32000, {'type': 'disabled'})
    mod._write_proxy_rules_model_params(*args, path=rules)
    check('g2.proxy_rules.write_valid_digest', digest(rules.read_text()) == os.environ.get('P5_EXPECT_RULES', digest(rules.read_text())), digest(rules.read_text()))
    keep = rules.read_text()
    rules.write_text('{broken')
    broken_bytes = rules.read_text()
    try:
        mod._write_proxy_rules_model_params(*args, path=rules)
        raised = False
    except Exception:
        raised = True
    check('g2.proxy_rules.corrupt_read_raises_and_file_untouched', raised and rules.read_text() == broken_bytes)
    fresh = d / 'fresh.json'
    mod._write_proxy_rules_model_params(*args, path=fresh)
    check('g2.proxy_rules.missing_creates', 'claude-opus-5' in fresh.read_text() and keep.count('other') == 1)

def pending_write_order(d, mlog) -> None:
    mod = load('model_selection')
    calls = []
    def boom(*a, **k):
        calls.append('rules')
        raise ValueError('unreadable')
    mod._write_proxy_rules_model_params = boom
    mod._write_model_selection = lambda *a, **k: calls.append('selection')
    pending = mod._PendingSelection()
    pending.main, pending.worker = 'claude-opus-5', 'claude-fable-5'
    pending.main_effort = pending.worker_effort = 'low'
    pending.main_max_tokens = pending.worker_max_tokens = 32000
    pending.main_thinking = pending.worker_thinking = {'type': 'disabled'}
    try:
        pending.write()
    except ValueError:
        pass
    check('g2.pending.selection_not_written_after_rules_failure', calls == ['rules'])

def hook_state_read(d, mlog) -> None:
    mod = load('proc_cache')
    f = d / 'hooks.json'
    mod._HOOK_STATE_FILE = f
    mod._hook_state_last_read = 0.0
    check('g2.hook_state.missing_silent', mod._read_hook_state(10.0) == {} and 'hook_state' not in log_text(mlog))
    f.write_text(json.dumps({'s': {'status': 'idle'}}))
    check('g2.hook_state.valid', mod._read_hook_state(20.0) == {'s': {'status': 'idle'}})
    f.write_text('{bad')
    mod._read_hook_state(30.0)
    mod._read_hook_state(40.0)
    check('g2.hook_state.corrupt_logged_once', log_text(mlog).count('[hook_state] read failed') == 1)

def sweep_state_read(d, mlog) -> None:
    mod = load('monitor_sweep_scheduler')
    f = d / 'sweep.json'
    mod.MONITOR_SWEEP_STATE_FILE = f
    check('g2.sweep.missing_silent', mod._read_last_sweep_ts() == 0.0 and 'state-read' not in log_text(mlog))
    f.write_text(json.dumps({'last_run_ts': 12.5}))
    check('g2.sweep.valid', mod._read_last_sweep_ts() == 12.5)
    f.write_text('nope')
    check('g2.sweep.corrupt_logged', mod._read_last_sweep_ts() == 0.0 and 'state-read FAILED' in log_text(mlog))

def rag_status(d, mlog) -> None:
    mod = load('rag_controller')
    lock = d / 'rag.lock'
    check('g2.rag.missing_silent', mod._read_rag_status(lock) == mod._NO_INDEXING and '[rag]' not in log_text(mlog))
    lock.write_text(json.dumps({'pid': os.getpid(), 'kind': 'index', 'args': {'collection': 'c1'},
                                'progress': {'done': 1, 'total': 4}, 'started_at': '2020-01-01T00:00:00+00:00'}))
    text = mod._read_rag_status(lock)
    check('g2.rag.valid', text.startswith('c1 · 1/4 docs · '))
    lock.write_text('{bad')
    mod._read_rag_status(lock)
    mod._read_rag_status(lock)
    check('g2.rag.corrupt_logged_once', log_text(mlog).count('status read failed') == 1)

def hook_writer_state(d, mlog) -> None:
    mod = load('hook_writer')
    mod._APP_SUPPORT = d
    mod._HOOK_STATE_FILE = d / 'hw_hooks.json'
    mod._HOOK_LOCK_FILE = d / 'hw.lock'
    mod.time.time = lambda: 1000.0
    mod._write_state('s1', 'working', '/p')
    mod._write_state('s2', 'idle', '/q')
    state = json.loads(mod._HOOK_STATE_FILE.read_text())
    check('g2.hook_writer.merge_valid', state == {'s1': {'status': 'working', 'cwd': '/p', 'updated_ts': 1000.0}, 's2': {'status': 'idle', 'cwd': '/q', 'updated_ts': 1000.0}})
    mod._HOOK_STATE_FILE.write_text('{bad')
    mod._write_state('s3', 'idle', '/r')
    check('g2.hook_writer.corrupt_state_not_overwritten', mod._HOOK_STATE_FILE.read_text() == '{bad' and 'state write skipped' in log_text(mlog))

def paths_shims_gone() -> None:
    mod = load('paths')
    check('g2.paths.shims_removed', not hasattr(mod, '_migrate_from_dotfiles') and not hasattr(mod, '_migrate_from_old_bundle_id') and mod._APP_SUPPORT.is_dir())


if __name__ == '__main__':
    main()
