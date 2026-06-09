"""
CI regression test: composition invariant over synthetic fixture corpus.

Asserts that for every modified block across all 9 fixture entries:
  Inv1: "".join(t for tag,t in spans if tag in ("equal","stripped")) == C0_block_text
  Inv2: "".join(t for tag,t in spans if tag in ("equal","injected")) == Cfwd_block_text

A future pass that mutates content without recording an op breaks these invariants.
The fixture covers all 8 proxy passes + dedup_wakeup, including the money-shot
double-inject pattern (fix-3: TN with BG summary → first_pass + bg_exit + dedup_wakeup).

Run (from project root):
    ./venv/bin/python dev/proxy_dual_log/test_composition_invariant.py

Exit 0 = all blocks pass both invariants.
Exit 1 = at least one invariant violation (prints which entry/block/pass/detail).
"""

# INFRASTRUCTURE

import json
import sys
from pathlib import Path

_HERE = Path(__file__).parent.resolve()
sys.path.insert(0, str(_HERE))
sys.path.insert(0, str(_HERE.parents[1]))

import composition_probe as _probe

FIXTURE_PATH = _HERE / "fixtures" / "invariant_corpus.jsonl"

PASS_LIST = []
FAIL_LIST = []


# FUNCTIONS

# Load fixture entries — hard-fail if file absent (absent fixture = broken test, not a skip)
def load_fixture() -> list:
    if not FIXTURE_PATH.exists():
        print(f"FIXTURE MISSING: {FIXTURE_PATH}", file=sys.stderr)
        sys.exit(1)
    entries = []
    with open(FIXTURE_PATH) as f:
        for lineno, line in enumerate(f, 1):
            line = line.strip()
            if not line:
                continue
            try:
                entries.append(json.loads(line))
            except json.JSONDecodeError as e:
                print(f"FIXTURE PARSE ERROR line {lineno}: {e}", file=sys.stderr)
                sys.exit(1)
    return entries


def check(name: str, condition: bool, detail: str = "") -> None:
    if condition:
        PASS_LIST.append(name)
    else:
        FAIL_LIST.append(name)
        print(f"  FAIL  {name}" + (f": {detail}" if detail else ""))


# Run both invariants for every modified block across all fixture entries
def run_all_cases(entries: list) -> tuple:
    blocks_checked = 0
    blocks_passed = 0

    for entry in entries:
        fid = entry.get("flow_id", "?")
        payload = _probe._strip_cache_control(entry.get("payload", {}))
        messages = payload.get("messages", [])
        if not messages:
            continue

        orig = list(messages)
        final_msgs, ops = _probe.run_passes_and_collect_ops(list(messages))

        for msg_idx, blk_map in ops.items():
            c0_content   = orig[msg_idx].get("content", "")     if msg_idx < len(orig)       else ""
            cfwd_content = final_msgs[msg_idx].get("content", "") if msg_idx < len(final_msgs) else ""

            for blk_idx, op_list in blk_map.items():
                blocks_checked += 1
                c0_text   = _probe._block_text(c0_content,   blk_idx)
                cfwd_text = _probe._block_text(cfwd_content, blk_idx)
                spans     = _probe.compose_block(c0_text, op_list)
                ok, detail = _probe.check_invariants(spans, c0_text, cfwd_text)

                pass_chain = [op[0] for op in op_list]
                label = f"{fid}/msg[{msg_idx}]/blk[{blk_idx}] passes={pass_chain}"
                check(label, ok, detail)

                if ok:
                    blocks_passed += 1

    return blocks_checked, blocks_passed


# ORCHESTRATOR

def test_composition_invariant_workflow() -> None:
    entries = load_fixture()

    print(f"Loaded {len(entries)} fixture entries from {FIXTURE_PATH.name}")
    print()

    blocks_checked, blocks_passed = run_all_cases(entries)

    print()
    check(
        "blocks_checked > 0",
        blocks_checked > 0,
        f"fixture produced 0 modified blocks — fixture may be empty or have no trigger patterns",
    )

    total = len(PASS_LIST) + len(FAIL_LIST)
    print(f"{len(PASS_LIST)}/{total} checks passed")
    print(f"entries={len(entries)}  blocks_checked={blocks_checked}  blocks_passed={blocks_passed}")

    if FAIL_LIST:
        print(f"\nFAILED: {FAIL_LIST}")
        sys.exit(1)

    print("ALL PASS")


if __name__ == "__main__":
    test_composition_invariant_workflow()
