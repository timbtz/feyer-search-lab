import hashlib,json,os,pathlib,shlex,subprocess,time
ROOT=pathlib.Path('/Users/t.betz/Documents/Feyer challenge')
P=ROOT/'.lab/campaigns/overnight-20261122'
RUNTIME=ROOT/'.lab/worktrees/overnight-runtime-v1'
PYTHON=ROOT/'.lab/venv-topology-smac/bin/python'
DEADLINE=1795339664.0
if time.time()>=DEADLINE: raise SystemExit('Authorized campaign deadline passed')
if (P/'launch.json').exists(): raise SystemExit('Launch receipt already exists; inspect/resume, never duplicate launch')
wrapper=P/'evaluate'
wrapper.write_text('#!/bin/sh\ncd '+shlex.quote(str(RUNTIME))+'\nexec '+shlex.join([str(PYTHON),'-m','lab.overnight_client','--config',str(P/'client-config.json')])+'\n')
wrapper.chmod(0o755)
env=dict(os.environ)
env.update(PATH=str(P/'bin')+':/opt/homebrew/bin:'+env.get('PATH',''),GIT_CONFIG_COUNT='2',GIT_CONFIG_KEY_0='credential.helper',GIT_CONFIG_VALUE_0='',GIT_CONFIG_KEY_1='credential.helper',GIT_CONFIG_VALUE_1='!gh auth git-credential',OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1')
receipt={'campaign':'overnight-20261122','runtime_commit':subprocess.check_output(['git','-C',str(RUNTIME),'rev-parse','HEAD'],text=True).strip(),'runtime':str(RUNTIME),'deadline_unix':DEADLINE,'created_at':time.time(),'controllers':[],'client_config_sha256':hashlib.sha256((P/'client-config.json').read_bytes()).hexdigest(),'codex_wrapper_sha256':hashlib.sha256((P/'bin/codex').read_bytes()).hexdigest(),'source_review_required':True}
for lane,direction in enumerate(('overhead','numerics')):
 name='overnight-'+direction+'-v1'; worktree=ROOT/'.lab/worktrees'/name
 if (P/'sessions'/name/'status.json').exists(): raise RuntimeError('Existing session requires explicit resume')
 command=[str(PYTHON),'-m','lab.overnight_search','--campaign-dir',str(P),'--name',name,'--lane',str(lane),'--worktree',str(worktree),'--branch','explore/'+name,'--brief',str(RUNTIME/'experiments/briefs'/('overnight-20261122-'+direction+'.md')),'--deadline-unix',str(DEADLINE),'--evaluator-command',shlex.quote(str(wrapper)),'--codex-bin-dir',str(P/'bin'),'--hook-timeout','2400','--status-export',str(ROOT/'.lab/agent-status'/(name+'.json'))]
 log=(P/(name+'.supervisor.log')).open('ab')
 proc=subprocess.Popen(command,cwd=RUNTIME,env=env,stdin=subprocess.DEVNULL,stdout=log,stderr=subprocess.STDOUT,start_new_session=True,close_fds=True)
 awake=subprocess.Popen(['/usr/bin/caffeinate','-i','-s','-w',str(proc.pid)],stdin=subprocess.DEVNULL,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,start_new_session=True,close_fds=True)
 receipt['controllers'].append({'name':name,'pid':proc.pid,'caffeinate_pid':awake.pid,'command':command,'worktree':str(worktree),'branch':'explore/'+name,'started_at':time.time(),'status':'launched_pending_verification'})
 temporary=P/'launch.json.tmp'; temporary.write_text(json.dumps(receipt,indent=2)+'\n'); temporary.replace(P/'launch.json')
print(json.dumps(receipt,indent=2))
