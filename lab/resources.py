"""Conservative sampled RSS budget; not a kernel cgroup memory limit."""
import os
from pathlib import Path

DEFAULT_MEMORY_BUDGET_BYTES = 32_000_000_000


class MemoryMonitor:
    def __init__(self, limit_bytes=DEFAULT_MEMORY_BUDGET_BYTES, proc_root='/proc'):
        if isinstance(limit_bytes, bool) or int(limit_bytes) <= 0:
            raise ValueError('A positive memory budget is required')
        self.limit_bytes = int(limit_bytes)
        self.proc_root = Path(proc_root)
        self.available = (self.proc_root / 'self/stat').exists()
        self.peak_bytes = 0
        self.samples = 0
        self.exceeded = False

    def sample(self, pgid):
        if not self.available:
            return False
        resident = 0
        for path in self.proc_root.iterdir():
            if not path.name.isdigit():
                continue
            try:
                # comm can contain spaces and parentheses; pgrp follows state and ppid.
                fields = (path / 'stat').read_text().rsplit(')', 1)[1].split()
                if int(fields[2]) != pgid:
                    continue
                pages = int((path / 'statm').read_text().split()[1])
            except (FileNotFoundError, ProcessLookupError, PermissionError, IndexError, ValueError):
                continue
            resident += pages * os.sysconf('SC_PAGE_SIZE')
        self.samples += 1
        self.peak_bytes = max(self.peak_bytes, resident)
        self.exceeded = self.exceeded or resident > self.limit_bytes
        return self.exceeded

    def report(self):
        return {'budget_bytes': self.limit_bytes,
                'enforcement': 'sampled_process_group_rss' if self.available else 'unavailable',
                'kernel_memory_limit_enforced': False,
                'sampled_process_group_peak_rss_bytes': self.peak_bytes if self.available else None,
                'samples': self.samples, 'exceeded': self.exceeded,
                'notes': 'RSS sampling can miss brief peaks and counts shared pages in each process. '
                         'It excludes GPU VRAM and does not reserve RAM or constrain other instance work.'}
