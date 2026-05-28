# INFRASTRUCTURE
# py2app entry point — thin wrapper; avoids argparse dispatch in workflow.py
import os
# Augment PATH before any import: py2app bundles start with macOS default PATH
# (/usr/bin:/bin only), missing /opt/homebrew/bin — breaks tmux, bd, and other CLI tools.
os.environ['PATH'] = '/opt/homebrew/bin:/usr/local/bin:' + os.environ.get('PATH', '/usr/bin:/bin')

# ORCHESTRATOR
# Start menubar app — called by py2app native launcher at bundle launch
from src.menubar import run
run()
