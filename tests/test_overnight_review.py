import hashlib
import contextlib
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import uuid

from lab import overnight_review as review


class Registry:
    def __init__(self,*args): self.provider='claude'; self.failures=[]
    def choose(self): return self.provider
    def success(self,p,started_at=None): pass
    def failure(self,p,error):
        self.failures.append(error)
        if 'quota' in error: self.provider='codex'; return 'quota'
        return 'transient'


class ReviewTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name)
        self.sha='a'*40; self.parent=review.TRUSTED_SEED
        self.diff=b'diff --git a/differometor/a.py b/differometor/a.py\n+return value'
        (self.root/'source.diff').write_bytes(self.diff)
        self.receipt={'evaluation_id':uuid.uuid4().hex,'candidate_sha':self.sha,
                      'admission':{'promotion_ready':True},'benchmarks':{},'generalization':{}}
        (self.root/'receipt.json').write_text(json.dumps(self.receipt))
        self.payload={'candidate_sha':self.sha,'parent_sha':self.parent,
            'source_diff_sha256':hashlib.sha256(self.diff).hexdigest(),'source_diff_path':str(self.root/'source.diff'),
            'evaluation_receipt_path':str(self.root/'receipt.json'),'worktree':str(self.root),
            'evidence_root':str(self.root),'campaign_dir':str(self.root/'campaign'),'deadline_unix':review.DEADLINE}
        self.patch=patch.object(review,'git',side_effect=lambda path,*args:self.sha+'\n' if args[0]=='rev-parse'
                               else 'differometor/a.py\n' if '--name-only' in args else 'return value' if args[0]=='show'
                               else self.diff.decode()+'\n' if args[0]=='diff' else '')
        self.patch.start(); self.addCleanup(self.patch.stop)
        self.calls=[]

    def call(self,provider,directory,prompt,timeout,fds):
        self.calls.append((provider,prompt,timeout))
        return {'response':{'approved':True,'reasons':['General structural change; no fixture handling'],
                            'generalization_risks':[]},'session_id':'test-session','model':review.MODELS[provider]}

    def run_review(self,call=None,**kwargs):
        return review.review(self.payload,call=call or self.call,providers_factory=Registry,
                             clock=lambda:review.DEADLINE-100,**kwargs)

    def test_complete_review_is_persisted_and_idempotent(self):
        out=self.run_review(); again=self.run_review()
        self.assertEqual(out,again); self.assertEqual(len(self.calls),1)
        metadata=out['source_review']; self.assertTrue(metadata['approved'])
        artifact=self.root/metadata['artifact_path']
        self.assertEqual(review.file_digest(artifact),metadata['artifact_sha256'])
        self.assertEqual((self.root/metadata['diff_path']).read_bytes(),self.diff)
        self.assertEqual(metadata['scope'],'no-fixture-specialization-and-integrity')
        self.assertLessEqual(self.calls[0][2],100)
        stored=json.loads(artifact.read_text())
        for key in ('approved','candidate_sha','parent_sha','diff_sha256','reviewer','provider','model','session_id','scope'):
            self.assertEqual(stored[key],metadata[key])

    def test_publisher_archives_real_review_envelope(self):
        try: from lab import overnight_publish as publisher
        except ImportError: self.skipTest('Publisher available in integrated campaign runtime')
        metadata=self.run_review()
        receipt={**self.receipt,**metadata,'schema_version':'feyer-overnight-evaluation-v1','cohort_digest':'f'*64}
        path=self.root/'enriched.json'; path.write_text(json.dumps(receipt))
        control=self.root/'control'; control.mkdir()
        best=control/publisher.BEST; best.parent.mkdir(parents=True)
        best.write_text(json.dumps({'status':'seed_pending_fresh_calibration','candidate_sha':review.TRUSTED_SEED}))
        owner=publisher.Publisher.__new__(publisher.Publisher)
        owner.worktree=control; owner.evidence_root=self.root; owner.repository_url='https://example.invalid/repo'
        owner.locked=contextlib.nullcontext; owner._recover=lambda:None
        owner._submit=lambda identity,files,decision:files
        files=owner.publish(path)
        self.assertTrue(any(path.endswith('/source-review.json') for path in files))
        self.assertTrue(any(path.endswith('/reviewed-source.diff') for path in files))

    def test_no_numerical_admission_no_provider_call(self):
        self.receipt['admission']['promotion_ready']=False
        (self.root/'receipt.json').write_text(json.dumps(self.receipt))
        with self.assertRaisesRegex(ValueError,'numerical admission'): self.run_review()
        self.assertFalse(self.calls)

    def test_exact_source_diff_required(self):
        self.payload['source_diff_sha256']='f'*64
        with self.assertRaisesRegex(ValueError,'digest'): self.run_review()
        self.assertFalse(self.calls)

    def test_git_diff_must_match_committed_parent(self):
        with patch.object(review,'git',side_effect=lambda p,*a:self.sha if a[0]=='rev-parse' else 'other' if a[0]=='diff' else ''):
            with self.assertRaisesRegex(ValueError,'Stored diff'): self.run_review()
        self.assertFalse(self.calls)

    def test_failed_review_full_envelope_remains_unapproved(self):
        def failed(*args): raise TimeoutError('bounded review timeout')
        out=self.run_review(failed)['source_review']
        self.assertFalse(out['approved']); self.assertEqual(out['parent_sha'],self.parent)
        self.assertTrue((self.root/out['artifact_path']).exists())

    def test_wrong_model_cannot_leave_approved_response_behind(self):
        def wrong(*args):
            result=self.call(*args); result['model']='wrong'; return result
        self.assertFalse(self.run_review(wrong)['source_review']['approved'])

    def test_unresolved_risk_cannot_approve(self):
        def risky(*args):
            result=self.call(*args); result['response']['generalization_risks']=['Potential fixture specialization']; return result
        self.assertFalse(self.run_review(risky)['source_review']['approved'])

    def test_real_quota_classification_can_fall_back_once(self):
        def limited(provider,*args):
            if provider=='claude': raise RuntimeError('quota exceeded')
            return self.call(provider,*args)
        out=self.run_review(limited)['source_review']
        self.assertTrue(out['approved']); self.assertEqual(out['provider'],'codex')

    def test_transient_failure_does_not_silently_switch_provider(self):
        calls=[]
        def transient(provider,*args): calls.append(provider); raise RuntimeError('temporary unavailable')
        self.assertFalse(self.run_review(transient)['source_review']['approved'])
        self.assertEqual(calls,['claude'])

    def test_interrupted_started_review_not_executed_again(self):
        directory=self.root/'reviews'/self.receipt['evaluation_id']; directory.mkdir(parents=True)
        (directory/'started.json').write_text('{}')
        with self.assertRaisesRegex(ValueError,'not automatically'): self.run_review()
        self.assertFalse(self.calls)

    def test_deadline_cannot_extend_authorized_window(self):
        self.payload['deadline_unix']=review.DEADLINE+1
        with self.assertRaisesRegex(ValueError,'deadline'): self.run_review()

    def test_immediate_parent_cannot_hide_unreviewed_earlier_edits(self):
        self.payload['parent_sha']='b'*40
        with self.assertRaisesRegex(ValueError,'complete trusted'): self.run_review()

    def test_commands_use_no_claude_tools_and_readonly_pinned_codex(self):
        claude=review.commands('claude',self.root)
        self.assertEqual(claude[claude.index('--tools')+1],'')
        self.assertIn('--strict-mcp-config',claude)
        codex=review.commands('codex',self.root)
        self.assertIn('--ignore-user-config',codex)
        self.assertEqual(codex[codex.index('--sandbox')+1],'read-only')
        self.assertIn('approval_policy="never"',codex)
        self.assertNotIn('--approve-for-me',codex)


if __name__=='__main__': unittest.main()
