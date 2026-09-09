# INFRASTRUCTURE

# Menubar status-item icon glyphs + baseline tweak — split out of panel.py (menubar milestone B,
# ICON_* constant cluster). Used only by app.py (bar-icon set/blink); panel.py itself never reads
# these.
ICON_NORMAL          = '◉'
ICON_BLINK           = '●'
ICON_BASELINE_OFFSET = 1.0   # pts — vertical offset applied via NSBaselineOffsetAttributeName; adjust if icon drifts
