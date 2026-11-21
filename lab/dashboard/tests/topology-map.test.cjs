const test=require('node:test'),assert=require('node:assert/strict');
const {TopologyMap}=require('../app.js');
test('compact graph deduplicates candidate revisions but preserves all exact evaluations',()=>{
 const g=TopologyMap.build({jobs:[{id:'one',sha:'a',profile:'full'},{id:'two',sha:'a',profile:'screen'}]});assert.equal(g.nodes.length,1);assert.equal(g.nodes[0].runs.length,2);assert.equal(g.nodes[0].group,'unknown');assert.equal(g.edges.length,0);
});
test('recorded phase targets remain a phase focus, not an inferred topology',()=>{
 const g=TopologyMap.build({team_search:{research_records:{r:{record_id:'r',candidate_sha:'a',parents:['p','q'],target_phases:['compilation'],hypothesis:'Try sparse assembly'}}}});const n=g.nodes.find(n=>n.id==='a');assert.equal(n.groupKind,'Declared phase focus');assert.equal(g.edges.length,2);assert.ok(g.nodes.find(n=>n.id==='p'));assert.equal(n.rank,1);
});
test('campaign parents are scoped and source branches do not become parent arrows',()=>{
 const g=TopologyMap.build({jobs:[{id:'j',sha:'a',branch:'explore/solver',parent_run_key:'old'}],campaigns:[{id:'one',campaign:{spec:{space_version:'topology-A'}},candidates:[{candidate_id:'seed',commit_sha:'p'},{candidate_id:'child',commit_sha:'a',parents:['seed']}]},{id:'two',candidates:[{candidate_id:'seed',commit_sha:'different'}]}]});assert.deepEqual(g.edges,[{source:'p',target:'a'}]);assert.equal(g.nodes.find(n=>n.id==='a').groupLabel,'topology-A');
});
test('planned research stays unmeasured and receives only explicit input links',()=>{
 const g=TopologyMap.build({team_search:{research_records:{r:{record_id:'r',candidate_sha:null,parents:['p'],target_phases:[],hypothesis:'Investigate',status:'proposed'}}}});const n=g.nodes.find(n=>n.planned);assert.equal(n.runs.length,0);assert.equal(n.group,'unknown');assert.deepEqual(g.edges,[{source:'p',target:'plan:r'}]);
});
