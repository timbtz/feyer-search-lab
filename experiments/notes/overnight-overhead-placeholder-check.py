"""Small regression for no-link builds after custom links have been registered.

Default: execute the actual registry helpers and final linking block extracted
from build.py, using only stdlib. No optical simulation or timing is performed.
--jax: additionally check the selected placeholder's values and reverse gradients
through JAX's generic switch path. Requires the existing evaluation environment.
"""

import argparse
import ast
from pathlib import Path


def load_linking_code():
    path = Path(__file__).resolve().parents[2] / "differometor" / "build.py"
    tree = ast.parse(path.read_text())
    functions = {node.name: node for node in tree.body if isinstance(node, ast.FunctionDef)}
    namespace = {"LINKING_FUNCTIONS": []}
    helper_names = ("identity_link", "_identity_link_index", "parameter_linking")
    helpers = ast.Module(body=[functions[name] for name in helper_names], type_ignores=[])
    exec(compile(helpers, str(path), "exec"), namespace)
    body = functions["build"].body
    start = next(i for i, node in enumerate(body)
                 if isinstance(node, ast.Assign)
                 and any(isinstance(target, ast.Name) and target.id == "linked_indices"
                         for target in node.targets))
    assert isinstance(body[start + 1], ast.If)
    finish = compile(ast.Module(body=body[start:start + 2], type_ignores=[]), str(path), "exec")
    return namespace, finish


def finish_links(namespace, code, linked_names=(), destinations=(), functions=()):
    local = dict(namespace)
    local.update(parameter_names=["frequency", "power"], linked_names=list(linked_names),
                 indices_to_link=list(destinations), linking_function_indices=list(functions))
    exec(code, local)
    return local


def structural_checks():
    namespace, finish = load_linking_code()
    registry = namespace["LINKING_FUNCTIONS"]
    identity = namespace["identity_link"]
    checks = 0
    # Both first-build orders, and existing duplicate identities from older builds.
    for prefix in ([], [lambda x: 2 * x + 3], [lambda x: -x, lambda x: x + 11],
                   [identity, identity], [lambda x: x + 11, identity, identity]):
        registry[:] = prefix
        first_identity = next((i for i, f in enumerate(prefix) if f is identity), len(prefix))
        expected_size = len(prefix) + int(identity not in prefix)
        for _ in range(20):
            linked = finish_links(namespace, finish)
            assert linked["linked_indices"] == [0]
            assert linked["indices_to_link"] == [0]
            assert linked["linking_function_indices"] == [first_identity]
            assert registry[first_identity] is identity
            assert len(registry) == expected_size
            assert all(actual is original for actual, original in zip(registry, prefix))
            checks += 1
        # Register a real link using the actual existing builder function.
        destination, names, indices, values = [], [], [], [17]
        custom = lambda x: 2 * x + 3
        namespace["parameter_linking"]([("frequency", custom)], destination, names, indices, values)
        assert registry[indices[0]] is custom
        linked = finish_links(namespace, finish, names, destination, indices)
        assert linked["linked_indices"] == [0] and linked["indices_to_link"] == [1]
        assert linked["linking_function_indices"] == indices
        assert registry[indices[0]](17) == 37
        # A later no-link build must neither reuse the real link nor renumber it.
        assert finish_links(namespace, finish)["linking_function_indices"] == [first_identity]
        assert registry[indices[0]] is custom
        checks += 1
    print(f"PASS: {checks} registry/build-block cases (stdlib; no optical runs)")


def jax_checks():
    import jax
    import jax.numpy as jnp
    import numpy as np

    jax.config.update("jax_enable_x64", True)
    namespace, finish = load_linking_code()
    registry = namespace["LINKING_FUNCTIONS"]
    checks = 0
    for prefix in ([], [lambda x: 2 * x + 3], [lambda x: -x, lambda x: x + 11]):
        registry[:] = prefix
        index = finish_links(namespace, finish)["linking_function_indices"][0]
        branches = tuple(registry)
        selected = jax.jit(lambda x: jax.lax.switch(index, branches, x))
        for values in (np.array([0., -0., -2., 7.]), np.array([0j, -0j, 2 + 3j, -4 + 1j])):
            x = jnp.asarray(values)
            result, pullback = jax.vjp(selected, x)
            assert np.asarray(result).tobytes() == values.tobytes()
            cotangent = jnp.ones_like(x) * (2 + 3j if np.iscomplexobj(values) else 2)
            assert np.array_equal(np.asarray(pullback(cotangent)[0]), np.asarray(cotangent))
            checks += 1
    print(f"PASS: {checks} JAX generic-switch value/VJP cases")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--jax", action="store_true")
    args = parser.parse_args()
    structural_checks()
    if args.jax:
        jax_checks()
