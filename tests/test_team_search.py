import concurrent.futures
import copy
from pathlib import Path
import subprocess
import tempfile
import unittest

from lab.team_search import GitLedger, apply, assess, initial_state, ready
from lab.evolution_evidence import normalize_job
from test_evolution_evidence import full_job


PARENT = 'a' * 40
CHILD = 'b' * 40


def spec(identity='solver'):
    return dict(id=identity, kind='explore', hypothesis='Reuse one factorization',
                parents=[PARENT], max_candidates=2, deadline_unix=4000000000)


def observation(sha=PARENT, job_id='job-one', total=30, instance='amd-a', task=None):
    job = full_job()
    job['id'] = job_id
    job['sha'] = job['result']['sha'] = job['report.json']['source']['commit'] = sha
    report = job['report.json']
    factor = total / report['timing_seconds']['end_to_end']
    for phase in report['phases']:
        phase['seconds'] *= factor
    report['timing_seconds']['end_to_end'] = job['result']['first_run_seconds'] = total
    report['timing_seconds']['trace_lower_and_compile'] = sum(p['seconds'] for p in report['phases'] if p['category'] == 'compile')
    evidence = normalize_job(job)
    return dict(instance=instance, task=task, evidence=evidence, job=job)


class TeamSearchTests(unittest.TestCase):
    def setUp(self):
        self.state, _ = apply(initial_state('coordinator'), 'add', 'coordinator', spec())

    def claim(self):
        self.state, _ = apply(self.state, 'claim', 'alice',
                              dict(task='solver', instance='amd-a', claim_id='claim-one'))

    def test_atomic_owner_and_stale_claim_rejection(self):
        self.claim()
        before = copy.deepcopy(self.state)
        with self.assertRaises(ValueError):
            apply(self.state, 'claim', 'bob', dict(task='solver', instance='amd-b', claim_id='two'))
        with self.assertRaises(ValueError):
            apply(self.state, 'release', 'alice', dict(task='solver', claim_id='stale', reason='handoff'))
        self.assertEqual(self.state, before)
        self.state, _ = apply(self.state, 'release', 'alice', dict(task='solver', claim_id='claim-one', reason='queue drained'))
        self.assertEqual(ready(self.state)[0]['id'], 'solver')

    def test_deadline_budget_and_late_evidence(self):
        self.claim()
        reservation = dict(task='solver', sha=CHILD, claim_id='claim-one', code_branch='explore/alice/solver')
        self.state, _ = apply(self.state, 'candidate', 'alice', reservation)
        with self.assertRaises(ValueError):
            apply(self.state, 'candidate', 'alice', {**reservation, 'sha':'c' * 40}, now=4000000001)
        obs = observation(CHILD, task='solver')
        self.state, _ = apply(self.state, 'record', 'alice', dict(observation=obs, claim_id='claim-one'), now=4000000001)
        self.assertEqual(len(self.state['observations']), 1)
        again, _ = apply(self.state, 'record', 'alice', dict(observation=obs, claim_id='claim-one'))
        self.assertEqual(again, self.state)
        with self.assertRaises(ValueError):
            apply(self.state, 'record', 'alice', dict(observation=observation('c' * 40, 'unreserved', task='solver'), claim_id='claim-one'))
        self.state, _ = apply(self.state, 'candidate', 'alice', {**reservation, 'sha':'c' * 40})
        with self.assertRaises(ValueError):
            apply(self.state, 'candidate', 'alice', {**reservation, 'sha':'d' * 40})

    def test_only_full_parents_admitted_and_two_combination_inputs(self):
        task = {**spec('refine'), 'kind':'refine', 'max_candidates':1}
        with self.assertRaises(ValueError):
            apply(self.state, 'add', 'coordinator', task)
        obs = observation()
        obs['job']['result'].pop('worker_sha256')
        obs['evidence'] = normalize_job(obs['job'])
        self.state, _ = apply(self.state, 'record', 'coordinator', dict(observation=obs))
        with self.assertRaises(ValueError):
            apply(self.state, 'add', 'coordinator', task)
        self.state, _ = apply(self.state, 'record', 'coordinator', dict(observation=observation(job_id='full')))
        self.state, _ = apply(self.state, 'add', 'coordinator', task)
        with self.assertRaisesRegex(ValueError, 'one successor'):
            apply(self.state, 'add', 'coordinator', {**task, 'id':'multiple', 'max_candidates':2})
        with self.assertRaises(ValueError):
            apply(self.state, 'add', 'coordinator', {**spec('combo'), 'kind':'combine'})

    def test_comparison_requires_repeats_matching_host_cohort_and_best_parent(self):
        for sha, total in ((PARENT, 30), (CHILD, 25), ('c' * 40, 26)):
            for i in range(3):
                obs = observation(sha, sha[:1] + str(i), total)
                self.state, _ = apply(self.state, 'record', 'coordinator', dict(observation=obs))
        self.state['tasks']['solver']['parents'].append(CHILD)
        self.state['tasks']['solver']['candidates'] = ['c' * 40, CHILD]
        cohort = obs['evidence']['cohort_digest']
        result = assess(self.state, 'solver', 'c' * 40, 'amd-a', cohort)
        self.assertEqual(result['classification'], 'not_improved')
        self.assertEqual(result['reference_sha'], CHILD)
        self.assertEqual(assess(self.state, 'solver', 'c' * 40, 'amd-b', cohort)['classification'], 'needs_confirmation')
        self.assertEqual(assess(self.state, 'solver', 'c' * 40, 'amd-a', 'other')['classification'], 'needs_confirmation')
        self.state['tasks']['solver']['parents'] = [PARENT]
        self.assertEqual(assess(self.state, 'solver', CHILD, 'amd-a', cohort)['classification'], 'improved')
        self.state['observations'].pop('amd-a:b2')
        self.assertEqual(assess(self.state, 'solver', CHILD, 'amd-a', cohort)['classification'], 'needs_confirmation')

    def test_strict_failure_blocks_cherry_picked_passing_repeats(self):
        self.state['tasks']['solver']['candidates'] = [CHILD]
        for sha, total in ((PARENT, 30), (CHILD, 25)):
            for i in range(3):
                obs = observation(sha, sha[:1] + str(i), total)
                self.state, _ = apply(self.state, 'record', 'coordinator', dict(observation=obs))
        cohort = obs['evidence']['cohort_digest']
        bad = observation(CHILD, 'strict-failure', 25)
        job = bad['job']
        job['status'] = job['result']['status'] = 'failed'
        job['result']['regression_passed'] = False
        job['result']['comparison']['returncode'] = 1
        job['comparison.json']['passed'] = False
        job['comparison.json']['checks']['gradient']['passed'] = False
        bad['evidence'] = normalize_job(job)
        self.state, _ = apply(self.state, 'record', 'coordinator', dict(observation=bad))
        self.assertEqual(assess(self.state, 'solver', CHILD, 'amd-a', cohort)['classification'], 'numerical_review_required')
        with self.assertRaises(ValueError):
            assess(self.state, 'solver', 'e' * 40, 'amd-a', cohort)

    def test_concurrent_full_passes_are_not_serial_comparisons(self):
        self.state['tasks']['solver']['candidates'] = [CHILD]
        self.state, _ = apply(self.state, 'comparison-regime', 'coordinator', dict(
            mode='concurrent', reason='Two lanes admitted', receipt='capacity-epoch-1.json'), now=100)
        for sha, total in ((PARENT, 30), (CHILD, 25)):
            for i in range(3):
                obs = observation(sha, sha[:1] + str(i), total)
                obs['comparison_context'] = {'mode':'serial'}  # cannot override the shared regime
                self.state, _ = apply(self.state, 'record', 'coordinator', dict(observation=obs))
        cohort = obs['evidence']['cohort_digest']
        result = assess(self.state, 'solver', CHILD, 'amd-a', cohort)
        self.assertEqual(result['classification'], 'needs_serial_confirmation')
        self.assertEqual(len(result['exploratory_jobs_excluded']), 6)
        self.assertTrue(all(o['evidence']['eligible_full'] for o in self.state['observations'].values()))
        self.state, _ = apply(self.state, 'comparison-regime', 'coordinator', dict(
            mode='serial', reason='All lanes and jobs drained', receipt='drained.json'), now=200)
        repeated, _ = apply(self.state, 'record', 'coordinator', dict(observation=obs))
        self.assertEqual(repeated, self.state)  # retry cannot relabel earlier evidence
        for suffix, start in [('late', 150), ('missing', None), ('fresh', 201)]:
            row = observation(CHILD, suffix, 25)
            if start is not None:
                row['job']['started_at'] = start
                row['evidence'] = normalize_job(row['job'])
            self.state, _ = apply(self.state, 'record', 'coordinator', dict(observation=row))
        self.assertEqual(self.state['observations']['amd-a:late']['comparison_context']['mode'], 'unverified_timing')
        self.assertEqual(self.state['observations']['amd-a:missing']['comparison_context']['mode'], 'unverified_timing')
        self.assertEqual(self.state['observations']['amd-a:fresh']['comparison_context']['mode'], 'serial')

    def test_regime_requires_coordinator_receipt_and_reason(self):
        data = dict(mode='concurrent', reason='New lanes', receipt='receipt.json')
        with self.assertRaises(ValueError):
            apply(self.state, 'comparison-regime', 'alice', data)
        for invalid in ({**data, 'mode':'unknown'}, {**data, 'receipt':''}, {**data, 'reason':''}):
            with self.assertRaises(ValueError):
                apply(self.state, 'comparison-regime', 'coordinator', invalid)

    def test_cycles_rejected(self):
        self.claim()
        self.state, _ = apply(self.state, 'candidate', 'alice', dict(task='solver', sha=CHILD,
                              claim_id='claim-one', code_branch='explore/alice/solver'))
        self.state, _ = apply(self.state, 'add', 'coordinator', {**spec('back'), 'parents':[CHILD]})
        self.state, _ = apply(self.state, 'claim', 'bob', dict(task='back', instance='amd-b', claim_id='back'))
        with self.assertRaises(ValueError):
            apply(self.state, 'candidate', 'bob', dict(task='back', sha=PARENT,
                  claim_id='back', code_branch='explore/bob/back'))

    def test_dependencies_gate_claim_until_explicit_resolution(self):
        self.state, _ = apply(self.state, 'add', 'coordinator', {**spec('followup'), 'depends_on':['solver']})
        self.assertEqual([t['id'] for t in ready(self.state)], ['solver'])
        with self.assertRaises(ValueError):
            apply(self.state, 'claim', 'bob', dict(task='followup', instance='amd-b', claim_id='two'))
        self.claim()
        self.state, _ = apply(self.state, 'resolve', 'alice', dict(task='solver', claim_id='claim-one',
                              outcome='stalled', reason='No gain after confirmation; work drained'))
        self.assertEqual([t['id'] for t in ready(self.state)], ['followup'])

    def test_two_tasks_cannot_reserve_same_writable_branch(self):
        self.claim()
        data = dict(task='solver', sha=CHILD, claim_id='claim-one', code_branch='explore/alice/solver')
        self.state, _ = apply(self.state, 'candidate', 'alice', data)
        self.state, _ = apply(self.state, 'add', 'coordinator', spec('other'))
        self.state, _ = apply(self.state, 'claim', 'bob', dict(task='other', instance='amd-b', claim_id='two'))
        with self.assertRaises(ValueError):
            apply(self.state, 'candidate', 'bob', {**data, 'task':'other', 'claim_id':'two'})

    def test_reclaim_checks_retained_branches_and_preserves_history(self):
        self.claim()
        data = dict(task='solver', sha=CHILD, claim_id='claim-one', code_branch='explore/alice/solver')
        self.state, _ = apply(self.state, 'candidate', 'alice', data)
        self.state, _ = apply(self.state, 'release', 'alice', dict(
            task='solver', claim_id='claim-one', reason='All jobs drained'))
        self.state, _ = apply(self.state, 'add', 'coordinator', spec('other'))
        self.state, _ = apply(self.state, 'claim', 'bob', dict(task='other', instance='amd-b', claim_id='two'))
        self.state, _ = apply(self.state, 'candidate', 'bob', {**data, 'task':'other', 'claim_id':'two'})
        before = copy.deepcopy(self.state)
        with self.assertRaisesRegex(ValueError, 'retained writable code branch'):
            apply(self.state, 'claim', 'alice', dict(task='solver', instance='amd-a', claim_id='three'))
        self.assertEqual(self.state, before)
        self.state, _ = apply(self.state, 'release', 'bob', dict(
            task='other', claim_id='two', reason='All jobs drained'))
        self.state, task = apply(self.state, 'claim', 'alice', dict(
            task='solver', instance='amd-a', claim_id='three'))
        self.assertEqual(task['candidate_branches'], {CHILD: data['code_branch']})
        self.assertEqual(task['candidates'], [CHILD])
        self.assertEqual(task['claim_id'], 'three')

    def test_real_git_concurrent_claim_has_one_winner(self):
        with tempfile.TemporaryDirectory() as directory:
            remote = str(Path(directory) / 'remote.git')
            subprocess.run(['git', 'init', '--bare', '-q', remote], check=True)
            ledger = GitLedger(remote)
            ledger.transact('init', 'coordinator', {})
            ledger.transact('add', 'coordinator', spec())
            def claim(actor):
                try:
                    return GitLedger(remote).transact('claim', actor, dict(task='solver', instance='amd-' + actor, claim_id=actor))['owner']
                except ValueError:
                    return None
            with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
                outcomes = list(pool.map(claim, ['alice', 'bob']))
            self.assertEqual(sum(v is not None for v in outcomes), 1)
            self.assertEqual(ledger.read()['tasks']['solver']['owner'], next(v for v in outcomes if v))

    def test_lost_push_response_refuses_reassigned_claim(self):
        with tempfile.TemporaryDirectory() as directory:
            remote = str(Path(directory) / 'remote.git')
            subprocess.run(['git', 'init', '--bare', '-q', remote], check=True)
            ledger = GitLedger(remote)
            ledger.transact('init', 'coordinator', {})
            ledger.transact('add', 'coordinator', spec())

            class ReassignedResponse(GitLedger):
                @staticmethod
                def git(path, *args, **kwargs):
                    result = GitLedger.git(path, *args, **kwargs)
                    if args[0] == 'push' and result.returncode == 0:
                        ledger.transact('release', 'coordinator', dict(
                            task='solver', claim_id='one', reason='Prior work drained'))
                        ledger.transact('claim', 'bob', dict(
                            task='solver', instance='amd-b', claim_id='two'))
                        raise subprocess.TimeoutExpired(result.args, 120)
                    return result

            with self.assertRaisesRegex(RuntimeError, 'ownership changed'):
                ReassignedResponse(remote).transact('claim', 'alice', dict(
                    task='solver', instance='amd-a', claim_id='one'))
            self.assertEqual(ledger.read()['tasks']['solver']['owner'], 'bob')

    def test_lost_push_response_recovers_without_replaying_claim(self):
        class LostResponse(GitLedger):
            @staticmethod
            def git(path, *args, **kwargs):
                result = GitLedger.git(path, *args, **kwargs)
                if args[0] == 'push' and result.returncode == 0:
                    raise subprocess.TimeoutExpired(result.args, 120)
                return result
        with tempfile.TemporaryDirectory() as directory:
            remote = str(Path(directory) / 'remote.git')
            subprocess.run(['git', 'init', '--bare', '-q', remote], check=True)
            ledger = LostResponse(remote)
            ledger.transact('init', 'coordinator', {})
            ledger.transact('add', 'coordinator', spec())
            output = ledger.transact('claim', 'alice', dict(task='solver', instance='amd-a', claim_id='one'))
            self.assertEqual(output['owner'], 'alice')
            self.assertEqual(len(ledger.read()['events']), 2)


if __name__ == '__main__':
    unittest.main()
