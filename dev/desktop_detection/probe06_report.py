# INFRASTRUCTURE
from typing import List

# FUNCTIONS

def _print_result_table(results: List[dict]) -> None:
    print("=== Per-Primitive Result Table ===")
    hdr = f"{'Prim':<5}  {'Symbol':>6}  {'Moved':>5}  {'in_after':>8}  Shot_after"
    print(hdr)
    print("-" * 60)
    for r in results:
        sym_s    = "yes"  if r.get("sym_ok")           else "no"
        moved_s  = "yes"  if r.get("moved") is True    else ("no" if r.get("moved") is False else "-")
        iafter_s = str(r["in_after"]) if "in_after" in r else "-"
        shot_s   = r.get("shot_after", "-")
        print(f"{r['label']:<5}  {sym_s:>6}  {moved_s:>5}  {iafter_s:>8}  {shot_s}")
    print()

def _print_headline(results: List[dict], ax: bool, sc: bool) -> None:
    moved_labels = [r["label"] for r in results if r.get("moved")]
    if moved_labels:
        print(f"HEADLINE: primitive(s) {', '.join(moved_labels)} MOVED the window"
              f"  |  AX={ax}  ScreenCapture={sc}")
    else:
        print(f"HEADLINE: NO primitive moved the window  |  AX={ax}  ScreenCapture={sc}")
