"""Reproduce original b093f74 false acceptance without JAX; requires NumPy."""
import ast
import contextlib
import io
import json
from pathlib import Path
import subprocess
import sys
import tempfile
from types import SimpleNamespace
import numpy as np

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT))
from lab.jaxcompat import REQUIRED_TESTS, compare_reports
COMMIT='b093f74efa76c6457ffef04ccb6c27436524565d'
original=subprocess.check_output(['git','show',f'{COMMIT}:lab/jaxcompat.py'],cwd=ROOT,text=True)
namespace={'__name__':'audit_original'}; exec(compile(original,'b093f74/jaxcompat.py','exec'),namespace)

def receipt(value):
    return dict(setup='voyager',tests={key:dict(status='ok',seconds=0.,value=value) for key in REQUIRED_TESTS})

cases={
 'nan_candidate':(receipt([1.]),receipt([float('nan')])),
 'shape_changed':(receipt([1.,2.]),receipt([[1.,2.]])),
 'missing_leaf':(receipt({'a':[1.],'b':[2.]}),receipt({'a':[1.]})),
 'renamed_key':(receipt({'a':[1.]}),receipt({'wrong':[1.]})),
 'empty_inventory':(dict(setup='voyager',tests={}),dict(setup='voyager',tests={})),
 'failed_reference':(dict(setup='voyager',tests={k:dict(status='error') for k in REQUIRED_TESTS}),receipt([1.])),
}
report=dict(source_commit=COMMIT,scope='acceptance logic only; no physics or JAX executed',cases={})
with tempfile.TemporaryDirectory() as tmp:
    for name,(reference,candidate) in cases.items():
        a,b=Path(tmp)/'ref.json',Path(tmp)/'candidate.json'
        a.write_text(json.dumps(reference)); b.write_text(json.dumps(candidate))
        stdout=io.StringIO()
        with contextlib.redirect_stdout(stdout):
            namespace['compare'](SimpleNamespace(reference=str(a),candidate=str(b),tolerance=1e-6))
        report['cases'][name]=dict(original_final_line=stdout.getvalue().splitlines()[-1],
                                  hardened=compare_reports(reference,candidate))
    script=Path(tmp)/'original.py'; script.write_text(original)
    a.write_text(json.dumps(receipt([1.]))); b.write_text(json.dumps(receipt([100.])))
    proc=subprocess.run([sys.executable,str(script),'compare',str(a),str(b)],capture_output=True,text=True)
    report['mismatch_cli']=dict(returncode=proc.returncode,final_line=proc.stdout.splitlines()[-1])

toy=subprocess.check_output(['git','show',f'{COMMIT}:lab/custom_linear_solve_probe.py'],cwd=ROOT,text=True)
loop=next(node for node in ast.parse(toy).body if isinstance(node,ast.For))
for name,value in [('wrong',100.),('nonfinite',float('nan'))]:
    stdout=io.StringIO()
    with contextlib.redirect_stdout(stdout):
        exec(compile(ast.Module(body=[loop],type_ignores=[]),'original_probe_loop','exec'),
             dict(np=np,tests={name:lambda f:f},model=lambda solver:solver,dense_solve=1.,sparse_solve=value))
    report.setdefault('toy_loop',{})[name]=stdout.getvalue().strip()

out=ROOT/'experiments/numerical-audit/harness-false-positives.json'
out.write_text(json.dumps(report,indent=2,allow_nan=False)+'\n')
print(out)
