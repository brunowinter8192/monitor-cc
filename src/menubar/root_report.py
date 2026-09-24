# FUNCTIONS

def report_root(root, source: str) -> None:
    from .menubar_log import log_menubar
    log_menubar('paths', f'PROJECT_ROOT resolved: source={source} root={root}')
