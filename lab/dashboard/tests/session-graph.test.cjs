const test=require('node:test'),assert=require('node:assert/strict');
const {SessionGraph}=require('../app.js');
test('sessions remain separate and repeated jobs stay inside one revision',()=>{
 const g=SessionGraph.build({workers:[{id:'agent',session_id:'one',branch:'explore/shared'},{id:'agent',session_id:'two',branch:'explore/shared'}],jobs:[{id:'a',sha:'sha1',session_id:'one',branch:'explore/shared'},{id:'b',sha:'sha1',session_id:'one',branch:'explore/shared'},{id:'c',sha:'sha2',session_id:'two',branch:'explore/shared'}]});const sessions=g.nodes.filter(n=>n.kind==='session');assert.equal(sessions.length,2);assert.equal(sessions[0].members.length,1);assert.equal(sessions[0].members[0].runs.length,2);assert.equal(sessions[1].members[0].sha,'sha2');
});
test('ambiguous shared branch does not imply session membership',()=>{
 const g=SessionGraph.build({workers:[{id:'a',session_id:'one',branch:'explore/shared'},{id:'b',session_id:'two',branch:'explore/shared'}],jobs:[{id:'j',sha:'x',branch:'explore/shared'}]});assert.ok(g.nodes.filter(n=>n.kind==='session').every(n=>n.members.length===0));assert.ok(g.nodes.some(n=>n.kind==='evidence'&&n.members.some(m=>m.sha==='x')));
});
test('coverage-only numerical sweep preserves budget outcome separately from complete coverage',()=>{
 const r={record_id:'coverage',executor:{kind:'campaign',id:'numerical'},hypothesis:'Frozen sweep',candidate_sha:null,parents:['seed'],kind:'refine',status:'budget_exhausted',executor_stop_status:'budget_exhausted',stopping_reason:'Global budget ended',menu:{covered_count:9,legal_count:9}};const g=SessionGraph.build({workers:[{id:'numerical',branch:'explore/numerical'}],team_search:{research_records:{r}}});const sweep=g.nodes.find(n=>n.kind==='sweep'),decision=g.nodes.find(n=>n.kind==='decision');assert.equal(sweep.menu.covered_count,9);assert.equal(sweep.status,'budget_exhausted');assert.equal(decision.status,'budget_exhausted');assert.equal(g.nodes.filter(n=>n.kind==='session').length,0);assert.ok(g.edges.some(e=>e.kind==='campaign_outcome'&&e.source===sweep.id&&e.target===decision.id));
});
test('empty session invents no results or shared feedback',()=>{
 const g=SessionGraph.build({workers:[{id:'independent',session_id:'i',branch:'explore/independent',status:'running'}]});assert.equal(g.nodes.length,1);assert.equal(g.nodes[0].members.length,0);assert.equal(g.edges.length,0);assert.equal(g.measurements.length,0);
});
