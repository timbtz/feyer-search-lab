import copy
import unittest

from lab.research_lineage import build_lineage, digest, from_feedback, validate_record
from lab.team_search import apply, initial_state

A, B, C = 'a' * 40, 'b' * 40, 'c' * 40


def record():
    return dict(schema='feyer-research-record-v1', record_id='combine-one', kind='combine',
                executor={'kind':'manual', 'id':'reviewed-layout'}, status='evaluated',
                candidate_sha=C, parents=[A, B], target_phases=['compilation', 'forward'],
                hypothesis='Reuse factorizations and separate coefficient layout',
                change_summary='Apply the reviewed layout transformation',
                source_ref='https://example.org/commit/receipt.json', source_digest='d' * 64,
                evaluations=[dict(job_id='job-c', candidate_sha=C, profile='full')],
                stopping_reason=None)


class ResearchLineageTests(unittest.TestCase):
    def test_queue_terminal_outcomes_do_not_remain_evaluating(self):
        from lab.queue import TERMINAL_STATUSES
        feedback = dict(candidate_sha=C, agent_response={'summary':'Change', 'hypothesis':'Hypothesis'})
        for status in TERMINAL_STATUSES | {'queued', 'running'}:
            feedback['full'] = dict(id='job-c', sha=C, profile='full', status=status)
            converted = from_feedback(feedback, 'session', 'receipt.json')
            self.assertEqual(converted['status'], 'completed' if status in TERMINAL_STATUSES else 'evaluating')
            self.assertIsNone(converted['stopping_reason'])

    def test_feedback_retains_exact_identity_without_guessing_phase_or_stop(self):
        feedback = dict(candidate_sha=C, provenance={'parent_candidates':[A]},
            agent_response={'summary':'Change', 'hypothesis':'Compile parser then combine B', 'stop':True},
            full={'id':'job-c', 'sha':C, 'profile':'full', 'status':'failed'})
        r = from_feedback(feedback, 'agent-session', 'committed-feedback.json')
        self.assertEqual(r['parents'], [A])
        self.assertEqual(r['target_phases'], [])
        self.assertIsNone(r['stopping_reason'])
        self.assertIsNone(r['next_input'])
        self.assertEqual(r['feedback_ref']['artifact_digest'], digest(feedback))
        self.assertEqual(r['status'], 'completed')
        feedback['provenance'] = {'parent_candidates':[A, B], 'combined_candidates':[A, B]}
        self.assertEqual(from_feedback(feedback, 'agent-session', 'receipt.json')['kind'], 'combine')
        feedback['provenance']['combined_candidates'] = [A, 'd' * 40]
        with self.assertRaises(ValueError):
            from_feedback(feedback, 'agent-session', 'receipt.json')
        feedback['provenance'] = {'parent_candidates':[A]}
        feedback['full']['sha'] = B
        with self.assertRaises(ValueError):
            from_feedback(feedback, 'agent-session', 'committed-feedback.json')

    def test_menu_exhaustion_is_finite_and_source_backed(self):
        r = {**record(), 'status':'menu_exhausted', 'stopping_reason':'All four legal options tested'}
        with self.assertRaises(ValueError):
            validate_record(r)
        r['menu'] = dict(manifest_digest='e' * 64, legal_count=4, covered_count=4)
        self.assertEqual(validate_record(r)['status'], 'menu_exhausted')
        for bad in ({**r, 'status':'local_optimum'}, {**r, 'stopping_reason':None},
                    {**r, 'target_phases':['parser']}, {**r, 'parents':[A]},
                    {**r, 'evaluations':[dict(job_id='wrong', candidate_sha=B, profile='full')]}):
            with self.assertRaises(ValueError):
                validate_record(bad)

    def test_records_are_immutable_coordinator_only_and_cycle_checked(self):
        state = initial_state('coordinator')
        with self.assertRaises(ValueError):
            apply(state, 'research', 'worker', record())
        state, r = apply(state, 'research', 'coordinator', record())
        again, _ = apply(state, 'research', 'coordinator', record())
        self.assertEqual(again, state)
        with self.assertRaises(ValueError):
            apply(state, 'research', 'coordinator', {**record(), 'change_summary':'rewritten'})
        back = {**record(), 'record_id':'back', 'kind':'refine', 'parents':[C], 'candidate_sha':A, 'evaluations':[]}
        with self.assertRaisesRegex(ValueError, 'cycle'):
            apply(state, 'research', 'coordinator', back)

    def test_graph_declared_combination_exact_evaluation_and_context(self):
        r = record()
        evidence = dict(job_id='job-c', candidate_sha=C, profile='full', cohort_digest='cohort-1',
                        category='valid', eligible_full=True)
        context = dict(mode='concurrent', epoch=14)
        snapshot = {'team_search':dict(research_records={r['record_id']:r}, tasks={}, observations={
            'amd:job-c':dict(instance='amd', evidence=evidence, comparison_context=context)})}
        g = build_lineage(snapshot)
        links = [e for e in g['edges'] if e['kind'] == 'hypothesis_combination']
        self.assertEqual({e['source'] for e in links}, {'candidate:' + A, 'candidate:' + B})
        evaluations = [n for n in g['nodes'] if n['kind'] == 'evaluation']
        self.assertEqual(len(evaluations), 1)
        self.assertEqual(evaluations[0]['comparison_context'], context)
        self.assertEqual(evaluations[0]['cohort_digest'], 'cohort-1')
        self.assertNotIn('winner', g)
        self.assertEqual(g['issues'], [])

    def test_conflicting_feedback_never_creates_parent_edges(self):
        job = dict(id='job-c', sha=C, profile='full', recorded_feedback={
            'status':'conflicting_records', 'parent_candidates':[A], 'hypothesis':'combine B'})
        g = build_lineage({'jobs':[job]})
        self.assertFalse(any(e['kind'] == 'scientific_parent' for e in g['edges']))
        self.assertTrue(g['issues'])
        job['recorded_feedback']['status'] = 'recorded'
        g = build_lineage({'jobs':[job]})
        self.assertEqual([e['source'] for e in g['edges'] if e['kind']=='scientific_parent'], ['candidate:' + A])
        self.assertFalse(any(n.get('candidate_sha') == B for n in g['nodes']))

    def test_feedback_control_edges_require_delivery_receipt_and_stay_separate(self):
        r = record()
        r['feedback_ref'] = dict(artifact_ref='feedback.json', artifact_digest='f' * 64)
        r['input_receipt'] = dict(path='/private/local-prompt.json', sha256='1' * 64, turn=2)
        r['next_input'] = dict(artifact_ref='next-prompt.json', artifact_digest='2' * 64)
        def graph():
            return build_lineage({'team_search':{'research_records':{r['record_id']:r}}})
        g = graph()
        self.assertFalse(any(e['kind']=='control_feedback' for e in g['control_edges']))
        r['next_input']['feedback_digest'] = 'f' * 64
        g = graph()
        self.assertTrue(any(e['kind']=='control_feedback' for e in g['control_edges']))
        self.assertFalse(any(e['kind']=='control_feedback' for e in g['edges']))
        self.assertFalse(next(n for n in g['nodes'] if n['kind']=='dispatched_input')['available_in_export'])

    def test_campaign_parent_ids_resolve_only_inside_the_campaign(self):
        g = build_lineage({'campaigns':[dict(id='menu', status='budget_exhausted', candidates=[
            dict(candidate_id='one', commit_sha=A, parents=[]),
            dict(candidate_id='two', commit_sha=C, parents=['one'], kind='mutation')])]})
        self.assertTrue(any(e['source']=='candidate:' + A and e['target']=='candidate:' + C for e in g['edges']))
        self.assertFalse(any(n.get('status')=='menu_exhausted' for n in g['nodes']))

    def test_proposed_phase_research_links_inputs_without_inventing_output(self):
        r = {**record(), 'record_id':'planned', 'candidate_sha':None,
             'status':'proposed', 'evaluations':[]}
        g = build_lineage({'team_search':{'research_records':{'planned':r}}})
        inputs = [e for e in g['edges'] if e['kind']=='research_input']
        self.assertEqual({e['source'] for e in inputs}, {'candidate:' + A, 'candidate:' + B})
        self.assertFalse(any(n.get('candidate_sha')==C for n in g['nodes']))
        self.assertFalse(any(e['kind']=='hypothesis_combination' for e in g['edges']))

    def test_actual_consumed_feedback_receipt_links_prior_turn_only(self):
        prior = {**record(), 'feedback_ref':dict(artifact_ref='prior.json', artifact_digest='7' * 64)}
        later = {**record(), 'record_id':'later', 'candidate_sha':'e' * 40, 'parents':[C],
                 'kind':'refine', 'evaluations':[], 'input_receipt':dict(path='local.json', sha256='8' * 64,
                     consumed_feedback_digest='7' * 64, consumed_candidate_sha=C)}
        g = build_lineage({'team_search':{'research_records':{'combine-one':prior, 'later':later}}})
        self.assertEqual(len([e for e in g['control_edges'] if e['kind']=='control_feedback']), 1)
        later['input_receipt']['consumed_candidate_sha'] = A
        g = build_lineage({'team_search':{'research_records':{'combine-one':prior, 'later':later}}})
        self.assertFalse(any(e['kind']=='control_feedback' for e in g['control_edges']))
        self.assertTrue(g['issues'])

    def test_two_instances_do_not_collapse_or_average_jobs(self):
        observations = {}
        for instance in ('amd-a', 'amd-b'):
            observations[instance] = dict(instance=instance, evidence=dict(
                job_id='same-id', candidate_sha=C, profile='full', cohort_digest=instance,
                category='valid', eligible_full=True))
        g = build_lineage({'team_search':{'observations':observations}})
        nodes = [n for n in g['nodes'] if n['kind']=='evaluation']
        self.assertEqual(len(nodes), 2)
        self.assertEqual({n['instance'] for n in nodes}, {'amd-a', 'amd-b'})

    def test_malformed_campaign_candidate_does_not_hide_other_evidence(self):
        g = build_lineage({'campaigns':[dict(id='bad-menu', candidates=[None,
            dict(candidate_id='bad-sha', commit_sha='not-a-sha', parents=[]),
            dict(candidate_id='bad-parent', commit_sha=B, parents=[{}]),
            dict(candidate_id='self', commit_sha=A, parents=['self']),
            dict(candidate_id='good', commit_sha=C, parents=[])])]})
        self.assertTrue(g['issues'])
        self.assertTrue(any(n.get('candidate_sha') == C for n in g['nodes']))
        self.assertFalse(any(e['source']==e['target'] for e in g['edges']))


if __name__ == '__main__':
    unittest.main()
