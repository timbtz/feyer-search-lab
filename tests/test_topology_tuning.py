import copy
import importlib.util
import unittest
import tempfile
import subprocess
import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from lab.topology_tuning import VERSION, canonical, digest, observations, render, validate_manifest
from tests.test_evolution_evidence import full_job


def manifest():
    return {'version': VERSION, 'parent_sha': 'a' * 40,
        'base_sources': {'differometor/simulate.py': 'REUSE = True\nCHUNK = 1\n'},
        'dimensions': {'reuse': [True, False], 'chunk': [1, 2, 4, 8]},
        'defaults': {'reuse': True, 'chunk': 1},
        'legal': [{'reuse': r, 'chunk': c} for r in [True, False] for c in [1, 2, 4, 8]],
        'replacements': [
            {'path': 'differometor/simulate.py', 'dimension': 'reuse', 'anchor': 'REUSE = True',
             'values': {'true': 'REUSE = True', 'false': 'REUSE = False'}},
            {'path': 'differometor/simulate.py', 'dimension': 'chunk', 'anchor': 'CHUNK = 1',
             'values': {canonical(v): 'CHUNK = ' + str(v) for v in [1, 2, 4, 8]}}]}


class TopologyManifestTests(unittest.TestCase):
    def test_every_registered_assignment_has_unique_source_and_exact_default(self):
        m = manifest()
        self.assertEqual(len(validate_manifest(m)), 64)
        self.assertEqual(render(m, m['defaults']), m['base_sources'])
        self.assertEqual(render(m, {'reuse': False, 'chunk': 8})['differometor/simulate.py'],
                         'REUSE = False\nCHUNK = 8\n')
        with self.assertRaises(ValueError):
            render(m, {'reuse': False, 'chunk': 3})

    def test_unsafe_paths_overlap_and_duplicate_content_are_rejected(self):
        for mode in ['path', 'overlap', 'duplicate', 'anchor', 'default']:
            m = manifest()
            if mode == 'path':
                m['base_sources']['../benchmark.py'] = 'x = 1'
            if mode == 'overlap':
                m['replacements'].append(copy.deepcopy(m['replacements'][0]))
            if mode == 'duplicate':
                m['replacements'][0]['values']['false'] = 'REUSE = True'
            if mode == 'anchor':
                m['replacements'][0]['anchor'] = 'missing'
            if mode == 'default':
                m['defaults']['chunk'] = 2
            with self.subTest(mode=mode), self.assertRaises(ValueError):
                validate_manifest(m)

    def test_exact_source_cohort_and_full_evidence_are_required(self):
        m = manifest()
        seed = full_job()
        seed['report.json']['source']['simulator_files_sha256'] = {
            p: digest(s) for p, s in m['base_sources'].items()}
        other_topology = copy.deepcopy(seed)
        other_topology['id'] = 'other-topology'
        other_topology['report.json']['source']['simulator_files_sha256']['differometor/simulate.py'] = 'f'*64
        other_cohort = copy.deepcopy(seed)
        other_cohort['id'] = 'other-cohort'
        other_cohort['result']['worker_sha256'] = 'e'*64
        missing = copy.deepcopy(seed)
        missing['id'] = 'infrastructure'
        missing.pop('report.json')
        rows, cohort = observations(m, [other_topology, other_cohort, missing, seed], seed)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]['job_ids'], [seed['id']])
        self.assertEqual(rows[0]['commit_shas'], [seed['sha']])
        self.assertEqual(len(cohort), 64)
        with self.assertRaisesRegex(ValueError, 'source differs'):
            observations(m, [], other_topology)

    def test_failed_or_screen_seed_is_rejected_before_import(self):
        for mode in ['official', 'strict', 'screen', 'wrong-sha']:
            seed = full_job()
            if mode == 'official':
                seed['result']['official_passed'] = False
            elif mode == 'strict':
                seed['result']['regression_passed'] = False
                seed['comparison.json']['passed'] = False
                seed['comparison.json']['checks']['gradient']['passed'] = False
            elif mode == 'screen':
                seed['profile'] = seed['result']['profile'] = 'screen'
            else:
                seed['sha'] = seed['result']['sha'] = seed['report.json']['source']['commit'] = 'b' * 40
            with self.subTest(mode=mode), self.assertRaises(ValueError):
                observations(manifest(), [], seed)

    def test_bad_budget_does_not_create_state(self):
        from lab.topology_run import initialize
        import time
        with tempfile.TemporaryDirectory() as directory:
            state = Path(directory) / 'absent'
            for count, deadline in [(0, time.time()+10), (True, time.time()+10),
                                    (2, float('nan')), (2, float('inf')), (2, time.time()-1)]:
                with self.assertRaises(ValueError):
                    initialize(SimpleNamespace(state=state, max_evaluations=count, deadline_unix=deadline))
                self.assertFalse(state.exists())


@unittest.skipUnless(importlib.util.find_spec('smac'), 'Isolated SMAC environment required')
class TopologySmacTests(unittest.TestCase):
    def request(self, count=4):
        from lab.topology_smac import metadata
        m = manifest()
        return {'metadata': metadata(), 'dimensions': m['dimensions'], 'legal': m['legal'],
                'observations': [{'parameters': p, 'status': 'valid', 'cost': 20 + i * 5}
                                 for i, p in enumerate(m['legal'][:count])]}

    def test_startup_is_explicit_and_real_acquisition_replays(self):
        from lab.topology_smac import choose
        startup = choose(self.request(1))
        self.assertFalse(startup['decision']['model_trained'])
        self.assertEqual(startup['decision']['origin'], 'local-startup')
        a, b = choose(self.request()), choose(self.request())
        self.assertEqual(a, b)
        self.assertTrue(a['decision']['model_trained'])
        self.assertEqual(a['decision']['acquisition_rank'], 1)
        self.assertIn(a['parameters'], manifest()['legal'][4:])
        reverse = self.request()
        for i, row in enumerate(reverse['observations']):
            row['cost'] = 35 - i * 5
        self.assertNotEqual(a['parameters'], choose(reverse)['parameters'])

    def test_drift_duplicate_history_and_failure_cost_rejected(self):
        from lab.topology_smac import choose
        for mode in ['drift', 'duplicate', 'penalty']:
            r = self.request()
            if mode == 'drift':
                r['metadata']['n_trees'] += 1
            if mode == 'duplicate':
                r['observations'].append(r['observations'][0])
            if mode == 'penalty':
                r['observations'][0]['status'] = 'invalid'
            with self.subTest(mode=mode), self.assertRaises(ValueError):
                choose(r)

    def test_runner_persists_candidate_and_resumes_without_duplicate_commit(self):
        from lab import topology_run
        from lab.evolution import Campaign
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            repo = root / 'controller'
            repo.mkdir()
            def git(*args):
                return subprocess.check_output(['git', '-C', str(repo), *args], text=True).strip()
            git('init', '-q')
            git('config', 'user.name', 'Topology Test')
            git('config', 'user.email', 'topology@example.invalid')
            (repo / 'differometor').mkdir()
            m = manifest()
            (repo / 'differometor/simulate.py').write_text(m['base_sources']['differometor/simulate.py'])
            git('add', '.')
            git('commit', '-qm', 'seed')
            sha = git('rev-parse', 'HEAD')
            m['parent_sha'] = sha
            seed = full_job()
            seed['sha'] = seed['result']['sha'] = seed['report.json']['source']['commit'] = sha
            seed['report.json']['source']['simulator_files_sha256'] = {
                p: digest(s) for p, s in m['base_sources'].items()}
            manifest_path, seed_path = root / 'manifest.json', root / 'seed.json'
            manifest_path.write_text(json.dumps(m))
            seed_path.write_text(json.dumps(seed))
            state = root / 'state'
            import time
            args = SimpleNamespace(state=state, repo=repo, manifest=manifest_path, seed_report=seed_path,
                name='topology-test', deadline_unix=time.time()+120, max_evaluations=10,
                host='amd-hackathon', root='/workspace/feyer-lab', publish=False, once=True)
            topology_run.initialize(args)
            with patch.object(topology_run, 'evaluate') as evaluate:
                topology_run.run(args)
                first = Campaign(state / 'campaign.sqlite3').snapshot()
                self.assertEqual(len(first['candidates']), 2)
                candidate = evaluate.call_args.args[2]
                first_sha = candidate['commit_sha']
                topology_run.run(args)
                again = evaluate.call_args.args[2]
                self.assertEqual(again['commit_sha'], first_sha)
                self.assertEqual(again['candidate_id'], candidate['candidate_id'])
                self.assertEqual(len(Campaign(state / 'campaign.sqlite3').snapshot()['candidates']), 2)
                self.assertFalse((state / 'pending-topology.json').exists())


if __name__ == '__main__':
    unittest.main()
