const test=require('node:test'),assert=require('node:assert/strict');
const {TopologyFlow}=require('../app.js');
test('wide research narrows into a centered combination below all parents',()=>{
 const nodes=[...Array.from({length:7},(_,i)=>({id:'r'+i,rank:0})),{id:'combine',rank:1},{id:'result',rank:2}];
 const edges=[...nodes.slice(0,7).map(n=>({source:n.id,target:'combine'})),{source:'combine',target:'result'}];
 for(const columns of [1,2,4]){
  const flow=TopologyFlow.layout(nodes,edges,columns),byId=new Map(flow.nodes.map(n=>[n.id,n]));
  for(const e of edges)assert.ok(byId.get(e.source).row<byId.get(e.target).row);
  assert.equal(byId.get('combine').column,columns);assert.equal(byId.get('result').column,columns);
  for(const a of flow.nodes){assert.ok(a.column>=1&&a.column+1<=columns*2);for(const b of flow.nodes)if(a.id!==b.id&&a.row===b.row)assert.ok(Math.abs(a.column-b.column)>=2);}
 }
});
test('layout is stable and return links do not change ancestry ordering',()=>{
 const nodes=[{id:'b',rank:0},{id:'a',rank:0},{id:'end',rank:1}],edges=[{source:'a',target:'end'},{source:'end',target:'a',returnLink:true}];
 assert.deepEqual(TopologyFlow.layout(nodes,edges),TopologyFlow.layout([...nodes].reverse(),edges));assert.deepEqual(TopologyFlow.layout([],[]).nodes,[]);
});
