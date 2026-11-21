"""SMAC ask/tell for a frozen categorical topology menu; never runs physics."""
import contextlib
import hashlib
import importlib.metadata
import json
import math
from pathlib import Path
import sys
import tempfile

from .topology_tuning import canonical, FAILURE_COST, VERSION


def metadata():
    packages = {p: importlib.metadata.version(p) for p in ('smac', 'ConfigSpace', 'numpy', 'scipy', 'scikit-learn')}
    if packages['smac'] != '2.4.1':
        raise ValueError('Pinned SMAC 2.4.1 required')
    return {'version': VERSION, 'packages': packages, 'n_trees': 32, 'seed': 0,
        'source_hashes': {n: hashlib.sha256(Path(__file__).with_name(n).read_bytes()).hexdigest()
                          for n in ('topology_smac.py', 'topology_tuning.py')}}


def choose(request):
    from ConfigSpace import ConfigurationSpace, Categorical, Configuration
    from smac import HyperparameterOptimizationFacade as Facade, Scenario
    from smac.runhistory.dataclasses import TrialInfo, TrialValue
    from smac.runhistory.enumerations import StatusType
    from smac.main.config_selector import ConfigSelector
    from smac.random_design.probability_design import ProbabilityRandomDesign
    from smac.acquisition.maximizer.abstract_acquisition_maximizer import AbstractAcquisitionMaximizer

    if request['metadata'] != metadata():
        raise ValueError('Frozen helper metadata differs')
    dimensions, legal, rows = request['dimensions'], request['legal'], request['observations']
    if not rows or not legal or len(legal) > 4096:
        raise ValueError('Finite menu and validated seed observation required')
    keys = {canonical(p) for p in legal}
    if len(keys) != len(legal):
        raise ValueError('Duplicate legal assignment')
    for p in legal:
        if set(p) != set(dimensions) or any(canonical(p[k]) not in list(map(canonical, v)) for k, v in dimensions.items()):
            raise ValueError('Illegal parameter assignment')
    history = set()
    for row in rows:
        key = canonical(row['parameters'])
        if key not in keys or key in history or row['status'] not in ('valid', 'invalid'):
            raise ValueError('Invalid or duplicated history')
        if not math.isfinite(row['cost']) or row['cost'] <= 0:
            raise ValueError('Finite positive costs required')
        if row['status'] == 'invalid' and row['cost'] != FAILURE_COST:
            raise ValueError('Invalid observations require scientific failure penalty')
        if row['status'] == 'valid' and row['cost'] >= FAILURE_COST:
            raise ValueError('Measured costs must be below penalty')
        history.add(key)
    options = [p for p in legal if canonical(p) not in history]
    if not options:
        return {'parameters': None, 'decision': {'origin': 'exhausted', 'model_trained': False}}
    # Before four full observations use a transparent local neighborhood; never
    # present startup enumeration as trained SMAC acquisition.
    if len(rows) < 4:
        valid = [r for r in rows if r['status'] == 'valid']
        incumbent = min(valid, key=lambda r: r['cost'])['parameters'] if valid else rows[0]['parameters']
        choice = min(options, key=lambda p: (sum(p[k] != incumbent[k] for k in p), canonical(p)))
        return {'parameters': choice, 'decision': {'origin': 'local-startup', 'model_trained': False,
                'training_configurations': len(rows)}}
    cs = ConfigurationSpace(seed=0)
    cs.add([Categorical(k, list(map(canonical, v))) for k, v in dimensions.items()])
    def config(p):
        return Configuration(cs, values={k: canonical(v) for k, v in p.items()})
    def decode(c):
        return {k: json.loads(v) for k, v in dict(c).items()}

    class FiniteMaximizer(AbstractAcquisitionMaximizer):
        ranked = None
        def _maximize(self, previous_configs, n_points):
            candidates = [config(p) for p in options]
            for c in candidates:
                c.origin = 'Acquisition Function Maximizer: Exact Topology Menu'
            ranking = self._sort_by_acquisition_value(candidates)
            self.ranked = [{'parameters': decode(c), 'score': float(score), 'rank': i + 1}
                           for i, (score, c) in enumerate(ranking)]
            if any(not math.isfinite(r['score']) for r in self.ranked):
                raise ValueError('Nonfinite acquisition score')
            return ranking[:n_points]
    with tempfile.TemporaryDirectory(prefix='topology-smac-') as tmp:
        scenario = Scenario(cs, output_directory=Path(tmp), deterministic=True, seed=0,
                            n_trials=len(legal), n_workers=1, crash_cost=FAILURE_COST)
        maximizer = FiniteMaximizer(cs, challengers=len(options), seed=0)
        facade = Facade(scenario, target_function=None, overwrite=True, logging_level=False,
            model=Facade.get_model(scenario, n_trees=32),
            initial_design=Facade.get_initial_design(scenario, n_configs=0,
                additional_configs=[config(rows[0]['parameters'])]),
            acquisition_maximizer=maximizer,
            intensifier=Facade.get_intensifier(scenario, max_config_calls=1),
            config_selector=ConfigSelector(scenario, retrain_after=1, max_new_config_tries=64),
            random_design=ProbabilityRandomDesign(probability=0., seed=0))
        for r in rows:
            facade.tell(TrialInfo(config(r['parameters']), seed=0), TrialValue(cost=r['cost'],
                        status=StatusType.SUCCESS if r['status'] == 'valid' else StatusType.CRASHED))
        for _ in range(len(legal) * 2):
            trial = facade.ask()
            parameters = decode(trial.config)
            if parameters in options and maximizer.ranked:
                selected = next(r for r in maximizer.ranked if r['parameters'] == parameters)
                return {'parameters': parameters, 'decision': {
                    'origin': trial.config.origin, 'model_trained': True,
                    'training_configurations': len(rows), 'acquisition_rank': selected['rank'],
                    'acquisition_score': selected['score'], 'ranked_options': maximizer.ranked}}
        raise RuntimeError('SMAC produced no legal unseen acquired option; no random fallback')


def main():
    request = json.load(sys.stdin)
    with contextlib.redirect_stdout(sys.stderr):
        value = metadata() if request.get('action') == 'metadata' else choose(request)
    print(json.dumps(value, allow_nan=False))


if __name__ == '__main__':
    main()
