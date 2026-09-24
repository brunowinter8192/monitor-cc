# INFRASTRUCTURE
TABS = ('Sessions', 'RAG', 'Models', 'Launch')
TAB_KEYS = ('main', 'rag', 'models', 'launch')
TAB_SEPARATOR = ' · '

# FUNCTIONS

def header_pieces(active: str) -> list:
    return [f'[{tab}]' if tab == active else tab for tab in TABS]

def tab_header_text(active: str) -> str:
    return TAB_SEPARATOR.join(header_pieces(active))
