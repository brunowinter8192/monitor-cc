# INFRASTRUCTURE

# Main-panel NSGridView column geometry — split out of panel.py (menubar milestone B, _GRID_*
# constant cluster). Used only by panel_manager.py's session-grid construction; panel.py itself
# never reads these (grid construction lives entirely in panel_manager.py).
_GRID_COL0_W  = 40   # slot "[N]"/conflict "[!N]" (up to 4 chars × 7.8pt + buffer)
_GRID_COL1_W  = 17   # star "* " (2 chars × 7.8pt + buffer)
_GRID_COL3_W  = 25   # dot "[ ]"/"[*]" (3 chars × 7.8pt + buffer)
_GRID_COL4_W  = 72   # badge "[B M:SS]" max 9 chars × 7.8pt + buffer
_GRID_COL5_W  = 40   # monitor "mon" button, main rows only (3 chars × 7.8pt + buffer, same budget as col0)
_GRID_COL_SPC = 2    # column spacing (pts between adjacent columns)
