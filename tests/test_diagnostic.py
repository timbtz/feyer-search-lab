import copy
import gzip
import hashlib
import json
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import Mock, patch

from lab.client import Client
from lab.diagnostic import (ARTIFACTS, KINDS, LIMITS, MAX_TEXT_BYTES, SCHEMA,
                            STAGES, optional_analysis, save_ir, summarize_ir, validate_report)
from lab.evolution_evidence import normalize_job
from lab.remote import handle
from lab.worker import Worker, FIXTURE_SHA256, REFERENCE_SHA256, THREAD_VARIABLES
from tests import test_remote_idempotence as remote_tests
from tests import test_worker as worker_tests


def diagnostic_report():
    return dict(schema=SCHEMA, ranking_eligible=False,
                source={'commit': 'a' * 40, 'modified': False}, harness_sha256='b' * 64,
                benchmark_sha256='c' * 64,
                inputs=dict(frequency_count=101, gradient_parameter_count=193,
                            setup_sha256=FIXTURE_SHA256, reference_sha256=REFERENCE_SHA256),
                environment=dict(backend='cpu', cpu_affinity_ids=[2], jax_enable_x64=True,
                                 persistent_compilation_cache=False, xla_flags=None,
                                 thread_limits={key: '1' for key in THREAD_VARIABLES}),
                stages={name: dict(lower_seconds=.1, compile_seconds=1., execute_seconds=.2,
                                   ir={key: dict(available=False, reason='Fake compiler fixture') for key in KINDS})
                        for name in STAGES},
                sanity=dict(output_shapes=[[286, 1], [751, 101], [101]], gradient_shape=[193], finite=True),
                limits=LIMITS)


def validate(report):
    validate_report(report, 'a' * 40, 'b' * 64, 'c' * 64, 2, FIXTURE_SHA256, REFERENCE_SHA256)


class DiagnosticSummaryTests(unittest.TestCase):
    def test_hlo_counts_subcomputations_and_custom_calls_without_timing_claims(self):
        hlo = '''HloModule forward
helper {
  %a = c128[101,751,751] parameter(0)
  %lu = (c128[101,751,751],s32[101,751]) custom-call(%a), custom_call_target="lapack_zgetrf_ffi"
}
ENTRY main {
  ROOT %out = c128[101,751,751] call(%a), to_apply=helper
}
'''
        out = summarize_ir(hlo)
        self.assertEqual(out['opcode_counts_in_sample']['custom-call'], 1)
        self.assertEqual(out['computation_count_in_sample'], 2)
        self.assertEqual(out['largest_computations_in_sample'][0]['instructions'], 2)
        self.assertIn('751', out['custom_call_examples'][0])
        self.assertNotIn('seconds', out)

    def test_ir_exports_are_bounded_digested_and_explicitly_truncated(self):
        text = 'x' * (MAX_TEXT_BYTES + 300)
        with tempfile.TemporaryDirectory() as directory:
            result = save_ir(directory, 'forward', 'hlo', text)
            artifact = Path(directory) / result['artifact']
            self.assertTrue(result['truncated'])
            self.assertEqual(result['utf8_bytes'], len(text))
            self.assertEqual(len(gzip.decompress(artifact.read_bytes())), MAX_TEXT_BYTES)
            self.assertEqual(result['artifact_sha256'], hashlib.sha256(artifact.read_bytes()).hexdigest())
            with self.assertRaises(ValueError):
                save_ir(directory, '../escape', 'hlo', text)

    def test_unsupported_analysis_is_visible_and_nonfinite_cost_is_omitted(self):
        self.assertFalse(optional_analysis(lambda: None)['available'])
        def unsupported():
            raise NotImplementedError('not available')
        self.assertFalse(optional_analysis(unsupported)['available'])
        out = optional_analysis(lambda: {'flops': 123., 'bad': float('inf')})
        self.assertEqual(out['values'], {'flops': 123.})

    def test_validation_binds_exact_source_environment_workload_and_nonranking_status(self):
        valid = diagnostic_report()
        validate(valid)
        mutations = [lambda r: r.update(first_run_seconds=3),
                     lambda r: r.update(ranking_eligible=True),
                     lambda r: r['source'].update(commit='d'*40),
                     lambda r: r.update(benchmark_sha256='d'*64),
                     lambda r: r['environment'].update(cpu_affinity_ids=[3]),
                     lambda r: r['environment'].update(persistent_compilation_cache=True),
                     lambda r: r['inputs'].update(frequency_count=1),
                     lambda r: r['stages']['forward'].update(compile_seconds=float('nan')),
                     lambda r: r['stages'].pop('gradient'),
                     lambda r: r['sanity'].update(gradient_shape=[1]),
                     lambda r: r['sanity'].update(finite=False)]
        for mutation in mutations:
            with self.subTest(mutation=mutation):
                invalid = copy.deepcopy(valid)
                mutation(invalid)
                with self.assertRaises(ValueError):
                    validate(invalid)


class DiagnosticWorkerTests(unittest.TestCase):
    setUp = worker_tests.WorkerTests.setUp
    tearDown = worker_tests.WorkerTests.tearDown
    submit = worker_tests.WorkerTests.submit

    def evaluator(self, mutation=''):
        source = f'''import hashlib,json,subprocess,sys
from pathlib import Path
run=Path(sys.argv[1])
report=json.loads({json.dumps(diagnostic_report())!r})
report['source']['commit']=subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip()
report['harness_sha256']=hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
report['benchmark_sha256']=hashlib.sha256(Path('benchmark.py').read_bytes()).hexdigest()
{mutation}
(run/'diagnostic.json').write_text(json.dumps(report))
'''
        (self.evaluators / 'fake.py').write_text(source)

    def write_evaluator(self, source):
        worker_tests.WorkerTests.write_evaluator(self, source)

    def test_diagnostic_uses_existing_queue_lock_and_keeps_result_out_of_ranking(self):
        self.evaluator()
        job = self.submit('diagnostic')
        with patch.object(self.worker, '_validate_report', side_effect=AssertionError('Official validator invoked')):
            finished = self.worker.run_once()
        self.assertEqual(finished['status'], 'completed')
        result = finished['result']
        self.assertEqual(result['verdict'], 'diagnostic_completed')
        self.assertIs(result['ranking_eligible'], False)
        self.assertIsNone(result['official_passed'])
        self.assertIsNone(result['regression_passed'])
        self.assertNotIn('first_run_seconds', result)
        self.assertFalse((self.root / 'runs' / job['id'] / 'code').exists())
        self.assertIn('memory_monitoring', result)
        with self.assertRaises(ValueError):
            normalize_job(finished)

    def test_diagnostic_rejects_timing_disguised_as_score(self):
        self.evaluator("report['first_run_seconds']=3.0")
        self.submit('diagnostic')
        finished = self.worker.run_once()
        self.assertEqual(finished['status'], 'failed')
        self.assertIn('benchmark result fields', finished['error'])
        self.assertNotIn('first_run_seconds', finished['result'])

    def test_diagnostic_command_keeps_fixed_environment_and_has_no_benchmark_outputs(self):
        (self.evaluators / 'diagnostic.py').write_text('# trusted harness')
        job = self.submit('diagnostic')
        run = self.root / 'runs' / job['id']
        command, evaluator = Worker._build_command(self.worker, job, self.repo, run)
        self.assertEqual(evaluator.name, 'diagnostic.py')
        self.assertEqual(command[command.index('--sha') + 1], job['sha'])
        self.assertEqual(command[command.index('--output') + 1], str(run / 'diagnostic.json'))
        self.assertNotIn('--save-arrays', command)
        self.assertNotIn('--repeats', command)
        with patch.dict('os.environ', {'XLA_FLAGS': 'bad', 'JAX_LOG_COMPILES': 'true'}):
            env = self.worker._environment(self.repo)
        self.assertNotIn('XLA_FLAGS', env)
        self.assertNotIn('JAX_LOG_COMPILES', env)


class DiagnosticRemoteTests(unittest.TestCase):
    setUp = remote_tests.RemoteIdempotenceTests.setUp
    tearDown = remote_tests.RemoteIdempotenceTests.tearDown

    def test_fixed_artifacts_roundtrip_and_capabilities_without_scores(self):
        job = handle(self.root, dict(action='enqueue', sha=self.sha, branch='main', agent='test',
                                    direction='compiler', hypothesis='inspect IR', profile='diagnostic'))
        run = self.root / 'runs' / job['id']
        run.mkdir(parents=True)
        (run / 'diagnostic.json').write_text(json.dumps(diagnostic_report()))
        (run / ARTIFACTS[0]).write_bytes(gzip.compress(b'HloModule test'))
        (run / 'unlisted.secret').write_text('must not export')
        (run / ARTIFACTS[1]).symlink_to(run / 'unlisted.secret')
        files = handle(self.root, {'action': 'artifact', 'id': job['id']})
        self.assertEqual(set(files), {'diagnostic.json', ARTIFACTS[0]})
        shown = handle(self.root, {'action': 'show', 'id': job['id']})
        self.assertIn('diagnostic.json', shown)
        self.assertNotIn('report.json', shown)
        self.assertEqual(handle(self.root, {'action': 'capabilities'})['diagnostic_schema'], SCHEMA)

    def test_client_checks_diagnostic_support_before_any_publication(self):
        client = Client()
        client.request = Mock(return_value={'profiles': ['screen', 'full']})
        with patch('lab.client.git', return_value='a' * 40), patch('lab.client.publish_candidate') as publish, \
                patch('lab.client.subprocess.run') as upload:
            with self.assertRaisesRegex(RuntimeError, 'does not advertise'):
                client.submit('.', 'main', 'a', 'd', 'h', profile='diagnostic')
        publish.assert_not_called()
        upload.assert_not_called()


if __name__ == '__main__':
    unittest.main()
