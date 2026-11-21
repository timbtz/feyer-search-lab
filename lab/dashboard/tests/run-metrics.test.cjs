const test=require('node:test'),assert=require('node:assert/strict');
const {Metrics,Progression,build}=require('../app.js');
const phases={imports:.2,initialize:.1,load:.1,build:.6,forward_lower:1,forward_compile:2,sensitivity_lower:.1,sensitivity_compile:.2,gradient_lower:.4,gradient_compile:.8,forward:4,sensitivity:.01,gradient:2,host_transfer:.02};
const run=(sha,job,total,extra={})=>({sha,job_id:job,profile:'full',instance:'AMD-A',comparison_context:{mode:'serial',epoch:1},evidence:{eligible_full:true,cohort_digest:'cohort'},metrics:{total,setup:1,compilation:4.5,forward:4,sensitivity:.01,gradient:2,transfer:.02},phases,...extra});
test('five objectives separate lowering/compile from differentiation execution and preserve missing phases',()=>{
 const v=Metrics.values(run('a','1',11.53));assert.equal(v.setup,1);assert.equal(v.compilation,4.5);assert.equal(v.differentiation,2.01);assert.equal(v.forward_compilation,3);assert.deepEqual(Metrics.objectives,['total','setup','compilation','forward','differentiation']);assert.equal(Metrics.values({metrics:{sensitivity:1}}).differentiation,null);assert.equal(Metrics.values({}).setup,null);
});
test('explicit parent comparison uses matching repeats, and a combination compares against the better parent',()=>{
 const r=run('child','c',8,{recorded_feedback:{status:'recorded',parent_candidates:['parent-a','parent-b']}});
 const ref=Metrics.reference(r,[run('parent-a','a1',10),run('parent-a','a2',12),run('parent-b','b1',9),run('parent-b','wrong-host',1,{instance:'AMD-B'})]);assert.equal(ref.sha,'parent-b');assert.equal(ref.metrics.total,9);assert.equal(ref.runs,1);assert.equal(Metrics.delta(8,'total',ref).tone,'gain');assert.equal(Metrics.delta(10,'total',ref).tone,'loss');assert.equal(Metrics.delta(9.01,'total',ref).tone,'neutral');
});
test('different host, cohort, mode, epoch, unknown context and failed correctness cannot qualify a comparator',()=>{
 const a=run('a','1',10),b=run('b','2',11);
 for(const change of [{instance:'B'},{evidence:{eligible_full:true,cohort_digest:'other'}},{comparison_context:{mode:'concurrent',epoch:1}},{comparison_context:{mode:'serial',epoch:2}},{comparison_context:null},{evidence:{eligible_full:false,cohort_digest:'cohort'}}])assert.equal(!!Metrics.compatible(a,{...b,...change}),false);
 const r={...a,recorded_feedback:{status:'recorded',parent_candidates:['b']}};assert.equal(Metrics.reference(r,[{...b,instance:'B'}]).available,false);
});
test('chronological and Git predecessors are not silently selected as scientific parents',()=>{
 const r=run('a','1',10,{parent_candidate:'b',parent_run_key:'earlier'});assert.deepEqual(Metrics.parents(r).shas,[]);assert.equal(Metrics.reference(r,[run('b','2',11)]).available,false);
 const graph=build({historical:{candidates:[{run_key:'first',sha:'a'},{run_key:'second',sha:'b',parent_run_key:'first'}]}},{history:true});const edge=graph.edges.find(e=>e.label==='Recorded Git ancestry');assert.equal(edge.grouping,true);
});
test('conflicting declared parents fail closed and hypotheses do not become phase targets',()=>{
 const r=run('a','1',10,{recorded_feedback:{status:'recorded',parent_candidates:['b'],hypothesis:'We hope compilation is faster'},research_records:[{parents:['c']}]});assert.equal(Metrics.parents(r).conflict,true);assert.equal(Metrics.reference(r,[]).available,false);assert.deepEqual(Metrics.annotation(r).target_phases,[]);
});
test('legacy baseline comparisons remain labelled exploratory and are not reused in a new concurrent regime',()=>{
 const r=run('a','1',10,{comparison_context:undefined,validated:true,comparable:true,delta:{}}),base={runs:3,metrics:{total:{median:15,range:.1},sensitivity:{median:.1,range:.01},gradient:{median:2,range:.1}},phases:{}};
 const ref=Metrics.reference(r,[],base);assert.equal(ref.legacy,true);assert.equal(ref.exploratory,true);assert.equal(Metrics.reference({...r,comparison_context:{mode:'concurrent',epoch:14}},[],base).available,false);
});
test('all repeated full receipts remain in a branch and normalized source eligibility is preserved',()=>{
 const d={jobs:[run('a','1',10,{id:'1',branch:'explore/a'}),run('a','2',11,{id:'2',branch:'explore/a'})],historical:{candidates:[{job_id:'1',sha:'a',branch:'explore/a',idea:'Recorded summary'}]}};const m=Progression.build(d);assert.equal(m.research[0].records.length,2);assert.equal(m.research[0].records[0].idea,'Recorded summary');assert.equal(m.research[0].records[0].evidence.eligible_full,true);
});
test('control feedback is optional and cannot introduce a cycle into scientific layout',()=>{
 const data={search_lineage:{schema:'feyer-search-lineage-v1',nodes:[{id:'a',kind:'candidate',candidate_sha:'a'},{id:'b',kind:'candidate',candidate_sha:'b'},{id:'input',kind:'dispatched_input'}],edges:[{source:'a',target:'b',kind:'scientific_parent'}],control_edges:[{source:'b',target:'input',kind:'recorded_feedback'},{source:'input',target:'a',kind:'control_feedback'}]}};
 const normal=build(data,{lineage:true}),overlay=build(data,{lineage:true,control:true});assert.equal(normal.nodes.length,2);assert.equal(normal.controlEdges.length,0);assert.equal(overlay.controlEdges.length,2);assert.equal(overlay.edges.length,1);const laid=require('../app.js').layout(overlay);assert.ok(laid.nodes.find(n=>n.id==='b').x>laid.nodes.find(n=>n.id==='a').x);
});
