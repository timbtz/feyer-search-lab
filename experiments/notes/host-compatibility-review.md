# Host interpreter compatibility investigation

Parent: e2fd659e6f426289c526f79ae758bed4182879a9 (byte-identical teammate host engine).
Owned branch: `explore/host-compatibility-review`.
This is a focused semantic repair, not a claimed speed improvement or a general JAX implementation.

## Findings and change

1. The host primitive tangent rule used `sign(x) * tangent` for real `abs` and unguarded division by `abs(x)` for complex `abs`. Pinned JAX 0.9 chooses `+tangent` at both real signed zeros and zero at complex zero. The candidate follows those choices and the JAX operation order. Nonzero formulas remain mathematically equivalent, but the official full comparison must still check floating-point differences.
2. `_CALL_PRIMITIVES` included custom-JVP and custom-VJP calls. Both coverage checking and `_jvp_jaxpr` recursively used only the primal body, discarding its declared derivative rule. For example, a clipped/ReLU component may deliberately choose zero derivative at zero, while differentiating the underlying maximum chooses 0.5. This is a silent semantic error for a newly added component, not merely an unsupported API. The candidate rejects these custom derivative calls during coverage checking, activating the existing traced JAX fallback. Transparent jit/remat calls still recurse normally.
3. The module overview incorrectly said derivatives were traced with `jax.jvp`. The implementation traces a primal jaxpr with `jax.make_jaxpr` and applies hand-written primitive tangent rules. The overview now describes that actual boundary.

Pinned source reference: [JAX v0.9.0 abs JVP](https://github.com/jax-ml/jax/blob/jax-v0.9.0/jax/_src/lax/lax.py#L4079). Absolute value is not ordinarily differentiable at zero: the repair matches JAX's specified computational convention rather than proving a mathematical derivative exists there.

## Limits that remain

- Direct forward-mode JVP cannot cross `custom_vjp`; the reported failure is expected. The host reverse rule then calls a `pure_callback` with no derivative rule, so higher-order derivatives fail as well. These are distinct causes. Merely renaming the wrapper to `custom_jvp` is not enough: a tangent implementation and differentiable higher-order solve/component rules would be needed.
- The advertised traced JAX fallback is only a component-interpreter fallback. Its `make_linear_block` still uses `custom_vjp` plus callbacks for sparse solves, retaining the forward-mode/higher-order boundary. It must not be described as a fully JAX-compatible fallback.
- A conservative broader-compatibility option is an explicit original dense engine, using the matched `run_build_step_reference` and `simulate_reference` pair. That loses the host engine's speed advantage and still needs exact transform tests. Automatically reconstructing the dense engine inside an already-traced host call is not proposed here.
- Sparse signal factorization catches exact singularity and produces NaNs, but the carrier forward and reverse passes call `numpy.linalg.solve` directly. A singular carrier can raise inside a pure callback. This remains an unpatched scope limit. Handling singular batches per member with NaNs in both carrier solves is a separate candidate and needs tests against JAX failure semantics.
- Runtime real parameter assumptions are chosen at build time. Changing a previously real base parameter to complex without rebuilding the plan can discard its imaginary part in `HostEngine.forward`. Physical real-valued setup use is the supported domain; complex-extension equivalence is not claimed.
- Existing residual-cache tests passing does not prove functional purity under every transformation or concurrent schedule.

## Validation and next operator action

`experiments/notes/host_compatibility_probe.py` includes real signed-zero and complex-zero tangent checks, direct comparison of the full interpreter against pinned JAX, rejection of custom-JVP and custom-VJP calls, and a build-time fallback selection check using an existing component wrapped with an equivalent custom JVP.

Executed locally: two NumPy-only checks passed; Python syntax compilation and `git diff --check` passed. The local checks execute the actual `_tangent` AST because this coordinator environment has NumPy but no JAX. They do not substitute for full interpreter or workload validation.

Not executed by this sub-agent: pinned JAX tests, official benchmark, strict saved-array comparison, cross-setup generalization. The primary owns that serial test stream. Reproduction in the fixed environment:

```
/workspace/venv-feyer/bin/python experiments/notes/host_compatibility_probe.py
```

The exact candidate needs unchanged full evaluation before any correctness or speed promotion. Preserve any existing strict mismatch and generalization failures; this patch does not claim to repair sparse-solver roundoff, all-coordinate gradient failures, or broader transform support.

## Pinned follow-up

The primary's pinned run of `cb502e8` executed seven probe tests: six passed, including real/complex absolute-value comparison and direct custom-derivative rejection. The fallback test failed in its fixture before reaching the interpreter: replacing the shared component registry entry invalidated the builder's identity lookup for `laser`. The corrected fixture temporarily replaces only the interpreter's registry with a copied list, preserving builder and component export identities. Its pinned rerun is pending; the two NumPy checks and syntax/diff checks passed again locally.

The primary also reported a singular carrier solve during a three-step descent probe. This needs comparison with the reference trajectory and valid parameter bounds; it is not evidence that changing solve semantics or physics is justified. No additional simulator change was made for that failure.
