import copy
import hashlib
import json
from pathlib import Path
import tempfile
import unittest

from lab.evolution_report import (canonical_bytes, compact_context, export_campaign,
                                  freeze_context, lineage_mermaid, store_text_artifact)


def snapshot():
    return {'campaign': {'spec': {'campaign_id': 'pilot', 'budget': {'evaluations': 8}},
                         'spec_digest': 'a' * 64},
            'claims': [{'actor': 'qwen-1', 'role': 'proposer', 'version': 1, 'active': True,
                        'token_hash': 'must-not-export'}],
            'rounds': [{'round_id': 'r1', 'spec': {'operators': ['map-v1']}, 'spec_digest': 'b' * 64}],
            'lanes': [{'round_id': 'r1', 'lane_id': 'compile', 'owner': 'qwen-1',
                       'status': 'stalled', 'strikes': 3, 'stall_reason': 'Three numerical failures'}],
            'candidates': [
                {'candidate_id': 'seed', 'kind': 'seed', 'parents': [], 'commit_sha': '1' * 40,
                 'status': 'validated', 'valid': True, 'metrics': {'total': 35.7}},
                {'candidate_id': 'trial', 'kind': 'mutation', 'parents': ['seed'],
                 'git_parents': ['9' * 40], 'commit_sha': '2' * 40, 'proposal_id': 'p1',
                 'round_id': 'r1', 'lane_id': 'compile', 'owner': 'qwen-1', 'status': 'invalid',
                 'valid': False, 'metrics': {'total': 30}, 'parameters_before': {'batch': 1},
                 'parameters': {'batch': 2}, 'evidence_ids': ['j1:artifact'],
                 'model_manifest': {'provider': 'AMD', 'model': 'Qwen3.8-27B'},
                 'provenance': {'prompt_sha256': 'c' * 64, 'response_sha256': 'd' * 64}}],
            'evaluations': [{'candidate_id': 'trial', 'request_id': 'req-1', 'job_id': 'j1',
                             'profile': 'full', 'status': 'completed'}],
            'evidence': [{'evidence_id': 'j1:artifact', 'candidate_sha': '2' * 40,
                          'category': 'invalid_candidate', 'eligible_full': False,
                          'checks': {'official': 'passed', 'strict': 'failed'}}],
            'events': [{'seq': 1, 'type': 'proposal', 'actor': 'qwen-1', 'payload': {'candidate_id': 'trial'}},
                       {'seq': 2, 'type': 'numerical_failure', 'actor': 'worker', 'payload': {'job_id': 'j1'}}]}


class EvolutionReportTests(unittest.TestCase):
    def test_export_preserves_failed_path_and_exact_attribution(self):
        with tempfile.TemporaryDirectory() as directory:
            manifest = export_campaign(snapshot(), snapshot()['events'], directory)
            root = Path(manifest['directory'])
            saved = json.loads((root / 'snapshot.json').read_text())
            trial = saved['candidates'][1]
            self.assertFalse(trial['valid'])
            self.assertEqual(trial['parents'], ['seed'])
            self.assertEqual(trial['git_parents'], ['9' * 40])
            self.assertEqual(saved['evaluations'][0]['job_id'], 'j1')
            markdown = (root / 'README.md').read_text()
            self.assertIn('n0 -->|mutation| n1', markdown)
            self.assertIn('Three numerical failures', markdown)
            self.assertIn('parameters_before', markdown)
            self.assertIn('Qwen3.8-27B', markdown)
            self.assertNotIn('must-not-export', '\n'.join(p.read_text() for p in root.rglob('*.json')))

    def test_context_hash_is_exact_stable_and_order_independent(self):
        with tempfile.TemporaryDirectory() as directory:
            first = freeze_context({'b': 2, 'a': ['trial']}, directory)
            second = freeze_context({'a': ['trial'], 'b': 2}, directory)
            self.assertEqual(first, second)
            encoded = (Path(directory) / first['path']).read_bytes()
            self.assertEqual(first['sha256'], hashlib.sha256(encoded).hexdigest())
            self.assertEqual(encoded, canonical_bytes({'b': 2, 'a': ['trial']}))

    def test_immutable_context_corruption_is_detected(self):
        with tempfile.TemporaryDirectory() as directory:
            ref = freeze_context({'round': 1}, directory)
            (Path(directory) / ref['path']).write_text('altered')
            with self.assertRaisesRegex(ValueError, 'Immutable'):
                freeze_context({'round': 1}, directory)

    def test_event_history_can_append_but_cannot_rewrite_or_shorten(self):
        with tempfile.TemporaryDirectory() as directory:
            original = snapshot()
            export_campaign(original, directory)
            extended = copy.deepcopy(original)
            extended['events'].append({'seq': 3, 'type': 'guidance', 'actor': 'guide', 'payload': {'next': 'repair'}})
            export_campaign(extended, directory)
            with self.assertRaisesRegex(ValueError, 'rewritten or shortened'):
                export_campaign(original, directory)
            extended['events'][0]['payload']['candidate_id'] = 'rewritten'
            with self.assertRaisesRegex(ValueError, 'rewritten or shortened'):
                export_campaign(extended, directory)

    def test_mermaid_has_unique_ids_and_cannot_inject_markup(self):
        graph = lineage_mermaid([{'candidate_id': 'same"[<script>]', 'parents': [], 'kind': 'seed'},
                                 {'candidate_id': 'same_[<script>]', 'parents': ['same"[<script>]'], 'kind': 'combine'}])
        self.assertIn('n0 -->|combine| n1', graph)
        self.assertNotIn('<script>', graph)
        with self.assertRaisesRegex(ValueError, 'cycle'):
            lineage_mermaid([{'candidate_id': 'a', 'parents': ['b']}, {'candidate_id': 'b', 'parents': ['a']}])

    def test_campaign_path_traversal_and_credentials_are_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            bad = snapshot();bad['campaign']['spec']['campaign_id'] = '../outside'
            with self.assertRaises(ValueError):export_campaign(bad, directory)
            with self.assertRaisesRegex(ValueError, 'Credential'):
                store_text_artifact('Bearer rc-' + 'a' * 40, directory)

    def test_text_artifact_preserves_exact_prompt_bytes(self):
        with tempfile.TemporaryDirectory() as directory:
            text = 'Worker instructions\n\nKeep all 193 variables.\n'
            ref = store_text_artifact(text, directory, 'briefs')
            self.assertEqual((Path(directory) / ref['path']).read_bytes(), text.encode())
            self.assertEqual(ref['sha256'], hashlib.sha256(text.encode()).hexdigest())

    def test_compact_context_keeps_failure_and_model_evidence(self):
        context = compact_context(snapshot(), limit=1)
        self.assertEqual(context['older_candidates_omitted'], 1)
        self.assertEqual(context['candidates'][0]['model_manifest']['model'], 'Qwen3.8-27B')
        self.assertEqual(context['recent_decisions_and_failures'][0]['type'], 'numerical_failure')
        self.assertNotIn('token_hash', context['claims'][0])

    def test_private_fields_do_not_remove_usage_counts(self):
        state = snapshot()
        state['campaign']['spec']['diagnostic'] = {'GH_TOKEN': 'private-value',
            'role_token': 'private-role-value', 'actor_secret': 'secret-value',
            'raw_env': {'arbitrary': 'private-env'}, 'usage': {'input_tokens': 12}}
        context = compact_context(state)
        value = context['campaign']['spec']['diagnostic']
        self.assertEqual(value, {'usage': {'input_tokens': 12}})

    def test_explicit_proposer_context_is_not_replaced_by_summary(self):
        with tempfile.TemporaryDirectory() as directory:
            context = {'campaign_id': 'pilot', 'chosen_parent': 'seed', 'menu': ['map-v1']}
            manifest = export_campaign(snapshot(), directory, context=context)
            frozen = Path(manifest['directory']) / manifest['context']['path']
            self.assertEqual(json.loads(frozen.read_text()), context)

    def test_evidence_is_not_inherited_merely_from_matching_commit(self):
        state = snapshot()
        state['evidence'].append({'evidence_id': 'unassigned-job', 'candidate_sha': '2' * 40,
                                  'secret_attribution_marker': 'not assigned to this proposal'})
        with tempfile.TemporaryDirectory() as directory:
            manifest = export_campaign(state, directory)
            markdown = (Path(manifest['directory']) / 'README.md').read_text()
            self.assertNotIn('not assigned to this proposal', markdown)
            self.assertIn('j1:artifact', markdown)


if __name__ == '__main__':
    unittest.main()
