import hashlib, json, pathlib, shlex, subprocess, sys, time
ROOT = pathlib.Path('/Users/t.betz/Documents/Feyer challenge')
RUNTIME = ROOT/'.lab/worktrees/overnight-integration'
CAMPAIGN = ROOT/'.lab/campaigns/overnight-20261122'
sha = subprocess.check_output(['git','-C',str(RUNTIME),'rev-parse','HEAD'],text=True).strip()
release = '/workspace/feyer-final-validation/releases/'+sha
archive = subprocess.check_output(['git','-C',str(RUNTIME),'archive','--format=tar',sha])
command = ['ssh','-o','BatchMode=yes','-o','ConnectTimeout=15','amd-hackathon']
subprocess.run(command+[f'mkdir -p {shlex.quote(release)} && tar -xf - -C {shlex.quote(release)}'],input=archive,check=True)
remote = r'''
import hashlib,json,pathlib,shutil
root=pathlib.Path('/workspace/feyer-final-validation')
source=pathlib.Path('/workspace/feyer-transfer/53f38d3-official-v1')
manifest={}
for label,prefix in [('pristine','reference'),('initial_seed','candidate')]:
 for setup in ['grid','aligo']:
  target=root/'references'/label/setup
  target.mkdir(parents=True,exist_ok=True)
  for name in ['report.json','arrays.npz']:
   data=(source/(prefix+'-'+setup)/name).read_bytes()
   path=target/name
   if path.exists() and path.read_bytes()!=data: raise ValueError('Reference collision')
   path.write_bytes(data)
   manifest[str(path)]=hashlib.sha256(data).hexdigest()
for name,source in [('pristine-generalization.npz','/tmp/claude-gencheck/pristine.npz'),('initial-seed-generalization.npz','/workspace/feyer-transfer/53f38d3-extra-v1/generalization.npz'),('gencheck.py','/workspace/feyer-transfer/feyer-gencheck-0900bb4.py')]:
 path=root/'references'/name
 data=pathlib.Path(source).read_bytes()
 if path.exists() and path.read_bytes()!=data: raise ValueError('Reference collision')
 path.write_bytes(data)
 manifest[str(path)]=hashlib.sha256(data).hexdigest()
(root/'incoming').mkdir(exist_ok=True)
print(json.dumps(manifest))
'''
result=subprocess.run(command+['python3 -'],input=remote,text=True,capture_output=True,check=True)
manifest=json.loads(result.stdout)
receipt={'runtime_commit':sha,'remote_runtime':release,'archive_sha256':hashlib.sha256(archive).hexdigest(),'references':manifest,'deployed_at':time.time(),'existing_workers_changed':False}
(CAMPAIGN/'deployment.json').write_text(json.dumps(receipt,indent=2)+'\n')
print(json.dumps(receipt,indent=2))
