# INFRASTRUCTURE
import os
os.environ['PATH'] = '/opt/homebrew/bin:/usr/local/bin:' + os.environ.get('PATH', '/usr/bin:/bin')

# ORCHESTRATOR
from src.menubar import run
run()
