# INFRASTRUCTURE
import json
import os

from .paths import SETTINGS_FILE as _SETTINGS_PATH
from .panel_dims import PANEL_WIDTH, PANEL_HEIGHT, PANEL_MIN_WIDTH, PANEL_MIN_HEIGHT

# FUNCTIONS

def _load_settings():
    try:
        d = json.loads(open(_SETTINGS_PATH).read())
        raw_h = d.get('panel_min_height', d.get('panel_max_height', PANEL_HEIGHT))
        return (
            bool(d.get('auto_focus', False)),
            max(int(d.get('panel_width', PANEL_WIDTH)), PANEL_MIN_WIDTH),
            max(int(raw_h),                             PANEL_MIN_HEIGHT),
        )
    except Exception:
        return False, PANEL_WIDTH, PANEL_HEIGHT


def _save_settings(auto_focus: bool, panel_width: int, panel_min_height: int) -> None:
    try:
        tmp = _SETTINGS_PATH.with_name(_SETTINGS_PATH.name + '.tmp')
        open(tmp, 'w').write(json.dumps({
            'auto_focus': auto_focus,
            'panel_width': panel_width,
            'panel_min_height': panel_min_height,
        }))
        os.replace(tmp, _SETTINGS_PATH)
    except Exception:
        pass
