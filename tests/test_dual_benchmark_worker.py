import copy
import json
from pathlib import Path
import sqlite3
import subprocess
import sys
import tempfile
import time
import unittest
from unittest.mock import patch
import uuid

import numpy as np

from lab import dual_benchmark_worker as dual
from lab.transfer_validation import OUTPUTS, INPUTS, PHASES, THREADS, WORKLOADS


SHA = 'a' * 40
SEED = 'b' * 40


def arrays():
    values = {k: np.ones(3, dtype='complex128' if k in ('carrier', 'signal') else 'float64')
              for k in OUTPUTS + INPUTS}
    values['loss'] = np.asarray(-.1, dtype='float64')
    return values


def report(setup, sha=SHA):
    spec = WORKLOADS[setup]
    manifest = dual.checked_harness()['files']
    return {'benchmark': spec['benchmark'], 'source': {'commit': sha, 'modified': False},
            'starter_sha256': manifest['benchmark.py' if setup == 'grid' else 'benchmark_aligo.py'],
            'benchmark_harness_sha256': manifest['benchmark.py'],
            'inputs': {'frequency_count': 101, 'gradient_parameter_count': spec['variables'],
                       'setup_sha256': spec['setup'], 'reference_sha256': spec['reference']},
            'environment': {'cpu_affinity_ids': [2], 'cpu_affinity_count': 1, 'requested_logical_cpus': 1,
                            'thread_limits': dict.fromkeys(THREADS, '1'), 'backend': 'cpu',
                            'jax_enable_x64': True, 'persistent_compilation_cache': False,
                            'cpu_model': 'Test CPU', 'platform': 'Linux', 'python': '3.12.15',
                            'packages': {'jax': '0.9.0'}, 'xla_flags': '--new-organizer-permitted-option=true'},
            'phases': [{'key': k, 'seconds': 1.0} for k in PHASES],
            'timing_seconds': {'end_to_end': 14., 'trace_lower_and_compile': 6.},
            'validation': {'all_outputs_and_gradients_finite': True, 'upstream_sensitivity_check_passed': True,
                           'gradient_check': {'passed': True}, 'gradient_shape': [spec['variables']],
                           'gradient_norm': 1., 'loss': -.1, 'sensitivity_log_atol': spec['tolerance'],
                           'max_absolute_log_sensitivity_error': 0.,
                           'output_dtypes': {'carrier': 'complex128', 'signal': 'complex128', 'noise': 'float64'}}}


class FakeRunner(dual.Runner):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.executions = []
        self.mutate_report = lambda r: None
        self.mutate_arrays = lambda a: None
        self.mutate_generalization = lambda a: None
        self.fail_execution = None

    def _check_resources(self): pass
    def _verify_candidate(self, sha): pass

    def _checkout(self, directory, sha, deadline):
        code = directory/'code'; code.mkdir()
        return code

    def _execute(self, command, code, output, remaining, fds):
        self.executions.append((command, remaining, fds))
        if self.fail_execution: raise self.fail_execution
        if output.name == 'generalization':
            a = {case+'/'+k: v for case in dual.CASES for k, v in arrays().items()}
            self.mutate_generalization(a)
            np.savez(output/'arrays.npz', **a)
        else:
            setup = output.name.split('-')[0]
            r = report(setup); self.mutate_report(r)
            (output/'report.json').write_text(json.dumps(r))
            a = arrays(); self.mutate_arrays(a)
            np.savez(output/'arrays.npz', **a)
        return {'returncode': 0, 'failure': None, 'wall_seconds': .01, 'memory': {}}, command


class DualWorkerTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.base = Path(self.tmp.name)
        self.states = [self.base/'state0', self.base/'state1']
        for state in self.states:
            state.mkdir()
            with sqlite3.connect(state/'queue.sqlite3') as db:
                db.execute('CREATE TABLE jobs(status TEXT)')
        self.runner = FakeRunner(self.base/'runner', lock_states=self.states)
        self.payload = {'request_id': uuid.uuid4().hex, 'sha': SHA, 'deadline_unix': time.time()+120}
        self.git = patch.object(dual, 'git', side_effect=lambda path, *args: SHA if args == ('rev-parse','HEAD') else '')
        self.git.start()
        self.addCleanup(self.git.stop)
        self.addCleanup(self.tmp.cleanup)

    def run_request(self, **updates):
        self.payload.update(updates)
        self.runner.register(self.payload)
        return self.runner.run(self.payload['request_id'])

    def references(self, *, pristine_mismatch=False):
        roots = {}
        for label, sha in [('pristine', dual.BASELINE), ('initial_seed', SEED)]:
            root = self.base/label; roots[label] = root
            for setup in ('grid', 'aligo'):
                target = root/setup; target.mkdir(parents=True)
                (target/'report.json').write_text(json.dumps(report(setup, sha)))
                a = arrays()
                if pristine_mismatch and label == 'pristine': a['gradient'][0] *= 2
                np.savez(target/'arrays.npz', **a)
        harness = self.base/'gen.py'; harness.write_text('# trusted harness fixture')
        refs = {}
        for label in roots:
            archive = self.base/(label+'.npz')
            a = {case+'/'+k: v.copy() for case in dual.CASES for k,v in arrays().items()}
            if pristine_mismatch and label == 'pristine': a[dual.CASES[0]+'/gradient'][0] *= 2
            np.savez(archive, **a); refs[label] = archive
        self.runner = FakeRunner(self.base/'runner', lock_states=self.states,
            reference_root=roots['pristine'], seed_reference_root=roots['initial_seed'],
            generalization_harness=harness, generalization_reference=refs['pristine'], generalization_seed=refs['initial_seed'])

    def test_invalid_request_budgets_and_identity(self):
        for key, value in [('request_id','../../escape'), ('sha','a'*7), ('deadline_unix',True),
                           ('deadline_unix',float('nan')), ('timeout_seconds',float('inf')),
                           ('timeout_seconds',901), ('timeout_seconds',0), ('fresh_process_repetitions',True),
                           ('fresh_process_repetitions',2), ('run_generalization',1), ('worktree','/tmp')]:
            with self.subTest(key=key, value=value), self.assertRaises(ValueError):
                dual.normalize_request(dict(self.payload, **{key:value}))

    def test_uuid_canonical_registration_is_idempotent_and_conflicts_rejected(self):
        a = self.runner.register(self.payload)
        b = self.runner.register(dict(self.payload, request_id=str(uuid.UUID(self.payload['request_id']))))
        self.assertEqual(a, b)
        for field, value in [('sha', 'c'*40), ('deadline_unix', time.time()+10), ('fresh_process_repetitions',3)]:
            with self.subTest(field=field), self.assertRaisesRegex(ValueError, 'identity reused'):
                self.runner.register(dict(self.payload, **{field:value}))

    def test_repeated_run_executes_only_once_and_unknown_compiler_flags_recorded(self):
        result = self.run_request()
        self.assertTrue(result['official_passed'])
        self.assertFalse(result['promotion_ready'])
        self.assertEqual(len(self.runner.executions),2)
        again = self.runner.run(self.payload['request_id'])
        self.assertEqual(result,again)
        self.assertEqual(len(self.runner.executions),2)
        self.assertEqual(result['checks'][0]['official']['package_xla_flags'],'--new-organizer-permitted-option=true')
        self.assertEqual(result['generalization']['status'],'not_requested')

    def test_both_legacy_queues_must_be_drained(self):
        with sqlite3.connect(self.states[1]/'queue.sqlite3') as db:
            db.execute("INSERT INTO jobs VALUES ('queued')")
        state = self.run_request()
        self.assertEqual(state['status'],'queued')
        self.assertIn('not drained',state['blocked_reason'])
        self.assertFalse(self.runner.executions)

    def test_existing_worker_lock_prevents_execution(self):
        with dual.lock(self.states[0]/'worker.lock'):
            state = self.run_request()
        self.assertEqual(state['status'],'queued')
        self.assertFalse(self.runner.executions)

    def test_global_lock_prevents_duplicate_execution(self):
        self.runner.register(self.payload)
        with dual.lock(self.runner.root/'execution.lock'):
            state = self.runner.run(self.payload['request_id'])
        self.assertEqual(state['status'],'queued')
        self.assertFalse(self.runner.executions)

    def test_inherited_lock_survives_controller_descriptor_close(self):
        self.runner.register(self.payload)
        with dual.lock(self.runner.root/'execution.lock') as fd:
            child = subprocess.Popen([sys.executable,'-c',
                'import sys; print("ready",flush=True); sys.stdin.read()'],
                stdin=subprocess.PIPE,stdout=subprocess.PIPE,text=True,pass_fds=(fd,))
            self.assertEqual(child.stdout.readline().strip(),'ready')
        try:
            self.assertEqual(self.runner.run(self.payload['request_id'])['status'],'queued')
            self.assertFalse(self.runner.executions)
        finally:
            child.communicate('',timeout=5)
        self.assertTrue(self.runner.run(self.payload['request_id'])['official_passed'])

    def test_running_without_lock_is_interrupted_never_retried(self):
        state = self.runner.register(self.payload)
        self.runner._save(self.runner._directory(self.payload['request_id']),state,status='running')
        state = self.runner.run(self.payload['request_id'])
        self.assertEqual(state['status'],'interrupted')
        self.assertIsNone(state['official_passed'])
        self.runner.run(self.payload['request_id'])
        self.assertFalse(self.runner.executions)

    def test_crash_after_start_does_not_reexecute(self):
        self.runner.fail_execution = InterruptedError('terminated')
        state = self.run_request()
        self.assertEqual(state['status'],'interrupted')
        self.assertIsNone(state['official_passed'])
        self.runner.fail_execution = None
        self.runner.run(self.payload['request_id'])
        self.assertEqual(len(self.runner.executions),1)

    def test_registration_recovery_cannot_overwrite_missing_execution_state(self):
        self.runner.register(self.payload)
        directory = self.runner._directory(self.payload['request_id'])
        (directory/'state.json').unlink()
        self.assertEqual(self.runner.register(self.payload)['status'],'queued')
        (directory/'state.json').unlink()
        (directory/'code').mkdir()
        with self.assertRaisesRegex(ValueError,'Missing state'):
            self.runner.register(self.payload)

    def test_expired_request_never_starts(self):
        state = self.run_request(deadline_unix=time.time()-1)
        self.assertEqual(state['status'],'expired')
        self.assertFalse(self.runner.executions)

    def test_three_fresh_processes_each_and_three_warm_repeats(self):
        state = self.run_request(fresh_process_repetitions=3)
        self.assertEqual(len(self.runner.executions),6)
        for command, _, fds in self.runner.executions:
            self.assertEqual(command[:3], ['taskset','-c','2'])
            self.assertEqual(command[command.index('--repeats')+1], '3')
            self.assertEqual(len(fds),3)
        for setup in ('grid','aligo'):
            self.assertEqual(state['timings'][setup]['fresh_process_seconds'],[14.,14.,14.])

    def test_official_failure_is_distinct_from_strict_failure(self):
        self.runner.mutate_report = lambda r:r['environment'].update(cpu_affinity_ids=[2,3])
        state = self.run_request()
        self.assertFalse(state['official_passed'])
        self.assertEqual(state['status'],'failed')
        self.assertFalse(state['promotion_ready'])

    def test_nonfinite_saved_outputs_fail_even_if_report_passes(self):
        self.runner.mutate_arrays = lambda a:a['noise'].__setitem__(0,np.nan)
        state = self.run_request()
        self.assertFalse(state['official_passed'])
        self.assertTrue(state['checks'][0]['official']['passed'])

    def test_full_confirmation_promotes_only_with_all_seed_checks(self):
        self.references()
        state = self.run_request(fresh_process_repetitions=3, run_generalization=True)
        self.assertTrue(state['promotion_ready'])
        receipt = json.loads((self.runner.root/state['receipt_path']).read_text())
        self.assertEqual(receipt['candidate_sha'],SHA)
        self.assertEqual(receipt['generalization']['case_count'],14)
        self.assertTrue(receipt['generalization']['all_finite'])
        self.assertTrue(receipt['generalization']['inputs_identical'])
        self.assertTrue(receipt['generalization']['seed_comparison_passed'])
        self.assertEqual(receipt['generalization']['new_failures'],[])
        self.assertEqual(receipt['admission']['scope'],'public-benchmarks-and-no-new-regressions')

    def test_inherited_pristine_mismatch_retained_without_masking_seed_gate(self):
        self.references(pristine_mismatch=True)
        state = self.run_request(fresh_process_repetitions=3,run_generalization=True)
        self.assertTrue(state['promotion_ready'])
        self.assertFalse(state['strict_passed'])
        self.assertTrue(state['numerical_review_required'])
        receipt = json.loads((self.runner.root/state['receipt_path']).read_text())
        self.assertTrue(receipt['inherited_caveats'])
        self.assertFalse(state['generalization']['passed'])

    def test_new_seed_regression_blocks_promotion_while_preserving_official_pass(self):
        self.references()
        self.runner.mutate_arrays = lambda a:a['gradient'].__setitem__(0,2.)
        state = self.run_request(fresh_process_repetitions=3,run_generalization=True)
        self.assertTrue(state['official_passed'])
        self.assertFalse(state['promotion_ready'])
        self.assertFalse(state['strict_passed'])

    def test_generalization_missing_input_case_and_nonfinite_output_block(self):
        for mutation in ('input','missing','nonfinite'):
            with self.subTest(mutation=mutation):
                self.payload['request_id'] = uuid.uuid4().hex
                if not self.runner.reference_roots: self.references()
                def change(a):
                    if mutation == 'input': a[dual.CASES[0]+'/parameters'][0] += 1
                    elif mutation == 'missing': a.pop(dual.CASES[-1]+'/gradient')
                    else: a[dual.CASES[0]+'/signal'][0] = np.nan
                self.runner.mutate_generalization = change
                state = self.run_request(fresh_process_repetitions=3,run_generalization=True)
                self.assertTrue(state['official_passed'])
                self.assertFalse(state['promotion_ready'])

    def test_reference_mutation_after_registration_fails_closed(self):
        self.references()
        self.runner.register(self.payload)
        path = self.runner.reference_roots['initial_seed']/'grid/arrays.npz'
        path.write_bytes(b'changed')
        state = self.runner.run(self.payload['request_id'])
        self.assertEqual(state['status'],'failed')
        self.assertIn('policy changed',state['error'])
        self.assertFalse(self.runner.executions)

    def test_mismatched_reference_environment_blocks_promotion(self):
        self.references()
        path = self.runner.reference_roots['initial_seed']/'grid/report.json'
        r = json.loads(path.read_text()); r['environment']['cpu_model']='Other CPU'
        path.write_text(json.dumps(r))
        state = self.run_request(fresh_process_repetitions=3,run_generalization=True)
        self.assertTrue(state['official_passed'])
        self.assertFalse(state['promotion_ready'])
        receipt = json.loads((self.runner.root/state['receipt_path']).read_text())
        self.assertFalse(receipt['admission']['comparison_cohort_passed'])

    def test_package_flag_changes_remain_recorded_without_changing_cohort(self):
        self.references()
        first = self.run_request(fresh_process_repetitions=3,run_generalization=True)
        receipt1 = json.loads((self.runner.root/first['receipt_path']).read_text())
        self.payload['request_id'] = uuid.uuid4().hex
        self.runner.mutate_report = lambda r:r['environment'].update(xla_flags='--another-reviewed-choice')
        second = self.run_request(fresh_process_repetitions=3,run_generalization=True)
        receipt2 = json.loads((self.runner.root/second['receipt_path']).read_text())
        self.assertTrue(second['promotion_ready'])
        self.assertEqual(receipt1['cohort_digest'],receipt2['cohort_digest'])
        self.assertNotEqual(receipt1['benchmarks']['grid']['samples'][0]['effective_environment'],
                            receipt2['benchmarks']['grid']['samples'][0]['effective_environment'])

    def test_reference_requires_matching_exact_sha(self):
        self.references()
        path = self.runner.reference_roots['initial_seed']/'grid/report.json'
        r = json.loads(path.read_text()); r['source']['commit']='c'*40
        path.write_text(json.dumps(r))
        with self.assertRaisesRegex(ValueError,'same exact source'):
            self.runner.register(self.payload)

    def test_generalization_request_requires_all_reference_inputs(self):
        with self.assertRaisesRegex(ValueError,'both pristine'):
            self.run_request(run_generalization=True)

    def test_protected_files_rejected_before_execution(self):
        with patch.object(dual,'git',side_effect=lambda path,*args: args[1][:-9] if args[0]=='rev-parse' else 'benchmark.py'):
            with self.assertRaisesRegex(ValueError,'protected'):
                dual.Runner._verify_candidate(self.runner,SHA)

    def test_sampled_guard_has_independent_timeout_and_inherited_locks(self):
        with patch.object(dual,'execute',return_value={'returncode':0}) as execute:
            result, command = dual.Runner._execute(self.runner,['python','script.py'],Path('/tmp'),Path('/tmp'),123.456,(3,4,5))
        self.assertEqual(command[:4],['/usr/bin/timeout','--signal=TERM','--kill-after=5s','123.456'])
        self.assertEqual(execute.call_args.args[-1],(3,4,5))


if __name__ == '__main__': unittest.main()
