"""Fast negative controls for app_audit_gate, without starting SDL or the game."""
import copy
import importlib.util
from pathlib import Path
import unittest

SPEC = importlib.util.spec_from_file_location('app_audit_gate', Path(__file__).with_name('app_audit_gate.py'))
gate = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(gate)


def valid_report():
    return {
        'planned_checks': ['typed_backend_proof', 'typed_scalar_observation'],
        'checks': [{'id': 'typed_backend_proof', 'passed': True},
                   {'id': 'typed_scalar_observation', 'passed': True}],
        'complete': True, 'passed': True, 'completed_checks': 2, 'pass_count': 2,
        'fail_count': 0, 'unrun_count': 0,
        'backend_audit': {'backend': 'typed72', 'session': True, 'typed_steps': 3,
                          'typed_commands': 2, 'typed_tick': 3, 'v_tick_now': 0,
                          'v_tick_at_start': 0, 'v_native_tick_now': 0, 'v_native_tick_at_start': 0},
        'scalar_observation': {'projections_before': 12, 'projections_after': 12}}


class AuditGateTests(unittest.TestCase):
    def test_valid_typed(self):
        self.assertEqual(gate.validate(valid_report(), 'typed'), 2)

    def test_missing_empty_duplicate_or_failed_checks(self):
        for kind in ('missing', 'empty', 'duplicate', 'failed', 'incomplete', 'fatal'):
            row = copy.deepcopy(valid_report())
            if kind == 'missing': row['checks'].pop()
            if kind == 'empty': row['planned_checks'] = []
            if kind == 'duplicate': row['checks'].append(row['checks'][0])
            if kind == 'failed': row['checks'][0]['passed'] = False
            if kind == 'incomplete': row['complete'] = False
            if kind == 'fatal': row['fatal_error'] = 'injected'
            with self.subTest(kind=kind), self.assertRaises(ValueError):
                gate.validate(row, 'typed')

    def test_legacy_clock_motion_or_unexecuted_typed_path_rejected(self):
        for key in ('v_tick_now', 'v_native_tick_now', 'typed_steps', 'typed_commands', 'typed_tick'):
            row = valid_report()
            row['backend_audit'][key] = 1 if key.startswith('v_') else 0
            with self.subTest(key=key), self.assertRaises(ValueError):
                gate.validate(row, 'typed')

    def test_scalar_projection_rejected(self):
        row = valid_report()
        row['scalar_observation']['projections_after'] += 1
        with self.assertRaises(ValueError):
            gate.validate(row, 'typed')

    def test_missing_proof_rejected(self):
        row = valid_report()
        del row['backend_audit']
        with self.assertRaises(KeyError):
            gate.validate(row, 'typed')

    def test_baseline_does_not_require_typed_evidence(self):
        row = valid_report()
        del row['backend_audit']
        del row['scalar_observation']
        self.assertEqual(gate.validate(row, 'v-baseline'), 2)


if __name__ == '__main__':
    unittest.main()
