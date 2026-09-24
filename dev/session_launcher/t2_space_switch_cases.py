# INFRASTRUCTURE
from unittest.mock import MagicMock, patch

from dev.session_launcher.t2_fixtures import _imp

# FUNCTIONS

def _case_space_switch_units() -> str:
    sw = _imp('space_switch')
    fake = MagicMock()
    fake.CGPreflightPostEventAccess.return_value = False
    fake.CGRequestPostEventAccess.return_value = False
    out = [_check_post_event_access(sw, fake), _check_post_event_granted(sw, fake), _check_space_id_for_desktop(sw, fake),
           _check_desktop_hotkeys(sw), _check_wait_until_active(sw)]
    return ' | '.join(out)

def _check_post_event_access(sw, fake) -> str:
    with patch.object(sw, '_CG', fake):
        try:
            sw._require_post_event_access()
            raise AssertionError('no error without PostEvent')
        except sw.SpaceSwitchError as exc:
            assert str(exc) == 'postevent_not_granted'
        assert fake.CGRequestPostEventAccess.call_count == 0, 'switch path must not request access'
        assert sw.request_post_event_access_if_missing() is False
        assert fake.CGRequestPostEventAccess.call_count == 1
    return 'no PostEvent -> switch path raises without requesting; request function requests once and returns False'

def _check_post_event_granted(sw, fake) -> str:
    fake.CGPreflightPostEventAccess.return_value = True
    fake.CGRequestPostEventAccess.reset_mock()
    with patch.object(sw, '_CG', fake):
        sw._require_post_event_access()
        assert sw.request_post_event_access_if_missing() is True
    assert fake.CGRequestPostEventAccess.call_count == 0
    return 'PostEvent granted -> no request, returns True'

def _check_space_id_for_desktop(sw, fake) -> str:
    space_map = {3: ('D', 1), 4: ('D', 2), 5: ('D', 3), 6: ('D', 4), 7: ('D', 5)}
    fake.CGSMainConnectionID.return_value = 1
    with patch.object(sw, '_CG', fake), patch.object(sw, '_build_space_map', lambda cid: space_map):
        assert [sw._space_id_for_desktop(n) for n in range(1, 6)] == [3, 4, 5, 6, 7]
    with patch.object(sw, '_CG', fake), patch.object(sw, '_build_space_map', lambda cid: {3: ('D', 1)}):
        try:
            sw._space_id_for_desktop(4)
            raise AssertionError('missing desktop accepted')
        except sw.SpaceSwitchError as exc:
            assert 'desktop_4_space_matches=0' in str(exc)
    with patch.object(sw, '_CG', fake), patch.object(sw, '_build_space_map', lambda cid: {3: ('D', 1), 9: ('E', 1)}):
        try:
            sw._space_id_for_desktop(1)
            raise AssertionError('ambiguous desktop accepted')
        except sw.SpaceSwitchError as exc:
            assert 'desktop_1_space_matches=2' in str(exc)
    return 'desktop -> space id for 1..5; missing and ambiguous desktop raise'

def _check_desktop_hotkeys(sw) -> str:
    keys = []
    with patch.object(sw, '_post_key', lambda kc, down: keys.append((kc, down))):
        for n in range(1, 6):
            sw._post_desktop_hotkey(n)
    assert keys == [(18, True), (18, False), (19, True), (19, False), (20, True), (20, False),
                    (21, True), (21, False), (23, True), (23, False)], keys
    return 'hotkey key codes 18,19,20,21,23 down+up'

def _check_wait_until_active(sw) -> str:
    seq = iter([1, 1, 4])
    with patch.object(sw, 'active_space_id', lambda: next(seq)), patch.object(sw.time, 'sleep', lambda s: None):
        ms = sw._wait_until_active(4)
    assert ms >= 0
    with patch.object(sw, 'active_space_id', lambda: 1), patch.object(sw, '_SWITCH_TIMEOUT', 0.05):
        try:
            sw._wait_until_active(4)
            raise AssertionError('timeout not raised')
        except sw.SpaceSwitchError as exc:
            assert 'switch_timeout' in str(exc)
    return 'wait_until_active: returns on target, raises switch_timeout otherwise'
