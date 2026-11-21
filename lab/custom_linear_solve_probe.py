"""Can lax.custom_linear_solve with a SciPy SuperLU pure_callback keep full JAX semantics?"""
import os
import platform
import scipy
os.environ["JAX_PLATFORMS"] = "cpu"; os.environ["JAX_ENABLE_X64"] = "true"
import numpy as np, jax, jax.numpy as jnp, scipy.sparse as sp, scipy.sparse.linalg as spla
jax.config.update("jax_enable_x64", True)
rng = np.random.default_rng(1)
n = 30
dense = (rng.standard_normal((n, n)) + 1j * rng.standard_normal((n, n))) * (rng.random((n, n)) < 0.15) + 4 * np.eye(n)
rows, cols = np.nonzero(dense)

def host_solve(values, rhs, transpose):
    values, rhs = np.asarray(values), np.asarray(rhs)
    m = sp.csc_matrix((values, (rows, cols)), shape=(n, n))
    return spla.splu(m).solve(rhs, trans="T" if transpose else "N").astype(np.complex128)

def callback_solve(values, rhs, transpose):
    shape = jax.ShapeDtypeStruct(rhs.shape, jnp.complex128)
    return jax.pure_callback(lambda v, b: host_solve(v, b, transpose), shape, values, rhs, vmap_method="sequential")

def sparse_solve(values, rhs):
    matvec = lambda x: jax.ops.segment_sum(values * x[cols], rows, num_segments=n)
    return jax.lax.custom_linear_solve(matvec, rhs,
        solve=lambda _, b: callback_solve(values, b, False),
        transpose_solve=lambda _, b: callback_solve(values, b, True))

def dense_solve(values, rhs):
    return jnp.linalg.solve(jnp.zeros((n, n), jnp.complex128).at[rows, cols].set(values), rhs)

def model(solver):
    def f(p):  # matrix values and rhs depend nonlinearly on real parameters p
        values = jnp.asarray(dense[rows, cols]) * jnp.exp(1j * p[0] * jnp.arange(rows.size) / rows.size) + p[1]
        rhs = jnp.cos(p[2] * jnp.arange(n)) + 0j
        x = solver(values, rhs)
        return jnp.sum(jnp.abs(x) ** 2)
    return f

p = jnp.array([0.3, 0.2, 0.7]); v = jnp.array([0.5, -1.0, 0.25]); batch = jnp.stack([p, p * 1.1, p * 0.9])
tests = {
    "value": lambda f: f(p),
    "grad": lambda f: jax.grad(f)(p),
    "jvp": lambda f: jax.jvp(f, (p,), (v,))[1],
    "jacfwd": lambda f: jax.jacfwd(f)(p),
    "hessian": lambda f: jax.hessian(f)(p),
    "hvp_rev_over_rev": lambda f: jax.grad(lambda q: jnp.vdot(jax.grad(f)(q), v))(p),
    "vmap_grad": lambda f: jax.vmap(jax.grad(f))(batch),
    "jit_grad": lambda f: jax.jit(jax.grad(f))(p),
}
def evaluate(tolerance=1e-6):
    # This synthetic solve tests one mechanism, not Differometor or its speed.
    from jaxcompat import compare_values
    report = dict(scope="synthetic nonlinear complex 30x30 solve", seed=1,
                  tolerance=tolerance, python=platform.python_version(),
                  jax=jax.__version__, numpy=np.__version__, scipy=scipy.__version__,
                  x64=bool(jax.config.jax_enable_x64), tests={})
    for name, test in tests.items():
        try:
            ref = np.asarray(test(model(dense_solve))).tolist()
            got = np.asarray(test(model(sparse_solve))).tolist()
            result = compare_values(ref, got, tolerance)
            if result["passed"]:
                result.update(reference=ref, candidate=got)
            report["tests"][name] = result
        except Exception as error:
            report["tests"][name] = dict(status="unavailable", passed=False,
                                         error=f"{type(error).__name__}: {error}")
        print(name, report["tests"][name]["status"])
    report["passed"] = all(test["passed"] for test in report["tests"].values())
    return report


if __name__ == "__main__":
    import argparse, json, math, platform, scipy, sys
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", help="Structured toy-probe receipt")
    parser.add_argument("--tolerance", type=float, default=1e-6)
    args = parser.parse_args()
    if not math.isfinite(args.tolerance) or args.tolerance < 0:
        parser.error("tolerance must be finite and nonnegative")
    report = evaluate(args.tolerance)
    if args.out:
        with open(args.out, "w") as handle:
            json.dump(report, handle, indent=2, allow_nan=False)
    sys.exit(0 if report["passed"] else 1)
