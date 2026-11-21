"""One bounded diagnostic in the borrowed secondary slot, then exact worker restore."""
import hashlib,json,os,pathlib,shlex,sqlite3,subprocess,time
from lab.lane_worker import LaneWorker,secondary_slot
R=pathlib.Path('/workspace/feyer-diagnostic-v1');N=pathlib.Path('/workspace/feyer-lab-lane1')
EXPECTED='/workspace/feyer-lab-lane1/releases/bea601a8799aea4173c6c98287bac98ef755ef2f'
TOKEN='compiler-diagnostic-borrow-v1\n'
def save(name,data):
 p=R/'state'/name;t=p.with_suffix('.tmp');t.write_text(json.dumps(data,indent=2)+'\n');t.replace(p)
def active(root):
 with sqlite3.connect('file:'+str(root/'state/queue.sqlite3')+'?mode=ro',uri=True) as c:
  return c.execute("select id,status from jobs where status in ('running','queued')").fetchall()
assert str((N/'control').resolve())==EXPECTED
assert (N/'state/STOP').read_text()==TOKEN
assert not active(N)
oldpid=int((N/'state/worker.pid').read_text())
try:os.kill(oldpid,0)
except ProcessLookupError:pass
else:raise RuntimeError('Numerical worker still alive')
config=json.loads((R/'lane.json').read_text());start=time.time();end=time.monotonic()+600
try:
 with secondary_slot(config):
  worker=LaneWorker(config);worker.timeout=600
  ready={'pid':os.getpid(),'started_at':start,'release':str((R/'control').resolve()),'worker_sha256':hashlib.sha256((R/'control/lab/worker.py').read_bytes()).hexdigest(),'runner_sha256':hashlib.sha256(pathlib.Path(__file__).read_bytes()).hexdigest(),'cpu_affinity':sorted(os.sched_getaffinity(0)),'memory_budget_bytes':worker.memory_budget_bytes,'max_total_seconds':600,'timeout':600,'config':config}
  (R/'state/worker.pid').write_text(str(os.getpid())+'\n');save('lane-startup.json',ready)
  admission_end=time.monotonic()+60
  while time.monotonic()<admission_end:
   rows=worker.queue.list_jobs(limit=5)
   if rows:break
   time.sleep(.25)
  else:raise RuntimeError('No diagnostic admitted within60seconds')
  assert len(rows)==1 and rows[0]['profile']=='diagnostic' and rows[0]['status']=='queued'
  while time.monotonic()<end:
   worker.timeout=max(.1,end-time.monotonic())
   result=worker.run_once()
   if result is not None:
    save('one-job-result.json',{'finished_at':time.time(),'job':result});break
   time.sleep(1)
  else:raise RuntimeError('No diagnostic completed within total600seconds')
finally:
 save('lane-stopped.json',{'at':time.time(),'pid':os.getpid()})
 assert str((N/'control').resolve())==EXPECTED and (N/'state/STOP').read_text()==TOKEN
 assert not active(N),'Unexpected numerical admission while paused; manual restoration required'
 (N/'state/STOP').unlink()
 command=['taskset','-c','34','/workspace/venv-feyer/bin/python','-u','-m','lab.lane_worker','--config',str(N/'lane.json')]
 shell='cd '+shlex.quote(str(N/'control'))+' && exec '+shlex.join(command)+' >> '+shlex.quote(str(N/'state/worker.log'))+' 2>&1'
 subprocess.run(['tmux','new-session','-d','-s','feyer-worker-lane1',shell],check=True)
 for _ in range(100):
  s=json.loads((N/'state/lane-startup.json').read_text())
  if s['pid']!=oldpid and s['started_at']>start:
   os.kill(s['pid'],0);save('restored.json',{'at':time.time(),'startup':s,'original_release':EXPECTED,'queue_unchanged':True});break
  time.sleep(.1)
 else:raise RuntimeError('Restored numerical worker did not become ready')
