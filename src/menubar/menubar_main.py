# INFRASTRUCTURE
# py2app entry point — thin wrapper; avoids argparse dispatch in workflow.py

# ORCHESTRATOR
# Start menubar app — called by py2app native launcher at bundle launch
from src.menubar import run
run()
