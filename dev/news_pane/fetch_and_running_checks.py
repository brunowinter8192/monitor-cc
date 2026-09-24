# INFRASTRUCTURE
import importlib
import os
import stat
import sys
import tempfile
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_ROOT))

# ORCHESTRATOR


def main():
    workdir = Path(tempfile.mkdtemp(prefix='mcfix_news_'))
    pane_log = importlib.import_module('src.pane_error_log')
    pane_log.PANE_ERROR_LOG_PATH = str(workdir / 'pane_error.log')
    pane = importlib.import_module('src.news_pane.pane')
    parser = importlib.import_module('src.news_pane.log_parser')
    results = _fetch_checks(pane, workdir) + _last_run_checks(parser, workdir) + _running_checks(pane)
    for name, ok in results:
        print(('PASS: ' if ok else 'FAIL: ') + name)
    failed = [n for n, ok in results if not ok]
    print(f'{len(results) - len(failed)}/{len(results)} passed')
    sys.exit(1 if failed else 0)


# FUNCTIONS


def _set_rag_cli(workdir: Path, body: str | None) -> None:
    shim = workdir / 'bin' / 'rag-cli'
    shim.parent.mkdir(exist_ok=True)
    if shim.exists():
        shim.unlink()
    if body is not None:
        shim.write_text('#!/bin/sh\n' + body + '\n')
        shim.chmod(shim.stat().st_mode | stat.S_IXUSR)
    os.environ['PATH'] = f'{workdir / "bin"}:/usr/bin:/bin'


def _notes(workdir: Path) -> list:
    path = workdir / 'pane_error.log'
    if not path.exists():
        return []
    return [ln for ln in path.read_text().splitlines() if '] [news] note:' in ln]


def _fetch_checks(pane, workdir: Path) -> list:
    results = []
    _set_rag_cli(workdir, None)
    first = pane._fetch_doc_count()
    second = pane._fetch_doc_count()
    results.append(('doc_count with rag-cli absent is None and notes FileNotFoundError once',
                    first is None and second is None and len(_notes(workdir)) == 1 and 'FileNotFoundError' in _notes(workdir)[0]))
    _set_rag_cli(workdir, 'echo "a.md (3 chunks)"; echo "b.md (2 chunks)"')
    results.append(('doc_count success counts documents', pane._fetch_doc_count() == 2))
    _set_rag_cli(workdir, 'exit 3')
    before = len(_notes(workdir))
    value = pane._fetch_doc_count()
    results.append(('doc_count rc=3 after recovery is None and notes rc=3', value is None and len(_notes(workdir)) == before + 1 and 'rc=3' in _notes(workdir)[-1]))
    _set_rag_cli(workdir, 'echo \'[{"collection": "searxng_crypto", "chunks": 108}]\'')
    results.append(('chunk_count success returns chunks', pane._fetch_chunk_count() == 108))
    _set_rag_cli(workdir, 'echo \'[{"collection": "other", "chunks": 1}]\'')
    before = len(_notes(workdir))
    results.append(('chunk_count with collection not listed is None and notes it',
                    pane._fetch_chunk_count() is None and 'collection not listed' in _notes(workdir)[-1] and len(_notes(workdir)) == before + 1))
    _set_rag_cli(workdir, 'echo not-json')
    results.append(('chunk_count with malformed JSON is None and notes JSONDecodeError',
                    pane._fetch_chunk_count() is None and 'JSONDecodeError' in _notes(workdir)[-1]))
    return results


def _last_run_checks(parser, workdir: Path) -> list:
    parser.LAST_RUN_FILE = workdir / 'missing.txt'
    missing = parser.read_last_run_ts()
    parser.LAST_RUN_FILE = workdir
    try:
        parser.read_last_run_ts()
        raised = False
    except IsADirectoryError:
        raised = True
    return [
        ('read_last_run_ts on a missing file returns None', missing is None),
        ('read_last_run_ts on another OSError propagates', raised),
    ]


class _FakeProc:
    def __init__(self, code):
        self._code = code

    def poll(self):
        return self._code


def _running_checks(pane) -> list:
    pane._pipeline_proc = None
    idle = pane._is_running()
    pane._pipeline_proc = _FakeProc(None)
    alive = pane._is_running()
    pane._pipeline_proc = _FakeProc(0)
    done = pane._is_running()
    pane._pipeline_proc = None
    return [
        ('no handle is not running', idle is False),
        ('live handle is running', alive is True),
        ('exited handle is not running', done is False),
        ('log-based running path is gone', not hasattr(pane, '_is_running_via_log')),
    ]


if __name__ == '__main__':
    main()
