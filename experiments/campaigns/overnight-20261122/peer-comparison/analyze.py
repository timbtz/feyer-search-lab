"""Read-only fixed-plan peer comparison; never dispatches or promotes."""
import argparse, hashlib, json, math, random, statistics
from pathlib import Path
PLAN_SHA256='b8faf981e46a5a31d13bdeb5949cc211b495462cb3ed2b7268cf1ae15ef2e1d8'
def read(p):return json.loads(Path(p).read_text())
def digest(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def metrics(v):
 return {'samples_seconds':v,'count':len(v),'mean_seconds':statistics.mean(v),'median_seconds':statistics.median(v),'standard_deviation_seconds':statistics.stdev(v) if len(v)>1 else None,'min_seconds':min(v),'max_seconds':max(v),'coefficient_of_variation':statistics.stdev(v)/statistics.mean(v) if len(v)>1 else None}
def paired(own,peer,seed):
 ratios=[a/b for a,b in zip(own,peer)];logs=list(map(math.log,ratios));rng=random.Random(seed);n=len(logs)
 boot=sorted(math.exp(statistics.median(logs[rng.randrange(n)] for _ in range(n))) for _ in range(20000))
 return {'repaired_over_peer_ratios_by_block':ratios,'estimated_ratio':math.exp(statistics.median(logs)),'ratio_percentile_interval_95':[boot[499],boot[19499]],'repaired_faster_blocks':sum(x<1 for x in ratios),'blocks':n,'bootstrap_seed':seed,'resamples':20000,'warning':'Three selected matched blocks provide weak uncertainty; not judging-hardware proof or universal performance claim.'}
def analyze(folder,evidence,preflights):
 assert digest(folder/'plan.json')==PLAN_SHA256,'Frozen plan changed'
 plan=read(folder/'plan.json');rows={c['name']:{} for c in plan['candidates']};missing=[];issues=[];passed=0;cohorts=set();policies=set()
 for item in plan['requests']:
  assert digest(item['request_path'])==item['request_sha256'],'Frozen request changed'
  p=folder/'results'/(item['request_id']+'.json')
  if not p.exists():missing.append(item['request_id']);continue
  state=read(p)
  assert state['request_id']==item['request_id'] and state['sha']==item['sha'],'State identity mismatch'
  if state.get('status')!='completed':issues.append({'request_id':item['request_id'],'issue':'not_completed','status':state.get('status')});continue
  rp=evidence/state['receipt_path'];assert digest(rp)==state['receipt_sha256'],'Receipt changed';receipt=read(rp)
  assert receipt['evaluation_id']==item['request_id'] and receipt['candidate_sha']==item['sha'],'Receipt identity mismatch'
  row={'request_id':item['request_id'],'sha':item['sha'],'state_sha256':digest(p),'timings':{},'official':{},'strict_comparisons':{},'phases':{}}
  for setup in ('grid','aligo'):
   samples=receipt['benchmarks'][setup]['samples'];assert len(samples)==1,'Exactly one fresh process expected'
   sample=samples[0];report_path=evidence/sample['report_path'];assert digest(report_path)==sample['report_sha256'],'Report changed';report=read(report_path)
   check=next(x for x in state['checks'] if x['setup']==setup);env=report['environment'];v=report['validation'];inp=report['inputs'];seconds=sample['seconds']
   ok=(sample['candidate_sha']==item['sha'] and sample.get('fresh_process') is True and sample.get('official_passed') is True and check.get('returncode')==0 and check.get('failure') is None and check.get('official',{}).get('passed') is True and check.get('artifacts',{}).get('passed') is True and report['source']['commit']==item['sha'] and report['source']['modified'] is False and env['cpu_affinity_ids']==[2] and env['cpu_affinity_count']==1 and env['requested_logical_cpus']==1 and env['backend']=='cpu' and env['jax_enable_x64'] is True and env['persistent_compilation_cache'] is False and env['thread_limits']==dict.fromkeys(('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS','NUMEXPR_NUM_THREADS'),'1') and v['all_outputs_and_gradients_finite'] is True and v['upstream_sensitivity_check_passed'] is True and v['gradient_check']['passed'] is True and inp['frequency_count']==101 and inp['gradient_parameter_count']==(193 if setup=='grid' else 29))
   assert type(seconds) in (int,float) and math.isfinite(seconds) and seconds>0 and seconds==check['first_run_seconds']==report['timing_seconds']['end_to_end'],'Timing mismatch'
   row['official'][setup]=ok;row['timings'][setup]=seconds;row['strict_comparisons'][setup]=check.get('strict_comparisons',{});row['phases'][setup]={x['key']:x['seconds'] for x in report['phases']};passed+=int(ok)
   if not ok:issues.append({'request_id':item['request_id'],'setup':setup,'issue':'official_failed'})
  rows[item['candidate']][item['block']]=row;cohorts.add(receipt['cohort_digest']);policies.add(state['policy_digest'])
 if len(cohorts)>1 or len(policies)>1:issues.append({'issue':'mixed_cohort_or_policy'})
 complete=sum(map(len,rows.values()))==6 and not missing
 result={'schema_version':'feyer-peer-paired-analysis-v1','status':'complete' if complete else 'partial_not_final','plan_sha256':PLAN_SHA256,'complete_requests':sum(map(len,rows.values())),'official_checks_passed':passed,'expected_official_checks':12,'missing':missing,'issues':issues,'cohort_digests':sorted(cohorts),'policy_digests':sorted(policies),'promotion_ready':False,'candidates':{},'paired':{},'preflights':[], 'scope':'Same machine/runtime/CPU2, one fresh checkout per request, grid then aLIGO, all samples retained; no claim about judging hardware or other team final submission. Seed-relative strict mismatch is disclosed separately, not automatically treated as official failure.'}
 for name,blocks in rows.items():
  ordered=[blocks[b] for b in sorted(blocks)];result['candidates'][name]={'sha':next(c['sha'] for c in plan['candidates'] if c['name']==name),'raw_by_block':ordered,'metrics':{s:metrics([r['timings'][s] for r in ordered]) for s in ('grid','aligo')} if ordered else {}}
 if complete:
  result['paired']={s:paired([rows['repaired'][b]['timings'][s] for b in range(1,4)],[rows['peer'][b]['timings'][s] for b in range(1,4)],plan['bootstrap_seed']) for s in ('grid','aligo')}
 for path in preflights:
  state=read(path);assert state['sha'] in {c['sha'] for c in plan['candidates']},'Unrelated preflight'
  result['preflights'].append({'path':str(path),'sha256':digest(path),'candidate_sha':state['sha'],'official_passed':state.get('official_passed'),'checks':state.get('checks'),'generalization':state.get('generalization'),'note':'Raw results retained; pristine/seed disagreements are separate from official checks.'})
 result['both_exact_source_generalization_preflights_attached']={c['sha'] for c in plan['candidates']} <= {x['candidate_sha'] for x in result['preflights']}
 return result
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--directory',type=Path,default=Path(__file__).resolve().parent);p.add_argument('--evidence-root',type=Path,required=True);p.add_argument('--preflight',type=Path,action='append',default=[]);p.add_argument('--allow-partial',action='store_true');a=p.parse_args();r=analyze(a.directory,a.evidence_root,a.preflight);partial=r['status']=='partial_not_final'
 if not partial or a.allow_partial:
  out=a.directory/('partial-analysis.json' if partial else 'analysis.json');out.write_text(json.dumps(r,indent=2,allow_nan=False)+'\n')
 print(json.dumps({'status':r['status'],'complete_requests':r['complete_requests'],'official_checks_passed':r['official_checks_passed'],'issues':r['issues']}));raise SystemExit(2 if partial or r['issues'] else 0)
