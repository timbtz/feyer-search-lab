import subprocess
import tempfile
from pathlib import Path
import unittest

from lab.client import Client, git, publish_candidate


class ClientTests(unittest.TestCase):
    def test_rejects_shell_like_host_and_parent_traversal(self):
        for host in ('-oProxyCommand=bad', 'host;cmd', 'host name'):
            with self.assertRaises(ValueError):Client(host)
        with self.assertRaises(ValueError):Client(root='/workspace/../root')

    def test_publishing_older_candidate_keeps_newer_branch_tip(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory)
            repo=root/'repo'; remote=root/'remote.git'
            subprocess.run(['git','init','-q','-b','explore/test',str(repo)],check=True)
            git(repo,'config','user.name','Test')
            git(repo,'config','user.email','test@example.invalid')
            subprocess.run(['git','init','-q','--bare',str(remote)],check=True)
            git(repo,'remote','add','origin',str(remote))
            (repo/'file').write_text('first')
            git(repo,'add','file');git(repo,'commit','-qm','first')
            first=git(repo,'rev-parse','HEAD')
            (repo/'file').write_text('second')
            git(repo,'commit','-qam','second')
            second=git(repo,'rev-parse','HEAD')
            publish_candidate(repo,first,'explore/test')
            self.assertEqual(git(remote,'rev-parse','refs/heads/explore/test'),second)


if __name__=='__main__':unittest.main()
