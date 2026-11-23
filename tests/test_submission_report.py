import json
from pathlib import Path
import subprocess
import tempfile
import unittest
from lab.submission_report import source_changes, artifact, submission_snapshot


class SubmissionReportTests(unittest.TestCase):
    def test_exact_diff_has_both_line_numbers_and_symbols(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory)
            def git(*args):
                return subprocess.check_output(['git','-C',directory,*args],text=True,stderr=subprocess.DEVNULL).strip()
            git('init');git('config','user.email','test@example.test');git('config','user.name','Test')
            (root/'differometor').mkdir();p=root/'differometor/sample.py';p.write_text('def solve():\n    return 1\n')
            git('add','.');git('commit','-m','baseline');base=git('rev-parse','HEAD')
            p.write_text('def solve():\n    return 2\n');git('commit','-am','candidate');sha=git('rev-parse','HEAD')
            changes=source_changes(directory,base,sha)
            self.assertEqual(changes[0]['symbols']['solve'],{'start':1,'end':2})
            lines=changes[0]['hunks'][0]['lines']
            self.assertIn({'kind':'removed','old':2,'new':None,'text':'    return 1'},lines)
            self.assertIn({'kind':'added','old':None,'new':2,'text':'    return 2'},lines)
            self.assertEqual(changes[0]['added'],1)

    def test_artifacts_are_bounded_and_symlinks_are_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);(root/'.lab').mkdir();(root/'secret.json').write_text('{}')
            with self.assertRaises(ValueError):artifact(root,'secret.json')
            (root/'.lab/link.json').symlink_to(root/'secret.json')
            with self.assertRaises(ValueError):artifact(root,'.lab/link.json')
            (root/'.lab/big.json').write_text(' '*2_000_001)
            with self.assertRaises(ValueError):artifact(root,'.lab/big.json')

    def test_no_manifest_does_not_invent_final_selection(self):
        with tempfile.TemporaryDirectory() as directory:
            self.assertEqual(submission_snapshot(directory)['candidates'],[])
            self.assertIsNone(submission_snapshot(directory)['selected_sha'])

    def test_complete_sha_required(self):
        with self.assertRaises(ValueError):source_changes('.', 'main', 'HEAD')
