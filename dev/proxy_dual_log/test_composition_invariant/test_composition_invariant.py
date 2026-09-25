# INFRASTRUCTURE
import json
import sys
from pathlib import Path

_HERE = Path(__file__).parent.resolve()
sys.path.insert(0, str(_HERE))

_AREA_ROOT = next(p for p in Path(__file__).resolve().parents if p.name == 'proxy_dual_log')
_PROJECT_ROOT = _AREA_ROOT.parent.parent
sys.path.insert(0, str(_PROJECT_ROOT))

import composition_probe as _probe

FIXTURE_PATH = _AREA_ROOT / "fixtures" / "invariant_corpus.jsonl"

PASS_LIST = []
FAIL_LIST = []


# ORCHESTRATOR

def test_composition_invariant_workflow() -> None:
    entries = load_fixture()

    print_loaded(entries)
    print()

    blocks_checked, blocks_passed = run_all_cases(entries)

    print()
    run_check(blocks_checked)

    total = compute_total()
    print_checks_passed(total)
    print_entries(entries, blocks_checked, blocks_passed)

    if FAIL_LIST:
        print_failed()
        sys.exit(1)

    print("ALL PASS")


# FUNCTIONS

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


def print_loaded(entries):
    print(f"Loaded {len(entries)} fixture entries from {FIXTURE_PATH.name}")


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


def check(name: str, condition: bool, detail: str = "") -> None:
    if condition:
        PASS_LIST.append(name)
    else:
        FAIL_LIST.append(name)
        print(f"  FAIL  {name}" + (f": {detail}" if detail else ""))


def run_check(blocks_checked):
    check(
        "blocks_checked > 0",
        blocks_checked > 0,
        f"fixture produced 0 modified blocks — fixture may be empty or have no trigger patterns",
    )


def compute_total():
    return len(PASS_LIST) + len(FAIL_LIST)


def print_checks_passed(total):
    print(f"{len(PASS_LIST)}/{total} checks passed")


def print_entries(entries, blocks_checked, blocks_passed):
    print(f"entries={len(entries)}  blocks_checked={blocks_checked}  blocks_passed={blocks_passed}")


def print_failed():
    print(f"\nFAILED: {FAIL_LIST}")


if __name__ == "__main__":
    test_composition_invariant_workflow()
