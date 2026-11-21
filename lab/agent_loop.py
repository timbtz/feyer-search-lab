"""Run a bounded, resumable Codex conversation with measured evaluator feedback."""
import argparse
import json
import os
from pathlib import Path
import signal
import subprocess
import time

from .client import Client, git

SCHEMA = {
    'type':'object', 'additionalProperties':False,
    'properties':{
        'summary':{'type':'string'}, 'hypothesis':{'type':'string'},
        'ready_for_evaluation':{'type':'boolean'}, 'stop':{'type':'boolean'},
        'notes':{'type':'string'},
    }, 'required':['summary','hypothesis','ready_for_evaluation','stop','notes'],
}


def write_json(path, value):
    path=Path(path)
    temporary=path.with_suffix(path.suffix+'.tmp')
    temporary.write_text(json.dumps(value,indent=2,allow_nan=False)+'\n')
    temporary.replace(path)


def changed_paths(repo):
    tracked=subprocess.check_output(['git','-C',str(repo),'diff','--name-only','-z','HEAD']).decode().split('\0')
    new=subprocess.check_output(['git','-C',str(repo),'ls-files','--others','--exclude-standard','-z']).decode().split('\0')
    return sorted(set(p for p in tracked+new if p))


def validate_changes(repo, paths):
    for name in paths:
        if not name.startswith(('differometor/','experiments/notes/')):
            raise ValueError(f'Agent changed a protected path: {name}')
        path=Path(repo)/name
        if path.is_symlink():
            raise ValueError(f'Agent may not add symlinks: {name}')
        if path.exists() and path.stat().st_size>2*1024*1024:
            raise ValueError(f'Candidate file exceeds 2 MiB: {name}')


def github_status(slug, job, target=None):
    result=job.get('result') or {}
    if job['status'] in ('queued','running'):
        state,description='pending',f'{job["profile"]} queued on AMD CPU 2'
    elif job['status']=='completed':
        state='success'
        description=f'{result.get("verdict")}: {result.get("first_run_seconds",0):.3f}s; peak RAM {(result.get("peak_rss_kib") or 0)/1024**2:.2f} GiB'
    else:
        state,description='failure',(job.get('error') or job['status'])[:130]
    command=['gh','api','--method','POST',f'repos/{slug}/statuses/{job["sha"]}',
             '-f',f'state={state}','-f',f'context=feyer/{job["profile"]}',
             '-f',f'description={description[:140]}']
    if target:command+=['-f',f'target_url={target}']
    result=subprocess.run(command,stdout=subprocess.DEVNULL,stderr=subprocess.PIPE,text=True)
    if result.returncode:
        print('GitHub status publication failed: '+result.stderr.strip(),flush=True)


def codex_turn(worktree, session_dir, iteration, prompt, thread_id, timeout):
    output=session_dir/f'turn-{iteration:02d}.json'
    events=session_dir/f'turn-{iteration:02d}.jsonl'
    errors=session_dir/f'turn-{iteration:02d}.stderr.log'
    schema=session_dir/'response-schema.json'
    write_json(schema,SCHEMA)
    command=['codex','exec','-C',str(worktree),'--approve-for-me']
    if thread_id:
        command+=['resume','--json','--output-schema',str(schema),'-o',str(output),thread_id,'-']
    else:
        command+=['--json','--output-schema',str(schema),'-o',str(output),'-']
    with events.open('w') as stdout,errors.open('w') as stderr:
        process=subprocess.Popen(command,stdin=subprocess.PIPE,stdout=stdout,stderr=stderr,text=True,start_new_session=True)
        try:
            process.communicate(prompt,timeout=timeout)
        except subprocess.TimeoutExpired:
            os.killpg(process.pid,signal.SIGTERM)
            try:process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                os.killpg(process.pid,signal.SIGKILL)
                process.wait()
            raise TimeoutError('Agent session time budget reached; conversation logs retained')
    for line in events.read_text(errors='replace').splitlines():
        try:event=json.loads(line)
        except json.JSONDecodeError:continue
        if event.get('type')=='thread.started':thread_id=event['thread_id']
    if process.returncode:
        raise RuntimeError(f'Codex exited {process.returncode}; inspect {errors}')
    if not thread_id:
        raise RuntimeError('Codex did not report a resumable conversation ID')
    response=json.loads(output.read_text())
    if not all(k in response for k in SCHEMA['required']):
        raise ValueError('Incomplete agent response')
    return thread_id,response


def run(args):
    repo=args.repo.resolve()
    worktree=args.worktree.resolve()
    directory=repo/'.lab'/'sessions'/args.name
    directory.mkdir(parents=True,exist_ok=True)
    status_file=directory/'status.json'
    state=json.loads(status_file.read_text()) if args.resume and status_file.exists() else {}
    thread=state.get('thread_id')
    initial_count=int(state.get('candidates',0))
    state.update(pid=os.getpid(),branch=args.branch,worktree=str(worktree),status='starting')
    write_json(status_file,state)
    if not worktree.exists():
        subprocess.run(['git','-C',str(repo),'worktree','add','-b',args.branch,str(worktree),'main'],check=True)
    if git(worktree,'branch','--show-current')!=args.branch:
        raise ValueError('Worktree branch does not match assigned direction')
    if changed_paths(worktree) and not args.resume:
        raise ValueError('Initial agent worktree must be clean')
    client=Client(args.host)
    deadline=time.monotonic()+args.max_minutes*60
    brief=(repo/'experiments'/'initial-agent.md').read_text()
    feedback=state.get('feedback',{})
    try:
        for iteration in range(initial_count+1,args.max_candidates+1):
            if time.monotonic()>=deadline:break
            state.update(status='coding',iteration=iteration)
            write_json(status_file,state)
            prompt=(brief if not thread else 'Continue the same investigation using the evaluator feedback below.')
            prompt+='\n\nManaged session: edit only differometor/** and experiments/notes/**. Do NOT commit, push, invoke SSH, or run the full benchmark locally. The supervisor handles Git and evaluation. Keep the official benchmark and harness unchanged. Make one focused candidate, then return the requested JSON. Returning does not discard this conversation: you will be resumed with measured feedback. Do not spawn agents.\n'
            prompt+=f'Candidate {iteration}/{args.max_candidates}. Remaining session seconds: {max(0,int(deadline-time.monotonic()))}.\n'
            if feedback:prompt+='Evaluator feedback:\n'+json.dumps(feedback,indent=2)+'\n'
            before=git(worktree,'rev-parse','HEAD')
            thread,response=codex_turn(worktree,directory,iteration,prompt,thread,max(1,deadline-time.monotonic()))
            state.update(thread_id=thread,last_response=response)
            write_json(status_file,state)
            if git(worktree,'rev-parse','HEAD')!=before:
                raise ValueError('Agent changed Git history; manual review required')
            paths=changed_paths(worktree)
            validate_changes(worktree,paths)
            if not response['ready_for_evaluation'] or not paths:
                state.update(status='complete',reason='Agent returned no candidate',feedback=response)
                break
            subprocess.run(['git','-C',str(worktree),'add','--',*paths],check=True)
            subprocess.run(['git','-C',str(worktree),'commit','-m',f'Experiment {args.name} {iteration}: {response["summary"][:120]}'],check=True)
            sha=git(worktree,'rev-parse','HEAD')
            feedback={'candidate_sha':sha,'agent_response':response}
            for profile in ('screen','full'):
                if profile=='full':
                    screen=feedback.get('screen',{})
                    if screen.get('status')!='completed':break
                    # Validate the first successful candidate and later promising candidates.
                    total=(screen.get('result') or {}).get('first_run_seconds',float('inf'))
                    if iteration>1 and total>args.baseline_seconds*1.02:break
                state.update(status=f'evaluating_{profile}',candidate_sha=sha,candidates=iteration)
                write_json(status_file,state)
                job=client.submit(worktree,args.branch,args.name,args.direction,response['hypothesis'],profile,sha)
                state.update(job_id=job['id'])
                write_json(status_file,state)
                github_status(args.github_repo,job)
                job=client.wait(job['id'],timeout=1800)
                client.fetch(job['id'],directory/'results'/job['id'])
                feedback[profile]=job
                github_status(args.github_repo,job)
            records=worktree/'experiments'/'runs'/args.name
            records.mkdir(parents=True,exist_ok=True)
            record=records/f'candidate-{iteration:02d}.json'
            write_json(record,feedback)
            subprocess.run(['git','-C',str(worktree),'add','--',str(record.relative_to(worktree))],check=True)
            subprocess.run(['git','-C',str(worktree),'commit','-m',f'Record evaluator feedback for {sha[:12]}'],check=True)
            subprocess.run(['git','-C',str(worktree),'-c','credential.helper=!gh auth git-credential','push','origin',args.branch],check=True)
            record_sha=git(worktree,'rev-parse','HEAD')
            target=f'https://github.com/{args.github_repo}/blob/{record_sha}/{record.relative_to(worktree).as_posix()}'
            for profile in ('screen','full'):
                if profile in feedback:github_status(args.github_repo,feedback[profile],target)
            state.update(feedback=feedback,candidates=iteration,status='feedback_ready')
            write_json(status_file,state)
            if response['stop']:break
        state.update(status='complete',reason='Agent stopped or bounded session finished')
    except BaseException as exc:
        state.update(status='failed',error=f'{type(exc).__name__}: {exc}')
        raise
    finally:
        state['thread_id']=thread
        write_json(status_file,state)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--repo',type=Path,required=True)
    parser.add_argument('--worktree',type=Path,required=True)
    parser.add_argument('--branch',default='explore/seed-agent')
    parser.add_argument('--name',default='seed-agent')
    parser.add_argument('--direction',default='first-pass')
    parser.add_argument('--host',default='amd-hackathon')
    parser.add_argument('--github-repo',default='timkireply/feyer-search-lab')
    parser.add_argument('--max-candidates',type=int,default=4)
    parser.add_argument('--max-minutes',type=float,default=60)
    parser.add_argument('--baseline-seconds',type=float,default=35.737065)
    parser.add_argument('--resume',action='store_true')
    args=parser.parse_args()
    if args.max_candidates<1 or args.max_minutes<=0 or '/' in args.name or args.name in ('.','..'):
        parser.error('Invalid session name or budget')
    run(args)


if __name__=='__main__':
    main()
