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

test('unevaluated candidates join their recorded agent session and retain internal ancestry',()=>{
 const g=SessionGraph.build({workers:[{id:'agent',session_id:'one'}],team_search:{research_records:{
  first:{record_id:'first',executor:{id:'agent'},session_id:'one',candidate_sha:'a',parents:[],hypothesis:'First idea'},
  next:{record_id:'next',executor:{id:'agent'},session_id:'one',candidate_sha:'b',parents:['a'],hypothesis:'Second idea',feedback_ref:{artifact_digest:'digest'},next_input:{feedback_digest:'digest'}}
 }}});
 const session=g.nodes.find(n=>n.kind==='session');
 assert.deepEqual(session.members.map(n=>n.sha),['a','b']);assert.deepEqual(session.memberEdges,[{source:'a',target:'b'}]);assert.equal(session.feedbackRecords.length,1);assert.equal(g.edges.length,0);
});
test('a feedback reference alone never implies a recorded next input',()=>{
 const g=SessionGraph.build({workers:[{id:'agent',session_id:'one'}],team_search:{research_records:{r:{record_id:'r',executor:{id:'agent'},session_id:'one',candidate_sha:'a',parents:[],feedback_ref:{artifact_digest:'first'},next_input:{feedback_digest:'different'}}}}});
 assert.equal(g.nodes.find(n=>n.kind==='session').feedbackRecords.length,0);
});
test('reciprocal group links remain visible as returns without reversing the placement DAG',()=>{
 const g=SessionGraph.build({workers:[{id:'agent',session_id:'one',branch:'work'}],jobs:[{id:'a',sha:'a',session_id:'one'},{id:'b',sha:'b',session_id:'one'}],team_search:{research_records:{r:{record_id:'r',candidate_sha:'b',parents:['a'],kind:'combine'}}}});
 assert.equal(g.edges.length,2);assert.equal(g.edges.filter(e=>e.returnLink).length,1);
 const byId=new Map(g.nodes.map(n=>[n.id,n]));for(const e of g.edges.filter(e=>!e.returnLink))assert.ok(byId.get(e.source).rank<byId.get(e.target).rank);
});
