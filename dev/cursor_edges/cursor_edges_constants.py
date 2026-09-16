# INFRASTRUCTURE
from AppKit import (
    NSTrackingActiveAlways,
    NSTrackingCursorUpdate,
    NSTrackingInVisibleRect,
    NSTrackingMouseEnteredAndExited,
    NSTrackingMouseMoved,
)

PANEL_WIDTH  = 380
PANEL_HEIGHT = 460
_FOOTER_H    = 30
_TOP_BAR_H   = 21
_ROW_H       = 21
EDGE         = 8
PANEL_MIN_WIDTH  = 250
PANEL_MIN_HEIGHT = 120
PANEL_MAX_DIM    = 900

_TA_OPTS = NSTrackingMouseEnteredAndExited | NSTrackingMouseMoved | NSTrackingActiveAlways

_TA_TRACKING_OPTS = (NSTrackingCursorUpdate | NSTrackingMouseMoved |
                     NSTrackingMouseEnteredAndExited | NSTrackingActiveAlways |
                     NSTrackingInVisibleRect)

_LEAF_RECTS_ENABLED = False
_TRACKING_ENABLED   = False
