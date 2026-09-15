# INFRASTRUCTURE
from typing import Dict, List, Tuple

# FUNCTIONS

def _print_session_table(rows: List[dict]) -> None:
    H = '{:<20} {:<38} {:<9} {:<8} {:<12} {:<8} {:<9} {:<10}'
    print(H.format('session_name', 'cwd', 'tty', 'uuid[:8]', 'cgwindow_id', 'space_id', 'display', 'desktop_no'))
    print('-' * 120)
    for r in rows:
        cd = ('...' + r['cwd'][-35:]) if len(r['cwd']) > 38 else r['cwd']
        ns = lambda v: str(v) if v is not None else 'None'
        print(H.format(r['session_name'][:20], cd, r['tty'], r['uuid'][:8],
                       ns(r['cgwindow_id']), ns(r['space_id']),
                       r['display_id'], ns(r['desktop_no'])))

def _print_space_overview(space_map: Dict[int, Tuple[str, int]], active_space: int) -> None:
    print(f'\n=== Active Space: {active_space}  '
          f'(desktop {space_map.get(active_space, ("?","?"))[1]})')

    print('\n=== All Spaces per Display (ordered by desktop_no):')
    by_display: Dict[str, List[Tuple[int, int]]] = {}
    for sid, (disp, dno) in sorted(space_map.items(), key=lambda x: x[1][1]):
        by_display.setdefault(disp, []).append((sid, dno))
    for disp, spc in by_display.items():
        print(f'  Display {disp}...: space_ids=[{", ".join(str(s) for s,_ in spc)}]'
              f'  desktops=[{", ".join(str(d) for _,d in spc)}]')

def _print_detection_summary(rows: List[dict]) -> None:
    n_matched = sum(1 for r in rows if r['cgwindow_id'] is not None)
    print(f'\n=== Detected Mains: {len(rows)}   With CGWindowID: {n_matched}   Without: {len(rows)-n_matched}')

    misses = [r for r in rows if r['cgwindow_id'] is None]
    if misses:
        print('\n=== Mains without CGWindowID match:')
        for r in misses:
            print(f'  - {r["session_name"]}: win_name={repr(r["win_name"])} diag={r["diagnostic"]}')

    by_strategy: Dict[str, int] = {}
    for r in rows:
        by_strategy[r['strategy']] = by_strategy.get(r['strategy'], 0) + 1
    print('\n=== Strategy breakdown: ' + '  '.join(f'{s}:{c}' for s, c in sorted(by_strategy.items())))
