# INFRASTRUCTURE
from AppKit import (
    NSTrackingActiveAlways,
    NSTrackingCursorUpdate,
    NSTrackingInVisibleRect,
    NSTrackingMouseEnteredAndExited,
    NSTrackingMouseMoved,
)

# Mirror production geometry constants exactly
PANEL_WIDTH  = 380
PANEL_HEIGHT = 460
_FOOTER_H    = 30
_TOP_BAR_H   = 21
_ROW_H       = 21
EDGE         = 8   # cursor-rect / edge-detection width in production
PANEL_MIN_WIDTH  = 250
PANEL_MIN_HEIGHT = 120
PANEL_MAX_DIM    = 900   # upper clamp for custom drag resize

# NSTrackingArea option flags for legacy (non-tracking) modes
_TA_OPTS = NSTrackingMouseEnteredAndExited | NSTrackingMouseMoved | NSTrackingActiveAlways

# NSTrackingArea option flags for --tracking mode
# .cursorUpdate fires cursorUpdate_ regardless of key-window status (activeAlways guarantees this)
_TA_TRACKING_OPTS = (NSTrackingCursorUpdate | NSTrackingMouseMoved |
                     NSTrackingMouseEnteredAndExited | NSTrackingActiveAlways |
                     NSTrackingInVisibleRect)

# Module-level flags set by argparse before panel construction.
_LEAF_RECTS_ENABLED = False
_TRACKING_ENABLED   = False
