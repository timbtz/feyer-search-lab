import os
from pathlib import Path
import tempfile
import unittest
from lab.resources import MemoryMonitor


class MemoryMonitorTests(unittest.TestCase):
    def test_process_group_sum_excludes_other_jobs_and_latches_peak(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);(root/'self').mkdir();(root/'self/stat').write_text('')
            for pid,group,pages in [(11,10,3),(12,10,4),(13,20,1000)]:
                p=root/str(pid);p.mkdir()
                (p/'stat').write_text(f'{pid} (name (with spaces)) S 1 {group} 0')
                (p/'statm').write_text(f'1000 {pages} 0')
            page=os.sysconf('SC_PAGE_SIZE');m=MemoryMonitor(6*page,root)
            self.assertTrue(m.sample(10));self.assertEqual(m.report()['sampled_process_group_peak_rss_bytes'],7*page)
            (root/'12/statm').write_text('1000 1 0')
            self.assertTrue(m.sample(10));self.assertEqual(m.peak_bytes,7*page)
            self.assertFalse(m.report()['kernel_memory_limit_enforced'])

    def test_unavailable_sampling_is_not_reported_as_enforcement(self):
        with tempfile.TemporaryDirectory() as folder:
            m=MemoryMonitor(proc_root=folder)
            self.assertFalse(m.sample(1));self.assertEqual(m.report()['enforcement'],'unavailable')
            self.assertIsNone(m.report()['sampled_process_group_peak_rss_bytes'])

    def test_invalid_budget_is_rejected(self):
        for value in (0,-1,True):
            with self.assertRaises(ValueError):MemoryMonitor(value)
