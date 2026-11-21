import copy
import importlib.util
import unittest

from lab.evolution_space import assignments, DEFAULTS, canonical
from lab.search_policy import resolve
from lab.smac_search import FAILURE_COST, training_observations
from lab.smac_transport import invoke


class SearchPolicyTests(unittest.TestCase):
    def test_auto_respects_remaining_space_and_evaluation_count(self):
        self.assertEqual(resolve('auto', 14, 28)['effective'], 'enumeration')
        self.assertEqual(resolve('auto', 14, 6)['effective'], 'smac')
        self.assertEqual(resolve('auto', 100, 300)['effective'], 'smac')
        self.assertEqual(resolve('local-search', 100, 300)['effective'], 'local-search')
        self.assertEqual(resolve('smac', 14, 28)['effective'], 'smac')

    def test_remote_endpoint_requires_complete_absolute_paths(self):
        with self.assertRaises(ValueError):
            invoke({}, {'host': 'host', 'python': None, 'root': '/tmp'})
        with self.assertRaises(ValueError):
            invoke({}, {'host': '-oProxyCommand=bad', 'python': '/python', 'root': '/tmp'})

    def test_only_same_cohort_full_verdicts_train_and_failures_are_penalized(self):
        snapshot = {'campaign': {'spec': {'cohort_digest': 'cohort'}}, 'candidates': [], 'evidence': []}
        cases = [('good', 'valid', 'full', 'cohort', True),
                 ('bad', 'invalid_candidate', 'full', 'cohort', False),
                 ('screen', 'screen', 'screen', 'cohort', False),
                 ('transport', 'infrastructure_error', 'full', 'cohort', False),
                 ('other', 'valid', 'full', 'other-cohort', True)]
        for name, category, profile, cohort, valid in cases:
            snapshot['candidates'].append({'candidate_id': name, 'commit_sha': name,
                'parameters': DEFAULTS, 'evidence_ids': [name], 'valid': valid})
            snapshot['evidence'].append({'evidence_id': name, 'job_id': name, 'category': category,
                'profile': profile, 'cohort_digest': cohort, 'eligible_full': valid, 'metrics': {'total': 30.}})
        rows = training_observations(snapshot)
        self.assertEqual([r['candidate_id'] for r in rows], ['good', 'bad'])
        self.assertEqual([r['cost'] for r in rows], [30., FAILURE_COST])


@unittest.skipUnless(importlib.util.find_spec('smac'), 'Optional isolated SMAC controller environment required')
class RealSmacTests(unittest.TestCase):
    def setUp(self):
        from lab.smac_search import metadata
        self.metadata = metadata()
        self.space = assignments()
        self.rows = [{'parameters': p, 'cost': 30. + i * 10, 'status': 'valid'}
                     for i, p in enumerate(self.space[:5])]
        self.request = {'metadata': self.metadata, 'seed': 0,
                        'options': self.space[5:], 'observations': self.rows}

    def test_round_trip_all_conditional_configurations(self):
        from ConfigSpace import Configuration
        from lab.smac_search import configuration_space, encode, decode
        cs = configuration_space(0)
        for p in self.space:
            config = Configuration(cs, values=encode(p))
            self.assertEqual(decode(config), p)
            self.assertEqual('prevent_cse' in dict(config), p['checkpoint'])

    def test_real_acquisition_changes_with_evidence_and_replays(self):
        from lab.smac_search import choose
        first = choose(self.request)
        repeated = choose(self.request)
        self.assertEqual(first['parameters'], repeated['parameters'])
        self.assertIn('Acquisition Function', first['decision']['selection_origin'])
        opposite = copy.deepcopy(self.request)
        for i, row in enumerate(opposite['observations']):
            row['cost'] = 70. - i * 10
        changed = choose(opposite)
        self.assertNotEqual(first['parameters'], changed['parameters'])
        self.assertIn(first['parameters'], self.request['options'])
        self.assertEqual(first['decision']['training_configurations'], 5)

    def test_duplicate_history_and_runtime_drift_fail_closed(self):
        from lab.smac_search import choose
        bad = copy.deepcopy(self.request)
        bad['metadata']['n_trees'] += 1
        with self.assertRaisesRegex(ValueError, 'runtime differs'):
            choose(bad)
        bad = copy.deepcopy(self.request)
        bad['options'].append(self.rows[0]['parameters'])
        with self.assertRaisesRegex(ValueError, 'already evaluated'):
            choose(bad)

    def test_scientific_failure_is_learned_without_dispatching_it_again(self):
        from lab.smac_search import choose
        request = copy.deepcopy(self.request)
        request['observations'][1].update(status='invalid', cost=FAILURE_COST)
        result = choose(request)
        self.assertIn(result['parameters'], request['options'])
        self.assertNotEqual(result['parameters'], request['observations'][1]['parameters'])


if __name__ == '__main__':
    unittest.main()
