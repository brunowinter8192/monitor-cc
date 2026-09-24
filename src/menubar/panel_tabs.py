# INFRASTRUCTURE
TABS = ('Sessions', 'RAG', 'Models')

# FUNCTIONS

def tab_header_text(active: str) -> str:
    return ' · '.join(f'[{tab}]' if tab == active else tab for tab in TABS)
