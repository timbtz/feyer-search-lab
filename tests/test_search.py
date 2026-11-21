import copy
import hashlib
import json
from pathlib import Path
import subprocess
import tempfile
import unittest

from lab.phase_report import GROUPS
from lab.search import build_context, committed_documents, markdown, run_evidence


def report():
    return {'benchmark': 'official', 'starter_sha256': 'e' * 64,
            'phases': [{'key': k, 'seconds': 1.0} for keys in GROUPS.values() for k in keys],
            'timing_seconds': {'end_to_end': 14, 'runtime_median': 7},
            'environment': {'cpu_model': 'same', 'cpu_affinity_ids': [2],
                'requested_logical_cpus': 1, 'backend': 'cpu', 'jax_enable_x64': True,
                'persistent_compilation_cache': False, 'python': '3.12',
                'packages': {'jax': 'same'}, 'thread_limits': {'OMP_NUM_THREADS': '1'}, 'xla_flags': None},
            'inputs': {'frequency_count': 101, 'gradient_parameter_count': 193,
                       'setup_sha256': 'fixture', 'reference_sha256': 'reference'}}


def job(sha, identifier='run-a', profile='full'):
    return {'id': identifier, 'sha': sha, 'profile': profile, 'status': 'completed',
            'agent': 'a', 'branch': 'explore/a', 'direction': 'matrix',
            'report.json': report(), 'comparison.json': {'passed': True},
            'result': {'official_passed': profile == 'full', 'regression_passed': True,
                'peak_rss_kib': 1000, 'wall_seconds': 30, 'evaluator_sha256': 'e' * 64,
                'memory_budget_bytes': 32_000_000_000,
                'memory_monitoring': {'enforcement': 'sampled_process_group_rss',
                                      'kernel_memory_limit_enforced': False, 'exceeded': False}}}


class SearchEvidenceTests(unittest.TestCase):
    def test_screen_and_official_only_do_not_qualify(self):
        self.assertFalse(run_evidence(job('a' * 40, profile='screen'))['validated'])
        j = job('a' * 40)
        j['comparison.json']['passed'] = False
        self.assertFalse(run_evidence(j)['validated'])
        j['comparison.json']['passed'] = True
        j['result']['memory_monitoring']['exceeded'] = True
        self.assertFalse(run_evidence(j)['validated'])

    def test_hash_mismatch_or_incomplete_provenance_fails_closed(self):
        j = job('a' * 40)
        self.assertTrue(run_evidence(j)['validated'])
        j['result']['evaluator_sha256'] = 'different'
        self.assertFalse(run_evidence(j)['validated'])
        j = job('a' * 40)
        j['report.json']['environment'].pop('thread_limits')
        self.assertFalse(run_evidence(j)['validated'])

    def test_resource_and_environment_changes_split_cohorts(self):
        original = job('a' * 40)
        a = run_evidence(original)
        for field in ('cpu_model', 'python', 'cpu_affinity_ids'):
            other = copy.deepcopy(original)
            other['report.json']['environment'][field] = ['different'] if field == 'cpu_affinity_ids' else 'different'
            self.assertNotEqual(a['cohort'], run_evidence(other)['cohort'])
        other = copy.deepcopy(original)
        other['result']['memory_budget_bytes'] = 55_000_000_000
        self.assertNotEqual(a['cohort'], run_evidence(other)['cohort'])


class SearchGraphTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.repo = Path(self.tmp.name)
        self.git('init', '-b', 'main')
        self.git('config', 'user.name', 'Test')
        self.git('config', 'user.email', 'test@example.invalid')
        (self.repo / 'differometor').mkdir()
        (self.repo / 'differometor/simulate.py').write_text('# source a\n')
        self.git('add', '.')
        self.git('commit', '-m', 'a')
        self.a = self.git('rev-parse', 'HEAD')
        (self.repo / 'differometor/simulate.py').write_text('# source b\n')
        self.git('add', '.')
        self.git('commit', '-m', 'b')
        self.b = self.git('rev-parse', 'HEAD')

    def tearDown(self):
        self.tmp.cleanup()

    def git(self, *args):
        return subprocess.check_output(['git', '-C', str(self.repo), *args], text=True,
                                       stderr=subprocess.PIPE).strip()

    def document(self, name, payload):
        path = self.repo / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload))

    def save(self):
        self.git('add', '.')
        self.git('commit', '-m', 'records')

    def feedback(self, sha, identifier, **kwargs):
        return {'candidate_sha': sha, 'agent_response': {'hypothesis': 'Faster setup', 'notes': 'Measured once'},
                'full': job(sha, identifier), **kwargs}

    def test_reads_other_branch_records_ignores_dirty_files_and_deduplicates_refs(self):
        self.git('switch', '-c', 'explore/records')
        self.document('experiments/runs/a/candidate-01.json', self.feedback(self.a, 'first'))
        self.document('experiments/agents/a.json', {'agent_id': 'a', 'branch': 'explore/records', 'direction': 'matrix'})
        self.save()
        self.git('branch', 'duplicate')
        self.git('switch', 'main')
        self.document('experiments/runs/uncommitted/candidate-99.json', self.feedback(self.b, 'dirty'))
        docs = committed_documents(self.repo)
        self.assertEqual(len(docs), 2)
        self.assertTrue(all(len(d['origins']) == 2 for d in docs))
        context = build_context(self.repo)
        self.assertEqual([n['sha'] for n in context['candidates']], [self.a])
        self.assertEqual(context['agents'][0]['id'], 'a')

    def test_failed_repeat_is_retained_and_blocks_combination(self):
        self.document('experiments/runs/a/candidate-01.json', self.feedback(self.a, 'first'))
        failed = self.feedback(self.a, 'repeat')
        failed['full']['comparison.json']['passed'] = False
        failed['full']['status'] = 'failed'
        self.document('experiments/runs/a/candidate-01-repeat.json', failed)
        self.document('experiments/runs/a/candidate-02.json', self.feedback(self.b, 'second'))
        self.save()
        context = build_context(self.repo)
        node = next(n for n in context['candidates'] if n['sha'] == self.a)
        self.assertEqual(len(node['runs']), 2)
        self.assertTrue(node['has_full_failure'])
        self.assertFalse(node['validated_measurements'][0]['combination_review_eligible'])
        self.assertEqual(context['combination_reviews'], [])
        self.assertIn('strict=False', markdown(context))

    def test_declared_edges_separate_from_git_and_tradeoffs_remain_reviewable(self):
        self.document('experiments/runs/a/candidate-01.json', self.feedback(self.a, 'first',
            provenance={'approach_tags': ['assembly']}))
        other = self.feedback(self.b, 'second', provenance={'parent_candidates': [self.a],
            'combined_candidates': [self.a, 'f' * 40], 'approach_tags': ['assembly']})
        phases = other['full']['report.json']['phases']
        for phase in phases:
            if phase['key'] == 'forward': phase['seconds'] = 2
            if phase['key'] == 'gradient': phase['seconds'] = 0.5
        self.document('experiments/runs/a/candidate-02.json', other)
        self.save()
        context = build_context(self.repo)
        node = next(n for n in context['candidates'] if n['sha'] == self.b)
        self.assertEqual(node['nearest_git_candidate'], self.a)
        self.assertEqual(node['parents_declared'], [self.a])
        self.assertIn('f' * 40, node['combined_candidates'])
        self.assertEqual(len(context['combination_reviews']), 1)
        self.assertEqual(context['combination_reviews'][0]['status'], 'review_required')
        self.assertTrue(all(n['validated_measurements'][0]['observed_pareto_frontier'] for n in context['candidates']))
        self.assertEqual(node['validated_measurements'][0]['repeat_evidence'], 'single_run_provisional')

    def test_mismatched_candidate_and_job_sha_is_not_silently_accepted(self):
        bad = self.feedback(self.a, 'wrong')
        bad['full']['sha'] = self.b
        self.document('experiments/runs/a/candidate-01.json', bad)
        self.save()
        context = build_context(self.repo)
        self.assertFalse(context['candidates'])
        self.assertTrue(context['warnings'])

    def test_brief_uses_recorded_revision_and_exact_content_digest(self):
        text = '# Brief\n\nInvestigate shapes.\n\n'
        self.document('experiments/agents/a.json', {'agent_id': 'a', 'brief_path': 'experiments/brief.md'})
        path = self.repo / 'experiments/brief.md'
        path.write_text(text)
        self.save()
        path.write_text('Uncommitted change')
        brief = build_context(self.repo)['agents'][0]['brief']
        self.assertEqual(brief['excerpt'], text)
        self.assertEqual(brief['sha256'], hashlib.sha256(text.encode()).hexdigest())


if __name__ == '__main__':
    unittest.main()
