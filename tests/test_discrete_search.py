import hashlib
import json
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from lab.discrete_search import incumbent, select, distance, prior_observations
from lab.evolution import Campaign, PHASES
from lab.evolution_run import initialize, run
from lab.evolution_space import DEFAULTS, SEED_SHA, assignments, canonical


def node(name, parameters, total=30, created=0, valid=True, spread=0):
    return {'candidate_id': name, 'parameters': parameters, 'metrics': {'total': total},
            'created_at': created, 'valid': valid, 'cohort_digest': 'c' * 64,
            'metric_ranges': {'total': spread}}


class DiscreteSelectionTests(unittest.TestCase):
    def test_prior_evidence_checks_full_verdict_and_all_source_files(self):
        seed = {'report.json': {'source': {'simulator_files_sha256': {
            'differometor/simulate.py': 'original', 'differometor/build.py': 'unchanged'}}}}
        params = dict(DEFAULTS, prevent_cse=True)
        def render(source, p):
            return canonical(p)
        digest = hashlib.sha256(canonical(params).encode()).hexdigest()
        files = dict(seed['report.json']['source']['simulator_files_sha256'])
        files['differometor/simulate.py'] = digest
        job = {'sha': 'a' * 40, 'report.json': {'source': {'simulator_files_sha256': files}}}
        verdict = {'profile': 'full', 'category': 'valid'}
        with tempfile.TemporaryDirectory() as directory, patch('lab.discrete_search.materialize', side_effect=render):
            path = Path(directory) / 'prior.json'
            path.write_text(json.dumps(job))
            rows = prior_observations([path], seed, '', {}, lambda *a, **k: verdict)
            self.assertEqual(rows[0][0], params)
            self.assertEqual(rows[0][2]['sha'], 'a' * 40)
            files['differometor/build.py'] = 'changed'
            path.write_text(json.dumps(job))
            with self.assertRaisesRegex(ValueError, 'outside the registered materializer'):
                prior_observations([path], seed, '', {}, lambda *a, **k: verdict)
            with self.assertRaisesRegex(ValueError, 'full scientific verdict'):
                prior_observations([path], seed, '', {}, lambda *a, **k: {'profile': 'screen', 'category': 'screen'})

    def test_expands_to_interactions_then_returns_to_improved_parent(self):
        seed = node('seed', DEFAULTS)
        remaining = [p for p in assignments() if distance(p, DEFAULTS) >= 2]
        parent, choice, decision = select('local-search', [seed], remaining)
        self.assertEqual(decision['neighborhood_radius'], 2)
        improved = node('improved', choice, 25, 1)
        next_options = [p for p in remaining if p != choice]
        parent, _, decision = select('local-search', [seed, improved], next_options)
        self.assertEqual(parent['candidate_id'], 'improved')
        self.assertEqual(decision['neighborhood_radius'], 1)

    def test_noise_and_invalid_measurements_cannot_replace_incumbent(self):
        seed = node('seed', DEFAULTS, spread=.5)
        noisy = node('noisy', DEFAULTS, 29.6, 1)
        invalid = node('invalid', DEFAULTS, 1, 2, valid=False)
        self.assertEqual(incumbent([seed, noisy, invalid])['candidate_id'], 'seed')
        wrong = node('wrong', DEFAULTS, 20, 3)
        wrong['cohort_digest'] = 'd' * 64
        with self.assertRaisesRegex(ValueError, 'cohorts'):
            incumbent([seed, wrong])

    def test_both_selectors_cover_all_legal_assignments_without_duplicates(self):
        for selector in ('enumeration', 'local-search'):
            rows = [node('seed', DEFAULTS)]
            remaining = [p for p in assignments() if p != DEFAULTS]
            chosen = {canonical(DEFAULTS)}
            while remaining:
                _, choice, _ = select(selector, rows, remaining)
                self.assertNotIn(canonical(choice), chosen)
                chosen.add(canonical(choice))
                remaining.remove(choice)
                rows.append(node(str(len(rows)), choice, 30, len(rows)))
            self.assertEqual(len(chosen), 15)


class DeterministicRunnerTests(unittest.TestCase):
    def test_actual_campaign_recovers_and_exhausts_with_no_provider_or_credentials(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            state = root / 'state'
            source = 'reviewed-source'
            def render(_source, p):
                return source if p == DEFAULTS else canonical(p)
            def git(_repo, *args):
                if args == ('status', '--porcelain'):
                    return ''
                return SEED_SHA
            reports = []
            for i in range(3):
                path = root / ('seed-' + str(i) + '.json')
                path.write_text(json.dumps({'id': 'seed-' + str(i)}))
                reports.append(path)
            def evidence(job, **kwargs):
                return {'evidence_id': job['id'], 'job_id': job['id'],
                    'candidate_sha': kwargs.get('expected_sha', SEED_SHA),
                    'profile': 'full', 'category': 'valid', 'eligible_full': True,
                    'evidence_digest': 'a' * 64, 'cohort_digest': 'c' * 64,
                    'metrics': dict({p: 1. for p in PHASES}, total=30., compilation=12.,
                                    runtime=15., peak_rss_bytes=1000000.)}
            args = SimpleNamespace(state=state, repo=root, name='test', seed_report=reports,
                env_file=root / 'DOES-NOT-EXIST', minutes=10, max_evaluations=28,
                max_model_calls=0, selector='local-search', host='amd-hackathon',
                root='/workspace/feyer-lab', publish=False)
            from lab.evolution_report import export_campaign, store_text_artifact
            components = (Campaign, evidence, lambda job: {}, export_campaign, store_text_artifact)
            def evaluate(campaign, _state, candidate, secrets, runtime):
                for profile in ('screen', 'full'):
                    reservation = campaign.reserve_evaluation('coordinator', secrets['coordinator'], candidate['candidate_id'], profile)
                    jid = candidate['candidate_id'] + '-' + profile
                    campaign.bind_evaluation('coordinator', secrets['coordinator'], reservation['request_id'], jid)
                    e = evidence({'id': jid}, expected_sha=candidate['commit_sha'])
                    if profile == 'screen':
                        e.update(profile='screen', category='screen', eligible_full=False, screen_passed=True)
                    campaign.observe('coordinator', secrets['coordinator'], candidate['candidate_id'], e)
            with patch('lab.evolution_run.components', return_value=components), \
                 patch('lab.evolution_run.git', side_effect=git), \
                 patch('lab.evolution_run.source_from_git', return_value=source), \
                 patch('lab.evolution_run.materialize', side_effect=render), \
                 patch('lab.evolution_run.subprocess.run'), \
                 patch('lab.evolution_run.publish', return_value={'context_sha256': 'b' * 64}), \
                 patch('lab.evolution_run.settings') as settings, \
                 patch('lab.evolution_run.TokenFactory') as provider, \
                 patch('lab.evolution_run.materialize_commit', side_effect=lambda repo, parameters, *a, **k:
                       {'sha': hashlib.sha1(canonical(parameters).encode()).hexdigest()}), \
                 patch('lab.evolution_run.evaluate', side_effect=evaluate):
                initialize(args)
                for _ in range(14):
                    result = run(SimpleNamespace(state=state, once=True))
                    self.assertEqual(result['status'], 'evaluated')
                result = run(SimpleNamespace(state=state, once=True))
                self.assertEqual(result['status'], 'budget_exhausted')
                settings.assert_not_called()
                provider.assert_not_called()
                campaign = Campaign(state / 'campaign.sqlite3')
                snap = campaign.snapshot()
                self.assertEqual(len(snap['candidates']), 15)
                self.assertEqual(snap['usage'], {'proposals': 15, 'evaluations': 28, 'model_calls': 0})
                self.assertEqual(snap['campaign']['spec']['budget']['max_model_calls'], 0)
                self.assertNotIn('qwen', snap['campaign']['spec']['model_manifest'])
                self.assertTrue(campaign.verify_log())
                secrets = json.loads((state / 'credentials.json').read_text())
                with self.assertRaisesRegex(RuntimeError, 'model_calls budget'):
                    campaign.record_model_call('coordinator', secrets['coordinator'], 'forbidden', {})
                runtime = json.loads((state / 'runtime.json').read_text())
                runtime['selector'] = 'qwen'
                (state / 'runtime.json').write_text(json.dumps(runtime))
                with self.assertRaisesRegex(ValueError, 'Selector differs'):
                    run(SimpleNamespace(state=state, once=True))


if __name__ == '__main__':
    unittest.main()
