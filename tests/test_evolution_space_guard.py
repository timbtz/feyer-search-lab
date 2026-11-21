"""Finite-space rendering cannot inherit unrelated code or follow symlinks."""
import hashlib
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

from lab.evolution_space import DEFAULTS, SOURCE_PATH, materialize_commit

SOURCE = '''def _evaluate_component(function_and_inputs):
    branches = tuple(jax.checkpoint(function, prevent_cse=False) for function in FUNCTIONS)
    return branches

def update():
    output_matrix = lax.map(
        _evaluate_component,
        (function_indices, function_inputs),
    )
    return output_matrix
'''


class MaterializerGuardTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.root=Path(self.temp.name);self.repo=self.root/'repo';self.repo.mkdir()
        self.git('init','-b','explore/test')
        self.git('config','user.email','test@example.invalid');self.git('config','user.name','Test')
        source=self.repo/SOURCE_PATH;source.parent.mkdir();source.write_text(SOURCE)
        fixture=self.repo/'examples/data/input.json';fixture.parent.mkdir(parents=True);fixture.write_text('{}\n')
        self.seed=self.commit('seed')
        self.patches=[patch('lab.evolution_space.SEED_SHA',self.seed),
                      patch('lab.evolution_space.SOURCE_SHA256',hashlib.sha256(SOURCE.encode()).hexdigest())]
        for context in self.patches:context.start()

    def tearDown(self):
        for context in reversed(self.patches):context.stop()
        self.temp.cleanup()

    def git(self,*args):
        return subprocess.check_output(['git','-C',str(self.repo),*args],text=True,stderr=subprocess.PIPE).strip()

    def commit(self,message):
        self.git('add','-A');self.git('commit','-m',message)
        return self.git('rev-parse','HEAD')

    def render(self,head=None,campaign_id='demo'):
        return materialize_commit(self.repo,dict(DEFAULTS,checkpoint=False),'explore/test',
                                  head or self.git('rev-parse','HEAD'),campaign_id=campaign_id)

    def test_committed_startup_hook_outside_target_is_rejected(self):
        (self.repo/'sitecustomize.py').write_text('raise RuntimeError("unexpected startup")\n')
        self.commit('unregistered startup hook')
        with self.assertRaisesRegex(ValueError,'outside'):self.render()
        self.assertEqual((self.repo/SOURCE_PATH).read_text(),SOURCE)

    def test_changed_physical_fixture_is_rejected(self):
        (self.repo/'examples/data/input.json').write_text('{"changed":true}\n')
        self.commit('changed fixture')
        with self.assertRaisesRegex(ValueError,'outside'):self.render()

    def test_committed_source_symlink_never_writes_external_file(self):
        outside=self.root/'external.py';outside.write_text(SOURCE)
        target=self.repo/SOURCE_PATH;target.unlink();target.symlink_to(outside)
        self.commit('source symlink')
        with self.assertRaisesRegex(ValueError,'symlink'):self.render()
        self.assertEqual(outside.read_text(),SOURCE)

    def test_only_the_exact_campaign_record_prefix_is_allowed(self):
        path=self.repo/'experiments/campaigns/demo-other/README.md';path.parent.mkdir(parents=True)
        path.write_text('not owned by demo\n');self.commit('other campaign')
        with self.assertRaisesRegex(ValueError,'outside'):self.render()

    def test_owned_campaign_records_are_preserved_and_only_source_is_rendered(self):
        path=self.repo/'experiments/campaigns/demo/README.md';path.parent.mkdir(parents=True)
        path.write_text('record\n');parent=self.commit('own campaign')
        result=self.render(parent)
        self.assertTrue(result['changed'])
        self.assertEqual(self.git('diff','--name-only',parent,result['sha']),SOURCE_PATH)
        self.assertEqual(path.read_text(),'record\n')
        self.assertEqual((self.repo/'examples/data/input.json').read_text(),'{}\n')

    def test_stale_head_and_dirty_tree_are_rejected(self):
        (self.repo/'experiments').mkdir(exist_ok=True)
        (self.repo/'experiments/note').write_text('untracked\n')
        with self.assertRaisesRegex(ValueError,'clean'):self.render()
        self.commit('unrelated edit')
        with self.assertRaisesRegex(ValueError,'head changed'):self.render(self.seed)


if __name__=='__main__':unittest.main()
