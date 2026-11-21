import subprocess
import tempfile
from pathlib import Path
import unittest
from unittest.mock import Mock, patch
import uuid

from lab.client import Client, git, publish_candidate


class ClientTests(unittest.TestCase):
    def test_submit_passes_caller_request_id_without_replacing_it(self):
        client=Client();client.request=Mock(side_effect=[None,{'id':'job'}])
        request_id=str(uuid.uuid4())
        def run(command,**kwargs):
            if 'bundle' in command:
                Path(command[5]).write_bytes(b'git bundle fixture')
            return subprocess.CompletedProcess(command,0)
        with patch('lab.client.git',return_value='a'*40),patch('lab.client.subprocess.run',side_effect=run):
            self.assertEqual(client.submit('.', 'explore/test','a','d','h',publish=False,request_id=request_id),{'id':'job'})
        self.assertEqual(client.request.call_args.args[0]['request_id'],uuid.UUID(request_id).hex)

    def test_old_server_error_is_actionable_and_has_no_fallback(self):
        error=subprocess.CalledProcessError(1,['ssh'],stderr='ValueError: Unknown action: lookup_request')
        with patch('lab.client.subprocess.check_output',side_effect=error):
            with self.assertRaisesRegex(RuntimeError,'Deploy the updated'):
                Client().request({'action':'lookup_request','request_id':'1'*32})

    def test_capability_failure_precedes_publish_or_upload(self):
        client=Client();client.request=Mock(side_effect=RuntimeError('server requires deployment'))
        with patch('lab.client.git',return_value='a'*40),patch('lab.client.publish_candidate') as publish, \
             patch('lab.client.subprocess.run') as upload:
            with self.assertRaisesRegex(RuntimeError,'requires deployment'):
                client.submit('.','main','a','d','h',request_id='1'*32)
        publish.assert_not_called();upload.assert_not_called()

    def test_existing_matching_request_returns_without_upload(self):
        job={'id':'existing','sha':'a'*40,'branch':'main','agent':'a','direction':'d',
             'hypothesis':'h','profile':'screen','request_id':'1'*32}
        client=Client();client.request=Mock(return_value=job)
        with patch('lab.client.git',return_value='a'*40),patch('lab.client.publish_candidate') as publish, \
             patch('lab.client.subprocess.run') as upload:
            self.assertEqual(client.submit('.','main','a','d','h',request_id='1'*32),job)
        publish.assert_not_called();upload.assert_not_called()

    def test_existing_request_payload_mismatch_rejects_without_upload(self):
        client=Client();client.request=Mock(return_value={'id':'existing','sha':'b'*40})
        with patch('lab.client.git',return_value='a'*40),patch('lab.client.publish_candidate') as publish, \
             patch('lab.client.subprocess.run') as upload:
            with self.assertRaisesRegex(ValueError,'different submission payload'):
                client.submit('.','main','a','d','h',request_id='1'*32)
        publish.assert_not_called();upload.assert_not_called()

    def test_invalid_request_id_rejected_before_git_or_network(self):
        with patch('lab.client.git') as command:
            with self.assertRaises(ValueError):Client().submit('.','main','a','d','h',request_id='invalid')
        command.assert_not_called()

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
