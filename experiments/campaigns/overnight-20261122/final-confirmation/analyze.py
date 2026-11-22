"""Read-only analysis of the frozen paired plan; never dispatches a benchmark.

Without --allow-partial, missing/incomplete results cause exit 2 and no final report.
Five blocks give limited precision; bootstrap intervals are descriptive evidence,
not an automatic promotion or a universal correctness/statistics claim.
"""
import argparse
import hashlib
import json
import math
from pathlib import Path
import random
import statistics
import sys

PLAN_SHA256 = '06ae4418a089cd9bc17a509b1555279e6617f032bfb54651b1ac750285eca9db'
THREADS = ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS','NUMEXPR_NUM_THREADS')


def digest(path): return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def read(path): return json.loads(Path(path).read_text())


def summary(values):
    if not values: return {'count':0,'samples_seconds':[]}
    mean=statistics.mean(values);median=statistics.median(values)
    std=statistics.stdev(values) if len(values)>1 else None
    return {'count':len(values),'samples_seconds':values,'mean_seconds':mean,'median_seconds':median,
            'standard_deviation_seconds':std,'coefficient_of_variation':std/mean if std is not None else None,
            'minimum_seconds':min(values),'maximum_seconds':max(values),'range_seconds':max(values)-min(values),
            'relative_range':(max(values)-min(values))/median,
            'median_absolute_deviation_seconds':statistics.median(abs(x-median) for x in values)}


def quantile(values,p):
    values=sorted(values);position=(len(values)-1)*p;left=int(position);right=min(left+1,len(values)-1)
    return values[left]+(values[right]-values[left])*(position-left)


def paired(candidate,incumbent,seed=20261123,resamples=20000):
    if len(candidate)!=5 or len(incumbent)!=5: raise ValueError('Five complete matched blocks required')
    ratios=[c/a for c,a in zip(candidate,incumbent)];logs=list(map(math.log,ratios));rng=random.Random(seed)
    boot=[math.exp(statistics.median(logs[rng.randrange(5)] for _ in range(5))) for _ in range(resamples)]
    low,high=quantile(boot,.025),quantile(boot,.975)
    return {'paired_ratios_by_block':ratios,'paired_seconds_difference_by_block':[c-a for c,a in zip(candidate,incumbent)],
        'estimator':'exp(median(log(candidate/incumbent)))', 'estimated_ratio':math.exp(statistics.median(logs)),
        'ratio_percentile_interval_95':[low,high], 'relative_time_reduction_interval_95':[1-high,1-low],
        'improving_blocks':sum(r<1 for r in ratios),'blocks':5,'bootstrap_seed':seed,'bootstrap_resamples':resamples,
        'method':'Resample whole matched blocks with replacement; selected candidates and five blocks limit inference.'}


def analyze(directory,evidence_root):
    directory=Path(directory);evidence_root=Path(evidence_root)
    if digest(directory/'plan.json')!=PLAN_SHA256: raise ValueError('Frozen plan was altered')
    plan=read(directory/'plan.json')
    if len(plan['requests'])!=20: raise ValueError('Expected frozen twenty-request plan')
    candidates={c['name']:c for c in plan['candidates']}
    observed={name:{} for name in candidates};issues=[];missing=[];official_count=0;complete=0;policies=set();cohorts=set();provenance=[]
    for item in plan['requests']:
        request_path=Path(item['request_path'])
        if digest(request_path)!=item['request_sha256']: raise ValueError('Frozen request changed: '+str(request_path))
        request=read(request_path)
        if request['fresh_process_repetitions']!=1 or request['run_generalization']!=(item['block']==1):
            raise ValueError('Unexpected repetition/generalization design')
        path=directory/'results'/(item['request_id']+'.json')
        if not path.exists(): missing.append(item['request_id']);continue
        state=read(path);provenance.append({'request_id':item['request_id'],'state_sha256':digest(path)})
        if state.get('request_id')!=item['request_id'] or state.get('sha')!=item['sha']:
            raise ValueError('Result identity mismatch')
        if state.get('status')!='completed':
            issues.append({'request_id':item['request_id'],'issue':'not_completed','status':state.get('status'),'error':state.get('error')});continue
        if not state.get('receipt_path'):
            missing.append(item['request_id']+':receipt');continue
        receipt_path=evidence_root/state['receipt_path']
        if not receipt_path.exists(): missing.append(item['request_id']+':receipt_download');continue
        if digest(receipt_path)!=state['receipt_sha256']: raise ValueError('Receipt digest mismatch')
        receipt=read(receipt_path)
        if receipt['evaluation_id']!=item['request_id'] or receipt['candidate_sha']!=item['sha']:
            raise ValueError('Receipt source mismatch')
        checks=state.get('checks',[])
        if len(checks)!=2 or {c['setup'] for c in checks}!={'grid','aligo'}:
            raise ValueError('Unexpected official check count')
        row={'block':item['block'],'request_id':item['request_id'],'sha':item['sha'],'official':{},'timings':{},'phases':{}}
        all_reports=True
        for setup in ('grid','aligo'):
            check=next(c for c in checks if c['setup']==setup);samples=receipt['benchmarks'][setup]['samples']
            if len(samples)!=1: raise ValueError('Each paired request must contain one fresh process per setup')
            sample=samples[0];report_path=evidence_root/sample['report_path']
            if not report_path.exists(): missing.append(item['request_id']+':'+setup);all_reports=False;continue
            if digest(report_path)!=sample['report_sha256'] or check['report_sha256']!=sample['report_sha256']:
                raise ValueError('Official report digest mismatch')
            report=read(report_path);env=report['environment'];v=report['validation'];inputs=report['inputs']
            passed=(check.get('returncode')==0 and check.get('failure') is None and check.get('official',{}).get('passed') is True
                and check.get('artifacts',{}).get('passed') is True and sample.get('official_passed') is True
                and sample.get('fresh_process') is True and sample.get('candidate_sha')==item['sha']
                and report['source']['commit']==item['sha'] and report['source']['modified'] is False
                and env['cpu_affinity_ids']==[2] and env['cpu_affinity_count']==1 and env['requested_logical_cpus']==1
                and env['thread_limits']==dict.fromkeys(THREADS,'1') and env['backend']=='cpu'
                and env['jax_enable_x64'] is True and env['persistent_compilation_cache'] is False
                and v['all_outputs_and_gradients_finite'] is True and v['upstream_sensitivity_check_passed'] is True
                and v['gradient_check']['passed'] is True and inputs['frequency_count']==101
                and inputs['gradient_parameter_count']==(193 if setup=='grid' else 29))
            seconds=sample['seconds']
            if not (type(seconds) in (float,int) and math.isfinite(seconds) and seconds>0
                    and seconds==check['first_run_seconds']==report['timing_seconds']['end_to_end']):
                raise ValueError('Invalid/inconsistent first-run timing')
            row['official'][setup]=passed;official_count+=int(passed);row['timings'][setup]=seconds
            row['phases'][setup]={p['key']:p['seconds'] for p in report['phases']}
            seed=check.get('strict_comparisons',{}).get('initial_seed',{})
            if seed.get('passed') is not True: issues.append({'request_id':item['request_id'],'setup':setup,'issue':'seed_regression'})
            if not passed: issues.append({'request_id':item['request_id'],'setup':setup,'issue':'official_check_failed'})
        if not all_reports: continue
        if item['block']==1:
            gen=state.get('generalization',{});seed=gen.get('comparisons',{}).get('initial_seed',{})
            seedcases=seed.get('cases',[])
            refreshed=(gen.get('returncode')==0 and gen.get('failure') is None and gen.get('artifacts',{}).get('passed') is True
                       and seed.get('passed') is True and len(seedcases)==14 and len({c.get('case') for c in seedcases})==14
                       and all(c.get('passed') is True for c in seedcases))
            row['refreshed_generalization']={'passed':refreshed,'case_count':len(seedcases),'seed_comparison':seed,
                'pristine_passed':gen.get('comparisons',{}).get('pristine',{}).get('passed'),
                'candidate_archive_sha256':gen.get('archive_sha256')}
            if not refreshed: issues.append({'request_id':item['request_id'],'issue':'refreshed_14case_seed_gate_failed'})
        observed[item['candidate']][item['block']]=row
        policies.add(state['policy_digest']);cohorts.add(receipt['cohort_digest']);complete+=1
    if len(policies)>1 or len(cohorts)>1: issues.append({'issue':'mixed_execution_policy_or_cohort'})
    finished=complete==20 and not missing
    report={'schema_version':'feyer-paired-confirmation-analysis-v1','plan_sha256':PLAN_SHA256,
        'status':('complete' if not issues else 'complete_with_validation_failures') if finished else 'partial_not_final',
        'complete_requests':complete,'expected_requests':20,'official_checks_passed':official_count,'expected_official_checks':40,
        'missing':missing,'issues':issues,'cohort_digests':sorted(cohorts),'policy_digests':sorted(policies),'candidates':{},
        'promotion_ready':False,'physics_tolerances_changed':False,
        'source_review_status':'All four finalists on generalization hold: approximate adjoint guards lack amplification bounds; numerical timings descriptive only.',
        'source_review_evidence':'review-latest-metadata.json; adjoint-counterexample.json; local-semantic-audit.md',
        'sample_scope':'Fresh checkout for every request; grid first, then aLIGO; every sample retained.',
        'comparison_to_prior':'Do not pool with old three-process-per-checkout medians. Source-bytecode/OS caching explanation for first-process effect remains a hypothesis.',
        'source_provenance':provenance}
    for name,candidate in candidates.items():
        blocks=observed[name];ordered=[blocks[b] for b in sorted(blocks)]
        item={'sha':candidate['sha'],'raw_by_block':ordered,'metrics':{},'phase_metrics':{},
              'prior_metrics_separate_scope':candidate['prior_metrics'],'prior_source_review_approved':candidate['prior_source_review_approved'],
              'existing_14_case_proof_verified':candidate['existing_14_case_proof_verified']}
        for setup in ('grid','aligo'):
            item['metrics'][setup]=summary([r['timings'][setup] for r in ordered])
            phases={key for r in ordered for key in r['phases'][setup]}
            item['phase_metrics'][setup]={key:summary([r['phases'][setup][key] for r in ordered]) for key in sorted(phases)}
        if finished and name!='incumbent':
            item['paired_vs_incumbent']={setup:paired([blocks[b]['timings'][setup] for b in range(1,6)],
                [observed['incumbent'][b]['timings'][setup] for b in range(1,6)],plan['bootstrap_seed'],plan['bootstrap_resamples'])
                for setup in ('grid','aligo')}
        report['candidates'][name]=item
    return report


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--directory',type=Path,default=Path(__file__).resolve().parent)
    p.add_argument('--evidence-root',type=Path,required=True);p.add_argument('--allow-partial',action='store_true');args=p.parse_args()
    result=analyze(args.directory,args.evidence_root)
    partial=result['status']=='partial_not_final'
    if partial and not args.allow_partial:
        print(json.dumps({'status':result['status'],'complete_requests':result['complete_requests'],'missing':result['missing']}))
        return 2
    path=args.directory/('partial-analysis.json' if partial else 'analysis.json')
    path.write_text(json.dumps(result,indent=2,allow_nan=False)+'\n')
    print(json.dumps({'status':result['status'],'complete_requests':result['complete_requests'],'official_checks_passed':result['official_checks_passed'],'path':str(path)}))
    return 2 if partial or result['issues'] else 0


if __name__=='__main__': sys.exit(main())
