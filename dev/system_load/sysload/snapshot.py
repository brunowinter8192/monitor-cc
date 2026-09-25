# INFRASTRUCTURE
import json
from datetime import datetime, timezone
from pathlib import Path

from sysload.classify import classify_snapshot, cwd_candidate_pids
from sysload.collect import (
    collect_cpu_now, collect_cwds, collect_established, collect_procs, collect_system,
    collect_task_files, collect_tmux, read_own_identity,
)
from sysload.config import SNAPSHOT_DIR
from sysload.render import render_report


# ORCHESTRATOR

def snapshot_workflow(argv: list) -> int:
    options = parse_options(argv)
    identity = read_own_identity()
    procs = collect_procs()
    cwds = collect_cwds(cwd_candidate_pids(procs))
    snap = assemble_snapshot(
        identity, procs, cwds, collect_cpu_now(), collect_tmux(),
        collect_task_files(identity['taken_at']), collect_established(), collect_system(), options)
    result = classify_snapshot(snap)
    out_path = write_result(result, options)
    emit_report(result, out_path, options)
    return 0


# FUNCTIONS

def parse_options(argv: list) -> dict:
    options = {'protect_pids': [], 'protect_roots': [], 'out': None, 'as_json': False}
    i = 0
    while i < len(argv):
        flag = argv[i]
        if flag == '--protect-pid':
            options['protect_pids'].append(int(argv[i + 1]))
            i += 2
        elif flag == '--protect-root':
            options['protect_roots'].append(argv[i + 1].rstrip('/'))
            i += 2
        elif flag == '--out':
            options['out'] = argv[i + 1]
            i += 2
        elif flag == '--json':
            options['as_json'] = True
            i += 1
        else:
            raise SystemExit(f'unknown snapshot option: {flag}')
    return options


def assemble_snapshot(identity, procs, cwds, cpu_now, tmux, task_files, established, system, options) -> dict:
    return {
        **identity,
        'procs': procs,
        'cwds': cwds,
        'cpu_now': cpu_now,
        'tmux': tmux,
        'task_files': task_files,
        'established': established,
        'system': system,
        'protect_pids': options['protect_pids'],
        'protect_roots': options['protect_roots'],
    }


def write_result(result: dict, options: dict) -> Path:
    if options['out']:
        path = Path(options['out'])
    else:
        stamp = datetime.fromtimestamp(result['taken_at'], timezone.utc).strftime('%Y%m%dT%H%M%S')
        path = SNAPSHOT_DIR / f'{stamp}.json'
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(result, indent=1), encoding='utf-8')
    return path


def emit_report(result: dict, out_path: Path, options: dict) -> None:
    if options['as_json']:
        print(json.dumps(result, indent=1))
        return
    print(render_report(result, str(out_path)))
