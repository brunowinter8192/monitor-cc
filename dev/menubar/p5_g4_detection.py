# INFRASTRUCTURE
from unittest import mock

from p5_common import load, tmpdir, check, point_log, log_text, digest


# ORCHESTRATOR

def main() -> None:
    d = tmpdir()
    mlog = point_log(d)
    mod = load('desktop_detection')
    patch_cf(mod)
    normal_space_map(mod)
    normal_resolve(mod)
    normal_cwd_resolution(mod)
    if hasattr(mod, '_log_route'):
        alternate_keys_skipped(mod, mlog)
        routes_logged_on_change(mod, mlog)
        lkg_removed(mod)


# FUNCTIONS

def patch_cf(mod) -> None:
    mod._cf_count = lambda arr: len(arr)
    mod._cf_at = lambda arr, i: arr[i]
    mod._dict_val = lambda d, key: d.get(key)
    mod._dict_str = lambda d, key: d.get(key)
    mod._dict_long = lambda d, key: d.get(key)


def normal_space_map(mod) -> None:
    mod._CG = _FakeCG([
        {'Display Identifier': 'ABCDEFGH-1234', 'Spaces': [{'ManagedSpaceID': 5}, {'ManagedSpaceID': 9}]},
        {'Display Identifier': 'ZZZZZZZZ-9999', 'Spaces': [{'ManagedSpaceID': 21}]},
    ])
    result = mod._build_space_map(1)
    print(f'DIFF space_map {digest(sorted(result.items()))}')
    check('g4.space_map.normal', result == {5: ('ABCDEFGH', 1), 9: ('ABCDEFGH', 2), 21: ('ZZZZZZZZ', 1)})


class _FakeCG:
    def __init__(self, displays):
        self.displays = displays
    def CGSCopyManagedDisplaySpaces(self, cid):
        return self.displays


def normal_resolve(mod) -> None:
    outs = []
    mod._spaces_for_wid = lambda cid, wid: {10: [5], 11: [9], 12: [5]}.get(wid, [])
    outs.append(mod._resolve_cgwindow_id('w', {'w': [10]}, set(), 1, None, 1))
    outs.append(mod._resolve_cgwindow_id('w', {'w': [10, 11]}, {5}, 1, None, 1))
    outs.append(mod._resolve_cgwindow_id('w', {'w': [10, 12]}, set(), 1, None, 1))
    outs.append(mod._resolve_cgwindow_id('x', {'w': [10]}, set(), 1, None, 1))
    print(f'DIFF resolve {digest(outs)}')
    check('g4.resolve.normal', outs == [10, 11, None, None])


def normal_cwd_resolution(mod) -> None:
    mod._ghostty_pid_int = lambda: None
    result, ctx = mod._resolve_cwds_to_desktops({'/a': 'u1', '/b': 'u2'}, {})
    print(f'DIFF cwds {digest((sorted(result.items()), ctx))}')
    check('g4.cwds.ghostty_absent_all_none', result == {'/a': None, '/b': None} and ctx == {})


def alternate_keys_skipped(mod, mlog) -> None:
    mod._CG = _FakeCG([
        {'DisplayIdentifier': 'ABCDEFGH-1', 'Spaces': [{'ManagedSpaceID': 5}]},
        {'Display Identifier': 'GOODGOOD-1', 'spaces': [{'ManagedSpaceID': 6}]},
        {'Display Identifier': 'OKOKOKOK-1', 'Spaces': [{'id': 7}, {'ManagedSpaceID': 0}]},
    ])
    result = mod._build_space_map(1)
    text = log_text(mlog)
    check('g4.space_map.alternates_skipped_and_logged',
          result == {0: ('OKOKOKOK', 2)} and 'display 0: key Display Identifier missing' in text
          and 'display 1: key Spaces missing' in text and 'display 2 space 0: key ManagedSpaceID missing' in text)
    before = log_text(mlog)
    mod._build_space_map(1)
    check('g4.space_map.problem_logged_once', log_text(mlog) == before)


def routes_logged_on_change(mod, mlog) -> None:
    load('menubar_log')._last_by_key.clear()
    start = len(log_text(mlog))
    mod._spaces_for_wid = lambda cid, wid: {10: [5], 11: [9]}.get(wid, [])
    mod._resolve_cgwindow_id('w', {'w': [10]}, set(), 1, None, 1)
    mod._resolve_cgwindow_id('w', {'w': [10]}, set(), 1, None, 1)
    mod._resolve_cgwindow_id('w', {'w': [10, 11]}, {5}, 1, None, 1)
    text = log_text(mlog)[start:]
    check('g4.route.logged_on_change_only', text.count('route=single_name_match') == 1 and text.count('route=unclaimed_space') == 1)


def lkg_removed(mod) -> None:
    check('g4.lkg_removed', not hasattr(mod, '_cwd_desktop_lkg'))


if __name__ == '__main__':
    main()
