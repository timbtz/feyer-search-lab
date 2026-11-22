"""Install a committed evaluator release and start its serial tmux worker."""
import argparse
import json
from pathlib import Path
import shlex
import subprocess

from .client import Client, git
from .compiler_policy import LEGACY, POLICIES, policy_descriptor, policy_digest


def deploy(repo, host='amd-hackathon', root='/workspace/feyer-lab', compiler_policy=LEGACY):
    descriptor = policy_descriptor(compiler_policy)
    repo=Path(repo).resolve()
    client=Client(host,root)
    sha=git(repo,'rev-parse','HEAD')
    release=f'{root}/releases/{sha}'
    paths=[f'{root}/{name}' for name in ('incoming','state','runs','releases')]
    command='mkdir -p '+shlex.join(paths)
    command+=f' && if [ ! -d {shlex.quote(root + "/repo.git")} ]; then git clone --mirror /workspace/feyer-pristine {shlex.quote(root + "/repo.git")}; fi'
    command+=f' && mkdir -p {shlex.quote(release)}'
    subprocess.run(client.ssh+[command],check=True,timeout=120)
    archive=subprocess.check_output(['git','-C',str(repo),'archive','--format=tar.gz',sha,'lab','tests','AGENTS.md','.wiki'])
    command=shlex.join(['tar','-xzf','-','-C',release])
    subprocess.run(client.ssh+[command],input=archive,check=True,timeout=180)
    # Never switch a running worker to new evaluator code midway through a job.
    command=f'if tmux has-session -t feyer-worker 2>/dev/null; then printf "Worker already exists; release uploaded without switching it.\\n"; exit 3; fi; '
    command+=f'ln -sfn {shlex.quote(release)} {shlex.quote(root + "/control")}; '
    worker=shlex.join(['/workspace/venv-feyer/bin/python','-u','-m','lab.remote','--root',root,'worker',
                       '--compiler-policy', compiler_policy])
    shell=f'cd {shlex.quote(root + "/control")} && exec {worker} >> {shlex.quote(root + "/state/worker.log")} 2>&1'
    command+=shlex.join(['tmux','new-session','-d','-s','feyer-worker',shell])
    subprocess.run(client.ssh+[command],check=True,timeout=60)
    record={'release_sha':sha,'host':host,'root':root,'worker_session':'feyer-worker',
            'compiler_policy':descriptor,'compiler_policy_sha256':policy_digest(compiler_policy)}
    destination=repo/'.lab'/'deployment.json'
    destination.parent.mkdir(parents=True,exist_ok=True)
    destination.write_text(json.dumps(record,indent=2)+'\n')
    return record


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--repo',type=Path,default=Path.cwd())
    parser.add_argument('--host',default='amd-hackathon')
    parser.add_argument('--root',default='/workspace/feyer-lab')
    parser.add_argument('--compiler-policy', choices=POLICIES, default=LEGACY)
    args=parser.parse_args()
    print(json.dumps(deploy(args.repo,args.host,args.root,args.compiler_policy),indent=2))


if __name__=='__main__':
    main()
