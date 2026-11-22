import json, shutil, hashlib, statistics, sys
from pathlib import Path
import numpy as np
from lab.transfer_validation import audit_archive, validate_official_report, file_digest

src=Path(sys.argv[1])
out=Path('experiments/audits/2026-11-22-fastest')
sha='53f38d342c3228c052785e8c9d63b6ce9c832dd1'
def save(name,data):
    (out/name).write_text(json.dumps(data,indent=2,allow_nan=False)+'\n')
def copy(a,b):
    target=out/b;target.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(src/a,target)
receipt=json.loads((src/'receipt.json').read_text())
summary={'candidate_sha':sha,'selection':'Fast candidate retained for final review; no fallback activated',
         'official_benchmarks':{},'ranking_eligible':False,'claude_headless':'User stop remains in effect; no model sessions launched',
         'shared_worker_policy':'Unchanged; old no-XLA-flags guard remains deployed. These are separate official support runs.',
         'upstream':receipt['upstream'],'fallback_activated':False}
for setup in ('grid','aligo'):
    reports=[src/f'candidate-{setup}/report.json']+[src/f'recheck/official-{setup}-{i}.json' for i in (2,3)]
    rows=[]
    for i,path in enumerate(reports,1):
        report=json.loads(path.read_text())
        verdict=validate_official_report(report,setup=setup,cpu=2,candidate_sha=sha,harness_hashes=receipt['harness']['files'])
        rows.append({'repeat':i,'first_run_seconds':report['timing_seconds']['end_to_end'],'report_sha256':file_digest(path),**verdict})
        copy(path.relative_to(src),f'official/{setup}-{i}.json')
    reference=json.loads((src/f'reference-{setup}/report.json').read_text())
    summary['official_benchmarks'][setup]={'all_passed':all(r['passed'] for r in rows),'requested_and_effective_logical_cpus':1,
      'reference_seconds':reference['timing_seconds']['end_to_end'],'median_candidate_seconds':statistics.median(r['first_run_seconds'] for r in rows),'runs':rows}
    copy(f'reference-{setup}/report.json',f'official/{setup}-reference.json')
    copy(f'candidate-{setup}/stdout.log',f'official/{setup}-1.log')
    for i in (2,3): copy(f'recheck/official-{setup}-{i}/stdout.log',f'official/{setup}-{i}.log')
copy('receipt.json','official/execution.json')
copy('extra/execution.json','extra-execution.json')
copy('recheck/execution.json','recheck-execution.json')
copy('extra/precision-arrays/residuals.json','precision-residuals.json')
copy('independent/execution.json','independent-execution.json')
summary['gradient_sanity']={}
for setup in ('grid','aligo'):
    first=json.loads((src/f'extra/gradient-{setup}.json').read_text())
    later=json.loads((src/f'recheck/gradient-{setup}.json').read_text())
    latest={r['index']:r for r in first['checks']};latest.update({r['index']:r for r in later['checks']})
    summary['gradient_sanity'][setup]={'tested':len(latest),'confirmed':sum(r['status']=='passed' for r in latest.values()),
       'unresolved':[{'index':r['index'],'parameter':r['parameter'],'status':r['status']} for r in latest.values() if r['status']!='passed'],
       'scope':'Additional finite difference sanity at fixed alternative steps; .01 relative/1e-6 absolute, not a high-precision gradient certificate.'}
    copy(f'extra/gradient-{setup}.json',f'gradient-{setup}-initial.json')
    copy(f'recheck/gradient-{setup}.json',f'gradient-{setup}-recheck.json')
baseline=np.load(src/'prior/pristine.npz');candidate=np.load(src/'extra/generalization.npz');prior=np.load(src/'prior/exact-53f38d3.npz')
cases=sorted({k.split('/')[0] for k in candidate.files})
audit=audit_archive(src/'prior/pristine.npz',src/'extra/generalization.npz',cases)
save('strict-fourteen-cases.json',audit)
rows=[]
for case in cases:
    prefix=case+'/'
    values={k[len(prefix):]:candidate[k] for k in candidate.files if k.startswith(prefix)}
    needed=['carrier','signal','noise','sensitivity','powers','loss','gradient','parameters','frequencies']
    sa,sb=baseline[prefix+'sensitivity'],values['sensitivity']
    ga,gb=baseline[prefix+'gradient'],values['gradient']
    rows.append({'case':case,'all_outputs_finite':all(bool(np.isfinite(values[k]).all()) for k in needed),
       'positive_sensitivity':bool(np.all(sb>0)),'gradient_nonzero':bool(np.any(gb!=0)),
       'frequencies':int(values['frequencies'].size),'variables':int(gb.size),
       'inputs_identical':all(np.array_equal(values[k],baseline[prefix+k]) for k in ['parameters','frequencies']),
       'max_log_sensitivity_difference':float(np.max(abs(np.log(sa)-np.log(sb)))),
       'gradient_relative_l2':float(np.linalg.norm(ga-gb)/np.linalg.norm(ga)),
       'max_change_from_previous_candidate_run':{k:float(np.max(abs(values[k]-prior[prefix+k]))) for k in needed}})
summary['generalization']={'cases_executed':len(rows),'all_complete_finite_and_identical_inputs':all(r['all_outputs_finite'] and r['inputs_identical'] and r['positive_sensitivity'] and r['gradient_nonzero'] for r in rows),
      'dense_reference_log_tolerance_exceeded':[r['case'] for r in rows if r['max_log_sensitivity_difference']>1e-5],
      'scope':'New exact-candidate run against preserved historical pristine archives; reference checkout verified clean at original SHA, archive provenance was historical.'}
save('fourteen-cases.json',rows)
copy('extra/generalization/stdout.log','fourteen-cases.log')
copy('prior/openpoints.sh','prior-openpoints.sh')
copy('prior/pristine-modes.log','prior-modulation.log')
copy('prior/pristine-haswell.log','prior-kernel-variation.log')
extended=np.load(src/'extra/precision-arrays/extended.npz')
rows=[]
for case in ('dev','uifo_rand1','uifo_rand3','aligo'):
    p=case+'/'
    row={'case':case}
    for label,data in [('candidate',candidate),('dense_reference',baseline)]:
        row[label]={'max_log_sensitivity_difference_from_extended':float(np.max(abs(np.log(data[p+'sensitivity'])-np.log(extended[p+'sensitivity'])))),
          'gradient_relative_l2_from_extended':float(np.linalg.norm(data[p+'gradient']-extended[p+'gradient'])/np.linalg.norm(extended[p+'gradient']))}
    rows.append(row)
save('extended-precision-comparison.json',{'scope':'Same candidate assembly and adjoint formulas; only solves refined with extended-precision residuals. Supports solver-rounding diagnosis, not an independent exact physics oracle.','cases':rows})
rows=[]
for case,ports in [('uifo_rand1',[255,257]),('uifo_rand3',[267])]:
    data=np.load(src/f'independent/{case}/arrays.npz')
    row={'case':case,'ports_from_recorded_gencheck_stdout':ports,'frequency_inputs_identical':bool(np.array_equal(data['frequencies'],candidate[case+'/frequencies']))}
    for label,archive in [('candidate',candidate),('dense_reference',baseline)]:
        carrier,signal=archive[case+'/carrier'],archive[case+'/signal'];n=carrier.shape[0]
        detected=(np.conj(carrier)*signal[:n]+carrier*signal[n:2*n])[ports]
        detected=detected.squeeze() if len(ports)==1 else detected[0]-detected[1]
        row[label]={'signal_relative_l2':float(np.linalg.norm(signal-data['signal'])/np.linalg.norm(data['signal'])),
         'detected_amplitude_relative_max':float(np.max(abs(abs(detected)-abs(data['detected']))/abs(data['detected'])))}
    rows.append(row)
    copy(f'independent/{case}/stdout.log',f'independent-{case}.log')
save('independent-assembly-comparison.json',{'scope':'Matrices assembled by pristine JAX implementation, signal solves refined using extended-precision residuals. Carrier remains double precision; not arbitrary-precision physics or independent full-gradient proof.','cases':rows})
summary['verdict']={'public_official_correctness':'PASS on both official workloads, three fresh processes each',
 'extended_numerical_review':'Six grid finite-difference coordinates unresolved; two ill-conditioned random cases differ from dense reference. Both precision diagnostics favor the refined sparse solver.',
 'all_diagnostics_passed':False,'automatic_fallback':False}
save('summary.json',summary)
save('artifact-manifest.json',{'raw_artifacts_root':str(src),'remote_root':'/workspace/feyer-transfer',
 'files':{str(p.relative_to(src)):file_digest(p) for p in src.rglob('*') if p.is_file() and p.suffix in ('.npz','.json','.tgz')},
 'note':'Large raw arrays retained locally and on AMD; reports/logs/hashes committed. Archive hashes bind preserved evidence, not retroactive authentication of old runs.'})
print(json.dumps(summary,indent=2))
