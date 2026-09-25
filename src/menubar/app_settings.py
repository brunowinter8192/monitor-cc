# INFRASTRUCTURE
import json
import os

from src.menubar.menubar_log import log_menubar
from src.menubar.paths import SETTINGS_FILE as _SETTINGS_PATH
from src.menubar.panel_dims import PANEL_WIDTH, PANEL_HEIGHT, PANEL_MIN_WIDTH, PANEL_MIN_HEIGHT

# FUNCTIONS

def _load_settings():
    try:
        d = json.loads(open(_SETTINGS_PATH).read())
        return (
            max(int(d.get('panel_width', PANEL_WIDTH)), PANEL_MIN_WIDTH),
            max(int(d.get('panel_min_height', PANEL_HEIGHT)), PANEL_MIN_HEIGHT),
        )
    except FileNotFoundError:
        return PANEL_WIDTH, PANEL_HEIGHT
    except Exception as exc:
        log_menubar('settings', f'load failed path={_SETTINGS_PATH} err={exc!r}')
        return PANEL_WIDTH, PANEL_HEIGHT


def _save_settings(panel_width: int, panel_min_height: int) -> None:
    try:
        tmp = _SETTINGS_PATH.with_name(_SETTINGS_PATH.name + '.tmp')
        open(tmp, 'w').write(json.dumps({
            'panel_width': panel_width,
            'panel_min_height': panel_min_height,
        }))
        os.replace(tmp, _SETTINGS_PATH)
    except Exception as exc:
        log_menubar('settings', f'save failed path={_SETTINGS_PATH} err={exc!r}')
