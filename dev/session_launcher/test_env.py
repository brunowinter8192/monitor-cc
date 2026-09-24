# INFRASTRUCTURE
import atexit
import os
import shutil
import sys
import tempfile
from pathlib import Path

_PATHS_MODULE = 'src.menubar.paths'

# FUNCTIONS

def isolate_home() -> Path:
    if _PATHS_MODULE in sys.modules:
        raise RuntimeError('src.menubar.paths already imported, home cannot be isolated anymore')
    home = Path(tempfile.mkdtemp(prefix='session_launcher_home_'))
    os.environ['HOME'] = str(home)
    atexit.register(shutil.rmtree, str(home), True)
    return home
