import argparse
import json
from pathlib import Path
import tempfile
import unittest

from lab.capacity_sampler import lane_stopped_in_epoch, positive_duration


class CapacitySamplerTests(unittest.TestCase):
    def test_duration_rejects_unbounded_and_invalid_values(self):
        for value in ['nan', 'inf', '-inf', 0, -1, True, 'bad']:
            with self.subTest(value=value), self.assertRaises(argparse.ArgumentTypeError):
                positive_duration(value)
        self.assertEqual(positive_duration('0.5'), 0.5)

    def test_old_receipt_does_not_stop_restarted_epoch(self):
        with tempfile.TemporaryDirectory() as tmp:
            state = Path(tmp) / 'state'; state.mkdir()
            lane = {'root': tmp, 'worker_pid': 42}
            epoch = {'started_at': 100}
            def write(name, data):
                (state / name).write_text(json.dumps(data))
            write('lane-startup.json', {'pid': 42, 'started_at': 101})
            # Stale PID, or reused PID with stale timestamp, must both be rejected.
            for old in [{'pid': 41, 'at': 102}, {'pid': 42, 'at': 99},
                        {'pid': 42, 'at': float('nan')}]:
                write('lane-stopped.json', old)
                self.assertFalse(lane_stopped_in_epoch(lane, epoch))
            write('lane-stopped.json', {'pid': 42, 'at': 102})
            self.assertTrue(lane_stopped_in_epoch(lane, epoch))
            self.assertFalse(lane_stopped_in_epoch(lane, {'started_at': 103}))
            write('lane-startup.json', {'pid': 43, 'started_at': 103})
            self.assertFalse(lane_stopped_in_epoch(lane, epoch))
            (state / 'lane-stopped.json').write_text('partial')
            self.assertFalse(lane_stopped_in_epoch(lane, epoch))
            (state / 'lane-stopped.json').unlink()
            self.assertFalse(lane_stopped_in_epoch(lane, epoch))
