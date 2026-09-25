# INFRASTRUCTURE
import re
from datetime import datetime, timedelta

from p5_common import load, tmpdir, capture_stderr, digest, check


# ORCHESTRATOR

def main() -> None:
    mod = load('menubar_log')
    d = tmpdir()
    normal_append(mod, d)
    write_failure(mod, d)
    cleanup_normal(mod, d)
    cleanup_failure(mod, d)


# FUNCTIONS

def normal_append(mod, d) -> None:
    mod.MENUBAR_LOG = d / 'a.log'
    mod.log_menubar('cat', 'one')
    mod.log_menubar('cat2', 'two')
    check('g1.normal_append', digest(strip_ts(mod.MENUBAR_LOG.read_text())) == digest('TS [cat] one\nTS [cat2] two\n'))


def strip_ts(text: str) -> str:
    return re.sub(r'\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d', 'TS', text)


def write_failure(mod, d) -> None:
    blocker = d / 'blocker'
    blocker.write_text('x')
    mod.MENUBAR_LOG = blocker / 'sub' / 'a.log'
    _, err = capture_stderr(lambda: mod.log_menubar('cat', 'msg'))
    check('g1.write_failure_stderr', '[menubar_log] write failed category=cat' in err)


def cleanup_normal(mod, d) -> None:
    now = datetime.now()
    old = (now - timedelta(days=9)).isoformat(timespec='seconds')
    new = now.isoformat(timespec='seconds')
    mod.MENUBAR_LOG = d / 'c.log'
    mod.MENUBAR_LOG.write_text(f'{old} [x] old\n{new} [x] new\nno-timestamp line\n')
    mod.cleanup_old_lines()
    check('g1.cleanup_normal', strip_ts(mod.MENUBAR_LOG.read_text()) == 'TS [x] new\nno-timestamp line\n')


def cleanup_failure(mod, d) -> None:
    mod.MENUBAR_LOG = d
    _, err = capture_stderr(mod.cleanup_old_lines)
    check('g1.cleanup_failure_stderr', '[menubar_log] cleanup failed' in err)


if __name__ == '__main__':
    main()
