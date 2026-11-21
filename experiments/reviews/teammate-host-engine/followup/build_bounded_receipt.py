from pathlib import Path
import json,hashlib
from lab.verification import digest,assess,template
p=Path('experiments/reviews/teammate-host-engine/followup')
read=lambda n:json.loads((p/(n+'.json')).read_text())
hashfile=lambda n:hashlib.sha256((p/(n+'.json')).read_bytes()).hexdigest()
c=read('bounded-candidate'); r=read('bounded-reference'); comparison=read('bounded-comparison'); execution=read('execution')
sha='cb502e8a5a15689e6f41971bd4a611cf6612283f'
descriptors={'setup':{k:c[k] for k in ['setup','pairs','initial','frequencies','projection']},'harness':{'files':execution['files'],'runs':execution['runs'][:3]},'environment':{'identity':{k:v for k,v in c['identity'].items() if k not in ['source_sha256','harness_sha256','comparison_sha256']},'cpu':101,'command':execution['runs'][1]['command']},'acceptance':{'reference_sha':'02ec741d8a1bf1a2278294ea74f9fc1d68f08f1f','reference_report_sha256':hashfile('bounded-reference'),'tolerance':comparison['tolerance'],'comparator_source_sha256':execution['files']['bounded_jaxcompat.py']}}
binding={k+'_digest':digest(v) for k,v in descriptors.items()}
checks=[]
for row in comparison['checks']:
 checks.append(dict(id=row['test'],capability=row['test'],setup='voyager-bounded-40freq-45params',method='Sequential pinned CPU101 run against clean unchanged02ec741; saved input trajectories checked',status=row['status'],evidence_kind='independent_measurement',source_ref='experiments/reviews/teammate-host-engine/followup/bounded-comparison.json',source_digest=hashfile('bounded-comparison'),observed_at=execution['runs'][2]['finished_at'],binding=binding,outputs=row,summary='Valid-input diagnostic only; does not replace historical stress or certify full JAX.',thresholds={'relative_output_tolerance':comparison['tolerance']}))
receipt=dict(schema='feyer-verification-v1',candidate_sha=sha,checks=checks)
policy=dict(schema='feyer-verification-policy-v1',policy_id='bounded-voyager-first-order-review-v1',purpose='Require both bounded Voyager trajectory checks only; broader JAX and official benchmark remain separate.',scope='internal_opt_in',requirements=[dict(id=x['id'],capability=x['capability'],setup=x['setup'],binding=binding,minimum_passes=1) for x in checks])
for name,value in [('binding-descriptors',descriptors),('bounded-verification',receipt),('bounded-policy',policy),('bounded-policy-decision',assess(sha,policy,[receipt]))]: (p/(name+'.json')).write_text(json.dumps(value,indent=2,allow_nan=False)+'\n')
print('Bounded gate',assess(sha,policy,[receipt])['status'])
