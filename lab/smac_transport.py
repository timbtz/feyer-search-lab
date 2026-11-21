"""Bounded optional SSH transport for the isolated SMAC environment."""
import hashlib
import json
from pathlib import Path
import re
import shlex
import subprocess


def invoke(request, endpoint=None):
    if not endpoint:
        from .smac_search import metadata, choose
        return metadata() if request.get('action') == 'metadata' else choose(request)
    if set(endpoint) != {'host', 'python', 'root'} or not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9._-]*', endpoint['host']):
        raise ValueError('SMAC endpoint requires an SSH alias and absolute Python/source paths')
    for name in ('python', 'root'):
        if not isinstance(endpoint[name], str) or not endpoint[name].startswith('/') or '..' in Path(endpoint[name]).parts:
            raise ValueError('SMAC endpoint paths must be absolute without parent traversal')
    command = ['env', 'OMP_NUM_THREADS=1', 'OPENBLAS_NUM_THREADS=1', 'MKL_NUM_THREADS=1',
               'PYTHONPATH=' + endpoint['root'], endpoint['python'], '-m', 'lab.smac_search']
    result = subprocess.run(['ssh', '-o', 'BatchMode=yes', '-o', 'ConnectTimeout=15',
                             endpoint['host'], shlex.join(command)],
                            input=json.dumps(request, allow_nan=False), text=True,
                            capture_output=True, check=True, timeout=90)
    return json.loads(result.stdout)


def verify_metadata(metadata):
    from .smac_search import VERSION, SMAC_VERSION
    from .evolution_space import SPACE_VERSION
    if metadata.get('adapter_version') != VERSION or metadata.get('space_version') != SPACE_VERSION:
        raise ValueError('SMAC adapter/search-space version mismatch')
    if metadata.get('packages', {}).get('smac') != SMAC_VERSION:
        raise ValueError('SMAC package is not pinned to the required version')
    root = Path(__file__).parent
    for key, filename in [('source_sha256', 'smac_search.py'), ('space_sha256', 'evolution_space.py')]:
        if metadata.get(key) != hashlib.sha256((root / filename).read_bytes()).hexdigest():
            raise ValueError('SMAC helper source differs from this controller: ' + filename)
    return metadata
