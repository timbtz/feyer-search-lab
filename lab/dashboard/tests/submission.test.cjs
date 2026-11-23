const test=require('node:test'),assert=require('node:assert/strict');
const {transferPairs,evidenceStatus,filteredJobs}=require('../submission.js');
test('transfer comparisons require exact candidate and matching setup reference',()=>{
 const candidate={sha:'abc',artifacts:[{path:'receipt',data:{schema:'feyer-official-transfer-run-v1',candidate_sha:'abc',reference_sha:'base',ranking_eligible:false,checks:[{name:'reference',sha:'base',setup:'grid',total_seconds:30},{name:'candidate',sha:'abc',setup:'grid',total_seconds:18},{name:'candidate',sha:'abc',setup:'aligo',total_seconds:5}],comparisons:[{setup:'grid',passed:false}]}}]};
 const pairs=transferPairs(candidate);assert.equal(pairs[0].saved,12);assert.equal(pairs[0].comparison.passed,false);assert.equal(pairs[0].ranking_eligible,false);assert.equal(pairs[1].saved,null);
 candidate.sha='other';assert.deepEqual(transferPairs(candidate),[]);
});
test('missing and failing diagnostics never become passed',()=>{
 assert.equal(evidenceStatus({passed:false}),'Needs review');assert.equal(evidenceStatus({}),'Recorded evidence');
});
test('archive includes screens, failures and exact revisions across rounds',()=>{
 const data={jobs:[{id:'a',sha:'old',profile:'screen',status:'failed',updated_at:1},{id:'b',sha:'new',profile:'full',status:'completed',updated_at:2}]};
 assert.equal(filteredJobs(data,'').length,2);assert.equal(filteredJobs(data,'failed')[0].id,'a');assert.equal(filteredJobs(data,'new')[0].id,'b');
});
const {benchmarkRuns,defaultCandidate}=require('../submission.js');
test('selected performance candidate takes precedence over list order',()=>{
 assert.equal(defaultCandidate({selected_sha:'fast',candidates:[{sha:'slow'},{sha:'fast'}]}),'fast');
});
test('benchmark logs join exact unmodified reports including later repeat runs',()=>{
 const report={source:{commit:'fast',modified:false},timing_seconds:{end_to_end:.997},phases:[{key:'forward',seconds:.18}]};
 const c={sha:'fast',artifacts:[{path:'fastest/candidate-grid/report.json',data:report},{path:'fastest/candidate-grid/stdout.log',data:'first run'},{path:'fastest/recheck/official-grid-2.json',data:report},{path:'fastest/recheck/official-grid-2/stdout.log',data:'repeat'},{path:'wrong.json',data:{...report,source:{commit:'other',modified:false}}},{path:'modified.json',data:{...report,source:{commit:'fast',modified:true}}}]};
 const runs=benchmarkRuns(c);assert.equal(runs.length,2);assert.equal(runs[0].log.data,'first run');assert.equal(runs[1].log.data,'repeat');
 assert.equal(benchmarkRuns({sha:'fast',artifacts:[{path:'missing/report.json',data:report}]})[0].log,undefined);
});
