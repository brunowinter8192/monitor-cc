# INFRASTRUCTURE
from Foundation import NSMakeRect

from src.menubar.panel import _ROW_H
from src.menubar.panel_views import _CursorlessButton

_APPLY_BTN_W          = 78
_APPLY_BTN_H          = 22
_APPLY_SUCCESS_TITLE  = 'Applied successfully'
_APPLY_SUCCESS_W      = 160
_APPLY_SUCCESS_DURATION = 1.5

# FUNCTIONS

def _make_model_row_btn(panel_width: int):
    btn = _CursorlessButton.alloc().initWithFrame_(NSMakeRect(0, 0, panel_width - 22, _ROW_H - 1))
    btn.setBordered_(False)
    btn.setButtonType_(7)
    return btn

def _make_apply_btn():
    btn = _CursorlessButton.alloc().initWithFrame_(NSMakeRect(0, 0, _APPLY_BTN_W, _APPLY_BTN_H))
    btn.setTitle_('Apply')
    btn.setBezelStyle_(1)
    return btn
