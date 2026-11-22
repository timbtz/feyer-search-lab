"""Trial27 sideband assembly/pullback checks and allocations, without timings."""
import ast
from pathlib import Path
import subprocess
from types import SimpleNamespace
import tracemalloc
import numpy as np

ROOT = Path(__file__).resolve().parents[2]
PARENT = 'ee4fea28c04d482566be16e916b609d7c6a99e5e'
parent = subprocess.check_output(['git', 'show', PARENT+':differometor/host_pass.py'], cwd=ROOT, text=True)
source = (ROOT/'differometor/host_pass.py').read_text()

def load(text):
    tree = ast.parse(text)
    names = {'_assemble', '_expand', '_split', '_sum_to'}
    nodes = [n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name in names]
    backward = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == 'host_backward')
    def assigns(node, name):
        return isinstance(node, ast.Assign) and any(isinstance(t, ast.Name) and t.id == name for t in node.targets)
    start = next(i for i,n in enumerate(backward.body) if assigns(n, 'placed_bar'))
    stop = next(i for i,n in enumerate(backward.body) if assigns(n, 'carrier_size'))
    wrapper = ast.parse('def sideband(structure, carrier, plan, signal_values_bar, carrier_bar, state):\n pass').body[0]
    wrapper.body = backward.body[start:stop] + ast.parse('return placed_bar, raw_bar, carrier_total_bar').body
    nodes.append(wrapper)
    module = ast.fix_missing_locations(ast.Module(body=nodes, type_ignores=[]))
    ns = dict(np=np, _products=lambda p: None, _factor=lambda *args: None,
              _solve=lambda products, values, factor, rhs, trans: rhs.copy())
    exec(compile(module, '<assembly and sideband pullback>', 'exec'), ns)
    return ns

old, new = load(parent), load(source)
rng = np.random.default_rng(2026112227)
checks = 0
for carrier_count, sweeps in ((1,1),(1,3),(1,13),(2,1),(5,1)):
    count = carrier_count*sweeps
    size, width = 3, 47
    carrier = rng.normal(size=(carrier_count,size))+1j*rng.normal(size=(carrier_count,size))
    coefficients = rng.normal(size=(count,width))+1j*rng.normal(size=(count,width))
    placing = np.array([2,4,9,17,30,45])
    carrier_indices = np.array([0,1,1,2,0,2])
    mask = rng.random(width) < .5
    for mode in ('random','zero','nonfinite'):
        raw = coefficients.copy()
        if mode == 'zero':
            raw.real[:] = -0.; raw.imag[:] = 0.
        elif mode == 'nonfinite':
            raw.real[:,::7] = np.nan; raw.imag[:,1::9] = np.inf
        for active in (False,True,mask,mask[None,:],np.broadcast_to(mask,(count,width))):
            for reuse in (False, True):
                cs = SimpleNamespace(size=size,nnz=0,augmented=True,rhs_rows=np.arange(size),pattern=None)
                structure = SimpleNamespace(carrier=cs, signal_placing_positions=placing, signal_conjugate=active)
                plan = SimpleNamespace(structure=structure, carrier_changing=np.array([],dtype=int),
                    signal_changing=np.array([],dtype=int), signal_carrier_indices=carrier_indices,
                    noise_row_reuse=reuse,
                    carrier=SimpleNamespace(values=lambda rows,base: carrier.copy()),
                    signal=SimpleNamespace(values=lambda rows,base: raw.copy()),
                    noise=SimpleNamespace(values=lambda rows,base: rows.copy()))
                inputs=(np.ones((1,7),complex),np.empty((0,carrier_count)),np.empty((0,sweeps)),
                        np.zeros(1),np.zeros(1),np.zeros(1))
                bar = rng.normal(size=(count,width))+1j*rng.normal(size=(count,width))
                cbar = rng.normal(size=carrier.shape)+1j*rng.normal(size=carrier.shape)
                states=[]; pullbacks=[]
                with np.errstate(all='ignore'):
                    for ns in (old,new):
                        state=ns['_assemble'](plan,*inputs)
                        states.append(state)
                        pullbacks.append(ns['sideband'](structure,carrier,plan,bar.copy(),cbar, state))
                for key in states[0]:
                    if key == 'carrier_factors': continue
                    assert states[0][key].tobytes() == states[1][key].tobytes(), key
                for a,b in zip(*pullbacks):
                    np.testing.assert_array_equal(a,b)
                    assert a.tobytes()==b.tobytes()
                assert states[1]['raw_signal'].tobytes()==raw.tobytes()
                assert not np.shares_memory(states[1]['raw_signal'],states[1]['signal_values'])
                checks+=1

# Measure actual source statements for a small synthetic coefficient buffer.
def forward_fragment(text):
    func=next(n for n in ast.parse(text).body if isinstance(n,ast.FunctionDef) and n.name=='_assemble')
    start=next(i for i,n in enumerate(func.body) if isinstance(n,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='placed' for t in n.targets))
    stop=next(i for i,n in enumerate(func.body) if isinstance(n,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='noise_rows' for t in n.targets))
    return compile(ast.Module(body=func.body[start:stop],type_ignores=[]),'<forward sideband>','exec')
raw=rng.normal(size=(17,1024)).astype(complex); carrier=np.ones((1,3),complex)
plan=SimpleNamespace(signal_carrier_indices=np.array([0,1,2]))
structure=SimpleNamespace(signal_conjugate=np.arange(1024)%2==0)
peaks=[]
for text in (parent,source):
    code=forward_fragment(text)
    local=dict(np=np,raw_signal=raw,carrier=carrier,placing=np.array([0,3,6]),plan=plan,structure=structure)
    tracemalloc.start()
    exec(code,local)
    peaks.append(tracemalloc.get_traced_memory()[1]); tracemalloc.stop()
assert peaks[1]<peaks[0]
print(dict(assembly_and_pullback_cases=checks,all_arrays_bitwise_equal=True,
           forward_peak_bytes=peaks,peak_reduction_bytes=peaks[0]-peaks[1],
           scope='synthetic assembly/pullback and allocations, no optical benchmark'))
