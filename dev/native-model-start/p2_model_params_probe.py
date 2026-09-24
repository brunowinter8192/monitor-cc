# INFRASTRUCTURE
import sys
from pathlib import Path

WORKTREE_ROOT = Path(__file__).resolve().parents[2]

sys.path.insert(0, str(WORKTREE_ROOT / 'src'))
from model_override_injection_tests import (
    test_legacy_only_is_ignored,
    test_model_params_hit,
    test_model_params_miss,
    test_suffixed_model_id_is_deliberate_miss,
    test_model_params_presence_wins_over_legacy,
    test_empty_and_partial_entries,
    test_config_load_failure_fails_open,
    test_fixation_pins_model_params_snapshot,
    test_fixation_fresh_instance_picks_up_new_config,
    test_fixation_legacy_only_config_pins_no_op,
    test_fixation_miss_is_pinned_too,
    test_fixation_load_failure_does_not_pin,
)
from thinking_context_management_tests import (
    test_clear_thinking_edit_stripped_when_thinking_disabled,
    test_forwarded_delta_includes_thinking,
    test_context_management_strip_is_attributed,
)
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from dev.refactoring.strand_runner import strand_workflow

_STRANDS = [
    'test_legacy_only_is_ignored',
    'test_model_params_hit',
    'test_model_params_miss',
    'test_suffixed_model_id_is_deliberate_miss',
    'test_model_params_presence_wins_over_legacy',
    'test_empty_and_partial_entries',
    'test_config_load_failure_fails_open',
    'test_fixation_pins_model_params_snapshot',
    'test_fixation_fresh_instance_picks_up_new_config',
    'test_fixation_legacy_only_config_pins_no_op',
    'test_fixation_miss_is_pinned_too',
    'test_fixation_load_failure_does_not_pin',
    'test_clear_thinking_edit_stripped_when_thinking_disabled',
    'test_forwarded_delta_includes_thinking',
    'test_context_management_strip_is_attributed',
]

# ORCHESTRATOR

def run_probe_workflow() -> int:
    return strand_workflow(globals(), __file__, _STRANDS, report_path=str(WORKTREE_ROOT / 'dev' / 'native-model-start' / 'md' / 'p2_model_params_probe.md'), title='p2_model_params_probe')

if __name__ == '__main__':
    sys.exit(run_probe_workflow())
