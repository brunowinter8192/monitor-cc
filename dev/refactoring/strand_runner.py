# INFRASTRUCTURE
import subprocess
import sys
import traceback
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

STRAND_FLAG = '--strand'
STRAND_TIMEOUT_SECONDS = 300
STDERR_TAIL_CHARS = 1500

# ORCHESTRATOR


def strand_workflow(script_globals: dict, script_path: str, strand_names: list, report_path=None, title: str = 'strands') -> int:
    requested = parse_strand_argument(sys.argv)
    if requested is not None:
        return run_named_strand(script_globals, requested)
    results = run_strands_parallel(script_path, strand_names)
    print_verdicts(results)
    if report_path is not None:
        write_report(Path(report_path), title, results)
    return 0 if all(r['returncode'] == 0 for r in results) else 1


# FUNCTIONS


def parse_strand_argument(argv: list):
    if STRAND_FLAG not in argv:
        return None
    return argv[argv.index(STRAND_FLAG) + 1]


def run_named_strand(script_globals: dict, name: str) -> int:
    try:
        script_globals[name]()
    except BaseException:
        traceback.print_exc()
        return 1
    return 0


def run_strands_parallel(script_path: str, strand_names: list) -> list:
    with ThreadPoolExecutor(max_workers=len(strand_names)) as pool:
        futures = [pool.submit(launch_strand, script_path, name) for name in strand_names]
        return [f.result() for f in futures]


def launch_strand(script_path: str, name: str) -> dict:
    try:
        proc = subprocess.run(
            [sys.executable, script_path, STRAND_FLAG, name],
            capture_output=True, text=True, timeout=STRAND_TIMEOUT_SECONDS)
    except subprocess.TimeoutExpired as exc:
        return {'name': name, 'returncode': -1, 'stdout': exc.stdout or '', 'stderr': f'timeout after {STRAND_TIMEOUT_SECONDS}s'}
    return {'name': name, 'returncode': proc.returncode, 'stdout': proc.stdout, 'stderr': proc.stderr}


def print_verdicts(results: list) -> None:
    for r in results:
        if r['returncode'] == 0:
            print(f"PASS  {r['name']}")
        else:
            print(f"ABORT {r['name']}")
            print(r['stdout'].rstrip())
            print(r['stderr'][-STDERR_TAIL_CHARS:].rstrip())
    aborted = [r['name'] for r in results if r['returncode'] != 0]
    print(f"{len(results) - len(aborted)}/{len(results)} strands passed")
    if aborted:
        print('aborted strands: ' + ', '.join(aborted))


def write_report(report_path: Path, title: str, results: list) -> None:
    report_path.parent.mkdir(parents=True, exist_ok=True)
    passed = sum(1 for r in results if r['returncode'] == 0)
    lines = [f'# {title}', '', f'{passed}/{len(results)} strands passed', '']
    for r in results:
        verdict = 'PASS' if r['returncode'] == 0 else 'ABORT'
        lines.append(f"## {verdict} {r['name']}")
        lines.append('')
        lines.extend(r['stdout'].rstrip().split('\n') if r['stdout'].strip() else ['(no output)'])
        lines.append('')
    report_path.write_text('\n'.join(lines), encoding='utf-8')


def check(label: str, condition) -> bool:
    print(f"  {'PASS' if condition else 'FAIL'}  {label}")
    if not condition:
        raise AssertionError(label)
    return True
