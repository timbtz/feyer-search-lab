"""Operator support probe: pristine JAX assembly, extended residual signal solve."""
from pathlib import Path
import hashlib
import subprocess
import time
from lab.transfer_run import reserve, execute, BASELINE
from lab.worker import atomic_json

tree = Path('/workspace/feyer-pristine')
if subprocess.check_output(['git','-C',str(tree),'rev-parse','HEAD'],text=True).strip() != BASELINE:
    raise RuntimeError('Reference SHA mismatch')
if subprocess.check_output(['git','-C',str(tree),'status','--porcelain','--untracked-files=no'],text=True).strip():
    raise RuntimeError('Reference modified')
probe = Path(__file__).with_name('independent_accuracy_probe.py')
out = Path('/workspace/feyer-transfer/53f38d3-independent-assembly-v1')
out.mkdir(exist_ok=False)
receipt = {'reference_sha': BASELINE, 'probe_sha256': hashlib.sha256(probe.read_bytes()).hexdigest(),
           'scope': 'Independent pristine JAX matrix assembly; same-input extended residual signal solve, not exact arithmetic.',
           'ranking_eligible': False, 'started_at': time.time(), 'tasks': []}
try:
    with reserve(['/workspace/feyer-lab/state','/workspace/feyer-lab-lane1/state']) as fds:
        deadline = time.monotonic()+600
        for case in ('uifo_rand1','uifo_rand3'):
            folder = out/case
            folder.mkdir()
            command = ['taskset','-c','2','/workspace/venv-feyer/bin/python','-u',str(probe),case,'signal',str(folder/'arrays.npz')]
            result = execute(command,tree,folder,max(.01,deadline-time.monotonic()),fds)
            receipt['tasks'].append({'case':case,'command':command,**result})
            atomic_json(out/'execution.json',receipt)
            if time.monotonic() >= deadline:
                break
finally:
    receipt['finished_at'] = time.time()
    atomic_json(out/'execution.json',receipt)
