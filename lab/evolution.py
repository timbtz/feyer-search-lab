"""Transactional, versioned search bookkeeping; never executes model code or jobs.

Tokens prevent accidental cross-owner updates through this API. They are not a
security boundary against someone who can edit the SQLite file on the same OS.
"""
import contextlib
import hashlib
import hmac
import json
import math
from pathlib import Path
import re
import secrets
import sqlite3
import statistics
import time
import uuid

PHASES = ('setup', 'compilation', 'forward', 'sensitivity', 'gradient', 'transfer')
ROLES = ('coordinator', 'strong', 'qwen', 'evaluator')
TERMINAL = ('valid', 'invalid', 'duplicate', 'infrastructure_abandoned')
PROVENANCE = ('heuristic_id', 'target_symbols', 'hypothesis', 'model_manifest',
              'context_sha256', 'prompt_sha256', 'response_sha256', 'parameters_before')


class BudgetExhausted(RuntimeError):
    """A new reservation would exceed the immutable campaign or round budget."""


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False)


def digest(value):
    return hashlib.sha256(canonical(value).encode()).hexdigest()


def identifier(value, name='identifier'):
    if not isinstance(value, str) or not re.fullmatch(r'[A-Za-z0-9_.:@/\-]{1,160}', value):
        raise ValueError(f'Invalid {name}')
    return value


def positive(value, name):
    if isinstance(value, bool) or not isinstance(value, int) or value < 1:
        raise ValueError(f'{name} must be a positive integer')
    return value


def checked_hash(value, size=64):
    if not isinstance(value, str) or not re.fullmatch('[0-9a-f]{' + str(size) + '}', value):
        raise ValueError(f'Expected a {size}-character lowercase hash')
    return value


class Campaign:
    def __init__(self, path):
        self.path = Path(path)
        if self.path.is_dir():
            self.path /= 'campaign.sqlite3'
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as db:
            db.execute('PRAGMA journal_mode=WAL')
            db.executescript('''
                CREATE TABLE IF NOT EXISTS campaign(id INTEGER PRIMARY KEY CHECK(id=1), spec TEXT NOT NULL,
                    spec_digest TEXT NOT NULL, created_at REAL NOT NULL);
                CREATE TABLE IF NOT EXISTS claims(actor TEXT NOT NULL, version INTEGER NOT NULL,
                    role TEXT NOT NULL, token_hash TEXT NOT NULL, granted_by TEXT NOT NULL, at REAL NOT NULL,
                    PRIMARY KEY(actor,version));
                CREATE TABLE IF NOT EXISTS rounds(round_id TEXT PRIMARY KEY, version INTEGER UNIQUE NOT NULL,
                    spec TEXT NOT NULL, spec_digest TEXT NOT NULL, closed INTEGER NOT NULL DEFAULT 0,
                    created_at REAL NOT NULL);
                CREATE TABLE IF NOT EXISTS lanes(round_id TEXT NOT NULL, lane_id TEXT NOT NULL,
                    state TEXT NOT NULL, PRIMARY KEY(round_id,lane_id));
                CREATE TABLE IF NOT EXISTS candidates(candidate_id TEXT PRIMARY KEY, proposal_id TEXT UNIQUE NOT NULL,
                    round_id TEXT NOT NULL, lane_id TEXT NOT NULL, proposal TEXT NOT NULL,
                    owner TEXT NOT NULL, owner_version INTEGER NOT NULL, state TEXT NOT NULL, created_at REAL NOT NULL);
                CREATE TABLE IF NOT EXISTS evaluations(request_id TEXT PRIMARY KEY, candidate_id TEXT NOT NULL,
                    profile TEXT NOT NULL, attempt INTEGER NOT NULL, job_id TEXT UNIQUE, state TEXT NOT NULL,
                    UNIQUE(candidate_id,profile,attempt));
                CREATE TABLE IF NOT EXISTS evidence(evidence_id TEXT PRIMARY KEY, job_id TEXT UNIQUE NOT NULL,
                    candidate_id TEXT NOT NULL, payload TEXT NOT NULL, digest TEXT NOT NULL, at REAL NOT NULL);
                CREATE TABLE IF NOT EXISTS model_calls(call_id TEXT PRIMARY KEY, actor TEXT NOT NULL,
                    metadata TEXT NOT NULL, at REAL NOT NULL);
                CREATE TABLE IF NOT EXISTS model_outcomes(call_id TEXT PRIMARY KEY, actor TEXT NOT NULL,
                    metadata TEXT NOT NULL, at REAL NOT NULL);
                CREATE TABLE IF NOT EXISTS guidance(guidance_id TEXT PRIMARY KEY, actor TEXT NOT NULL,
                    payload TEXT NOT NULL, at REAL NOT NULL);
                CREATE TABLE IF NOT EXISTS decisions(decision_id TEXT PRIMARY KEY, actor TEXT NOT NULL,
                    payload TEXT NOT NULL, at REAL NOT NULL);
                CREATE TABLE IF NOT EXISTS events(seq INTEGER PRIMARY KEY AUTOINCREMENT, type TEXT NOT NULL,
                    actor TEXT NOT NULL, payload TEXT NOT NULL, at REAL NOT NULL,
                    previous_hash TEXT NOT NULL, event_hash TEXT NOT NULL);
                CREATE TRIGGER IF NOT EXISTS immutable_events_update BEFORE UPDATE ON events
                    BEGIN SELECT RAISE(ABORT,'events are append-only'); END;
                CREATE TRIGGER IF NOT EXISTS immutable_events_delete BEFORE DELETE ON events
                    BEGIN SELECT RAISE(ABORT,'events are append-only'); END;
                CREATE TRIGGER IF NOT EXISTS immutable_round_spec BEFORE UPDATE OF spec,spec_digest,version ON rounds
                    BEGIN SELECT RAISE(ABORT,'round specification is immutable'); END;
                CREATE TRIGGER IF NOT EXISTS immutable_proposals BEFORE UPDATE OF proposal,proposal_id,owner,owner_version ON candidates
                    BEGIN SELECT RAISE(ABORT,'proposal identity is immutable'); END;
                CREATE TRIGGER IF NOT EXISTS immutable_campaign BEFORE UPDATE ON campaign
                    BEGIN SELECT RAISE(ABORT,'campaign budget and specification are immutable'); END;
            ''')

    def _connect(self):
        db = sqlite3.connect(self.path, timeout=30)
        db.row_factory = sqlite3.Row
        db.execute('PRAGMA busy_timeout=30000')
        return db

    @contextlib.contextmanager
    def _transaction(self):
        with self._connect() as db:
            db.execute('BEGIN IMMEDIATE')
            yield db

    def _event(self, db, actor, kind, payload):
        last = db.execute('SELECT seq,event_hash FROM events ORDER BY seq DESC LIMIT 1').fetchone()
        previous = last['event_hash'] if last else '0' * 64
        seq = last['seq'] + 1 if last else 1
        at = time.time()
        event_hash = digest(dict(seq=seq, type=kind, actor=actor, payload=payload, at=at, previous_hash=previous))
        db.execute('INSERT INTO events(seq,type,actor,payload,at,previous_hash,event_hash) VALUES(?,?,?,?,?,?,?)',
                   (seq, kind, actor, canonical(payload), at, previous, event_hash))

    def _campaign(self, db):
        row = db.execute('SELECT * FROM campaign WHERE id=1').fetchone()
        if row is None:
            raise ValueError('Campaign is not initialized')
        return dict(spec=json.loads(row['spec']), spec_digest=row['spec_digest'], created_at=row['created_at'])

    def _auth(self, db, actor, token, roles=None):
        claim = db.execute('SELECT * FROM claims WHERE actor=? ORDER BY version DESC LIMIT 1', (actor,)).fetchone()
        supplied = hashlib.sha256(token.encode()).hexdigest() if isinstance(token, str) else ''
        if claim is None or not hmac.compare_digest(claim['token_hash'], supplied):
            raise PermissionError('Unknown owner token or stale ownership version')
        if roles and claim['role'] not in roles:
            raise PermissionError('Role is not authorized for this operation')
        return claim

    def _new_claim(self, db, actor, role, grantor):
        previous = db.execute('SELECT MAX(version) FROM claims WHERE actor=?', (actor,)).fetchone()[0] or 0
        token = secrets.token_urlsafe(32)
        db.execute('INSERT INTO claims VALUES(?,?,?,?,?,?)',
                   (actor, previous + 1, role, hashlib.sha256(token.encode()).hexdigest(), grantor, time.time()))
        self._event(db, grantor, 'owner_claimed', dict(actor=actor, role=role, version=previous + 1))
        return token

    def initialize(self, spec, actor):
        identifier(actor, 'actor')
        spec = json.loads(canonical(spec))
        identifier(spec['campaign_id'], 'campaign_id')
        objective = spec.setdefault('objective', {})
        objective.setdefault('primary', 'total')
        objective.setdefault('direction', 'minimize')
        axes = objective.setdefault('pareto_axes', list(PHASES))
        if objective['primary'] != 'total' or objective['direction'] != 'minimize' or not isinstance(axes, list) or not axes or len(axes) > 16 or len(set(axes)) != len(axes):
            raise ValueError('Use a total-minimization objective and distinct named Pareto axes')
        for axis in axes:
            identifier(axis, 'Pareto axis')
        budget = spec['budget']
        for key in ('max_proposals', 'max_evaluations'):
            positive(budget[key], key)
        budget.setdefault('max_model_calls', budget['max_proposals'])
        calls = budget['max_model_calls']
        if type(calls) is not int or calls < 0:
            raise ValueError('max_model_calls must be a nonnegative integer')
        deadline = budget['deadline_unix']
        if isinstance(deadline, bool) or not isinstance(deadline, (float, int)) or not math.isfinite(deadline) or deadline <= time.time():
            raise ValueError('Campaign requires an explicit future deadline')
        with self._transaction() as db:
            if db.execute('SELECT 1 FROM campaign').fetchone():
                raise ValueError('Campaign already initialized; budgets cannot be silently extended')
            db.execute('INSERT INTO campaign VALUES(1,?,?,?)', (canonical(spec), digest(spec), time.time()))
            self._event(db, actor, 'campaign_initialized', dict(spec_digest=digest(spec)))
            return self._new_claim(db, actor, 'coordinator', actor)

    def grant(self, actor, token, worker, role):
        identifier(worker, 'worker')
        if role not in ROLES:
            raise ValueError('Unknown role')
        with self._transaction() as db:
            self._auth(db, actor, token, ('coordinator',))
            return self._new_claim(db, worker, role, actor)

    def _round(self, db, round_id):
        row = db.execute('SELECT * FROM rounds WHERE round_id=?', (round_id,)).fetchone()
        if row is None:
            raise ValueError('Unknown round')
        return dict(round_id=row['round_id'], version=row['version'], spec=json.loads(row['spec']),
                    spec_digest=row['spec_digest'], closed=bool(row['closed']), created_at=row['created_at'])

    def _lane(self, db, round_id, lane_id):
        row = db.execute('SELECT state FROM lanes WHERE round_id=? AND lane_id=?', (round_id, lane_id)).fetchone()
        if row is None:
            raise ValueError('Unknown lane')
        return json.loads(row['state'])

    def _save_lane(self, db, lane):
        db.execute('UPDATE lanes SET state=? WHERE round_id=? AND lane_id=?',
                   (canonical(lane), lane['round_id'], lane['lane_id']))

    def _candidate(self, db, candidate_id):
        row = db.execute('SELECT * FROM candidates WHERE candidate_id=?', (candidate_id,)).fetchone()
        if row is None:
            raise ValueError(f'Unknown candidate: {candidate_id}')
        proposal = json.loads(row['proposal'])
        return dict(proposal, proposal=proposal, owner=row['owner'], owner_version=row['owner_version'],
                    created_at=row['created_at'], **json.loads(row['state']))

    def _save_candidate(self, db, candidate):
        fields = ('status', 'valid', 'cohort_digest', 'metrics', 'evidence_ids', 'counted',
                  'improved', 'duplicate_of', 'progress', 'full_run_count', 'metric_ranges')
        state = {k: candidate[k] for k in fields if k in candidate}
        db.execute('UPDATE candidates SET state=? WHERE candidate_id=?',
                   (canonical(state), candidate['candidate_id']))

    def _usage(self, db):
        return dict(proposals=db.execute('SELECT count(*) FROM candidates').fetchone()[0],
                    evaluations=db.execute("SELECT count(*) FROM evaluations WHERE json_extract(state,'$.imported')=0").fetchone()[0],
                    model_calls=db.execute('SELECT count(*) FROM model_calls').fetchone()[0])

    def _budget(self, db, kind, round_id=None):
        budget = self._campaign(db)['spec']['budget']
        if time.time() >= budget['deadline_unix']:
            raise BudgetExhausted('Campaign deadline exhausted')
        if self._usage(db)[kind] >= budget['max_' + kind]:
            raise BudgetExhausted(f'Campaign {kind} budget exhausted')
        if round_id and kind in ('proposals', 'evaluations'):
            spec = self._round(db, round_id)['spec']
            limit = spec['budget']['max_' + kind]
            if kind == 'proposals':
                used = db.execute('SELECT count(*) FROM candidates WHERE round_id=?', (round_id,)).fetchone()[0]
            else:
                used = db.execute("SELECT count(*) FROM evaluations e JOIN candidates c ON c.candidate_id=e.candidate_id WHERE c.round_id=? AND json_extract(e.state,'$.imported')=0", (round_id,)).fetchone()[0]
            if used >= limit:
                raise BudgetExhausted(f'Round {kind} budget exhausted')

    def add_round(self, actor, token, spec):
        spec = json.loads(canonical(spec))
        round_id = identifier(spec['round_id'], 'round_id')
        dimensions = spec['dimensions']
        if not isinstance(dimensions, dict) or not dimensions or len(dimensions) > 32:
            raise ValueError('Round requires finite named dimensions')
        for name, values in dimensions.items():
            identifier(name, 'dimension')
            if not isinstance(values, list) or not 1 <= len(values) <= 256:
                raise ValueError('Dimensions require a finite nonempty value list')
            if any(isinstance(v, (dict, list)) for v in values) or len({canonical(v) for v in values}) != len(values):
                raise ValueError('Dimension values must be distinct JSON scalars')
        for recipe, rule in spec.get('recipes', {}).items():
            identifier(recipe, 'recipe')
            if not rule.get('dimensions') or not set(rule['dimensions']).issubset(dimensions):
                raise ValueError('Recipe dimensions must belong to the frozen space')
        progress = spec.setdefault('progress', {})
        progress.setdefault('relative', .03)
        progress.setdefault('absolute', .02)
        for value in progress.values():
            if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or value < 0:
                raise ValueError('Progress thresholds must be finite and nonnegative')
        if not spec.get('lanes'):
            raise ValueError('Round requires owned lanes')
        with self._transaction() as db:
            self._auth(db, actor, token, ('coordinator',))
            budget = spec.setdefault('budget', {})
            for kind in ('proposals', 'evaluations'):
                budget.setdefault('max_' + kind, self._campaign(db)['spec']['budget']['max_' + kind])
                positive(budget['max_' + kind], 'round max_' + kind)
            for lane_spec in spec['lanes'].values():
                lane_spec.setdefault('max_proposals', budget['max_proposals'])
            prior = db.execute('SELECT spec FROM rounds WHERE round_id=?', (round_id,)).fetchone()
            if prior:
                if prior['spec'] == canonical(spec):
                    return self._round(db, round_id)
                raise ValueError('Round ID already has a different immutable specification')
            self._budget(db, 'proposals')
            if db.execute("SELECT 1 FROM lanes WHERE json_extract(state,'$.inflight_candidate') IS NOT NULL").fetchone():
                raise RuntimeError('Drain in-flight candidates before creating a new round')
            combination_parents = spec.get('combination_parents', [])
            if combination_parents and (len(set(combination_parents)) < 2 or len(set(combination_parents)) != len(combination_parents)
                                       or not all(self._candidate(db, p)['valid'] for p in combination_parents)):
                raise ValueError('Frozen combination parents require at least two distinct validated candidates')
            for lane_id, lane_spec in spec['lanes'].items():
                identifier(lane_id, 'lane_id')
                owner = identifier(lane_spec['owner'], 'lane owner')
                if not db.execute('SELECT 1 FROM claims WHERE actor=?', (owner,)).fetchone():
                    raise ValueError('Lane owner must have a registered claim')
                if not lane_spec.get('dimensions') or not set(lane_spec['dimensions']).issubset(dimensions):
                    raise ValueError('Lane owns a nonempty subset of frozen dimensions')
                lane_spec.setdefault('max_proposals', budget['max_proposals'])
                positive(lane_spec['max_proposals'], 'lane max_proposals')
                positive(lane_spec.get('stall_limit', 3), 'lane stall_limit')
                base = lane_spec.get('base_candidate')
                if base and not self._candidate(db, base)['valid']:
                    raise ValueError('Lane base candidate must be fully validated')
            version = (db.execute('SELECT MAX(version) FROM rounds').fetchone()[0] or 0) + 1
            db.execute('UPDATE rounds SET closed=1 WHERE closed=0')
            db.execute('INSERT INTO rounds VALUES(?,?,?,?,0,?)', (round_id, version, canonical(spec), digest(spec), time.time()))
            for lane_id, lane_spec in spec['lanes'].items():
                lane = dict(round_id=round_id, lane_id=lane_id, owner=lane_spec['owner'], status='ready',
                            strikes=0, inflight_candidate=None, proposals=0, base_candidate=lane_spec.get('base_candidate'))
                db.execute('INSERT INTO lanes VALUES(?,?,?)', (round_id, lane_id, canonical(lane)))
            self._event(db, actor, 'round_created', dict(round_id=round_id, version=version, spec_digest=digest(spec)))
            return self._round(db, round_id)

    def propose(self, actor, token, proposal):
        proposal = json.loads(canonical(proposal))
        if len(canonical(proposal)) > 100000:
            raise ValueError('Proposal metadata exceeds 100 KB')
        proposal_id = identifier(proposal['proposal_id'], 'proposal_id')
        candidate_id = identifier(proposal.setdefault('candidate_id', proposal_id), 'candidate_id')
        proposal.setdefault('parents', [])
        proposal.setdefault('parameters', {})
        proposal.setdefault('recipe', None)
        provenance = proposal.setdefault('provenance', {})
        if not isinstance(provenance, dict):
            raise ValueError('Provenance must be an object')
        for key in PROVENANCE:
            if key in proposal:
                provenance[key] = proposal[key]
        checked_hash(proposal['content_sha256'])
        checked_hash(proposal['commit_sha'], 40)
        with self._transaction() as db:
            claim = self._auth(db, actor, token, ('coordinator', 'strong', 'qwen'))
            existing = db.execute('SELECT candidate_id,proposal,owner FROM candidates WHERE proposal_id=?', (proposal_id,)).fetchone()
            if existing:
                if existing['proposal'] != canonical(proposal) or existing['owner'] != actor:
                    raise ValueError('Proposal ID conflicts with an immutable proposal')
                return self._candidate(db, existing['candidate_id'])
            if db.execute('SELECT 1 FROM candidates WHERE candidate_id=?', (candidate_id,)).fetchone():
                raise ValueError('Candidate ID is already assigned to a different proposal')
            round_data = self._round(db, proposal['round_id'])
            if round_data['closed']:
                raise ValueError('Round is frozen/closed; create a new version')
            spec = round_data['spec']
            lane = self._lane(db, proposal['round_id'], proposal['lane_id'])
            lane_spec = spec['lanes'][proposal['lane_id']]
            seed = proposal['kind'] == 'seed'
            if seed and claim['role'] != 'coordinator':
                raise PermissionError('Only a coordinator may import seed evidence')
            if not seed and actor != lane['owner']:
                raise PermissionError('Another owner holds this lane')
            if lane['status'] != 'ready' or lane['inflight_candidate']:
                raise RuntimeError('Lane is not accepting proposals or already has an in-flight candidate')
            self._budget(db, 'proposals', proposal['round_id'])
            if lane['proposals'] >= lane_spec['max_proposals']:
                raise RuntimeError('Lane proposal budget exhausted')
            parents = proposal['parents']
            if not isinstance(parents, list) or len(set(parents)) != len(parents):
                raise ValueError('Candidate parents must be distinct existing candidate IDs')
            parent_nodes = [self._candidate(db, p) for p in parents]
            kind = proposal['kind']
            if kind == 'seed' and parents or kind == 'mutate' and len(parents) != 1 or kind == 'combine' and len(parents) < 2:
                raise ValueError('Seed/mutation/combination parent count is invalid')
            if kind not in ('seed', 'mutate', 'combine'):
                raise ValueError('Unsupported proposal kind')
            if not seed and not all(p['valid'] for p in parent_nodes):
                raise ValueError('Mutation and combination parents must be fully validated')
            if len({p['cohort_digest'] for p in parent_nodes}) > 1:
                raise ValueError('Parents must share the same comparable evidence cohort')
            if kind == 'combine' and claim['role'] == 'qwen' and set(parents) != set(spec.get('combination_parents', [])):
                raise PermissionError('Qwen combination parents must match the coordinator-frozen round specification')
            params = proposal['parameters']
            if set(params) != set(spec['dimensions']):
                raise ValueError('Proposal must carry a complete finite parameter assignment')
            for key, value in params.items():
                if canonical(value) not in {canonical(v) for v in spec['dimensions'][key]}:
                    raise ValueError('Proposal leaves the frozen finite parameter space')
            if not seed:
                before = parent_nodes[0]['parameters']
                changed = {k for k in params if canonical(params[k]) != canonical(before.get(k))}
                if not changed.issubset(lane_spec['dimensions']):
                    raise ValueError('Proposal changes dimensions owned by another lane')
                base = self._candidate(db, lane['base_candidate']) if lane['base_candidate'] else parent_nodes[0]
                if any(canonical(params[k]) != canonical(base['parameters'].get(k)) for k in params if k not in lane_spec['dimensions']):
                    raise ValueError('Proposal changes the lane frozen base outside its owned dimensions')
                if 'parameters_before' in provenance and canonical(provenance['parameters_before']) != canonical(before):
                    raise ValueError('parameters_before does not match the selected parent')
                if claim['role'] == 'qwen':
                    recipe = spec.get('recipes', {}).get(proposal['recipe'])
                    if not recipe or not changed.issubset(recipe['dimensions']) or not set(recipe['dimensions']).issubset(lane_spec['dimensions']):
                        raise ValueError('Qwen must use a registered recipe within its owned dimensions')
            duplicate = db.execute("SELECT candidate_id FROM candidates WHERE json_extract(proposal,'$.content_sha256')=? ORDER BY created_at LIMIT 1", (proposal['content_sha256'],)).fetchone()
            state = dict(status='duplicate' if duplicate else 'proposed', valid=False, cohort_digest=None,
                         metrics=None, evidence_ids=[], counted=False, improved=False,
                         duplicate_of=duplicate['candidate_id'] if duplicate else None, full_run_count=0)
            db.execute('INSERT INTO candidates VALUES(?,?,?,?,?,?,?,?,?)',
                       (candidate_id, proposal_id, proposal['round_id'], proposal['lane_id'], canonical(proposal),
                        actor, claim['version'], canonical(state), time.time()))
            lane['proposals'] += 1
            if not duplicate:
                lane['inflight_candidate'] = candidate_id
                lane['status'] = 'active'
            self._save_lane(db, lane)
            self._event(db, actor, 'candidate_proposed', dict(candidate_id=candidate_id, proposal_id=proposal_id,
                        owner_version=claim['version'], proposal_digest=digest(proposal), duplicate_of=state['duplicate_of']))
            return self._candidate(db, candidate_id)

    def record_model_call(self, actor, token, call_id, metadata):
        identifier(call_id, 'call_id')
        encoded = canonical(metadata)
        if len(encoded) > 100000:
            raise ValueError('Model call metadata is too large')
        with self._transaction() as db:
            self._auth(db, actor, token, ('coordinator', 'strong', 'qwen'))
            previous = db.execute('SELECT * FROM model_calls WHERE call_id=?', (call_id,)).fetchone()
            if previous:
                if previous['actor'] != actor or previous['metadata'] != encoded:
                    raise ValueError('Model call ID conflicts with an existing reservation')
                return dict(call_id=call_id, reserved=True)
            self._budget(db, 'model_calls')
            db.execute('INSERT INTO model_calls VALUES(?,?,?,?)', (call_id, actor, encoded, time.time()))
            self._event(db, actor, 'model_call_reserved', dict(call_id=call_id, metadata=metadata))
            return dict(call_id=call_id, reserved=True)

    def record_model_outcome(self, actor, token, call_id, metadata):
        encoded = canonical(metadata)
        if len(encoded) > 100000:
            raise ValueError('Model outcome metadata is too large')
        with self._transaction() as db:
            claim = self._auth(db, actor, token, ('coordinator', 'strong', 'qwen'))
            call = db.execute('SELECT * FROM model_calls WHERE call_id=?', (call_id,)).fetchone()
            if call is None:
                raise ValueError('Reserve a model call before recording its outcome')
            if actor != call['actor'] and claim['role'] != 'coordinator':
                raise PermissionError('Another owner reserved this model call')
            prior = db.execute('SELECT * FROM model_outcomes WHERE call_id=?', (call_id,)).fetchone()
            if prior:
                if prior['metadata'] != encoded:
                    raise ValueError('Model outcome conflicts with recorded immutable outcome')
                return dict(call_id=call_id, metadata=json.loads(prior['metadata']))
            db.execute('INSERT INTO model_outcomes VALUES(?,?,?,?)', (call_id, actor, encoded, time.time()))
            self._event(db, actor, 'model_call_finished', dict(call_id=call_id, metadata=metadata))
            return dict(call_id=call_id, metadata=metadata)

    def record_guidance(self, actor, token, guidance_id, payload):
        identifier(guidance_id, 'guidance_id')
        encoded = canonical(payload)
        if len(encoded) > 100000:
            raise ValueError('Guidance payload is too large')
        with self._transaction() as db:
            self._auth(db, actor, token, ('coordinator', 'strong'))
            for parent in payload.get('parents', []):
                self._candidate(db, parent)
            for key in ('context_sha256', 'spec_sha256', 'prompt_sha256', 'response_sha256'):
                if key in payload:
                    checked_hash(payload[key])
            prior = db.execute('SELECT * FROM guidance WHERE guidance_id=?', (guidance_id,)).fetchone()
            if prior:
                if prior['actor'] != actor or prior['payload'] != encoded:
                    raise ValueError('Guidance ID conflicts with an immutable draft')
                return dict(guidance_id=guidance_id, actor=actor, payload=payload)
            db.execute('INSERT INTO guidance VALUES(?,?,?,?)', (guidance_id, actor, encoded, time.time()))
            self._event(db, actor, 'guidance_recorded', dict(guidance_id=guidance_id, payload_digest=digest(payload), payload=payload))
            return dict(guidance_id=guidance_id, actor=actor, payload=payload)

    def _evaluation(self, row):
        return dict(request_id=row['request_id'], candidate_id=row['candidate_id'], profile=row['profile'],
                    attempt=row['attempt'], job_id=row['job_id'], **json.loads(row['state']))

    def record_decision(self, actor, token, decision_id, payload):
        identifier(decision_id, 'decision_id')
        encoded = canonical(payload)
        if not isinstance(payload, dict) or len(encoded) > 100000:
            raise ValueError('Decision payload must be an object of at most 100000 characters')
        with self._transaction() as db:
            self._auth(db, actor, token, ('coordinator',))
            prior = db.execute('SELECT * FROM decisions WHERE decision_id=?', (decision_id,)).fetchone()
            if prior:
                if prior['actor'] != actor or prior['payload'] != encoded:
                    raise ValueError('Decision ID conflicts with an immutable decision')
                return dict(decision_id=decision_id, actor=actor, payload=payload)
            db.execute('INSERT INTO decisions VALUES(?,?,?,?)', (decision_id, actor, encoded, time.time()))
            self._event(db, actor, 'decision_recorded', dict(decision_id=decision_id,
                        payload_digest=digest(payload), payload=payload))
            return dict(decision_id=decision_id, actor=actor, payload=payload)

    def reserve_evaluation(self, actor, token, candidate_id, profile, retry=False):
        if profile not in ('screen', 'full'):
            raise ValueError('Unknown evaluation profile')
        with self._transaction() as db:
            self._auth(db, actor, token, ('coordinator',))
            candidate = self._candidate(db, candidate_id)
            latest = db.execute('SELECT * FROM evaluations WHERE candidate_id=? AND profile=? ORDER BY attempt DESC LIMIT 1',
                                (candidate_id, profile)).fetchone()
            if latest:
                previous = self._evaluation(latest)
                if not retry or previous['status'] != 'infrastructure_error':
                    return previous
            if candidate['status'] not in ('proposed', 'screened', 'retryable'):
                raise RuntimeError('Candidate is not awaiting evaluation')
            if profile == 'full' and candidate['kind'] != 'seed':
                screened = db.execute("SELECT 1 FROM evidence WHERE candidate_id=? AND json_extract(payload,'$.category')='screen'", (candidate_id,)).fetchone()
                if not screened:
                    raise RuntimeError('Full evaluation requires successful screening')
            self._budget(db, 'evaluations', candidate['round_id'])
            attempt = latest['attempt'] + 1 if latest else 1
            request_id = uuid.uuid4().hex
            state = dict(status='reserved', evidence_id=None, imported=False)
            db.execute('INSERT INTO evaluations VALUES(?,?,?,?,NULL,?)',
                       (request_id, candidate_id, profile, attempt, canonical(state)))
            candidate['status'] = 'evaluating_' + profile
            self._save_candidate(db, candidate)
            self._event(db, actor, 'evaluation_reserved', dict(request_id=request_id, candidate_id=candidate_id,
                        profile=profile, attempt=attempt))
            return dict(request_id=request_id, candidate_id=candidate_id, profile=profile, attempt=attempt,
                        job_id=None, **state)

    def bind_evaluation(self, actor, token, request_id, job_id):
        identifier(job_id, 'job_id')
        with self._transaction() as db:
            self._auth(db, actor, token, ('coordinator',))
            row = db.execute('SELECT * FROM evaluations WHERE request_id=?', (request_id,)).fetchone()
            if row is None:
                raise ValueError('Unknown evaluation request')
            if row['job_id'] is not None:
                if row['job_id'] != job_id:
                    raise ValueError('Request is already bound to a different job')
                return self._evaluation(row)
            db.execute('UPDATE evaluations SET job_id=? WHERE request_id=?', (job_id, request_id))
            self._event(db, actor, 'evaluation_bound', dict(request_id=request_id, job_id=job_id))
            return self._evaluation(db.execute('SELECT * FROM evaluations WHERE request_id=?', (request_id,)).fetchone())

    def _valid_candidates(self, db, cohort=None):
        candidates = [self._candidate(db, row[0]) for row in db.execute('SELECT candidate_id FROM candidates')]
        return [c for c in candidates if c['valid'] and (cohort is None or c['cohort_digest'] == cohort)]

    def _progress(self, db, candidate, old_valid):
        policy = self._round(db, candidate['round_id'])['spec']['progress']
        axes = self._campaign(db)['spec']['objective']['pareto_axes']
        threshold = lambda key, parent: max(policy['absolute'], policy['relative'] * parent['metrics'][key], parent.get('metric_ranges', {}).get(key, 0))
        reference = [p for p in old_valid if p['cohort_digest'] == candidate['cohort_digest']]
        best_parent = min(reference, key=lambda p:p['metrics']['total']) if reference else None
        best = best_parent['metrics']['total'] if best_parent else None
        total = best is not None and best - candidate['metrics']['total'] > threshold('total', best_parent)
        parents = [p for p in reference if p['candidate_id'] in candidate['parents']]
        pareto = any(all(candidate['metrics'][k] - p['metrics'][k] <= threshold(k, p) for k in axes)
                     and any(p['metrics'][k] - candidate['metrics'][k] > threshold(k, p) for k in axes)
                     for p in parents)
        return dict(meaningful_total=total, meaningful_pareto=pareto, reference_best_total=best,
                    reference_parents=[p['candidate_id'] for p in parents], axes=axes, policy=policy)

    def observe(self, actor, token, candidate_id, evidence):
        evidence = json.loads(canonical(evidence))
        evidence_id = identifier(evidence['evidence_id'], 'evidence_id')
        job_id = identifier(evidence['job_id'], 'job_id')
        profile = evidence['profile']
        category = evidence['category']
        if profile not in ('screen', 'full') or category not in ('screen', 'valid', 'invalid_candidate', 'infrastructure_error'):
            raise ValueError('Unsupported evidence category/profile')
        if evidence.get('job_terminal') is False:
            raise ValueError('Only terminal job evidence can be observed')
        checked_hash(evidence['evidence_digest'])
        if evidence.get('schema_version') == 'feyer-evolution-evidence-v1':
            signed = {k: v for k, v in evidence.items() if k != 'evidence_digest'}
            if not hmac.compare_digest(evidence['evidence_digest'], digest(signed)):
                raise ValueError('Evidence digest does not match the adapter envelope')
        with self._transaction() as db:
            self._auth(db, actor, token, ('coordinator', 'evaluator'))
            candidate = self._candidate(db, candidate_id)
            if evidence.get('candidate_sha') != candidate['commit_sha']:
                raise ValueError('Evidence commit does not match immutable candidate')
            previous = db.execute('SELECT * FROM evidence WHERE evidence_id=? OR job_id=?', (evidence_id, job_id)).fetchone()
            if previous:
                if previous['candidate_id'] != candidate_id or previous['payload'] != canonical(evidence):
                    raise ValueError('Evidence/job ID conflicts with an existing observation')
                return candidate
            if candidate['status'] in ('duplicate', 'infrastructure_abandoned'):
                raise RuntimeError('Candidate cannot accept new observations')
            reservation = db.execute('SELECT * FROM evaluations WHERE job_id=?', (job_id,)).fetchone()
            imported = candidate['kind'] == 'seed' and profile == 'full'
            if reservation is None and not imported:
                raise ValueError('Bind the durable evaluation request before observing its result')
            if reservation and (reservation['candidate_id'] != candidate_id or reservation['profile'] != profile):
                raise ValueError('Evidence does not match the bound request')
            if category == 'valid':
                if profile != 'full' or evidence.get('eligible_full') is not True:
                    raise ValueError('Only eligible full evidence can validate a candidate')
                checked_hash(evidence['cohort_digest'])
                metrics = evidence['metrics']
                required_metrics = set(('total', *PHASES)) | set(self._campaign(db)['spec']['objective']['pareto_axes'])
                if any(k not in metrics for k in required_metrics) or any(isinstance(metrics[k], bool) or not isinstance(metrics[k], (float, int)) or not math.isfinite(metrics[k]) or metrics[k] < 0 for k in required_metrics) or metrics['total'] <= 0:
                    raise ValueError('Full evidence requires complete finite nonnegative phase timings')
                if candidate['cohort_digest'] and candidate['cohort_digest'] != evidence['cohort_digest']:
                    raise ValueError('Candidate confirmation runs have different cohorts')
                expected = self._campaign(db)['spec'].get('cohort_digest')
                if expected and evidence['cohort_digest'] != expected:
                    raise ValueError('Evidence cohort differs from frozen campaign reference')
            if category == 'screen' and (profile != 'screen' or evidence.get('screen_passed') is not True):
                raise ValueError('Screening evidence must explicitly pass screening')
            if reservation is None:
                attempt = (db.execute('SELECT MAX(attempt) FROM evaluations WHERE candidate_id=? AND profile=?', (candidate_id, profile)).fetchone()[0] or 0) + 1
                request_id = uuid.uuid4().hex
                db.execute('INSERT INTO evaluations VALUES(?,?,?,?,?,?)', (request_id, candidate_id, profile, attempt, job_id,
                           canonical(dict(status='reserved', evidence_id=None, imported=True))))
                reservation = db.execute('SELECT * FROM evaluations WHERE request_id=?', (request_id,)).fetchone()
            old_valid = self._valid_candidates(db)
            db.execute('INSERT INTO evidence VALUES(?,?,?,?,?,?)',
                       (evidence_id, job_id, candidate_id, canonical(evidence), digest(evidence), time.time()))
            evaluation_state = json.loads(reservation['state'])
            evaluation_state.update(status=category, evidence_id=evidence_id)
            db.execute('UPDATE evaluations SET state=? WHERE request_id=?', (canonical(evaluation_state), reservation['request_id']))
            candidate['evidence_ids'].append(evidence_id)
            lane = self._lane(db, candidate['round_id'], candidate['lane_id'])
            if category == 'infrastructure_error':
                candidate['status'] = 'retryable'
            elif category == 'screen':
                candidate['status'] = 'screened'
            else:
                candidate['status'] = 'valid' if category == 'valid' else 'invalid'
                candidate['valid'] = category == 'valid'
                if category == 'valid':
                    runs = [json.loads(row[0]) for row in db.execute("SELECT payload FROM evidence WHERE candidate_id=? AND json_extract(payload,'$.category')='valid'", (candidate_id,))]
                    invalid = db.execute("SELECT 1 FROM evidence WHERE candidate_id=? AND json_extract(payload,'$.category')='invalid_candidate'", (candidate_id,)).fetchone()
                    candidate['valid'] = invalid is None
                    candidate['status'] = 'valid' if candidate['valid'] else 'invalid'
                    common = set.intersection(*(set(r['metrics']) for r in runs))
                    numeric = {k for k in common if all(isinstance(r['metrics'][k], (int,float)) and not isinstance(r['metrics'][k],bool) and math.isfinite(r['metrics'][k]) for r in runs)}
                    candidate['metrics'] = {k: statistics.median(r['metrics'][k] for r in runs) for k in sorted(numeric)}
                    candidate['metric_ranges'] = {k: max(r['metrics'][k] for r in runs)-min(r['metrics'][k] for r in runs) for k in sorted(numeric)}
                    candidate['cohort_digest'] = evidence['cohort_digest']
                    candidate['full_run_count'] = len(runs)
                if not candidate['counted'] and candidate['kind'] != 'seed':
                    progress = self._progress(db, candidate, old_valid) if candidate['valid'] else dict(meaningful_total=False, meaningful_pareto=False)
                    candidate['progress'] = progress
                    candidate['improved'] = bool(progress['meaningful_total'] or progress['meaningful_pareto'])
                    candidate['counted'] = True
                    lane['strikes'] = 0 if candidate['improved'] else lane['strikes'] + 1
                if lane['inflight_candidate'] == candidate_id:
                    lane['inflight_candidate'] = None
                    stall_limit = self._round(db, candidate['round_id'])['spec']['lanes'][candidate['lane_id']].get('stall_limit', 3)
                    lane['status'] = 'stalled' if lane['strikes'] >= stall_limit else 'ready'
                if candidate['kind'] == 'seed' and candidate['valid'] and not lane['base_candidate']:
                    lane['base_candidate'] = candidate_id
                if candidate['kind'] == 'seed' and candidate['valid']:
                    for other in db.execute('SELECT state FROM lanes WHERE round_id=?', (candidate['round_id'],)).fetchall():
                        other_lane = json.loads(other['state'])
                        if other_lane['lane_id'] != lane['lane_id'] and other_lane['base_candidate'] is None and other_lane['status'] == 'ready':
                            other_lane['base_candidate'] = candidate_id
                            self._save_lane(db, other_lane)
            self._save_candidate(db, candidate)
            self._save_lane(db, lane)
            self._event(db, actor, 'evidence_observed', dict(candidate_id=candidate_id, evidence_id=evidence_id,
                        job_id=job_id, evidence_digest=digest(evidence), category=category,
                        status=candidate['status'], strikes=lane['strikes'], progress=candidate.get('progress')))
            return self._candidate(db, candidate_id)

    def lane_exhausted(self, actor, token, round_id, lane_id, reason='finite registered choices exhausted'):
        with self._transaction() as db:
            self._auth(db, actor, token, ('coordinator',))
            lane = self._lane(db, round_id, lane_id)
            if lane['inflight_candidate']:
                raise RuntimeError('Drain the in-flight candidate before declaring exhaustion')
            if lane['status'] != 'exhausted':
                lane['status'] = 'exhausted'
                self._save_lane(db, lane)
                self._event(db, actor, 'lane_exhausted', dict(round_id=round_id, lane_id=lane_id, reason=reason))
            return lane

    def abandon_infrastructure(self, actor, token, candidate_id, reason):
        with self._transaction() as db:
            self._auth(db, actor, token, ('coordinator',))
            candidate = self._candidate(db, candidate_id)
            if candidate['status'] != 'retryable':
                raise ValueError('Only infrastructure failures can be abandoned without a strike')
            candidate['status'] = 'infrastructure_abandoned'
            self._save_candidate(db, candidate)
            lane = self._lane(db, candidate['round_id'], candidate['lane_id'])
            lane.update(status='ready', inflight_candidate=None)
            self._save_lane(db, lane)
            self._event(db, actor, 'infrastructure_abandoned', dict(candidate_id=candidate_id, reason=reason))

    def _events(self, db):
        return [dict(seq=r['seq'], type=r['type'], actor=r['actor'], payload=json.loads(r['payload']),
                     at=r['at'], previous_hash=r['previous_hash'], event_hash=r['event_hash'])
                for r in db.execute('SELECT * FROM events ORDER BY seq')]

    def events(self):
        with self._connect() as db:
            return self._events(db)

    def verify_log(self):
        previous = '0' * 64
        for expected_seq, event in enumerate(self.events(), 1):
            signed = {k: v for k, v in event.items() if k != 'event_hash'}
            if event['seq'] != expected_seq or event['previous_hash'] != previous or digest(signed) != event['event_hash']:
                raise ValueError('Event chain verification failed')
            previous = event['event_hash']
        return True

    def snapshot(self):
        with self._connect() as db:
            db.execute('BEGIN')
            campaign = self._campaign(db)
            claims = [dict(actor=r['actor'], role=r['role'], version=r['version'], granted_by=r['granted_by'], at=r['at']) for r in db.execute('SELECT * FROM claims ORDER BY actor,version')]
            for claim in claims:
                claim['active'] = claim['version'] == max(c['version'] for c in claims if c['actor'] == claim['actor'])
            rounds = [self._round(db, r[0]) for r in db.execute('SELECT round_id FROM rounds ORDER BY version')]
            lanes = [json.loads(r[0]) for r in db.execute('SELECT state FROM lanes ORDER BY round_id,lane_id')]
            candidates = [self._candidate(db, r[0]) for r in db.execute('SELECT candidate_id FROM candidates ORDER BY created_at,candidate_id')]
            valid = [c for c in candidates if c['valid']]
            axes = campaign['spec']['objective']['pareto_axes']
            for candidate in candidates:
                rivals = [r for r in valid if r['candidate_id'] != candidate['candidate_id'] and r['cohort_digest'] == candidate['cohort_digest']]
                candidate['exact_pareto'] = candidate['valid'] and not any(all(r['metrics'][k] <= candidate['metrics'][k] for k in axes) and any(r['metrics'][k] < candidate['metrics'][k] for k in axes) for r in rivals)
            return dict(campaign=campaign, claims=claims, rounds=rounds, lanes=lanes, candidates=candidates,
                        evaluations=[self._evaluation(r) for r in db.execute('SELECT * FROM evaluations ORDER BY rowid')],
                        evidence=[json.loads(r[0]) for r in db.execute('SELECT payload FROM evidence ORDER BY at,evidence_id')],
                        model_calls=[dict(call_id=r['call_id'], actor=r['actor'], metadata=json.loads(r['metadata']), at=r['at']) for r in db.execute('SELECT * FROM model_calls ORDER BY at')],
                        model_outcomes=[dict(call_id=r['call_id'], actor=r['actor'], metadata=json.loads(r['metadata']), at=r['at']) for r in db.execute('SELECT * FROM model_outcomes ORDER BY at')],
                        guidance=[dict(guidance_id=r['guidance_id'], actor=r['actor'], payload=json.loads(r['payload']), at=r['at']) for r in db.execute('SELECT * FROM guidance ORDER BY at')],
                        decisions=[dict(decision_id=r['decision_id'], actor=r['actor'], payload=json.loads(r['payload']), at=r['at']) for r in db.execute('SELECT * FROM decisions ORDER BY at')],
                        events=self._events(db), usage=self._usage(db))

    def context(self):
        data = self.snapshot()
        return dict(campaign=data['campaign'], rounds=data['rounds'], lanes=data['lanes'],
                    candidates=data['candidates'], usage=data['usage'], decisions=data['decisions'], guidance=data['guidance'],
                    event_head=data['events'][-1]['event_hash'] if data['events'] else None,
                    policy='Full eligibility and same cohort required. Exact Pareto membership is separate from noise-qualified progress. The frozen lane stall_limit defaults to three terminal non-improvements; infrastructure and retries do not count.')

    def plan(self, actor, token):
        with self._connect() as db:
            self._auth(db, actor, token, ('coordinator',))
        data = self.snapshot()
        active = [r for r in data['rounds'] if not r['closed']]
        if not active:
            return dict(action='meta_guidance', reason='Create a frozen round specification')
        round_data = active[-1]
        lanes = [l for l in data['lanes'] if l['round_id'] == round_data['round_id']]
        inflight = [l['inflight_candidate'] for l in lanes if l['inflight_candidate']]
        pending = [e for e in data['evaluations'] if e['candidate_id'] in inflight and e['status'] == 'reserved']
        if pending:
            return dict(action='wait', round_id=round_data['round_id'], inflight=inflight, evaluations=pending)
        budget = data['campaign']['spec']['budget']
        kinds = ('proposals', 'evaluations', 'model_calls') if budget['max_model_calls'] else ('proposals', 'evaluations')
        if time.time() >= budget['deadline_unix'] or any(data['usage'][k] >= budget['max_' + k] for k in kinds):
            return dict(action='budget_exhausted', reason='Frozen campaign deadline or resource budget reached')
        if inflight:
            return dict(action='wait', round_id=round_data['round_id'], inflight=inflight)
        round_candidates = [c for c in data['candidates'] if c['round_id'] == round_data['round_id']]
        round_requests = [e for e in data['evaluations'] if e['candidate_id'] in {c['candidate_id'] for c in round_candidates} and not e['imported']]
        if len(round_candidates) >= round_data['spec']['budget']['max_proposals'] or len(round_requests) >= round_data['spec']['budget']['max_evaluations']:
            return dict(action='budget_exhausted', reason='Frozen round resource budget reached')
        cohort = data['campaign']['spec'].get('cohort_digest')
        valid = [c for c in data['candidates'] if c['valid'] and (cohort is None or c['cohort_digest'] == cohort)]
        for lane in lanes:
            if lane['status'] == 'ready' and lane['proposals'] < round_data['spec']['lanes'][lane['lane_id']]['max_proposals']:
                dimensions = round_data['spec']['lanes'][lane['lane_id']]['dimensions']
                base = next((c for c in valid if c['candidate_id'] == lane.get('base_candidate')), None)
                parents = [c['candidate_id'] for c in valid if base is None or all(canonical(c['parameters'].get(k)) == canonical(base['parameters'].get(k)) for k in base['parameters'] if k not in dimensions)]
                return dict(action='mutate', round_id=round_data['round_id'], lane_id=lane['lane_id'], owner=lane['owner'],
                            dimensions=round_data['spec']['lanes'][lane['lane_id']]['dimensions'],
                            recipes=round_data['spec'].get('recipes', {}), parent_candidates=parents,
                            base_candidate=lane.get('base_candidate'),
                            attempted_parameters=[c['parameters'] for c in data['candidates'] if c['round_id'] == lane['round_id'] and c['lane_id'] == lane['lane_id']])
        parents = [c['candidate_id'] for c in sorted(valid, key=lambda c: (not c['exact_pareto'], c['metrics']['total']))]
        if len(parents) < 2:
            return dict(action='meta_guidance', round_id=round_data['round_id'], parent_candidates=parents,
                        reason='Fewer than two distinct validated frontier parents; do not invent a combination')
        return dict(action='combine', round_id=round_data['round_id'], parent_candidates=parents,
                    reason='Lanes stalled or exhausted; coordinator must freeze a new combination round')
