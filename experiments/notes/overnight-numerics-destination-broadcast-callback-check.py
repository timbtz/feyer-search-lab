"""Tiny actual host callbacks comparing component destination broadcasting.

No optical benchmark workloads or timings. Based on the preserved factor-zero
callback inspection, but each version loads its own production host.py kernels.
"""
import ast
import hashlib
from pathlib import Path
import runpy
import subprocess
from types import SimpleNamespace
import numpy as np
from scipy.sparse import csc_matrix
from scipy.sparse.linalg import splu

ROOT=Path(__file__).resolve().parents[2]
helper=runpy.run_path(str(ROOT/'experiments/notes/overnight-numerics-surface-check.py'))
component_loader=runpy.run_path(str(ROOT/'experiments/notes/overnight-numerics-destination-broadcast-check.py'))['load']
names={'SystemPlan','_digest','_Products','_solve','_split','_assembly_key',
       '_noise_amplitude','host_forward','host_backward','_sum_to','_cast_bar',
       '_expand','_expand_backward','_assemble','_selections','_is_hermitian',
       '_transpose_index','_collinear_coefficient','_factor','_construct_csc','_superlu_gstrf'}


def load(source, component_source):
    namespace,_=component_loader(component_source)
    ns=dict(namespace,np=np,hashlib=hashlib,_ASSEMBLY={},_TRANSPOSES={},_GSTRF=None,
            _scipy=lambda:(splu,csc_matrix),REFINEMENT_STEPS=3,REFINEMENT_TOLERANCE=1e-14,
            UNIT_VACUUM=1.,H_PLANCK=1.,F0=1.,_NOISE_SCALE=.5)
    nodes=[n for n in ast.parse(source).body if
        isinstance(n,(ast.ClassDef,ast.FunctionDef)) and n.name in names or
        isinstance(n,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='_SUPERLU_OPTIONS' for t in n.targets)]
    exec(compile(ast.Module(body=nodes,type_ignores=[]),'host-callbacks','exec'),ns)
    counts=dict(factors=0)
    real_factor=ns['_factor']
    def counted(*args):
        counts['factors']+=1
        return real_factor(*args)
    ns.update(_factor=counted,_products=ns['_Products'])
    return ns,counts


class Pattern(SimpleNamespace):
    __hash__=object.__hash__
    __eq__=object.__eq__


def system(size,writes,augmented):
    pattern=Pattern(size=size,rows=np.tile(np.arange(size),size),
                    indices=np.tile(np.arange(size),size),cols=np.repeat(np.arange(size),size),
                    indptr=np.arange(size+1)*size)
    return SimpleNamespace(pattern=pattern,size=size,nnz=size*size,augmented=augmented,
        rhs_rows=np.array([0,size-1]) if augmented else np.array([],int),
        write_positions=np.array(writes),_key='synthetic')


parent=subprocess.check_output(['git','show','7a9480332bad29b5aaeacc5a4628481581507e7a:differometor/host_pass.py'],cwd=ROOT,text=True)
parent_components=subprocess.check_output(['git','show','e5cbeba07943b6c797932263ff9deb721bf3ca89:differometor/host.py'],cwd=ROOT,text=True)
versions=[load(parent,parent_components),load((ROOT/'differometor/host_pass.py').read_text(),(ROOT/'differometor/host.py').read_text())]
checks=0; max_difference=0.; nonzero_parameter_checks=0
for count in (1,5):
 for reuse in (False,True):
  for mode in ('matched','cleared','interleaved'):
   for modulation in ('signal_function','laser_amplitude_modulation','laser_frequency_modulation','laser_frequency_modulation_lower'):
    for zero_value in (0.,.03):
     results=[]; totals=[]
     for ns,counters in versions:
        counters['factors']=0; ns['_ASSEMBLY'].clear()
        cs,ss,nn=system(2,[4],True),system(4,[16,1],True),system(4,[0],False)
        functions={f.__name__:i for i,f in enumerate(ns['HOST_FUNCTIONS'])}
        def plan(sys,name):
            return ns['SystemPlan'](sys,[(functions[name],np.arange(7)[None,:],(0,1))],[0],[0])
        # The second signal component writes an off-diagonal coefficient, with
        # amplitude zero or nonzero at this point. Its derivative is always present.
        signal=ns['SystemPlan'](ss,[(functions[modulation],np.arange(7)[None,:],(0,1)),
                         (functions['signal_function'],np.array([[2,3,4,5,6,0,1]]),(0,1))],[0,1],[0,0])
        structure=SimpleNamespace(carrier=cs,signal=ss,noise=nn,
            signal_placing_positions=np.array([],int),signal_conjugate=np.zeros(18,bool))
        hp=SimpleNamespace(_key='synthetic',structure=structure,noise_row_reuse=reuse,
            carrier_changing=np.array([1]),signal_changing=np.array([0]),
            signal_carrier_indices=np.array([],int),carrier=plan(cs,'laser'),
            signal=signal,noise=plan(nn,'signal_function'))
        params=np.full((1,7),.4,dtype=complex); params[0,2]=zero_value
        cv=np.array([[3.]],complex); sv=np.linspace(20.,107.,count)[None,:].astype(complex)
        cb=np.r_[(np.eye(2)*3).ravel(),[0.,.1]].astype(complex)
        sb=np.r_[(np.eye(4)*4).ravel(),[0.,.1]].astype(complex)
        nb=(np.eye(4)*2).ravel().astype(complex)
        if not reuse: nb[4]=.02j  # Exercise non-Hermitian adjoint fallback too.
        selects=np.array([[[.2,.3j,.5,.7j]],[[.3j,.1,.8j,.2]]])
        args=(params,cv,sv,cb,sb,nb,selects)
        forward=ns['host_forward'](hp,*args)
        if mode=='cleared': ns['_ASSEMBLY'].clear()
        elif mode=='interleaved':
            changed=params.copy(); changed[0,2]+=.1
            ns['host_forward'](hp,changed,*args[1:])
        c,s,n,cov,w=forward
        bars=(np.full(c.shape,.01+.02j),np.full(s.shape,.02-.03j),np.full(n.shape,.04))
        backward=ns['host_backward'](hp,*args,c,s,n,cov,w,*bars)
        assert not ns['_ASSEMBLY']
        assert abs(backward[0][0,2]) > 0, 'zero-valued coefficient lost derivative'
        nonzero_parameter_checks+=1
        before=counters['factors']
        again=ns['host_forward'](hp,*args)
        assert counters['factors']-before==1+count, 'forward failed to factor afresh'
        helper['check_equal'](forward,again)
        results.append((*forward,*backward)); totals.append(counters['factors'])
     helper['check_equal'](results[0],results[1])
     assert totals[0]==totals[1]
     for old,new in zip(*results):
        assert old.shape==new.shape and np.all(np.isfinite(new))
        scale=max(float(np.max(np.abs(old))) if old.size else 0.,1e-300)
        np.testing.assert_allclose(new,old,rtol=1e-12,atol=1e-14*scale)
        if old.size: max_difference=max(max_difference,float(np.max(np.abs(new-old)))/scale)
     checks+=1
print(dict(callback_cases=checks,zero_or_nonzero_parameter_derivative_checks=nonzero_parameter_checks,
           compared_arrays_per_case=12,max_relative_array_difference=max_difference,
           finite_arrays_bitwise_equal=True,fresh_factor_counts='identical',scope='synthetic only; no timings'))
