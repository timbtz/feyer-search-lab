"""Candidate29 synthetic adapter check; supervisor fixed-environment execution only.

No timing or optical benchmark. Uses the actual adapter, sparse gathers and host
custom-VJP boundary, with toy host math in an isolated namespace. Compares the
nested-JIT candidate with its unwrapped parent for all differentiable inputs.
"""
import ast
from functools import partial
from pathlib import Path
from types import SimpleNamespace

import jax
import jax.numpy as jnp
from jax import lax, jit
import numpy as np
from differometor.sparse import SparseSystem

jax.config.update("jax_enable_x64", True)
jax.config.update("jax_enable_compilation_cache", False)
root = Path(__file__).resolve().parents[2]


def definitions(path, names, namespace):
    nodes = [n for n in ast.parse(path.read_text()).body
             if isinstance(n, ast.FunctionDef) and n.name in names]
    assert {n.name for n in nodes} == names
    exec(compile(ast.Module(body=nodes, type_ignores=[]), str(path), "exec"), namespace)


scope = dict(jax=jax, jnp=jnp, np=np, partial=partial, lax=lax, jit=jit)
# Reuse only the toy math definitions, not the older candidate-specific tests.
definitions(root / "experiments/notes/overnight-overhead-callback-check.py",
            {"bases", "forward", "backward"}, scope)
scope.update(host_forward=scope["forward"], host_backward=scope["backward"])
definitions(root / "differometor/host_pass.py",
            {"_shapes", "_forward_call", "host_pass", "_host_pass_fwd", "_host_pass_bwd"}, scope)
scope["host_pass"].defvjp(scope["_host_pass_fwd"], scope["_host_pass_bwd"])
scope["_host_pass"] = SimpleNamespace(host_pass=scope["host_pass"])
definitions(root / "differometor/simulate.py", {"_simulate_host_pass"}, scope)
candidate = scope["_simulate_host_pass"]
reference = candidate.__wrapped__


@jax.tree_util.register_static
class Plan:
    def __init__(self, sparse):
        systems = []
        for shape in ((3, 4), (4, 5), (4, 4)):
            rows, cols = np.indices(shape)
            if sparse:
                rows, cols = rows.ravel()[::2], cols.ravel()[::2]
            # Structural writes include entries whose current values are zero.
            systems.append(SparseSystem(np.zeros(shape, complex), rows, cols))
        self.structure = SimpleNamespace(carrier=systems[0], signal=systems[1], noise=systems[2])


rng = np.random.default_rng(2929)
checked = 0
for sparse in (False, True):
    plan = Plan(sparse)
    for places in ([], [[0, 0, 0]], [[0, 0, 0], [0, 0, 3]]):
        placements = np.asarray(places, np.int64).reshape(-1, 3)

        def evaluator(adapter):
            def boundary(*inputs):
                args = list(inputs)
                args[1] = jnp.exp(1j * jnp.radians(args[1]))
                return adapter(plan, *args, placements)

            def evaluate(*inputs):
                output, pullback = jax.vjp(boundary, *inputs)
                bars = tuple(jnp.ones_like(x) * (1 + 0.5j if jnp.iscomplexobj(x) else 1)
                             for x in output)
                return output, pullback(bars)
            return jax.jit(evaluate)

        actual, expected = evaluator(candidate), evaluator(reference)
        for update in (False, True):
            shapes = [(1, 3), (len(places),), (1, 1), (1, 2), (3, 4), (4, 5), (4, 4), (1, 1, 4)]
            inputs = [jnp.asarray(rng.normal(size=s) + 1j * rng.normal(size=s)) for s in shapes]
            inputs[1] = jnp.asarray(np.arange(len(places)) * 37. if update else np.zeros(len(places)))
            inputs[4] = inputs[4].at[0, 0].set(0)
            inputs[7] = inputs[7].at[0, 0, 0].set(0)
            got, want = actual(*inputs), expected(*inputs)
            for a, b in zip(jax.tree.leaves(got), jax.tree.leaves(want)):
                np.testing.assert_allclose(np.asarray(a), np.asarray(b), rtol=1e-13, atol=1e-13)
            assert len(got[1]) == 8
            checked += 1
print(f"PASS: {checked} synthetic primal/all-input VJP comparisons; no optical correctness or timing claim")
