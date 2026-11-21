"""Bounded compiler evidence for one exact candidate; never benchmark evidence.

Executed only by the serial worker's diagnostic profile. Numerical imports occur
inside run(), so summary/validation tests do not import JAX or run physics.
"""
from __future__ import annotations

import argparse
from collections import Counter
import gzip
import hashlib
import importlib.metadata
import importlib.util
import json
import math
import os
from pathlib import Path
import platform
import re
import sys
from time import perf_counter

SCHEMA = 'feyer-compiler-diagnostic-v1'
STAGES = ('forward', 'sensitivity', 'gradient')
KINDS = ('stablehlo', 'hlo', 'optimized-hlo')
ARTIFACTS = tuple(f'{stage}.{kind}.txt.gz' for stage in STAGES for kind in KINDS)
MAX_TEXT_BYTES = 2 * 1024 * 1024
MAX_REPORT_BYTES = 1024 * 1024
LIMITS = [
    'Instrumented diagnostic timings are excluded from the benchmark objective and all rankings.',
    'HLO instruction counts and compiler estimates are structural evidence, not native operator timings.',
    'One first execution per stage; no warm benchmark or finite-difference validation is performed.',
    'IR text and summaries are bounded; truncation and unavailable analyses are explicit.',
    'Compiler cost/memory analyses are backend dependent and do not measure process peak RSS.',
]


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def summarize_ir(text):
    """Bounded best-effort text statistics, without interpreting them as timings."""
    raw = text.encode('utf-8')
    sample = raw[:MAX_TEXT_BYTES].decode('utf-8', errors='ignore')
    operations = Counter()
    calls, computations = [], []
    current = None
    instructions = 0
    for line in sample.splitlines():
        # Optimized/pre-optimized XLA HLO. StableHLO is counted separately below.
        match = re.search(r'=\s*(?:[^\s]+\s+)([\w-]+)\(', line)
        if match:
            operations[match.group(1)] += 1
            instructions += 1
            if current is not None:
                current['instructions'] += 1
        for op in re.findall(r'\bstablehlo\.([\w_]+)\b', line):
            operations['stablehlo.' + op] += 1
        if line and not line[0].isspace() and line.rstrip().endswith('{') and not line.startswith('HloModule'):
            current = {'name': line[:240], 'instructions': 0}
            computations.append(current)
        if 'custom_call_target=' in line and len(calls) < 30:
            calls.append(line.strip()[:700])
    return dict(utf8_bytes=len(raw), sha256=hashlib.sha256(raw).hexdigest(),
                analyzed_bytes=len(sample.encode('utf-8')), truncated=len(raw) > MAX_TEXT_BYTES,
                instruction_count_in_sample=instructions,
                opcode_counts_in_sample=dict(operations.most_common(80)),
                computation_count_in_sample=len(computations),
                largest_computations_in_sample=sorted(computations, key=lambda row: -row['instructions'])[:20],
                custom_call_examples=calls)


def save_ir(directory, stage, kind, text):
    if not isinstance(text, str) or not text:
        return {'available': False, 'reason': 'Backend returned no text'}
    summary = summarize_ir(text)
    name = f'{stage}.{kind}.txt.gz'
    if name not in ARTIFACTS:
        raise ValueError('Unknown diagnostic artifact name')
    payload = text.encode('utf-8')[:MAX_TEXT_BYTES]
    with (Path(directory) / name).open('wb') as stream:
        with gzip.GzipFile(fileobj=stream, mode='wb', mtime=0) as compressed:
            compressed.write(payload)
    return dict(summary, available=True, artifact=name, stored_uncompressed_bytes=len(payload),
                artifact_sha256=digest(Path(directory) / name))


def optional_analysis(function):
    """Keep backend/version-specific analyses useful but strictly bounded."""
    try:
        value = function()
        if value is None:
            return {'available': False, 'reason': 'Unsupported by backend'}
        if isinstance(value, dict):
            value = {str(k)[:120]: v for k, v in list(value.items())[:100]
                     if type(v) in (int, float) and math.isfinite(v)}
            return {'available': True, 'values': value}
        # JAX memory analysis is a backend object, not a stable JSON schema.
        return {'available': True, 'text': str(value)[:8000]}
    except (AttributeError, NotImplementedError, RuntimeError, ValueError, TypeError) as exc:
        return {'available': False, 'reason': (type(exc).__name__ + ': ' + str(exc))[:500]}


def validate_report(report, expected_sha, expected_harness_sha256, expected_benchmark_sha256,
                    cpu, fixture_sha256, reference_sha256):
    """Diagnostics cannot masquerade as an official score or correctness pass."""
    if not isinstance(report, dict) or report.get('schema') != SCHEMA or report.get('ranking_eligible') is not False:
        raise ValueError('Invalid nonranking diagnostic envelope')
    if any(key in report for key in ('first_run_seconds', 'timing_seconds', 'official_passed', 'regression_passed')):
        raise ValueError('Diagnostic report contains benchmark result fields')
    source = report.get('source', {})
    if source.get('commit') != expected_sha or source.get('modified') is not False:
        raise ValueError('Diagnostic source does not match the clean exact candidate')
    if report.get('harness_sha256') != expected_harness_sha256 or report.get('benchmark_sha256') != expected_benchmark_sha256:
        raise ValueError('Diagnostic harness or official benchmark digest mismatch')
    inputs = report.get('inputs', {})
    if inputs != dict(frequency_count=101, gradient_parameter_count=193,
                      setup_sha256=fixture_sha256, reference_sha256=reference_sha256):
        raise ValueError('Diagnostic workload differs from the fixed workload')
    env = report.get('environment', {})
    if not (env.get('backend') == 'cpu' and env.get('cpu_affinity_ids') == [cpu]
            and env.get('jax_enable_x64') is True and env.get('persistent_compilation_cache') is False
            and env.get('xla_flags') is None
            and env.get('thread_limits') == {key: '1' for key in
                ('OMP_NUM_THREADS', 'OPENBLAS_NUM_THREADS', 'MKL_NUM_THREADS', 'NUMEXPR_NUM_THREADS')}):
        raise ValueError('Diagnostic does not identify the fixed execution environment')
    stages = report.get('stages')
    if not isinstance(stages, dict) or set(stages) != set(STAGES):
        raise ValueError('Diagnostic must identify all three JIT stages')
    for stage in stages.values():
        for key in ('lower_seconds', 'compile_seconds', 'execute_seconds'):
            value = stage.get(key)
            if type(value) not in (int, float) or not math.isfinite(value) or value < 0:
                raise ValueError('Invalid diagnostic stage timing')
        ir = stage.get('ir')
        if not isinstance(ir, dict) or set(ir) != set(KINDS):
            raise ValueError('Missing diagnostic IR evidence')
        if not all(isinstance(v, dict) and type(v.get('available')) is bool for v in ir.values()):
            raise ValueError('Invalid diagnostic IR availability')
    if report.get('sanity') != dict(output_shapes=[[286, 1], [751, 101], [101]],
                                   gradient_shape=[193], finite=True):
        raise ValueError('Diagnostic did not complete the full output/gradient shape and finite checks')


def run(repo, output, expected_sha):
    repo, output = Path(repo).resolve(), Path(output).resolve()
    if output.is_relative_to(repo):
        raise ValueError('Diagnostic artifacts must be outside the candidate checkout')
    output.parent.mkdir(parents=True, exist_ok=True)
    sys.path.insert(0, str(repo))
    spec = importlib.util.spec_from_file_location('feyer_official_benchmark', repo / 'benchmark.py')
    benchmark = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = benchmark
    spec.loader.exec_module(benchmark)
    jax, jnp, np, df = benchmark.jax, benchmark.jnp, benchmark.np, benchmark.df
    if Path(df.__file__).resolve().parent != repo / 'differometor':
        raise ValueError('Diagnostic imported a different simulator')
    jax.config.update('jax_enable_x64', True)
    jax.config.update('jax_enable_compilation_cache', False)
    jax.devices('cpu')
    source = benchmark.git_state(repo)
    if source['commit'] != expected_sha or source['modified'] is not False:
        raise ValueError('Diagnostic requires a clean exact candidate SHA')
    fixture_path, reference_path = (repo / 'examples/data' / name for name in
                                    ('uifo_800_3000.json', 'uifo_800_3000_test_data.json'))
    if digest(fixture_path) != benchmark.FIXTURE_SHA256 or digest(reference_path) != benchmark.REFERENCE_SHA256:
        raise ValueError('Fixed input fixture digest mismatch')
    fixture, reference = json.loads(fixture_path.read_bytes()), json.loads(reference_path.read_bytes())
    setup = df.Setup.from_data(fixture)
    pairs = benchmark.constrain_inter_grid_cell_spaces(setup.parameters, benchmark.PROPERTIES)
    initial = []
    for pair in pairs:
        members = pair if isinstance(pair[0], list) else [pair]
        values = [fixture['nodes' if name in fixture['nodes'] else 'edges'][name]['properties'][prop]
                  for name, prop in members]
        if any(value != values[0] for value in values):
            raise ValueError('Grouped physical parameters do not agree')
        initial.append(values[0])
    parameters = jnp.asarray(initial, dtype=jnp.float64)
    frequencies = jnp.asarray(reference['frequencies'], dtype=jnp.float64)
    expected = jnp.asarray(reference['sensitivities'], dtype=jnp.float64)
    if parameters.shape != (193,) or frequencies.shape != (101,):
        raise ValueError('Diagnostic requires all 101 frequencies and 193 design variables')
    arrays, ports, *_ = df.run_build_step(setup, [('f', 'frequency')], frequencies, pairs)
    arrays['optimized_parameters'] = parameters
    ports, one = jnp.asarray(ports), jnp.asarray(1.0, dtype=jnp.float64)
    stages = {}

    def stage(name, function, *values):
        start = perf_counter()
        lowered = jax.jit(function).lower(*values)
        lower_seconds = perf_counter() - start
        start = perf_counter()
        compiled = lowered.compile()
        compile_seconds = perf_counter() - start
        start = perf_counter()
        result = compiled(*values)
        jax.block_until_ready(result)
        execute_seconds = perf_counter() - start
        ir = {}
        for kind, inspect in (('stablehlo', lambda: lowered.as_text()),
                              ('hlo', lambda: lowered.compiler_ir('hlo').as_hlo_text()),
                              ('optimized-hlo', lambda: compiled.as_text())):
            try:
                ir[kind] = save_ir(output.parent, name, kind, inspect())
            except (AttributeError, NotImplementedError, RuntimeError, ValueError, TypeError) as exc:
                ir[kind] = dict(available=False, reason=(type(exc).__name__ + ': ' + str(exc))[:500])
        stages[name] = dict(lower_seconds=lower_seconds, compile_seconds=compile_seconds,
                            execute_seconds=execute_seconds, ir=ir,
                            cost_analysis=optional_analysis(lambda: compiled.cost_analysis()),
                            memory_analysis=optional_analysis(lambda: compiled.memory_analysis()))
        print(f'{name}: lower {lower_seconds:.4f}s; compile {compile_seconds:.4f}s; execute {execute_seconds:.4f}s (diagnostic only)', flush=True)
        return result

    outputs, simulation_pullback = stage('forward', benchmark.forward_with_pullback, parameters, arrays)
    loss, readout_pullback, (sensitivity, powers) = stage('sensitivity', benchmark.sensitivity_with_pullback,
                                                       outputs, ports, expected)
    gradient = stage('gradient', benchmark.backward, simulation_pullback, readout_pullback, one)
    host = jax.device_get((outputs, sensitivity, powers, loss, gradient))
    del simulation_pullback, readout_pullback
    finite = all(np.all(np.isfinite(value)) for value in jax.tree.leaves(host))
    report = dict(schema=SCHEMA, ranking_eligible=False, source=source,
                  harness_sha256=digest(__file__), benchmark_sha256=digest(repo / 'benchmark.py'),
                  inputs=dict(frequency_count=101, gradient_parameter_count=193,
                              setup_sha256=digest(fixture_path), reference_sha256=digest(reference_path)),
                  environment=dict(backend=jax.default_backend(), cpu_affinity_ids=sorted(os.sched_getaffinity(0)),
                                   jax_enable_x64=bool(jax.config.jax_enable_x64),
                                   persistent_compilation_cache=bool(jax.config.jax_enable_compilation_cache),
                                   python=platform.python_version(), cpu_model=benchmark.cpu_model(),
                                   packages={name: importlib.metadata.version(name) for name in ('jax', 'jaxlib', 'numpy')},
                                   xla_flags=os.environ.get('XLA_FLAGS'),
                                   thread_limits={key: os.environ.get(key) for key in
                                       ('OMP_NUM_THREADS', 'OPENBLAS_NUM_THREADS', 'MKL_NUM_THREADS', 'NUMEXPR_NUM_THREADS')}),
                  stages=stages, sanity=dict(output_shapes=[list(value.shape) for value in outputs],
                                            gradient_shape=list(gradient.shape), finite=bool(finite)),
                  limits=LIMITS)
    payload = json.dumps(report, indent=2, allow_nan=False) + '\n'
    if len(payload.encode()) > MAX_REPORT_BYTES:
        raise ValueError('Diagnostic summary exceeds bounded report size')
    output.write_text(payload)
    if not finite:
        raise ValueError('Diagnostic produced nonfinite outputs or gradient')
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--repo', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--sha', required=True)
    parser.add_argument('--cpus', type=int, choices=(1,), default=1)
    args = parser.parse_args()
    if not re.fullmatch(r'[0-9a-f]{40}', args.sha):
        parser.error('--sha must be an exact commit')
    run(args.repo, args.output, args.sha)


if __name__ == '__main__':
    main()
