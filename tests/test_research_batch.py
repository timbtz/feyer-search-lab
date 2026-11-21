import copy
import unittest

from lab.team_search import apply, initial_state


def record(identity, sha):
    return dict(schema='feyer-research-record-v1', record_id=identity,
                executor=dict(kind='manual', id='review'), kind='diagnose', status='completed',
                candidate_sha=sha, parents=[], target_phases=['compilation'],
                hypothesis='Review compilation', change_summary='Source review',
                source_ref='https://example.com/immutable', source_digest='a' * 64,
                evaluations=[])


class ResearchBatchTests(unittest.TestCase):
    def test_idempotence_and_immutable_conflicts(self):
        state = initial_state('owner')
        rows = [record('one', 'b' * 40), record('two', 'c' * 40)]
        updated, output = apply(state, 'research-batch', 'owner', rows)
        self.assertEqual(len(output), 2)
        again, _ = apply(updated, 'research-batch', 'owner', rows)
        self.assertEqual(updated, again)
        before = copy.deepcopy(updated)
        with self.assertRaises(ValueError):
            apply(updated, 'research-batch', 'owner',
                  [record('three', 'd' * 40), {**rows[0], 'hypothesis': 'Changed'}])
        self.assertEqual(updated, before)

    def test_coordinator_and_all_or_nothing_validation(self):
        state = initial_state('owner')
        before = copy.deepcopy(state)
        with self.assertRaises(ValueError):
            apply(state, 'research-batch', 'other', [record('one', 'b' * 40)])
        with self.assertRaises(ValueError):
            apply(state, 'research-batch', 'owner', [record('one', 'b' * 40), {}])
        self.assertEqual(state, before)
