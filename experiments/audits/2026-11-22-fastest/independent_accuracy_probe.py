import os, sys, json, time
os.environ["JAX_PLATFORMS"]="cpu"; os.environ["JAX_ENABLE_X64"]="true"
sys.path.insert(0, "/workspace/feyer-pristine")
import jax, jax.numpy as jnp, numpy as np
import scipy.sparse as sp, scipy.sparse.linalg as spla
import differometor as df
from differometor import setups as dsetups
from differometor.setups import constrain_inter_grid_cell_spaces
from differometor.simulate import update, expand_parameters
from differometor.build import LINKING_FUNCTIONS
from differometor.components import UNIT_VACUUM, H_PLANCK, F0
from jax import vmap, lax
PROPERTIES = ["reflectivity", "tuning", "db", "angle", "power", "mass", "length"]
name=sys.argv[1]
if name=="dev":
    fx=json.load(open("/workspace/feyer-pristine/examples/data/uifo_800_3000.json")); rf=json.load(open("/workspace/feyer-pristine/examples/data/uifo_800_3000_test_data.json"))
    setup=df.Setup.from_data(fx); pairs=constrain_inter_grid_cell_spaces(setup.parameters, PROPERTIES); freqs=np.asarray(rf["frequencies"])
elif name=="voyager" or name=="aligo":
    setup, cp = getattr(dsetups,name)(); pairs=[list(p) for p in cp if p[1] in PROPERTIES]; freqs=np.logspace(np.log10(20),np.log10(5000),100)
else:
    seed=int(name[len("uifo_rand"):]); setup, cp = dsetups.uifo(3, random=True, random_seed=seed); pairs=constrain_inter_grid_cell_spaces(cp, PROPERTIES); freqs=np.linspace(800,3000,101)
data=setup.to_data()
init=[]
for pair in pairs:
    members = pair if isinstance(pair[0], list) else [pair]; n_, pr = members[0]
    init.append(float(np.real(data["nodes" if n_ in data["nodes"] else "edges"][n_]["properties"][pr])))
arrays, ports, *_ = df.run_build_step(setup, [("f","frequency")], jnp.asarray(freqs), pairs)
arrays["optimized_parameters"]=jnp.asarray(init)
def assemble(optimized_parameters, optimized_parameter_indices, optimized_value_indices, carrier_changing_parameter_indices, carrier_changing_values, signal_changing_parameter_indices, signal_changing_values, parameters, carrier_matrix, signal_matrix, noise_matrix, noise_selection_vectors, qhd_parameter_indices, qhd_placing_indices, linked_indices, linking_function_indices, indices_to_link, carrier_function_input_indices, carrier_function_indices, carrier_output_indices, carrier_matrix_indices, signal_function_input_indices, signal_function_indices, signal_output_indices, signal_matrix_indices, signal_carrier_indices, signal_carrier_placing_indices, noise_function_input_indices, noise_function_indices, noise_output_indices, noise_system_matrix_indices):
    parameters = parameters.at[[0], optimized_parameter_indices].set(optimized_parameters[optimized_value_indices])
    outputs_to_link = vmap(lambda i, x: lax.switch(i, LINKING_FUNCTIONS, x))(linking_function_indices, parameters[0, linked_indices])
    parameters = parameters.at[[0], indices_to_link].set(outputs_to_link)
    qhd = jnp.exp(1j * jnp.radians(parameters[0, qhd_parameter_indices]))
    parameters = expand_parameters(parameters, carrier_changing_parameter_indices, carrier_changing_values)
    cmat = vmap(update, in_axes=(0, None, None, None, None, None))(parameters, carrier_matrix, carrier_function_input_indices, carrier_output_indices, carrier_matrix_indices, carrier_function_indices)
    carrier = vmap(jnp.linalg.solve)(cmat[:, :, :-1].astype(complex), cmat[:, :, -1].astype(complex))
    parameters = expand_parameters(parameters, signal_changing_parameter_indices, signal_changing_values)
    smat = vmap(update, in_axes=(0, None, None, None, None, None))(parameters, signal_matrix, signal_function_input_indices, signal_output_indices, signal_matrix_indices, signal_function_indices)
    se = -smat[:, signal_carrier_placing_indices[0], signal_carrier_placing_indices[1]] * carrier[:, signal_carrier_indices.flatten()]
    smat = smat.at[:, signal_carrier_placing_indices[0], signal_carrier_placing_indices[1]].set(se)
    cs = carrier.shape[1]
    smat = smat.at[:, cs:2*cs, cs:2*cs].set(jnp.conjugate(smat[:, cs:2*cs, cs:2*cs]))
    smat = smat.at[:, 2*cs:, :cs].set(jnp.conjugate(smat[:, 2*cs:, :cs]))
    smat = smat.at[:, cs:2*cs, 2*cs:].set(jnp.conjugate(smat[:, cs:2*cs, 2*cs:]))
    nsv = lax.scatter_mul(noise_selection_vectors, qhd_placing_indices.reshape(-1, 3), qhd, lax.ScatterDimensionNumbers(update_window_dims=(), inserted_window_dims=(0, 1, 2), scatter_dims_to_operand_dims=(0, 1, 2)), unique_indices=True)
    nsv = jnp.tile(nsv, (1, carrier.shape[0], 1))
    up = nsv[:, :, :cs] * carrier; up = nsv.at[:, :, :cs].set(up)
    lo = jnp.conjugate(up[:, :, cs:2*cs] * carrier); sel = up.at[:, :, cs:2*cs].set(lo)
    nmat = vmap(update, in_axes=(0, None, None, None, None, None))(parameters, noise_matrix, noise_function_input_indices, noise_output_indices, noise_system_matrix_indices, noise_function_indices)
    return smat, nmat, sel, carrier
smat, nmat, sel, carrier = [np.asarray(x) for x in jax.jit(assemble)(**arrays)]
A=smat[:,:,:-1]; rhs=smat[:,:,-1]; B,n,_=A.shape; D=sel.shape[0]
c=np.broadcast_to(sel,(D,B,n))
K=2*UNIT_VACUUM*H_PLANCK*F0*0.25
def noise_from(solveA, solveAH):
    out=np.zeros((D,B)); outL=np.zeros((D,B))
    for b in range(B):
        for d in range(D):
            w=solveAH(b, c[d,b]); q=nmat[b]@w; cov=solveA(b,q)
            out[d,b]=np.sum(np.real(cov*np.conj(c[d,b])))
    return out
def refine(Mb, x, rhsv, solver, iters):
    ML=Mb.astype(np.clongdouble); xL=x.astype(np.clongdouble); bL=rhsv.astype(np.clongdouble)
    for _ in range(iters):
        r=bL-ML@xL; xL=xL+solver(r.astype(np.complex128)).astype(np.clongdouble)
    return xL
lus={}; lush={}
def lu(b):
    if b not in lus:
        lus[b]=spla.splu(sp.csc_matrix(A[b]), permc_spec="COLAMD")
    return lus[b]
res={}
if len(sys.argv)>2 and sys.argv[2]=="signal":
    P=np.asarray(ports)
    def detected(S):
        sig=np.asarray(df.signal_detector(jnp.asarray(carrier.T), jnp.asarray(S.T)))[P]
        return sig.squeeze() if P.shape[0]==1 else sig[0]-sig[1]
    sols={}
    sols["dense"]=np.array([np.linalg.solve(A[b], rhs[b]) for b in range(B)])
    sols["sparse"]=np.array([lu(b).solve(rhs[b]) for b in range(B)])
    def dref1(b):
        M=sp.csc_matrix(A[b]); x=lu(b).solve(rhs[b]); return x+lu(b).solve(rhs[b]-M@x)
    sols["sp_dref1"]=np.array([dref1(b) for b in range(B)])
    sols["truth"]=np.array([refine(A[b], lu(b).solve(rhs[b]), rhs[b], lambda r, b=b: lu(b).solve(r), 5).astype(np.complex128) for b in range(B)])
    dt=detected(sols["truth"])
    tr=sols["truth"]; scale=np.abs(tr).max()
    for k,v in sols.items():
        print(f"{name:10s} {k:9s} strict-style max normalized error vs truth {np.max(np.abs(v-tr)/(1e-12*scale+1e-7*np.abs(tr))):.3f}")
    for k,v in sols.items():
        print(f"{name:10s} {k:9s} max rel err |detected| vs truth {np.max(np.abs(np.abs(detected(v))-np.abs(dt))/np.abs(dt)):.3e}; signal relL2 {np.linalg.norm(v-sols['truth'])/np.linalg.norm(sols['truth']):.2e}")
    if len(sys.argv) > 3:
        np.savez_compressed(sys.argv[3], carrier=carrier.T, signal=sols['truth'].T,
                            detected=dt, dense_signal=sols['dense'].T, frequencies=freqs)
    sys.exit(0)
# dense numpy
res["dense"]=noise_from(lambda b,v: np.linalg.solve(A[b],v), lambda b,v: np.linalg.solve(A[b].conj().T,v))
res["sparse"]=noise_from(lambda b,v: lu(b).solve(v), lambda b,v: lu(b).solve(v, trans='H'))
# sparse with separate factorization of conj(A) transposed (as implemented): splu(conj(A)).solve(trans='T')
def luh(b):
    if b not in lush: lush[b]=spla.splu(sp.csc_matrix(A[b].conj()), permc_spec="COLAMD")
    return lush[b]
res["sparse_impl"]=noise_from(lambda b,v: lu(b).solve(v), lambda b,v: luh(b).solve(v, trans='T'))
# extended-precision refinement (truth proxy)
def true_noise(iters):
    out=np.zeros((D,B))
    for b in range(B):
        AL=A[b].astype(np.clongdouble); NL=nmat[b].astype(np.clongdouble)
        for d in range(D):
            w=refine(A[b].conj().T, lu(b).solve(c[d,b],trans='H'), c[d,b], lambda r: lu(b).solve(r,trans='H'), iters)
            q=NL@w
            # refine cov solve against q (longdouble rhs)
            cov=lu(b).solve(q.astype(np.complex128)).astype(np.clongdouble)
            for _ in range(iters):
                r=q-AL@cov; cov=cov+lu(b).solve(r.astype(np.complex128)).astype(np.clongdouble)
            out[d,b]=float(np.sum(np.real(cov*np.conj(c[d,b].astype(np.clongdouble)))))
    return out
res["refined5"]=true_noise(5)
def dref(b, v, trans, iters, factor):
    M = sp.csc_matrix(A[b])
    op = {"N": M, "H": M.conj().T.tocsc()}[trans]
    x = factor.solve(v, trans=trans)
    for _ in range(iters):
        x = x + factor.solve(v - op @ x, trans=trans)
    return x
for iters in (1, 2):
    res[f"sp_dref{iters}"]=noise_from(lambda b,v: dref(b,v,"N",iters,lu(b)), lambda b,v: dref(b,v,"H",iters,lu(b)))
for perm in ("NATURAL", "MMD_AT_PLUS_A"):
    cache={}
    def f(b, perm=perm, cache=cache):
        if b not in cache: cache[b]=spla.splu(sp.csc_matrix(A[b]), permc_spec=perm)
        return cache[b]
    res[f"sp_{perm}"]=noise_from(lambda b,v: f(b).solve(v), lambda b,v: f(b).solve(v, trans='H'))
cache2={}
def g(b):
    if b not in cache2: cache2[b]=spla.splu(sp.csc_matrix(A[b]), permc_spec="COLAMD", options=dict(Equil=True))
    return cache2[b]
res["sp_equil"]=noise_from(lambda b,v: g(b).solve(v), lambda b,v: g(b).solve(v, trans='H'))
ref=res["refined5"]
for k,v in res.items():
    print(f"{name:10s} {k:12s} max rel err in noise^2 vs refined5: {np.nanmax(np.abs(v-ref)/np.abs(ref)):.3e}  (min noise^2 {np.min(np.abs(v)):.3e})")
print("noise^2 sign check: any negative?", {k: bool(np.any(v<0)) for k,v in res.items()})
