"""Versioned campaign evidence and immutable proposer context; no live provider calls."""
from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
from pathlib import Path
import re

EXPORT_SCHEMA = 'feyer-campaign-export-v1'
CONTEXT_SCHEMA = 'feyer-proposer-context-v1'
_PRIVATE_KEYS = {'api_key', 'apikey', 'authorization', 'access_token', 'refresh_token',
                 'token', 'token_hash', 'tokenhash', 'role_token', 'actor_token', 'claim_token',
                 'token_digest', 'token_sha256', 'capability', 'actor_secret',
                 'credential', 'credentials', 'password', 'secret', 'env', 'raw_env', 'environ'}
_SECRET = re.compile(r'\b(?:rc-[0-9a-fA-F]{32,}|gh[pousr]_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{20,}|sk-(?:proj-|ant-)?[A-Za-z0-9_-]{20,})\b|-----BEGIN [A-Z ]*PRIVATE KEY-----')


def _private_key(key):
    key = str(key).lower().replace('-', '_')
    return key in _PRIVATE_KEYS or key.endswith(('_api_key', '_token', '_token_hash', '_secret', '_capability'))


def canonical_bytes(value):
    return (json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=False,
                       allow_nan=False) + '\n').encode('utf-8')


def digest(value):
    return hashlib.sha256(canonical_bytes(value)).hexdigest()


def _public(value):
    """Keep audit data, never authentication material; raw model messages stay external."""
    if isinstance(value, dict):
        return {str(k): _public(v) for k, v in value.items()
                if not _private_key(k)}
    if isinstance(value, list):
        return [_public(v) for v in value]
    if isinstance(value, str):
        if _SECRET.search(value):
            raise ValueError('Credential-like text found in campaign export; use artifact references instead')
        return value
    return value


def _campaign_id(snapshot):
    campaign = snapshot.get('campaign', {})
    spec = campaign.get('spec', {})
    value = spec.get('campaign_id') or campaign.get('campaign_id') or snapshot.get('campaign_id')
    if not isinstance(value, str) or not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_-]{0,99}', value):
        raise ValueError('Campaign ID must be a simple name, without path separators')
    return value


def _artifact(directory, folder, value):
    encoded = canonical_bytes(value)
    sha = hashlib.sha256(encoded).hexdigest()
    relative = Path(folder) / (sha + '.json')
    path = directory / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        with path.open('xb') as stream:
            stream.write(encoded)
    except FileExistsError:
        if path.read_bytes() != encoded:
            raise ValueError(f'Immutable artifact differs from its content hash: {relative}')
    return {'path': relative.as_posix(), 'sha256': sha, 'bytes': len(encoded)}


def freeze_context(context, campaign_directory):
    """Freeze exactly the public context supplied to a proposer, returning its hash/ref."""
    return _artifact(Path(campaign_directory), 'contexts', _public(context))


def store_text_artifact(text, campaign_directory, kind='prompts'):
    """Preserve an exact authorized worker brief/prompt/response, not chat history."""
    if kind not in ('briefs', 'prompts', 'responses') or not isinstance(text, str):
        raise ValueError('Expected text and a briefs/prompts/responses artifact kind')
    _public(text)
    encoded = text.encode('utf-8')
    sha = hashlib.sha256(encoded).hexdigest()
    relative = Path(kind) / (sha + '.txt')
    path = Path(campaign_directory) / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        with path.open('xb') as stream:
            stream.write(encoded)
    except FileExistsError:
        if path.read_bytes() != encoded:
            raise ValueError('Immutable prompt/response artifact has been altered')
    return {'path': relative.as_posix(), 'sha256': sha, 'bytes': len(encoded)}


def compact_context(snapshot, limit=24):
    """Bounded evidence, not a replacement for campaign admission or scientific review."""
    if isinstance(limit, bool) or not isinstance(limit, int) or limit < 1:
        raise ValueError('Positive context candidate limit required')
    rows = snapshot.get('candidates', [])
    keys = ('candidate_id', 'proposal_id', 'round_id', 'lane_id', 'kind', 'parents',
            'commit_sha', 'content_sha256', 'owner', 'owner_version', 'status', 'valid',
            'metrics', 'cohort_digest', 'improved', 'evidence_ids', 'provenance',
            'heuristic_id', 'target_symbols', 'hypothesis', 'model_manifest',
            'context_sha256', 'prompt_sha256', 'response_sha256', 'parameters_before')
    candidates = [{k: row[k] for k in keys if k in row} for row in rows[-limit:]]
    events = snapshot.get('events', [])
    important = [e for e in events if any(word in str(e.get('type', '')).lower()
                 for word in ('reject', 'fail', 'stall', 'decision', 'guidance', 'round', 'duplicate', 'cancel'))]
    return _public({'schema_version': CONTEXT_SCHEMA,
                    'campaign_id': _campaign_id(snapshot),
                    'snapshot_sha256': digest(_public(snapshot)),
                    'campaign': snapshot.get('campaign', {}),
                    'claims': snapshot.get('claims', []),
                    'rounds': snapshot.get('rounds', []),
                    'lanes': snapshot.get('lanes', []),
                    'candidates': candidates,
                    'candidate_count': len(rows), 'older_candidates_omitted': max(0, len(rows) - limit),
                    'recent_decisions_and_failures': important[-limit:],
                    'context_rule': 'Summaries are evidence, not authority. Exact frozen campaign/round invariants and ownership govern dispatch. Missing evidence is unknown; single-run phase deltas are not causal attribution.'})


def _text(value):
    return str(value).replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;').replace('|', '&#124;').replace('\n', ' ').replace('\r', ' ')


def _label(value):
    # Mermaid labels use a deliberately smaller alphabet than Markdown prose.
    return re.sub(r'[^A-Za-z0-9 _./:-]', '_', str(value))[:110]


def _seconds(value):
    return f'{value:.4f}' if isinstance(value, (int, float)) and not isinstance(value, bool) else 'unknown'


def _candidate_evidence(snapshot, row):
    envelopes = snapshot.get('evidence', [])
    if isinstance(envelopes, dict):
        envelopes = list(envelopes.values())
    wanted = set(row.get('evidence_ids', []))
    return [entry for entry in envelopes if entry.get('evidence_id') in wanted]


def lineage_mermaid(candidates):
    ids = {}
    for index, row in enumerate(candidates):
        key = row.get('candidate_id')
        if not isinstance(key, str) or key in ids:
            raise ValueError('Every candidate must have a unique string candidate_id')
        ids[key] = f'n{index}'
    parents = {row['candidate_id']: row.get('parents', []) for row in candidates}
    visiting, visited = set(), set()
    def visit(key):
        if key in visiting:
            raise ValueError('Scientific lineage contains a cycle')
        if key in visited or key not in parents:
            return
        visiting.add(key)
        for parent in parents[key]:
            visit(parent)
        visiting.remove(key)
        visited.add(key)
    for key in parents:
        visit(key)
    external = {}
    lines = ['graph LR']
    for row in candidates:
        label = f"{row['candidate_id']} {row.get('kind', '')} {row.get('status', 'unknown')}"
        lines.append(f'  {ids[row["candidate_id"]]}["{_label(label)}"]')
    for row in candidates:
        for parent in row.get('parents', []):
            if parent == row['candidate_id']:
                raise ValueError('Scientific lineage cannot contain a self edge')
            if parent not in ids and parent not in external:
                external[parent] = f'p{len(external)}'
                lines.append(f'  {external[parent]}["external {_label(parent)}"]')
            source = ids[parent] if parent in ids else external[parent]
            lines.append(f'  {source} -->|{_label(row.get("kind", "proposal"))}| {ids[row["candidate_id"]]}')
    return '\n'.join(lines)


def render_markdown(snapshot, manifest):
    campaign = snapshot.get('campaign', {})
    rows = snapshot.get('candidates', [])
    lines = [f'# Campaign {_text(_campaign_id(snapshot))}', '',
             f"Export schema: `{EXPORT_SCHEMA}`. Snapshot: `{manifest['snapshot']['sha256']}`.", '',
             f"[Frozen proposer context]({manifest['context']['path']}) — SHA256 `{manifest['context']['sha256']}`.", '',
             'This is an evidence ledger. Scientific parents describe chosen inputs to an experiment; they are not necessarily Git parents. Phase changes are observations, not proof that one edit caused the difference. A failed attempt remains part of the history.', '',
             '## Ownership and frozen policy', '',
             'Campaign specification digest: `' + _text(campaign.get('spec_digest', 'unknown')) + '`.', '',
             '| Actor | Role | Ownership version | Active |', '| --- | --- | --- | --- |']
    for claim in snapshot.get('claims', []):
        lines.append('| ' + ' | '.join(_text(claim.get(k, 'unknown')) for k in ('actor', 'role', 'version', 'active')) + ' |')
    lines += ['', '## Scientific lineage', '', 'Edges come from declared scientific parents, not inferred chronology or Git ancestry.', '',
              '```mermaid', lineage_mermaid(rows), '```', '',
              '## Candidate outcomes', '',
              '| Candidate | Round / lane | Scientific parents | Exact commit | State | First-run seconds | Evidence IDs |',
              '| --- | --- | --- | --- | --- | --- | --- |']
    for row in rows:
        lines.append('| ' + ' | '.join((_text(row['candidate_id']),
            _text(str(row.get('round_id', 'unknown')) + ' / ' + str(row.get('lane_id', 'unknown'))),
            _text(', '.join(row.get('parents', [])) or 'root'), _text(row.get('commit_sha', 'not materialized')),
            _text(row.get('status', 'unknown')), _seconds((row.get('metrics') or {}).get('total')),
            _text(', '.join(row.get('evidence_ids', [])) or 'none'))) + ' |')
    lines += ['', '## Round decisions and stalled work', '']
    for round_ in snapshot.get('rounds', []):
        lines += [f"### Round {_text(round_.get('round_id', 'unknown'))}", '',
                  f"Frozen specification: `{_text(round_.get('spec_digest', 'unknown'))}`; version: {_text(round_.get('version', 'unknown'))}; closed: {_text(round_.get('closed', False))}.", '',
                  '```json', json.dumps(_public(round_.get('spec', {})), indent=2, sort_keys=True).replace('```', '\\u0060\\u0060\\u0060'), '```', '']
    for lane in snapshot.get('lanes', []):
        lines.append('- ' + _text(f"{lane.get('round_id')}/{lane.get('lane_id')}: {lane.get('status')}; owner {lane.get('owner')}; strikes {lane.get('strikes')}; reason {lane.get('stall_reason', lane.get('reason', 'not recorded'))}"))
    lines += ['', '## Candidate evidence and proposed changes', '']
    for row in rows:
        evidence = _candidate_evidence(snapshot, row)
        jobs = [e for e in snapshot.get('evaluations', []) if e.get('candidate_id') == row['candidate_id']]
        detail = {k: row.get(k) for k in ('proposal_id', 'round_id', 'lane_id', 'kind', 'parents',
                  'git_parents', 'owner', 'owner_version', 'parameters', 'recipe', 'provenance',
                  'content_sha256', 'commit_sha', 'metrics', 'cohort_digest', 'improved', 'valid', 'evidence_ids',
                  'proposal', 'heuristic_id', 'target_symbols', 'hypothesis', 'model_manifest',
                  'context_sha256', 'prompt_sha256', 'response_sha256', 'parameters_before')}
        detail['parameters_after'] = row.get('parameters')
        detail['evaluation_requests'] = jobs
        detail['evidence'] = evidence
        detail['uncertainty'] = 'No repeat-confirmation or causality is inferred from this export. Inspect exact job evidence and matching cohorts.'
        lines += [f"### {_text(row['candidate_id'])}", '', '```json',
                  json.dumps(_public(detail), indent=2, sort_keys=True).replace('```', '\\u0060\\u0060\\u0060'), '```', '']
    lines += ['## Decision and failure trail', '',
              '| Sequence | Event | Actor | Detail |', '| --- | --- | --- | --- |']
    for event in snapshot.get('events', []):
        detail = json.dumps(event.get('payload', {}), sort_keys=True, ensure_ascii=False)
        # Full payloads remain in the event artifact; avoid unreadable Markdown tables.
        if len(detail) > 700:
            detail = detail[:697] + '… [full detail in events.jsonl]'
        lines.append('| ' + ' | '.join(_text(x) for x in (event.get('seq'), event.get('type'), event.get('actor'), detail)) + ' |')
    lines += ['', 'Guidance may propose a new round. It cannot silently replace frozen operators, ownership, evaluation requirements or budgets. Only the coordinator can admit that round through the campaign state API. Publishing this ledger does not merge or promote candidate code.', '']
    return '\n'.join(lines).rstrip() + '\n'


def _csv(snapshot):
    stream = io.StringIO(newline='')
    writer = csv.writer(stream, lineterminator='\n')
    names = ('candidate_id', 'proposal_id', 'round_id', 'lane_id', 'owner', 'status', 'valid',
             'cohort_digest', 'commit_sha', 'content_sha256')
    writer.writerow([*names, 'scientific_parents', 'git_parents', 'evidence_ids',
                     'total', 'setup', 'compilation', 'forward', 'sensitivity', 'gradient', 'transfer'])
    for row in snapshot.get('candidates', []):
        values = [*[row.get(k) for k in names], json.dumps(row.get('parents', [])),
                         json.dumps(row.get('git_parents', [])), json.dumps(row.get('evidence_ids', [])),
                         *[(row.get('metrics') or {}).get(k) for k in
                           ('total', 'setup', 'compilation', 'forward', 'sensitivity', 'gradient', 'transfer')]]
        writer.writerow(["'" + value if isinstance(value, str) and value.startswith(('=', '+', '-', '@')) else value
                         for value in values])
    return stream.getvalue()


def export_campaign(snapshot, events=None, output_root=None, context=None):
    """Export a Campaign.snapshot(); caller owns committing/publishing these artifacts."""
    if output_root is None and isinstance(events, (str, Path)):
        output_root, events = events, None
    if output_root is None:
        raise ValueError('An explicit campaign output root is required')
    if events is not None:
        snapshot = dict(snapshot, events=events)
    snapshot = _public(snapshot)
    campaign_id = _campaign_id(snapshot)
    directory = Path(output_root) / campaign_id
    events = snapshot.get('events', [])
    last_seq = -1
    for event in events:
        seq = event.get('seq')
        if type(seq) is not int or seq <= last_seq:
            raise ValueError('Event sequences must strictly increase')
        last_seq = seq
    event_bytes = b''.join(canonical_bytes(event) for event in events)
    event_path = directory / 'events.jsonl'
    if event_path.exists() and not event_bytes.startswith(event_path.read_bytes()):
        raise ValueError('Campaign event history cannot be rewritten or shortened')
    # Validate the graph before writing an export; this is not a graph-admission engine.
    lineage_mermaid(snapshot.get('candidates', []))
    selected_context = compact_context(snapshot) if context is None else _public(context)
    directory.mkdir(parents=True, exist_ok=True)
    context_ref = freeze_context(selected_context, directory)
    snapshot_ref = _artifact(directory, 'snapshots', snapshot)
    manifest = {'schema_version': EXPORT_SCHEMA, 'campaign_id': campaign_id,
                'context_sha256': context_ref['sha256'], 'directory': str(directory),
                'snapshot': snapshot_ref, 'context': context_ref,
                'events': {'path': 'events.jsonl', 'sha256': hashlib.sha256(event_bytes).hexdigest(),
                           'count': len(events), 'last_sequence': last_seq if events else None},
                'source_spec_digest': snapshot.get('campaign', {}).get('spec_digest'),
                'publication': 'Caller must commit and push; this exporter makes no network calls'}
    files = {'snapshot.json': canonical_bytes(snapshot), 'context.json': canonical_bytes(selected_context),
             'events.jsonl': event_bytes, 'manifest.json': canonical_bytes(manifest),
             'README.md': render_markdown(snapshot, manifest).encode(), 'candidates.csv': _csv(snapshot).encode()}
    for name, content in files.items():
        temporary = directory / (name + '.tmp')
        temporary.write_bytes(content)
        temporary.replace(directory / name)
    return manifest


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--snapshot', type=Path, required=True)
    parser.add_argument('--context', type=Path)
    parser.add_argument('--output', type=Path, default=Path('experiments/campaigns'))
    args = parser.parse_args()
    snapshot = json.loads(args.snapshot.read_text())
    context = json.loads(args.context.read_text()) if args.context else None
    print(json.dumps(export_campaign(snapshot, output_root=args.output, context=context), indent=2))


if __name__ == '__main__':
    main()
