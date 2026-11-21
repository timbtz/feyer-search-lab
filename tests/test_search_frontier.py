import copy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from lab.search_frontier import build_frontier, collect, comparison_context, write_snapshot
from lab.research_lineage import digest
from tests.test_evolution_evidence import full_job


def entry(name='one', sha='a', scale=1, mode='concurrent', epoch=14, instance='amd-one'):
    j = full_job()
    j['id'], j['sha'] = name, sha * 40
    j['result']['sha'] = j['sha']
    r = j['report.json']
    r['source']['commit'] = j['sha']
    r['timing_seconds']['end_to_end'] *= scale
    r['timing_seconds']['trace_lower_and_compile'] *= scale
    j['result']['first_run_seconds'] = r['timing_seconds']['end_to_end']
    for p in r['phases']:
        p['seconds'] *= scale
    return dict(job=j, instance=instance, executor='guided-one', source_ref='receipt/'+name,
                comparison_context={'mode':mode, 'epoch':epoch})


class SearchFrontierTests(unittest.TestCase):
    def test_exact_observed_dominance_retains_all_phase_objectives(self):
        r = build_frontier([entry(), entry('faster','b',.9)], generated_at=100)
        self.assertEqual(len(r['groups']), 1)
        g = r['groups'][0]
        self.assertEqual(g['observation_count'], 2)
        self.assertEqual([p['job_id'] for p in g['observed_frontier']], ['faster'])
        self.assertEqual(len(g['observed_frontier'][0]['phases']), 14)
        self.assertIn('exploratory', g['qualification'])
        self.assertEqual(g['own_best_observed']['guided-one']['job_id'], 'faster')

    def test_hosts_cohorts_and_epochs_never_compete(self):
        rows = [entry(), entry('host','b',.8,instance='amd-two'),
                entry('epoch','c',.7,epoch=15), entry('serial','d',.6,mode='serial')]
        changed = entry('worker','e',.5)
        changed['job']['result']['worker_sha256'] = 'e'*64
        rows.append(changed)
        self.assertEqual(len(build_frontier(rows)['groups']), 5)

    def test_unknown_context_is_unranked(self):
        r = build_frontier([entry(mode='unknown', epoch=None)])
        self.assertEqual(r['groups'], [])
        self.assertEqual(r['unranked_count'], 1)

    def test_strict_failure_cannot_be_hidden_by_valid_repeats(self):
        bad = entry('bad')
        bad['job']['comparison.json']['passed'] = False
        bad['job']['comparison.json']['checks']['gradient']['passed'] = False
        bad['job']['result']['regression_passed'] = False
        bad['job']['status'] = bad['job']['result']['status'] = 'failed'
        bad['job']['result']['comparison']['returncode'] = 1
        r = build_frontier([entry(), bad])
        self.assertEqual(r['groups'], [])
        self.assertIn('invalid_candidate', [f['category'] for f in r['failures']])
        self.assertIn('numerical_review_required', [f['category'] for f in r['failures']])

    def test_conflicting_same_job_never_silently_picks_copy(self):
        first, other = entry(), entry(scale=.5)
        r = build_frontier([first, other])
        self.assertEqual(r['groups'], [])
        self.assertEqual(r['failure_count'], 1)
        self.assertIn('Conflicting', r['failures'][0]['issues'][0])

    def test_conflicting_failure_quarantines_separate_passing_rerun(self):
        bad, cached, rerun = entry(), entry(), entry('rerun')
        bad['job']['comparison.json']['passed'] = False
        bad['job']['comparison.json']['checks']['gradient']['passed'] = False
        bad['job']['result']['regression_passed'] = False
        bad['job']['status'] = bad['job']['result']['status'] = 'failed'
        bad['job']['result']['comparison']['returncode'] = 1
        r = build_frontier([bad,cached,rerun])
        self.assertEqual(r['groups'], [])
        self.assertIn('numerical_review_required', [f['category'] for f in r['failures']])

    def test_deduplication_uses_job_not_number_of_files(self):
        a, b = entry(), entry()
        b['source_ref'] = 'second-copy'
        g = build_frontier([a,b])['groups'][0]
        self.assertEqual(g['observation_count'], 1)
        self.assertEqual(len(g['observed_frontier'][0]['sources']), 2)

    def test_unknown_copy_or_conflicting_intervals_cannot_upgrade_comparison(self):
        a, b = entry(), entry()
        b['comparison_context'] = {'mode':'unknown','epoch':None}
        self.assertEqual(build_frontier([a,b])['groups'], [])
        a['job'].update(started_at=100, finished_at=110)
        b['job'].update(started_at=101, finished_at=111)
        self.assertEqual(build_frontier([a,b])['failure_count'], 1)

    def test_ledger_label_cannot_upgrade_missing_execution_interval(self):
        team = {'observations':[{'instance':'amd-one','job':full_job(),
                'comparison_context':{'mode':'concurrent','epoch':14}}]}
        with tempfile.TemporaryDirectory() as d, \
             patch('lab.search_frontier.subprocess.check_output', return_value=''):
            rows, _ = collect(d,team,'amd-one',{})
        self.assertEqual(build_frontier(rows)['groups'], [])

    def test_screens_and_pending_jobs_not_full_candidates(self):
        screen, pending = entry(), entry('pending','b')
        screen['job']['profile'] = 'screen'
        pending['job']['status'] = 'running'
        self.assertEqual(build_frontier([screen,pending])['groups'], [])

    def test_context_uses_execution_interval_not_import_time(self):
        team = {'events':[dict(command='comparison-regime', at=100, seq=14,
                               data={'mode':'concurrent','receipt':'receipt'})]}
        for times in ({}, {'started_at':50,'finished_at':110}, {'started_at':20,'finished_at':50}):
            self.assertEqual(comparison_context(times,team)['mode'], 'unknown')
        self.assertEqual(comparison_context({'started_at':110,'finished_at':120},team)['epoch'],14)

    def test_collection_excludes_independent_feedback_even_without_job_agent(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            for session in ('astra-independent-v1','guided-one'):
                p = root/'experiments/runs'/session/'candidate-01.json'
                p.parent.mkdir(parents=True)
                p.write_text(json.dumps({'candidate_sha':'a'*40,'full':full_job()}))
            with patch('lab.search_frontier.subprocess.check_output', return_value=''):
                rows, issues = collect(root, {}, 'amd-one', {})
            self.assertEqual(issues, [])
            self.assertEqual([r['executor'] for r in rows], ['guided-one'])

    def test_published_independent_full_can_inform_guided_feed_one_way(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            p = root/'experiments/runs/astra-independent-v1/candidate-01.json'
            p.parent.mkdir(parents=True)
            p.write_text(json.dumps({'candidate_sha':'a'*40,'full':full_job()}))
            with patch('lab.search_frontier.subprocess.check_output', return_value=''), \
                 patch('lab.search_frontier.published_feedback', return_value='git:exact:feedback.json'):
                rows, _ = collect(root, {}, 'amd-one', {})
            self.assertEqual(len(rows), 1)
            self.assertEqual(rows[0]['source_ref'], 'git:exact:feedback.json')
            self.assertEqual(rows[0]['job']['profile'], 'full')

    def test_content_digest_and_atomic_snapshot_are_reproducible(self):
        r = build_frontier([entry()], generated_at=100)
        unsigned = copy.deepcopy(r)
        claimed = unsigned.pop('content_digest')
        self.assertEqual(digest(unsigned), claimed)
        with tempfile.TemporaryDirectory() as d:
            out = Path(d)/'current.json'
            archive = write_snapshot(r,out)
            self.assertEqual(out.read_bytes(), archive.read_bytes())
            self.assertEqual(write_snapshot(r,out), archive)

    def test_interrupted_archive_publish_leaves_no_partial_immutable_file(self):
        r = build_frontier([entry()], generated_at=100)
        with tempfile.TemporaryDirectory() as d:
            out = Path(d)/'current.json'
            with patch('lab.search_frontier.os.link', side_effect=OSError('interrupted')):
                with self.assertRaises(OSError):
                    write_snapshot(r,out)
            self.assertEqual(list((Path(d)/'artifacts').iterdir()), [])
            self.assertFalse(out.exists())


if __name__ == '__main__':
    unittest.main()
