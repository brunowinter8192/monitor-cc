# INFRASTRUCTURE

# Main-panel outer dimensions — split out of panel.py (menubar milestone B, PANEL_* constant
# cluster). Read by panel.py itself (_make_nspanel/_reposition_panel), app.py, app_settings.py,
# model_panel_ui.py, rag_controller.py.
#
# PANEL_WIDTH = old 380 + (_GRID_COL5_W + _GRID_COL_SPC) = 422 — the monitor column's own width
# plus the one extra inter-column gap it introduces, so the flexible name column (col2) keeps
# the exact same effective width it had before the column was added (verified: fixed-column +
# spacing budget grows by precisely 42pt on both sides of the subtraction).
PANEL_WIDTH      = 422   # pts
PANEL_HEIGHT     = 460   # pts — initial height; floor for first-run (no settings)
PANEL_MIN_WIDTH  = 250   # pts — minimum width enforced by setContentMinSize_
PANEL_MIN_HEIGHT = 120   # pts — minimum height enforced by setContentMinSize_
PANEL_GAP        = 4     # pts below the status bar button
