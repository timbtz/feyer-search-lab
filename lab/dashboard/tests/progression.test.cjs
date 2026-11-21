const test=require('node:test'),assert=require('node:assert/strict');
const {Progression}=require('../app.js');
test('progression separates finite numerical campaigns from research branches',()=>{
 const d={campaigns:[{id:'tuning',candidates:[{commit_sha:'tune'}]}],workers:[{id:'w',branch:'explore/research',direction:'a real hypothesis',status:'running',stale:false}],jobs:[{id:'j',sha:'tune',branch:'explore/tuning',profile:'full'},{id:'r',sha:'new',branch:'explore/research',profile:'screen'}]};
 const m=Progression.build(d);assert.equal(m.research.length,1);assert.equal(m.research[0].active,true);assert.equal(m.research[0].candidates.length,1);assert.equal(m.tuning.length,1);assert.equal(Progression.verdict(m.research[0].latest).label,'Screen only');
});
test('repeated receipts and screens do not become separate candidate revisions',()=>{
 const m=Progression.build({jobs:[{id:'s',sha:'a',branch:'explore/one',profile:'screen',created_at:1},{id:'f',sha:'a',branch:'explore/one',profile:'full',created_at:2,official_check:'passed',strict_check:'passed',metrics:{total:12}},{id:'f2',sha:'a',branch:'explore/one',profile:'full',created_at:3,official_check:'passed',strict_check:'passed',metrics:{total:14}}]});
 assert.equal(m.research[0].records.length,3);assert.equal(m.research[0].candidates.length,1);assert.equal(m.research[0].latest.metrics.total,14);assert.equal(Progression.verdict(m.research[0].latest).label,'Full pass');
});
test('completed processes are not promoted; rejected and conflicting evidence stays unconfirmed or failed',()=>{
 assert.equal(Progression.verdict({profile:'full',status:'completed'}).label,'Unconfirmed');
 assert.equal(Progression.verdict({profile:'full',official_check:'passed',strict_check:'passed',evidence:{eligible_full:false}}).label,'Unconfirmed');
 assert.equal(Progression.verdict({profile:'full',official_check:'passed',strict_check:'passed',resource_evidence:{budget_exceeded:true}}).label,'Resource limit');
 assert.equal(Progression.verdict({profile:'full',official_check:'passed',strict_check:'failed'}).label,'Check failed');
 assert.equal(Progression.verdict({profile:'screen',official_check:'passed',strict_check:'passed'}).label,'Screen only');
});
test('observed ledger evidence joins only the matching job and exact SHA',()=>{
 const d={jobs:[{id:'a',sha:'sha-a',branch:'explore/a',profile:'full'}],team_search:{observations:{one:{instance:'host-1',evidence:{job_id:'a',candidate_sha:'sha-b',eligible_full:true}}},tasks:{}}};
 assert.equal(Progression.build(d).research[0].latest.evidence,undefined);assert.equal(Progression.build(d).unassigned.length,1);
});
test('empty sources never invent a branch, combination, confirmation or final winner',()=>{
 const m=Progression.build({campaigns:[]});for(const k of ['research','tuning','combinations','confirmations'])assert.deepEqual(m[k],[]);
});

test('timing regime is separate from correctness and preserved on exact-job evidence',()=>{
 const context={mode:'concurrent',epoch:14,receipt:'https://github.com/example/repo/issues/6'};
 const d={jobs:[{id:'j',sha:'a',branch:'explore/one',profile:'full'}],team_search:{tasks:{},observations:{one:{instance:'AMD',comparison_context:context,evidence:{job_id:'j',candidate_sha:'a',eligible_full:true}}}}};
 const r=Progression.build(d).research[0].latest;
 assert.deepEqual(r.comparison_context,context);assert.equal(Progression.verdict(r).label,'Full pass');assert.match(Progression.timing(r.comparison_context),/Exploratory.*concurrent/);
 assert.match(Progression.timing({mode:'unverified_timing'}),/Exploratory.*unverified/);assert.match(Progression.timing({mode:'serial'}),/confirmation required/);assert.equal(Progression.timing(), 'Timing context not recorded');
});
