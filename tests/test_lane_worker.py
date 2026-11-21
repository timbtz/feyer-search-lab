import copy
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from lab.lane_worker import LaneWorker, cpu_set, inspect_limits, validate_config, secondary_slot
from lab.worker import Worker
from lab.evolution_evidence import normalize_job, policy_from_job
from tests.test_evolution_evidence import full_job


def config(root='/workspace/lane1', primary='/workspace/feyer-lab'):
    return dict(schema='feyer-lane-v1', root=root, primary_root=primary, cpu=34, primary_cpu=2,
                memory_budget_bytes=16_000_000_000, primary_memory_budget_bytes=32_000_000_000,
                host_reserve_bytes=8_000_000_000)


class LaneTests(unittest.TestCase):
    def test_roots_and_types_fail_closed(self):
        for key, value in [('cpu', True), ('cpu', -1), ('memory_budget_bytes', False),
                           ('memory_budget_bytes', 0), ('host_reserve_bytes', 1),
                           ('root', '/workspace/feyer-lab'), ('root', '/workspace/feyer-lab/child'),
                           ('root', '/workspace'), ('root', 'relative')]:
            with self.subTest(key=key, value=value):
                c=config();c[key]=value
                with self.assertRaises(ValueError):validate_config(c)
        self.assertEqual(validate_config(config())['cpu'],34)

    def limits(self, current=9_000_000_000, limit=59_055_800_320, siblings='34,98'):
        d=tempfile.TemporaryDirectory();self.addCleanup(d.cleanup);root=Path(d.name)
        (root/'memory.max').write_text(str(limit));(root/'memory.current').write_text(str(current))
        p=root/'cpu34/topology';p.mkdir(parents=True);(p/'thread_siblings_list').write_text(siblings)
        return root

    def test_budget_and_available_headroom_are_distinct(self):
        with patch('os.sched_getaffinity',return_value={34},create=True):
            p=self.limits();self.assertTrue(inspect_limits(config(),p,p)['can_admit'])
            (p/'memory.current').write_text('40000000000')
            self.assertFalse(inspect_limits(config(),p,p)['can_admit'])

    def test_shared_core_rejected(self):
        with patch('os.sched_getaffinity',return_value={34},create=True):
            p=self.limits(siblings='2,34')
            with self.assertRaises(ValueError):inspect_limits(config(),p,p)

    def test_aggregate_reserve_rejected(self):
        with patch('os.sched_getaffinity',return_value={34},create=True):
            p=self.limits(limit=55_000_000_000)
            with self.assertRaises(ValueError):inspect_limits(config(),p,p)

    def test_disallowed_cpu_rejected(self):
        with patch('os.sched_getaffinity',return_value={2},create=True):
            p=self.limits()
            with self.assertRaises(ValueError):inspect_limits(config(),p,p)

    def test_stop_and_memory_wait_never_claim(self):
        with tempfile.TemporaryDirectory() as d:
            w=LaneWorker.__new__(LaneWorker);w.lane_root=Path(d);w.lane_config=config();(Path(d)/'state').mkdir()
            with patch.object(Worker,'run_once') as claim:
                with patch('lab.lane_worker.inspect_limits',return_value={'can_admit':False}):self.assertIsNone(w.run_once())
                (Path(d)/'state/STOP').touch()
                with self.assertRaises(KeyboardInterrupt):w.run_once()
                claim.assert_not_called()

    def test_explicit_lane_policy_required_for_seed_bootstrap(self):
        j=full_job();r=j['result'];r['cpu']=34;r['memory_budget_bytes']=16_000_000_000
        j['report.json']['environment']['cpu_affinity_ids']=[34]
        r['reported_environment']=copy.deepcopy(j['report.json']['environment'])
        r['memory_monitoring']['budget_bytes']=16_000_000_000
        r['comparison']['memory_monitoring']['budget_bytes']=16_000_000_000
        self.assertFalse(normalize_job(j)['eligible_full'])
        with self.assertRaises(ValueError):policy_from_job(j)
        p=policy_from_job(j,policy_context={'cpu':34,'memory_budget_bytes':16_000_000_000})
        self.assertTrue(normalize_job(j,policy_context=p)['eligible_full'])
        with self.assertRaises(ValueError):policy_from_job(j,policy_context={'cpu':35,'memory_budget_bytes':16_000_000_000})

    def test_secondary_slot_serializes_and_unclean_state_latches(self):
        with tempfile.TemporaryDirectory() as d:
            c=config(str(Path(d)/'lane'),str(Path(d)/'primary'))
            with secondary_slot(c):
                with self.assertRaises(ValueError):
                    with secondary_slot(c):pass
            receipt=Path(c['primary_root'])/'state/additional-lane-state.json'
            self.assertIn('stopped',receipt.read_text())
            receipt.write_text('{"status":"running"}')
            with self.assertRaises(ValueError):
                with secondary_slot(c):pass

    def test_cpu_ranges(self):
        self.assertEqual(cpu_set('0-2,34,98'),{0,1,2,34,98})
        with self.assertRaises(ValueError):cpu_set('3-1')


if __name__=='__main__':unittest.main()
