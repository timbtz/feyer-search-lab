"""Independent diagnostic probes; no reported time is a benchmark score.
Run on the pinned environment with --tree EXACT_ARCHIVE --out RESULTS.json.
"""
import argparse, contextlib, io, json, pathlib, sys, time, traceback
parser=argparse.ArgumentParser();parser.add_argument('--tree',required=True);parser.add_argument('--out',required=True);parser.add_argument('--only');args=parser.parse_args()
sys.path.insert(0,args.tree)
import numpy as np
import jax
import jax.numpy as jnp
jax.config.update('jax_enable_x64',True);jax.config.update('jax_enable_compilation_cache',False)
import differometor as df
from differometor.setups import constrain_inter_grid_cell_spaces
from differometor.host import kernel
root=pathlib.Path(args.tree)
assert pathlib.Path(df.__file__).resolve().is_relative_to(root.resolve()),df.__file__
report={'candidate_sha':'e2fd659e6f426289c526f79ae758bed4182879a9','python':sys.version,'jax':jax.__version__,'numpy':np.__version__,'tests':[]}
def clean(x):
 if isinstance(x,float) and not np.isfinite(x):return None
 if isinstance(x,dict):return {k:clean(v) for k,v in x.items()}
 if isinstance(x,list):return [clean(v) for v in x]
 return x
def save():pathlib.Path(args.out).write_text(json.dumps(clean(report),indent=2,allow_nan=False))
def probe(identity,fn,kind='compatibility'):
 if args.only and identity!=args.only:return
 t=time.time();row={'id':identity,'kind':kind,'started_at':t}
 try:
  data=fn();row.update({'status':'passed',**(data or {})})
 except Exception as e:
  row.update(status='failed',error=type(e).__name__+': '+str(e),traceback=traceback.format_exc())
 row['duration_seconds']=time.time()-t;report['tests'].append(row);save();print(identity,row['status'],row.get('error',''),flush=True)
fixture=json.loads((root/'examples/data/uifo_800_3000.json').read_text());ref=json.loads((root/'examples/data/uifo_800_3000_test_data.json').read_text())
setup=df.Setup.from_data(fixture);props=['reflectivity','tuning','db','angle','power','mass','length'];pairs=constrain_inter_grid_cell_spaces(setup.parameters,props)
def values(data,pairs):
 out=[]
 for pair in pairs:
  name,prop=pair[0] if isinstance(pair[0],list) else pair
  out.append(data['nodes' if name in data['nodes'] else 'edges'][name]['properties'][prop])
 return jnp.asarray(out,dtype=jnp.float64)
p0=values(fixture,pairs);freqs=jnp.asarray(ref['frequencies']);arrays,ports,*_=df.run_build_step(setup,[('f','frequency')],freqs,pairs);ports=jnp.asarray(ports)
def loss(p):
 c,s,n=df.simulate(**dict(arrays,optimized_parameters=p));det=df.signal_detector(c,s)[ports].squeeze();return jnp.mean(jnp.log10(n/jnp.abs(det)))
grad=jax.jit(jax.grad(loss));g0=np.asarray(grad(p0))
def batch():
 ps=jnp.stack([p0.at[0].add(i*1e-5) for i in range(4)]);a=np.asarray(jax.jit(jax.vmap(jax.grad(loss)))(ps));b=np.stack([np.asarray(grad(p)) for p in ps]);np.testing.assert_allclose(a,b,rtol=1e-10,atol=1e-10);return {'max_abs_error':float(np.max(np.abs(a-b))),'designs':4,'frequencies':101,'gradients_per_design':193}
probe('jit-vmap-four-gradients',batch)
def eviction():
 _,pb=jax.vjp(loss,p0);before=np.asarray(pb(jnp.array(1.))[0]);
 for i in range(8):jax.block_until_ready(grad(p0.at[0].add((i+1)*1e-5)))
 after=np.asarray(pb(jnp.array(1.))[0]);np.testing.assert_allclose(before,after,rtol=0,atol=0);return {'max_abs_error':float(np.max(np.abs(before-after))),'intervening_forwards':8}
probe('pullback-after-cache-eviction',eviction)
def checkpoint():
 actual=np.asarray(jax.jit(jax.grad(jax.checkpoint(loss)))(p0));np.testing.assert_allclose(actual,g0,rtol=1e-10,atol=1e-10);return {'max_abs_error':float(np.max(np.abs(actual-g0)))}
probe('gradient-through-checkpoint',checkpoint)
probe('forward-mode-jvp',lambda: {'value':float(jax.jvp(loss,(p0,),(jnp.ones_like(p0),))[1])})
probe('second-reverse-derivative',lambda: {'norm':float(jnp.linalg.norm(jax.grad(lambda p:jax.grad(loss)(p)[0])(p0)))})
probe('hessian-vector-product',lambda: {'norm':float(jnp.linalg.norm(jax.jvp(jax.grad(loss),(p0,),(jnp.ones_like(p0),))[1]))})
def zero_abs():
 fn=lambda x:jnp.abs(x[0]);x=np.asarray([[0.]],dtype=np.float64);v,j=kernel(fn,(1,))(x);expected=np.asarray(jax.jacfwd(fn)(jnp.asarray([0.])));actual=np.asarray(j).reshape(-1);np.testing.assert_allclose(actual,expected,rtol=0,atol=0);return {'actual':actual.tolist(),'expected':expected.tolist()}
probe('interpreter-abs-at-zero',zero_abs,'component_edge_case')
def noopt():
 a,*_=df.run_build_step(setup,[('f','frequency')],freqs,None);out=jax.jit(df.simulate)(**a);jax.block_until_ready(out);assert all(np.isfinite(np.asarray(v)).all() for v in out);return {'shapes':[list(v.shape) for v in out]}
probe('no-optimization-parameters',noopt)
# All-coordinate finite differences at the same physical perturbation used by gencheck.
def finite_differences():
 data=json.loads(json.dumps(fixture));rng=np.random.default_rng(7)
 for group in ('nodes','edges'):
  for item in data[group].values():
   for key,value in list(item.get('properties',{}).items()):
    if not isinstance(value,(int,float)) or isinstance(value,bool):continue
    if key=='reflectivity':item['properties'][key]=float(min(max(value*(1+0.02*rng.standard_normal()),1e-4),1-1e-4))
    elif key=='tuning':item['properties'][key]=float(value+0.5*rng.standard_normal())
    elif key=='length' and value>0:item['properties'][key]=float(value*(1+0.01*rng.standard_normal()))
    elif key=='power' and value>0:item['properties'][key]=float(value*(1+0.05*rng.standard_normal()))
 st=df.Setup.from_data(data);ps=constrain_inter_grid_cell_spaces(st.parameters,props);p=values(data,ps)
 interior=np.asarray(p).copy()
 for i,pair in enumerate(ps):
  _,prop=pair[0] if isinstance(pair[0],list) else pair
  if prop=='reflectivity':interior[i]=np.clip(interior[i],1e-3,1-1e-3)
  elif prop in ['power','mass','length','db']:interior[i]=max(interior[i],0.01)
 p=jnp.asarray(interior);a,dp,*_=df.run_build_step(st,[('f','frequency')],freqs,ps);dp=jnp.asarray(dp)
 def objective(p):
  c,s,n=df.simulate(**dict(a,optimized_parameters=p));d=df.signal_detector(c,s)[dp].squeeze();return jnp.mean(jnp.log10(n/jnp.abs(d)))
 f=jax.jit(objective);g=np.asarray(jax.jit(jax.grad(objective))(p));pn=np.asarray(p);scale=np.maximum(1.,np.abs(pn));steps=[]
 for h in (1e-5,5e-6):
  fd=[]
  for i in range(len(pn)):
   d=np.zeros_like(pn);d[i]=h*scale[i];fd.append((float(f(p+d))-float(f(p-d)))/(2*h))
  estimate=np.asarray(fd);expected=g*scale;bound=1e-6+0.01*np.abs(expected);ratios=np.abs(estimate-expected)/bound
  steps.append({'dimensionless_step':h,'failed_count':int(np.sum((ratios>1)|~np.isfinite(ratios))),'nonfinite_count':int(np.sum(~np.isfinite(ratios))),'worst_ratio':float(ratios.max()),'failed_indices':np.flatnonzero((ratios>1)|~np.isfinite(ratios)).tolist(),'finite_difference_scaled':estimate.tolist(),'autodiff_scaled':expected.tolist()})
 return {'status':'passed' if all(s['failed_count']==0 for s in steps) else 'needs_review','setup':'seed 7 perturbed topology, all optimized values moved inside physical bounds','frequencies':101,'variables':len(pn),'rtol':0.01,'scaled_atol':1e-6,'steps':steps,'parameters':pn.tolist(),'parameters_sha256':__import__('hashlib').sha256(pn.tobytes()).hexdigest(),'limitations':'Finite differences are approximate; this is one perturbed design, not universal proof.'}
probe('all-193-coordinate-finite-differences',finite_differences,'gradient_validation')
save()
