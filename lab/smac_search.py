"""SMAC3 ask/tell adapter; fits bounded models, never runs physics.

Rebuild from immutable eligible observations on each decision. The campaign
ledger and pending recipe are authoritative; no second optimizer DB to recover.
"""
import contextlib
import hashlib
import importlib.metadata
import json
import math
from pathlib import Path
import sys
import tempfile
import time

from .evolution_space import SPACE_VERSION, assignments, canonical, validate

VERSION = 'smac-ask-tell-v1'
SMAC_VERSION = '2.4.1'
FAILURE_COST = 1_000_000.0


def metadata():
    packages = {p: importlib.metadata.version(p) for p in
                ('smac', 'ConfigSpace', 'numpy', 'scipy', 'scikit-learn')}
    if packages['smac'] != SMAC_VERSION:
        raise ValueError('Install the pinned controller SMAC version ' + SMAC_VERSION)
    return {'adapter_version': VERSION, 'space_version': SPACE_VERSION, 'packages': packages,
            'source_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
            'space_sha256': hashlib.sha256(Path(__file__).with_name('evolution_space.py').read_bytes()).hexdigest(),
            'n_trees': 32, 'acquisition_maximizer': 'registered-finite-set', 'max_config_calls': 1,
            'failure_cost': FAILURE_COST, 'n_workers': 1, 'startup_configs': 4, 'random_probability': 0.0,
            'history': 'one median of eligible full times per configuration; full scientific failures penalized'}


def configuration_space(seed):
    from ConfigSpace import ConfigurationSpace, Categorical, EqualsCondition
    cs = ConfigurationSpace(seed=seed)
    checkpoint = Categorical('checkpoint', ['on', 'off'], default='on')
    cse = Categorical('prevent_cse', ['off', 'on'], default='off')
    batch = Categorical('map_batch_size', ['scalar', '1', '2', '4', '8'], default='scalar')
    cs.add([checkpoint, cse, batch])
    cs.add(EqualsCondition(cse, checkpoint, 'on'))
    return cs


def encode(parameters):
    p = validate(parameters)
    value = {'checkpoint': 'on' if p['checkpoint'] else 'off',
             'map_batch_size': 'scalar' if p['map_batch_size'] is None else str(p['map_batch_size'])}
    if p['checkpoint']:
        value['prevent_cse'] = 'on' if p['prevent_cse'] else 'off'
    return value


def decode(configuration):
    c = dict(configuration)
    return validate({'checkpoint': c['checkpoint'] == 'on',
                     'prevent_cse': c.get('prevent_cse', 'off') == 'on',
                     'map_batch_size': None if c['map_batch_size'] == 'scalar' else int(c['map_batch_size'])})


def training_observations(snapshot):
    """Only trusted same-cohort full verdicts feed the optimizer."""
    cohort = snapshot['campaign']['spec']['cohort_digest']
    rows = []
    for candidate in snapshot['candidates']:
        observations = [e for e in snapshot['evidence'] if e['evidence_id'] in candidate['evidence_ids']
                        and e['profile'] == 'full' and e.get('cohort_digest') == cohort]
        invalid = any(e['category'] == 'invalid_candidate' for e in observations)
        valid = [e for e in observations if e.get('eligible_full') and e['category'] == 'valid']
        if not invalid and not (candidate['valid'] and valid):
            continue
        import statistics
        cost = FAILURE_COST if invalid else statistics.median(e['metrics']['total'] for e in valid)
        if not math.isfinite(cost) or cost <= 0 or (not invalid and cost >= FAILURE_COST):
            raise ValueError('Full timing must be positive, finite and below the frozen failure penalty')
        rows.append({'candidate_id': candidate['candidate_id'], 'commit_sha': candidate['commit_sha'],
                     'parameters': validate(candidate['parameters']), 'cost': cost,
                     'status': 'invalid' if invalid else 'valid',
                     'job_ids': [e['job_id'] for e in observations
                                 if e['category'] in ('valid', 'invalid_candidate')]})
    return rows


def choose(request):
    from ConfigSpace import Configuration
    from smac import HyperparameterOptimizationFacade as Facade, Scenario
    from smac.runhistory.dataclasses import TrialInfo, TrialValue
    from smac.runhistory.enumerations import StatusType
    from smac.main.config_selector import ConfigSelector
    from smac.random_design.probability_design import ProbabilityRandomDesign
    from smac.acquisition.maximizer.abstract_acquisition_maximizer import AbstractAcquisitionMaximizer

    class RegisteredSetMaximizer(AbstractAcquisitionMaximizer):
        """Score the actual unseen finite menu using SMAC's acquisition function."""
        ranked = None

        def _maximize(self, previous_configs, n_points):
            configs = [Configuration(self._configspace, values=encode(p)) for p in options.values()]
            for config in configs:
                config.origin = 'Acquisition Function Maximizer: Registered Finite Set'
            ranked = self._sort_by_acquisition_value(configs)[:n_points]
            self.ranked = [{'parameters': decode(config), 'score': float(score), 'rank': i + 1}
                           for i, (score, config) in enumerate(ranked)]
            if any(not math.isfinite(row['score']) for row in self.ranked):
                raise ValueError('SMAC acquisition returned a nonfinite score')
            return ranked

    started = time.monotonic()
    actual = metadata()
    if request['metadata'] != actual:
        raise ValueError('SMAC runtime differs from frozen campaign metadata')
    seed = request['seed']
    if type(seed) is not int or not 0 <= seed < 2**31:
        raise ValueError('Invalid frozen random seed')
    options = {canonical(validate(p)): p for p in request['options']}
    if not options:
        raise ValueError('No untested configurations remain')
    rows = request['observations']
    if not rows:
        raise ValueError('SMAC requires at least the validated seed observation')
    history = set()
    for row in rows:
        key = canonical(validate(row['parameters']))
        if key in history or key in options:
            raise ValueError('Repeated training content or already evaluated proposed option')
        history.add(key)
        if row['status'] not in ('valid', 'invalid') or not math.isfinite(row['cost']) or row['cost'] <= 0:
            raise ValueError('Invalid training observation')
        if row['status'] == 'invalid' and row['cost'] != FAILURE_COST:
            raise ValueError('Scientific failure must use the frozen penalty')
    cs = configuration_space(seed)
    with tempfile.TemporaryDirectory(prefix='feyer-smac-') as directory:
        scenario = Scenario(cs, name='selection', output_directory=Path(directory), seed=seed,
                            deterministic=True, n_trials=len(assignments()), n_workers=1,
                            crash_cost=FAILURE_COST)
        startup = max(0, actual['startup_configs'] - len(rows))
        design = Facade.get_initial_design(scenario, n_configs=startup, max_ratio=1.0,
                  additional_configs=[Configuration(cs, values=encode(rows[0]['parameters']))])
        maximizer = RegisteredSetMaximizer(cs, challengers=len(options), seed=seed)
        facade = Facade(scenario, target_function=None, overwrite=True, logging_level=False,
            model=Facade.get_model(scenario, n_trees=actual['n_trees']),
            initial_design=design,
            acquisition_maximizer=maximizer,
            intensifier=Facade.get_intensifier(scenario, max_config_calls=1),
            config_selector=ConfigSelector(scenario, retrain_after=1, max_new_config_tries=64),
            random_design=ProbabilityRandomDesign(probability=actual['random_probability'], seed=seed))
        # Median is one model observation. deterministic=True prevents SMAC
        # allocating repeated seeds; it does not assert noise-free measurements.
        for row in rows:
            info = TrialInfo(Configuration(cs, values=encode(row['parameters'])), seed=seed)
            facade.tell(info, TrialValue(cost=row['cost'],
                        status=StatusType.SUCCESS if row['status'] == 'valid' else StatusType.CRASHED))
        rejected = []
        for _ in range(len(assignments()) * 2):
            info = facade.ask()
            parameters = decode(info.config)
            if canonical(parameters) in options:
                rank = next((r for r in (maximizer.ranked or []) if r['parameters'] == parameters), None)
                return {'parameters': parameters, 'decision': {
                    'heuristic_id': VERSION, 'model': 'SMAC3 random forest + expected improvement',
                    'selection_origin': info.config.origin, 'trial_seed': info.seed,
                    'model_trained': bool(maximizer.ranked),
                    'acquisition_rank': rank['rank'] if rank else None,
                    'acquisition_score': rank['score'] if rank else None,
                    'ranked_options': maximizer.ranked,
                    'training_configurations': len(rows), 'startup_remaining': startup,
                    'rejected_asks': rejected, 'metadata': actual,
                    'fit_and_select_seconds': time.monotonic() - started,
                    'hypothesis': 'Evaluate the SMAC3 proposal under the fixed full correctness contract; speedup is unmeasured.'}}
            # No fake completed observations. These asks exist only in this
            # temporary facade; the controller never dispatches them.
            rejected.append(parameters)
        raise RuntimeError('SMAC returned no untested legal configuration; no fallback was evaluated')


def main():
    request = json.load(sys.stdin)
    with contextlib.redirect_stdout(sys.stderr):
        result = metadata() if request.get('action') == 'metadata' else choose(request)
    print(json.dumps(result, allow_nan=False))


if __name__ == '__main__':
    main()
