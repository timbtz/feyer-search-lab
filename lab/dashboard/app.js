/* Evidence graph: solid edges are recorded relationships; dashed edges are grouping. */
const SearchDAG = (() => {
  const arr = x => Array.isArray(x) ? x : [];
  const human = x => String(x ?? 'unknown').replace(/[_-]+/g, ' ');
  const key = (...parts) => JSON.stringify(parts);
  const measured = x => typeof x === 'number' && Number.isFinite(x) ? `${x.toFixed(2)} s` : 'Not measured';
  function build(data, {campaign = null, history = false, evaluations = false, team = false} = {}) {
    const nodes = [], edges = [], byId = new Map(), warnings = [];
    const node = (id, type, title, subtitle, record, extra = {}) => {
      if (!byId.has(id)) { const n = {id, type, title, subtitle, record, ...extra}; nodes.push(n); byId.set(id, n); }
      return id;
    };
    const edge = (source, target, label, grouping = false) => {
      if (source !== target && !edges.some(e => e.source === source && e.target === target && e.label === label)) edges.push({source, target, label, grouping});
    };
    const root = node('root', 'root', 'Feyer search', 'Research → implementations → evidence', {}, {status:'Read-only evidence'});
    const workers = team?[]:arr(data.workers);
    const selected = (team?[]:arr(data.campaigns)).filter(c => !campaign || c.id === campaign);
    const workerNode = w => node(key('worker', w.id), 'research', w.model && w.model !== 'inherited / not recorded' ? w.model : human(w.provider), w.direction || w.name || w.id, w, {status: `${human(w.status)}${w.stale ? ' · stale observation' : ''}`, description:w.description || w.reason});
    if (!campaign) for (const w of workers) { const id = workerNode(w); edge(root, id, 'Observed worker', true); }
    for (const c of selected) {
      const cid = id => key(c.id, 'candidate', id);
      const rid = id => key(c.id, 'round', id);
      for (const r of arr(c.rounds)) {
        const id = node(rid(r.round_id), 'topology', c.id, r.spec?.materializer_version || r.round_id, r, {campaign:c.id, status:r.closed ? 'Round closed' : 'Frozen search space', description:Object.entries(r.spec?.dimensions || {}).map(([k,v])=>`${human(k)}: ${arr(v).map(x=>x===null?'default':String(x)).join(' / ')}`).join('\n')});
        edge(root, id, 'Search round', true);
        for (const [lane, spec] of Object.entries(r.spec?.lanes || {})) {
          const lid = node(key(c.id, r.round_id, 'lane', lane), 'search', `${String(r.spec?.selector || c.selector || 'selector').toUpperCase()} · ${human(lane)}`, arr(spec.dimensions).map(human).join(' · ') || 'Reviewed implementation choices', spec, {campaign:c.id, status:human(c.status), description:`Owner: ${spec.owner || 'not recorded'}. Frozen small-parameter search; physical workload remains unchanged.`});
          edge(id, lid, 'Search lane', true);
        }
      }
      for (const call of arr(c.model_calls)) {
        const outcome = arr(c.model_outcomes).find(o=>o.call_id===call.call_id);
        const model = call.metadata?.model;
        const id = node(key(c.id,'call',call.call_id), 'research', typeof model === 'string' ? model : model?.model || 'Model invocation', call.metadata?.actor || call.actor, {call,outcome}, {campaign:c.id,status:outcome ? 'Outcome recorded' : 'Invocation reserved · outcome unknown'});
        edge(root,id,'Recorded model call',true);
      }
      for (const a of arr(c.candidates)) {
        const params = Object.entries(a.parameters || {}).map(([k,v])=>`${human(k)} ${v===null?'default':String(v)}`).join(' · ');
        const title = a.kind==='seed' ? `Reference · ${String(a.commit_sha || a.candidate_id).slice(0,8)}` : `${human(a.kind || 'candidate')} · ${String(a.commit_sha || a.candidate_id).slice(0,8)}`;
        const id = node(cid(a.candidate_id), 'candidate', title, params || a.provenance?.hypothesis || 'Recorded implementation', a, {campaign:c.id, candidate:a.candidate_id, status:a.valid ? `Full pass · ${measured(a.metrics?.total)}` : human(a.status), valid:a.valid===true, failed:a.status==='invalid', description:a.provenance?.hypothesis, metric:measured(a.metrics?.total)});
        const lane = key(c.id,a.round_id,'lane',a.lane_id);
        edge(byId.has(lane)?lane:byId.has(rid(a.round_id))?rid(a.round_id):root,id,'Lane membership',true);
      }
      for (const a of arr(c.candidates)) {
        for (const parent of arr(a.parents)) {
          if (!byId.has(cid(parent))) node(cid(parent),'missing','Unresolved parent',String(parent),{candidate_id:parent},{campaign:c.id,status:'Source record unavailable'});
          edge(cid(parent),cid(a.candidate_id),human(a.kind || 'derived from'));
        }
        const callId = key(c.id,'call',a.provenance?.model_call_id);
        if (byId.has(callId)) edge(callId,cid(a.candidate_id),'Proposed implementation');
        if (evaluations) for (const e of arr(c.evaluations).filter(e=>e.candidate_id===a.candidate_id)) {
          const evidence=arr(c.evidence).find(x=>x.evidence_id===e.evidence_id);
          const id=node(key(c.id,'evaluation',e.request_id), 'evaluation', `${human(e.profile)} · attempt ${e.attempt ?? 1}`, e.job_id ? `Job ${e.job_id.slice(0,8)}` : 'Queue job not recorded', {evaluation:e,evidence}, {campaign:c.id,status:human(e.status),valid:e.status==='valid',failed:e.status==='invalid'});
          edge(cid(a.candidate_id),id,'Measured exact candidate');
        }
      }
      for (const g of arr(c.guidance)) {
        const p=g.payload || {};
        const id=node(key(c.id,'guidance',g.guidance_id), 'guidance', p.proposed_operator?.id || p.heuristic_id || 'Research proposal', p.hypothesis || 'New topology / operator proposal', g, {campaign:c.id,status:'Proposal · not an evaluated improvement',description:p.hypothesis});
        const match=workers.find(w=>w.id===g.actor || p.session_id && w.session_id===p.session_id);
        const author=match ? workerNode(match) : node(key('actor',g.actor,p.actual_model), 'research', p.actual_model || g.actor, `Research · ${g.actor}`, {actor:g.actor,model:p.actual_model},{status:'Recorded research author'});
        edge(root,author,'Research author',true); edge(author,id,'Authored guidance');
        for (const parent of arr(p.parents)) if(byId.has(cid(parent))) edge(cid(parent),id,'Research starting point');
        // Admission is shown only when the frozen specification explicitly cites the guidance.
        for (const r of arr(c.rounds)) if(arr(r.spec?.guidance_ids).includes(g.guidance_id) || r.spec?.guidance_id===g.guidance_id) edge(id,rid(r.round_id),'Admitted guidance');
      }
    }
    if (team && data.team_search?.schema === 'feyer-team-search-v1') {
      const ledger=data.team_search,tasks=Object.values(ledger.tasks||{}),observations=Object.values(ledger.observations||{});
      const candidateIds=new Set(observations.map(o=>o.evidence?.candidate_sha).filter(Boolean));
      for(const t of tasks)for(const sha of [...arr(t.parents),...arr(t.candidates)])candidateIds.add(sha);
      const cn=sha=>key('team','candidate',sha),tn=id=>key('team','task',id);
      for(const sha of candidateIds){
        const evidence=observations.filter(o=>o.evidence?.candidate_sha===sha);
        const full=evidence.filter(o=>o.evidence.eligible_full===true),invalid=evidence.some(o=>o.evidence.category==='invalid_candidate');
        const cohorts=new Set(full.map(o=>key(o.instance,o.evidence.cohort_digest)));
        node(cn(sha),'team-candidate',`Implementation · ${sha.slice(0,8)}`,`${full.length} eligible full observations · ${cohorts.size} instance/cohorts`,{sha,observations:evidence},{status:invalid?'Numerical review required':full.length?'Full evidence recorded · no global ranking':'Awaiting full evidence',valid:full.length>0&&!invalid,failed:invalid});
      }
      for(const t of tasks){
        const types={explore:'research',refine:'search',combine:'combine',confirm:'confirmation',diagnose:'diagnosis'};
        const expired=typeof t.deadline_unix==='number'&&t.deadline_unix<=Date.now()/1000;
        node(tn(t.id),types[t.kind]||'task',`${human(t.kind)} · ${t.id}`,t.hypothesis||'Task brief not recorded',t,{teamTask:t.id,status:`${human(t.status)}${expired&&!['done','stalled','blocked'].includes(t.status)?' · deadline reached':''}${t.owner?` · ${t.owner} / ${t.instance}`:''}`,description:t.resolution||t.hypothesis});
      }
      for(const t of tasks){
        for(const sha of arr(t.parents))edge(cn(sha),tn(t.id),'Pinned scientific input');
        for(const sha of arr(t.candidates))if(!arr(t.parents).includes(sha))edge(tn(t.id),cn(sha),`${human(t.kind)} candidate`);
        for(const dep of arr(t.depends_on))if(byId.has(tn(dep)))edge(tn(dep),tn(t.id),'Task prerequisite',true);
      }
      for(const n of nodes.filter(n=>n.id!==root))if(!edges.some(e=>e.target===n.id))edge(root,n.id,'Shared search record',true);
      if(evaluations)for(const [id,o]of Object.entries(ledger.observations||{})){
        const e=o.evidence;if(!e?.candidate_sha||!byId.has(cn(e.candidate_sha)))continue;
        const eid=node(key('team','evaluation',id),'evaluation',`${human(e.profile)} · ${String(e.job_id).slice(0,8)}`,`${o.instance} · cohort ${String(e.cohort_digest||'unknown').slice(0,8)}`,o,{status:human(e.category),valid:e.eligible_full===true,failed:e.category==='invalid_candidate'});
        edge(cn(e.candidate_sha),eid,'Measured on named instance/cohort');
      }
    }

    if (history && !team) {
      const records=arr(data.historical?.candidates);
      const hid=(r,i)=>key('history',r.run_key || r.job_id || i);
      records.forEach((r,i)=> {
        const id=node(hid(r,i),'candidate',r.idea || `Experiment · ${String(r.sha).slice(0,8)}`,r.direction || r.branch || 'Historical experiment',r,{campaign:'history',candidate:r.run_key||r.job_id||`history-${i}`,status:r.validated?`Full pass · ${measured(r.metrics?.total)}`:`${human(r.profile)} · ${human(r.execution_status)}`,valid:r.validated===true,failed:r.official_check==='failed'||r.strict_check==='failed',description:r.hypothesis});
        const worker=workers.find(w=>r.branch && w.branch===r.branch);
        if(worker){const wid=workerNode(worker);edge(root,wid,'Observed worker',true);edge(wid,id,'Recorded research branch');}
        else edge(root,id,'Historical record',true);
      });
      records.forEach((r,i)=>{if(r.parent_run_key){const pi=records.findIndex(p=>p.run_key===r.parent_run_key);if(pi>=0)edge(hid(records[pi],pi),hid(r,i),'Recorded parent');}});
    }
    // Validate every edge and exclude cyclic records instead of manufacturing ancestry.
    const accepted=[], children=new Map();
    for(const e of edges){
      if(!byId.has(e.source)||!byId.has(e.target)){warnings.push('A relationship references unavailable evidence.');continue;}
      const queue=[e.target],seen=new Set();let cycle=false;
      while(queue.length){const id=queue.pop();if(id===e.source){cycle=true;break;}if(seen.has(id))continue;seen.add(id);queue.push(...(children.get(id)||[]));}
      if(cycle){warnings.push(`Cyclic relationship excluded: ${e.label}`);continue;}
      accepted.push(e);if(!children.has(e.source))children.set(e.source,[]);children.get(e.source).push(e.target);
    }
    return {nodes,edges:accepted,warnings};
  }
  function layout(graph, orientation='right') {
    const byId=new Map(graph.nodes.map(n=>[n.id,{...n,rank:0,x:0,y:0}]));
    const incoming=new Map(graph.nodes.map(n=>[n.id,[]])),outgoing=new Map(graph.nodes.map(n=>[n.id,[]]));
    for(const e of graph.edges){incoming.get(e.target).push(e.source);outgoing.get(e.source).push(e.target);}
    const degree=new Map([...incoming].map(([id,parents])=>[id,parents.length]));
    const queue=[...byId.keys()].filter(id=>degree.get(id)===0);
    for(let i=0;i<queue.length;i++){const id=queue[i];for(const target of outgoing.get(id)){byId.get(target).rank=Math.max(byId.get(target).rank,byId.get(id).rank+1);degree.set(target,degree.get(target)-1);if(degree.get(target)===0)queue.push(target);}}
    // Unlinked worker observations occupy a compact research field rather than one tall column.
    const observed=[...byId.values()].filter(n=>n.type==='research' && !n.teamTask && n.record?.id && !outgoing.get(n.id).length);
    observed.forEach((n,i)=>{n.rank=1+i%4;});
    const layers=[];for(const n of byId.values())(layers[n.rank] ||= []).push(n);
    const stepY=158,stepX=330,width=250,height=122;
    layers.forEach(layer=>layer.forEach((n,i)=>{n.y=i*stepY;}));
    // Barycentric sweeps reduce crossings while preserving deterministic ordering.
    for(let sweep=0;sweep<4;sweep++){
      const order=sweep%2?[...layers].reverse():layers;
      for(const layer of order){const neighbors=sweep%2?outgoing:incoming;
        const center=n=>{const ns=neighbors.get(n.id);return ns.length?ns.reduce((sum,id)=>sum+byId.get(id).y,0)/ns.length:n.y;};
        layer.sort((a,b)=>center(a)-center(b)||a.id.localeCompare(b.id));
        layer.forEach((n,i)=>{n.y=i*stepY;});
      }
    }
    const maxRows=Math.max(1,...layers.map(l=>l.length));
    for(const layer of layers)for(const n of layer){n.x=48+n.rank*stepX;n.y+=64+(maxRows-layer.length)*stepY/2;n.width=width;n.height=height;}
    if(orientation==='down'){
      for(const layer of layers)layer.forEach((n,i)=>{n.x=48+(i+(maxRows-layer.length)/2)*290;n.y=48+n.rank*190;});
      return {...graph,orientation,nodes:[...byId.values()],width:Math.max(600,maxRows*290+96),height:layers.length*190+96};
    }
    return {...graph,orientation,nodes:[...byId.values()],width:Math.max(600,layers.length*stepX+16),height:maxRows*stepY+112};
  }
  function trace(graph,id){
    const result=new Set([id]);
    for(const backwards of [true,false]){const queue=[id],seen=new Set(queue);while(queue.length){const current=queue.pop();for(const e of graph.edges){if(e.grouping)continue;const from=backwards?e.target:e.source,to=backwards?e.source:e.target;if(from===current&&!seen.has(to)){seen.add(to);result.add(to);queue.push(to);}}}}
    return result;
  }
  function readyTasks(ledger, now=Date.now()/1000){
    const tasks=ledger?.tasks||{};
    return Object.values(tasks).filter(t=>t.status==='ready'&&t.deadline_unix>now&&arr(t.depends_on).every(id=>['done','stalled'].includes(tasks[id]?.status))).sort((a,b)=>(a.priority??100)-(b.priority??100)||a.id.localeCompare(b.id));
  }
  return {build,layout,trace,readyTasks};
})();
if (typeof module !== 'undefined') module.exports = SearchDAG;

/* Read-only presentation of existing campaign evidence. PDS v4 supplies UI primitives. */
'use strict';
(() => {
  if (typeof document === 'undefined') return;
  const $ = id => document.getElementById(id);
  const REPO = 'https://github.com/timbtz/feyer-search-lab';
  const S = {data:null, campaign:'', view:'graph', step:0, selected:null, filter:'all', fetching:false};
  const list = v => Array.isArray(v) ? v : [];
  const numeric = v => typeof v === 'number' && Number.isFinite(v);
  const seconds = v => numeric(v) ? `${v.toFixed(2)} s` : '—';
  const memory = v => numeric(v) ? `${(v/1073741824).toFixed(2)} GiB` : '—';
  const short = v => String(v || '').slice(0,8);
  const stamp = v => !v ? null : typeof v==='number' ? v*1000 : Date.parse(v);
  const time = v => stamp(v) ? new Date(stamp(v)).toLocaleTimeString([], {hour:'2-digit',minute:'2-digit'}) : 'not recorded';
  const human = v => String(v || 'unknown').replace(/[_-]+/g,' ');
  const make = (tag, cls, text) => { const n=document.createElement(tag); if(cls)n.className=cls; if(text!==undefined)n.textContent=text; return n; };
  const clear = target => { const n=typeof target==='string'?$(target):target;n.replaceChildren();return n; };
  const link = (label,url) => { const a=make('a','',label);a.href=url;a.target='_blank';a.rel='noopener noreferrer';return a; };
  const commitLink = sha => /^[0-9a-f]{40}$/i.test(sha||'') ? link(`Code · ${short(sha)}`,`${REPO}/commit/${sha}`) : null;
  const branchLink = branch => typeof branch==='string' && /^[\w./-]+$/.test(branch) && !branch.includes('..') ? link('Open branch on GitHub',`${REPO}/tree/${branch.split('/').map(encodeURIComponent).join('/')}`) : null;
  const add = (parent,...items) => items.filter(Boolean).forEach(x=>parent.append(x));
  const pill = (text,tone='') => make('span',`status ${tone}`,text);
  const spec = c => c?.campaign?.spec || {};
  const history = () => ({id:'history',status:'historical',selector:'mixed',source_updated_at:S.data?.historical?.generated_at,
    candidates:list(S.data?.historical?.candidates).map((r,i)=>({candidate_id:r.run_key||r.job_id||`history-${i}`,commit_sha:r.sha,
      status:r.validated?'valid':r.official_check==='failed'||r.strict_check==='failed'?'invalid':'unconfirmed',valid:r.validated===true,
      owner:r.agent,parameters:{},parents:r.parent_run_key?[r.parent_run_key]:[],metrics:r.metrics,full_run_count:r.profile==='full'?1:0,
      historical:r,provenance:{hypothesis:r.hypothesis},created_at:r.created_at})),events:[],guidance:[],evaluations:[]});
  const current = () => S.campaign==='history'?history():list(S.data?.campaigns).find(c=>c.id===S.campaign);
  const rows = () => list(current()?.candidates);
  const seed = () => rows().find(c=>c.kind==='seed');
  const round = () => list(current()?.rounds).filter(r=>!r.closed).at(-1)||list(current()?.rounds).at(-1);
  const comparable = (a,b) => a?.valid && b?.valid && a.cohort_digest && a.cohort_digest===b.cohort_digest;
  const reduction = c => {const b=seed();return comparable(c,b)&&numeric(c.metrics?.total)&&b.metrics?.total>0 ?100*(b.metrics.total-c.metrics.total)/b.metrics.total:null;};
  const kind = c => c.valid ? ['Full pass','valid'] : /invalid/.test(c.status||'') ? ['Check failed','failed'] : /screened/.test(c.status||'') ? ['Screen passed','pending'] : /evaluating|proposed|queued/.test(c.status||'') ? ['In progress','running'] : ['Unconfirmed',''];
  function candidateName(c) {
    if(c.kind==='seed')return 'Reference implementation';
    if(c.historical)return c.historical.idea || human(c.historical.direction) || `Attempt ${short(c.commit_sha)}`;
    const p=c.parameters||{}, bits=[];
    if(p.checkpoint===false)bits.push('Checkpointing off');
    if(p.prevent_cse===true)bits.push('CSE prevention on');
    if(p.map_batch_size!==undefined&&p.map_batch_size!==null)bits.push(`Component batch ${p.map_batch_size}`);
    return bits.join(' · ')||`Attempt ${short(c.commit_sha||c.candidate_id)}`;
  }
  function phaseFacts(parent,data) {
    const dl=make('dl','phase-list');
    for(const [name,value]of data){const d=make('div');add(d,make('dt','',name),make('dd','',value));dl.append(d);}parent.append(dl);
  }
  function facts(parent,data) {
    const dl=make('dl','facts');for(const [name,value]of data){const d=make('div');add(d,make('dt','',name),make('dd','',value));dl.append(d);}parent.append(dl);
  }
  function disclosure(parent,title,value,key=title) {
    const d=make('details');d.dataset.key=key;add(d,make('summary','',title),make('pre','',typeof value==='string'?value:JSON.stringify(value,null,2)));parent.append(d);
  }
  function options() {
    const sel=$('campaign'), campaigns=list(S.data?.campaigns);
    if(!S.campaign||S.campaign!=='history'&&!campaigns.some(c=>c.id===S.campaign)) S.campaign=(campaigns.find(c=>c.status==='running')||campaigns.at(-1))?.id||'';
    sel.replaceChildren();for(const c of campaigns)sel.append(new Option(c.id,c.id));
    if(list(S.data?.historical?.candidates).length)sel.append(new Option('Earlier agent experiments','history'));
    if(!campaigns.length&&!sel.options.length)sel.append(new Option('No search rounds yet',''));
    sel.value=S.campaign;
  }
  function statusLabel(c) { return c?.status==='running'?'Search running':c?.status==='historical'?'Earlier experiments':c?.status==='budget_exhausted'?'Evaluation budget used':c?.status==='stopped'?'Search stopped':c?.status==='deadline_reached'?'Time limit reached':c?.status==='stop_requested'?'Finishing current work':'Status not confirmed'; }
  function renderSummary() {
    const target=clear('summary'), c=current(), b=seed();
    const eligible=rows().filter(r=>r.valid&&numeric(r.metrics?.total)&&(!spec(c).cohort_digest||r.cohort_digest===spec(c).cohort_digest));
    const best=S.campaign==='history'?null:[...eligible].sort((x,y)=>x.metrics.total-y.metrics.total)[0];
    const delta=best?reduction(best):null;
    const items=[['Best validated time',seconds(best?.metrics?.total),best?`${best.full_run_count||1} full measurement${best.full_run_count===1?'':'s'}${best.full_run_count>1?' · median':' · needs confirmation'}`:'Choose a search round for a comparable result'],
      ['Change from reference',delta===null?'—':`${Math.abs(delta).toFixed(1)}% ${delta<0?'slower':delta>0?'faster':'change'}`,b?`Reference: ${seconds(b.metrics?.total)}`:'Results use different reference cohorts'],
      ['Fully validated',`${rows().filter(r=>r.valid).length} / ${rows().length}`,'Correctness passed · speed assessed separately']];
    for(const [label,value,note]of items){const box=make('div','summary-item');add(box,make('p','summary-label',label),make('p','summary-value',value),make('p','summary-note',note));target.append(box);}
  }
  function renderNow() {
    const c=current(), target=clear('search-status'), running=c?.status==='running';
    const line=make('div','status-line');line.append(pill(statusLabel(c),running?'running':''));target.append(line);
    const selector=c?.selector, budget=c?.budget||{};
    target.append(make('h3','',selector==='smac'?(running?'SMAC is choosing what to try next.':'A search guided by full results.'):selector==='qwen'?'A bounded model proposal round.':selector==='local-search'||selector==='enumeration'?'A defined set of implementation choices.':'Recorded optimization experiments.'));
    target.append(make('p','search-description',selector==='smac'?'A statistical model learns from full evaluations and ranks the remaining legal configurations. It does not call an LLM.':selector==='qwen'?'Qwen proposes a narrow parameter choice. The same screening and full-validation gates apply.':'Each attempt uses an exact code commit. Screening and full validation run through the shared AMD queue.'));
    const pending=list(c?.evaluations).filter(e=>e.status==='reserved');
    target.append(make('p','meta-line',S.campaign==='history'?'Historical reports; no global winner inferred.':`${c?.usage?.evaluations||0} of ${budget.max_evaluations??'—'} evaluation slots used${pending.length?` · ${pending.length} pending`:''}${budget.deadline_unix?` · deadline ${time(budget.deadline_unix)}`:''}`));
    const agents=clear('agents');
    const active=list(S.data?.workers).filter(w=>/codex|claude|qwen/i.test(String(w.provider))&& !w.stale && /running|coding|evaluating/.test(w.status));
    if(!active.length)agents.append(make('p','empty','No research agent is currently confirmed running.'));
    for(const w of active.slice(0,4)){const item=make('div','agent-row'),desc=make('div');add(desc,make('strong','',w.model||human(w.provider)),make('p','',human(w.direction||w.name||w.id)),make('p','',w.deadline_unix?`Until ${time(w.deadline_unix)} · ${w.host}`:w.host));add(item,desc,pill('Working','running'));agents.append(item);}
    if(active.length>4)agents.append(make('p','meta-line',`${active.length-4} more workers in technical details.`));
  }
  function drawTable(target,candidates,compact=false) {
    clear(target);if(!candidates.length){target.append(make('p','empty','No matching results yet.'));return;}
    const wrap=make('div','table-wrap'),table=make('table'),head=make('thead'),hr=make('tr');
    for(const title of ['Implementation','Validation','First-run time',...(compact?[]:['Change']), ''])hr.append(make('th','',title));head.append(hr);table.append(head);
    const body=make('tbody');for(const c of candidates){const tr=make('tr',S.selected===c.candidate_id?'selected-row':''),name=make('td');add(name,make('div','',candidateName(c)),make('p','cell-subtitle',c.kind==='seed'?'Repeated reference':`${c.full_run_count||0} full run${c.full_run_count===1?'':'s'}`));const validation=make('td');validation.append(pill(...kind(c)));add(tr,name,validation,make('td','number',seconds(c.metrics?.total)));
      if(!compact){const d=reduction(c);tr.append(make('td',`number ${d>0?'positive':d<0?'negative':''}`,d===null?'—':d===0?'Reference':`${Math.abs(d).toFixed(1)}% ${d>0?'faster':'slower'}`));}
      const action=make('td'),button=make('button','text-button','View');button.type='button';button.setAttribute('aria-label',`View ${candidateName(c)}`);button.addEventListener('click',()=>{S.selected=c.candidate_id;showView('results');renderResults();$('result-detail').scrollIntoView({behavior:'smooth',block:'start'});});action.append(button);tr.append(action);body.append(tr);
    }table.append(body);wrap.append(table);target.append(wrap);
  }
  const steps=[
    {title:'Develop an idea',summary:'Codex or Claude investigates a change.',description:'A research agent works on one approach in its own branch. It explains the hypothesis and produces either a code change or guidance for a future search round.',input:'A validated starting point and a bounded brief.',output:'An isolated implementation or a documented proposal.',where:'Your Mac or the Hetzner agent broker.',note:'Guidance is an idea, not an evaluated improvement.'},
    {title:'Choose what to test',summary:'Search within reviewed implementation choices.',description:'The coordinator freezes a legal parameter menu. Enumeration covers small spaces; SMAC learns from full results to select promising untested choices. A materializer produces an exact Git commit.',input:'Allowed parameters, constraints, parents, and a fixed budget.',output:'One candidate commit and its recorded selection rationale.',where:'Coordinator on your Mac; SMAC helper on Hetzner.',note:'The 193 physical design variables are part of the fixed workload. These search parameters change how the simulator is implemented.'},
    {title:'Screen feasibility',summary:'Reject obvious failures before full validation.',description:'The shorter evaluation still computes all 101 frequencies and 193 gradients. It checks the public sensitivity criteria and finite outputs, but omits the finite-difference sanity check and strict saved-array comparison.',input:'An exact commit and a durable queue request.',output:'A provisional pass or a recorded failure.',where:'The shared AMD CPU evaluator.',note:'A screen pass cannot establish full correctness or promote a candidate.'},
    {title:'Validate and measure',summary:'Run the official test and the extra comparison.',description:'The unchanged official benchmark runs the full setup and gradient sanity check. A separate comparison checks saved physical outputs and all 193 gradients. Every phase and the complete first-run time are recorded.',input:'A screened candidate in the fixed environment.',output:'Separate correctness verdicts, timings, and memory evidence.',where:'AMD, one logical CPU and one benchmark at a time.',note:'The 32 GB policy uses a sampled RSS watchdog. It is not a kernel-enforced container limit.'},
    {title:'Learn and continue',summary:'Keep useful results and choose the next attempt.',description:'Only eligible full results from the same cohort inform the validated comparison. The selector learns from those results. The coordinator can combine compatible ideas or review a new operator when the frozen round stalls or ends.',input:'Full validation, phase times, and the recorded baseline.',output:'The next choice, a combination, or a reviewed new round.',where:'Campaign ledger and published GitHub evidence.',note:'A Pareto tradeoff is different from a repeatable total-time win. New combinations require their own evaluation.'}
  ];
  function renderWorkflow() {
    const target=clear('steps');steps.forEach((step,i)=>{const li=make('li'),button=make('button','step-button');button.type='button';button.id=`step-${i}`;button.setAttribute('aria-pressed',String(i===S.step));button.setAttribute('aria-controls','step-detail');const label=make('span');add(label,make('span','step-title',step.title),make('span','step-subtitle',step.summary));add(button,make('span','step-number',String(i+1)),label);button.addEventListener('click',()=>{S.step=i;renderWorkflow();});li.append(button);target.append(li);});
    const step=steps[S.step],detail=clear('step-detail');add(detail,make('p','eyebrow',`Step ${S.step+1} of ${steps.length}`),make('h3','',step.title),make('p','step-description',step.description));facts(detail,[['Input',step.input],['Output',step.output],['Runs on',step.where]]);detail.append(make('p','step-footnote',step.note));
    if(S.step===1){const latest=list(current()?.decisions).filter(d=>d.payload?.selection_origin).at(-1)?.payload;if(latest){const box=make('div','detail-section');box.append(make('h3','','Latest recorded choice'));phaseFacts(box,[['Trained on',`${latest.training_configurations} full configurations`],['Selection method',latest.model_trained?'Learned acquisition ranking':'Startup selection'],['Chosen rank',String(latest.acquisition_rank??'—')]]);detail.append(box);}}
    const topo=clear('topology'),dimensions=round()?.spec?.dimensions||{};
    topo.append(make('p','','These are implementation choices, not changes to the physical problem. A new choice requires a reviewed round specification.'));
    const descriptions={checkpoint:['Checkpointing','Controls recomputation during differentiation.'],prevent_cse:['Prevent common-subexpression elimination','A checkpoint compilation option.'],map_batch_size:['Component mapping batch size','How component updates are grouped.']};
    for(const [key,values]of Object.entries(dimensions)){const row=make('div','topology-row'),left=make('div'),desc=descriptions[key]||[human(key),'Registered implementation option.'];add(left,make('strong','',desc[0]),make('p','',desc[1]));const choices=make('div','choices');for(const v of list(values))choices.append(make('span','choice',v===null?'Default':v===true?'On':v===false?'Off':String(v)));add(row,left,choices);topo.append(row);}
    const limits=Object.values(round()?.spec?.lanes||{}).map(l=>l.stall_limit??3);if(limits.length)topo.append(make('p','step-footnote',`This round uses a stall limit of ${[...new Set(limits)].join(' / ')} terminal non-improvements. Infrastructure failures do not count. Its deadline is fixed.`));
    if(!Object.keys(dimensions).length)topo.append(make('p','empty','Select a search round to see its frozen parameter menu.'));
  }
  function renderResults() {
    let cs=rows();if(S.filter==='valid')cs=cs.filter(c=>c.valid);if(S.filter==='improved')cs=cs.filter(c=>c.valid&&(c.progress?.meaningful_total||c.progress?.meaningful_pareto));
    drawTable($('results-table'),[...cs].sort((a,b)=>(a.metrics?.total??Infinity)-(b.metrics?.total??Infinity)));
    const c=rows().find(x=>x.candidate_id===S.selected),target=clear('result-detail');target.hidden=!c;if(!c)return;
    const header=make('div','detail-header'),title=make('div');add(title,make('h2','',candidateName(c)),make('p','',c.provenance?.hypothesis||c.historical?.hypothesis||'Exact implementation measured under the recorded validation contract.'));const close=make('button','text-button','Close');close.addEventListener('click',()=>{S.selected=null;renderResults();});add(header,title,close);target.append(header);
    const grid=make('div','detail-grid'),timing=make('div'),validation=make('div');timing.append(make('h3','','Timing breakdown'));
    const metrics=c.metrics||{};phaseFacts(timing,[['Complete first run',seconds(metrics.total)],['Setup & imports',seconds(metrics.setup)],['Compilation',seconds(metrics.compilation)],['Forward simulation',seconds(metrics.forward)],['Sensitivity',seconds(metrics.sensitivity)],['Gradients',seconds(metrics.gradient)],['Result transfer',seconds(metrics.transfer)],['Peak memory',memory(metrics.peak_rss_bytes)]]);
    validation.append(make('h3','','What the result means'));const ev=list(current()?.evidence).filter(e=>list(c.evidence_ids).includes(e.evidence_id)&&e.profile==='full').at(-1);phaseFacts(validation,[['Full eligibility',c.valid?'Passed':kind(c)[0]],['Full measurements',String(c.full_run_count||0)],['Meaningful total gain',c.progress?c.progress.meaningful_total?'Yes':'No':'Not assessed'],['Meaningful Pareto gain',c.progress?c.progress.meaningful_pareto?'Yes':'No':'Not assessed'],['Exact Pareto member',c.valid&&typeof c.exact_pareto==='boolean'?c.exact_pareto?'Yes':'No':'Not assessed']]);
    validation.append(make('p','table-note',c.full_run_count>1?'Repeated full measurements are recorded. Inspect their variation before drawing conclusions.':'This is a single measurement or an incomplete evaluation. A speed gain needs repeated confirmation.'));add(grid,timing,validation);target.append(grid);
    const prov=c.provenance||{};if(prov.selection_origin){const section=make('div','detail-section');section.append(make('h3','','Why SMAC selected this attempt'));phaseFacts(section,[['Origin',prov.selection_origin],['Training configurations',String(prov.training_configurations??'—')],['Surrogate trained',prov.model_trained?'Yes':'No / startup'],['Acquisition rank',String(prov.acquisition_rank??'—')],['Acquisition score',numeric(prov.acquisition_score)?prov.acquisition_score.toPrecision(4):'—']]);disclosure(section,'Ranked alternatives',prov.ranked_options||[],'ranks');target.append(section);}
    const ancestry=make('div','detail-section');ancestry.append(make('h3','','Implementation history'));const chain=make('div','lineage');for(const parent of list(c.parents)){const p=rows().find(x=>x.candidate_id===parent);chain.append(make('span','lineage-item',p?candidateName(p):short(parent)));chain.append(make('span','lineage-line'));}chain.append(make('span','lineage-item',candidateName(c)));ancestry.append(chain);target.append(ancestry);
    const links=make('div','links');add(links,commitLink(c.commit_sha),branchLink(c.historical?.branch||current()?.branch));target.append(links);
    const evidence={candidate:c,full_evidence:ev||null,evaluations:list(current()?.evaluations).filter(e=>e.candidate_id===c.candidate_id)};disclosure(target,'Validation and provenance records',evidence,'result-record');
  }
  function renderTechnical() {
    const target=clear('technical-content'),c=current();
    disclosure(target,'Workers and infrastructure',{workers:S.data?.workers,infrastructure:S.data?.infrastructure},'workers');
    disclosure(target,'Search decisions and guidance',{decisions:c?.decisions,guidance:c?.guidance,rounds:c?.rounds},'decisions');
    disclosure(target,'Evaluation queue',{observed_at:S.data?.queue?.observed_at,stale:S.data?.queue?.stale,jobs:S.data?.queue?.jobs},'queue');
    disclosure(target,'Campaign event history',c?.events||[],'events');
    disclosure(target,'Controller log',c?.controller?.log_tail||'No log available.','logs');
    disclosure(target,'System notices',S.data?.alerts||[],'notices');
  }
  const G={graph:null, selected:null, scale:1, signature:'', initialized:false};
  const svg=(tag,attrs={})=>{const n=document.createElementNS('http://www.w3.org/2000/svg',tag);for(const [k,v]of Object.entries(attrs))n.setAttribute(k,String(v));return n;};
  function graphScale(scale,center=true) {
    if(!G.graph)return;
    const viewport=$('graph-viewport'),old=G.scale;
    const x=(viewport.scrollLeft+viewport.clientWidth/2-(G.offsetX||0))/old,y=(viewport.scrollTop+viewport.clientHeight/2)/old;
    G.scale=Math.max(.12,Math.min(1.8,scale));
    const plane=$('graph-plane');plane.style.width=`${G.graph.width*G.scale}px`;plane.style.height=`${G.graph.height*G.scale}px`;
    G.offsetX=Math.max(0,(viewport.clientWidth-G.graph.width*G.scale)/2);
    for(const id of ['graph-nodes','graph-edges']){$(id).style.left=`${G.offsetX}px`;$(id).style.transform=`scale(${G.scale})`;$(id).style.transformOrigin='0 0';}
    $('graph-scale').textContent=`${Math.round(G.scale*100)}%`;
    if(center){viewport.scrollLeft=x*G.scale+G.offsetX-viewport.clientWidth/2;viewport.scrollTop=y*G.scale-viewport.clientHeight/2;}
  }
  function fitGraph(){if(!G.graph)return;const v=$('graph-viewport');graphScale(Math.min((v.clientWidth-40)/G.graph.width,(v.clientHeight-40)/G.graph.height,1),false);v.scrollLeft=0;v.scrollTop=0;}
  function openGraph(){if(!G.graph)return;const v=$('graph-viewport');graphScale(Math.min(1,Math.max(.75,(v.clientWidth-40)/G.graph.width)),false);const anchor=G.graph.nodes.find(n=>n.type==='topology'&&n.campaign===S.campaign)||G.graph.nodes[0];v.scrollTop=G.graph.orientation==='down'?0:Math.max(0,(anchor.y+anchor.height/2)*G.scale-v.clientHeight/2);v.scrollLeft=G.graph.orientation==='down'?Math.max(0,(anchor.x+anchor.width/2)*G.scale+(G.offsetX||0)-v.clientWidth/2):0;}
  function centerNode(id){const n=G.graph?.nodes.find(n=>n.id===id);if(!n)return;const v=$('graph-viewport');graphScale(Math.max(.85,G.scale),false);v.scrollLeft=(n.x+n.width/2)*G.scale+(G.offsetX||0)-v.clientWidth/2;v.scrollTop=(n.y+n.height/2)*G.scale-v.clientHeight/2;}
  function selectGraphNode(id){G.selected=id;paintGraphSelection();renderGraphDetail();}
  function paintGraphSelection(){
    if(!G.graph)return;
    const related=G.selected?SearchDAG.trace(G.graph,G.selected):null, query=$('graph-find').value.trim().toLowerCase();
    let matches=0;
    for(const button of $('graph-nodes').children){const n=G.graph.nodes.find(n=>n.id===button.dataset.node);const match=!query||[n.title,n.subtitle,n.campaign,JSON.stringify(n.record)].join(' ').toLowerCase().includes(query);if(match)matches++;
      button.classList.toggle('dimmed',!match||related&&!related.has(n.id));button.classList.toggle('search-match',!!query&&match);button.setAttribute('aria-pressed',String(n.id===G.selected));}
    for(const p of $('graph-edges').querySelectorAll('path[data-source]')){const active=related&&related.has(p.dataset.source)&&related.has(p.dataset.target);p.classList.toggle('edge-active',!!active);p.classList.toggle('edge-dimmed',!!related&&!active);}
    $('graph-count').textContent=`${G.graph.nodes.length-1} nodes · ${G.graph.edges.length} connections${query?` · ${matches} matches`:''}`;
  }
  function renderGraphDetail(){
    const n=G.graph?.nodes.find(n=>n.id===G.selected),panel=$('graph-inspector');panel.hidden=!n;if(!n)return;
    const target=clear('graph-detail');add(target,make('p','eyebrow',human(n.type)),make('h2','',n.title),pill(n.status||'Recorded'),make('p','graph-description',n.description||n.subtitle));
    if(n.campaign)target.append(make('p','meta-line',`Campaign: ${n.campaign}`));
    teamDetails(target,n);
    if(n.type==='candidate'){
      const a=n.record;phaseFacts(target,[['Complete first run',seconds(a.metrics?.total)],['Compilation',seconds(a.metrics?.compilation)],['Runtime',seconds(a.metrics?.runtime)],['Full measurements',String(a.full_run_count??(a.profile==='full'?1:0))],['Total-time range',seconds(a.metric_ranges?.total)],['Meaningful total gain',a.progress?a.progress.meaningful_total?'Yes':'No':'Not assessed']]);
      const params=Object.entries(a.parameters||{});if(params.length)facts(target,params.map(([k,v])=>[human(k),v===null?'Default':String(v)]));
      const source=commitLink(a.commit_sha||a.sha);if(source)target.append(source);
      const button=make('button','graph-action','Open full result');button.addEventListener('click',()=>{S.campaign=n.campaign;S.selected=n.candidate;options();render();showView('results');});target.append(button);
    }
    const connections=G.graph.edges.filter(e=>e.source===n.id||e.target===n.id);
    const section=make('div','graph-connections');section.append(make('h3','','Connected evidence'));
    for(const e of connections){const incoming=e.target===n.id,other=G.graph.nodes.find(x=>x.id===(incoming?e.source:e.target));const b=make('button','connection-link');add(b,make('span','',other.title),make('small','',`${incoming?'Input':'Output'} · ${e.label}${e.grouping?' · grouping':''}`));b.addEventListener('click',()=>{selectGraphNode(other.id);centerNode(other.id);});section.append(b);}target.append(section);
    disclosure(target,'Source record',n.record,'graph-record');
  }
  function renderTeam(){
    const summary=clear('team-summary'),queue=clear('team-next'),ledger=S.data?.team_search,source=S.data?.team_search_source;
    if(ledger?.schema!=='feyer-team-search-v1'){
      summary.append(make('span','','Shared team queue unavailable · campaign evidence remains separate.'));
      queue.append(make('p','','No shared ledger snapshot is connected. This does not mean the queue is empty. Connect the read-only team snapshot or use the synthetic demo to explore the workflow.'));
      if(source?.error)queue.append(make('p','meta-line',source.error));
      return;
    }
    const tasks=Object.values(ledger.tasks||{}),next=SearchDAG.readyTasks(ledger),observations=Object.values(ledger.observations||{});
    const instances=new Set(observations.map(o=>o.instance).filter(Boolean));
    for(const [value,label]of [[next.length,'ready tasks'],[tasks.filter(t=>t.status==='claimed').length,'claimed tasks'],[tasks.filter(t=>t.status==='stalled').length,'stalled branches'],[instances.size,'instances with evidence']]){const item=make('span');add(item,make('strong','',String(value)),document.createTextNode(` ${label}`));summary.append(item);}
    summary.append(make('span','team-freshness',source?.observed_at?`${source.stale?'Stale snapshot':'Observed'} ${time(source.observed_at)}`:S.data?.demo?'Synthetic team workflow':'Snapshot freshness unknown'));
    if(source?.error)queue.append(make('p','notice',source.error));
    queue.append(make('p','meta-line','Read-only task routing. A claim does not prove a model is running; done does not mean a validated winner. Start work only after a successful CLI claim. Compare evidence within one instance and cohort.'));
    if(!next.length)queue.append(make('p','empty','No currently ready tasks. Inspect dependencies, deadlines, stalled directions, and blocked work below.'));
    const ordered=[...next,...tasks.filter(t=>!next.some(n=>n.id===t.id))];
    for(const t of ordered){const row=make('div','team-task-row'),left=make('div');add(left,make('strong','',`${human(t.kind)} · ${t.id}`),make('p','',t.hypothesis),make('p','meta-line',`${human(t.status)} · ${t.owner||'Unclaimed'}${t.instance?` / ${t.instance}`:''}${list(t.depends_on).length?` · requires ${t.depends_on.join(', ')}`:''}${t.resolution?` · ${t.resolution}`:''}`));const b=make('button','graph-action','Inspect branch');b.addEventListener('click',()=>{$('graph-scope').value='team';renderGraph();const id=JSON.stringify(['team','task',t.id]);selectGraphNode(id);centerNode(id);$('graph-viewport').scrollIntoView({block:'center',behavior:'smooth'});});add(row,left,b);queue.append(row);}
    if(!tasks.length)queue.append(make('p','empty','The shared ledger is connected and contains no admitted tasks yet.'));
  }
  function teamDetails(target,n){
    if(n.teamTask){
      const t=n.record;facts(target,[['State',human(t.status)],['Owner',t.owner||'Unclaimed'],['Instance',t.instance||'Not assigned'],['Candidate budget',String(t.max_candidates??'Unknown')],['Deadline',t.deadline_unix?new Date(t.deadline_unix*1000).toLocaleString():'Not recorded'],['Full repeats',String(t.minimum_full_runs??'Unknown')],['Gain threshold',`${t.minimum_gain_fraction!==undefined?t.minimum_gain_fraction*100+'%':'Unknown'} / ${seconds(t.minimum_gain_seconds)}`]]);
      target.append(make('p','table-note',t.kind==='refine'?'One successor per refinement task. Its frozen parent is the incumbent; a new improvement gets a new task.':t.kind==='combine'?'Measure both parents and the combination on the same host. The combination must beat the better parent; preserve it if the combination regresses.':t.kind==='confirm'?'Confirmation is for the exact candidate or merged SHA. Task completion alone does not establish the final winner.':'This task is routed by a human owner. The frontend does not dispatch models or submit benchmarks.'));
    }
    if(n.type==='team-candidate'){
      const a=n.record,groups=new Map();
      for(const o of a.observations){const e=o.evidence,k=JSON.stringify([o.instance,e.cohort_digest]);if(!groups.has(k))groups.set(k,{instance:o.instance,cohort:e.cohort_digest,values:[],invalid:false});const g=groups.get(k);if(e.eligible_full&&numeric(e.metrics?.total))g.values.push(e.metrics.total);if(e.category==='invalid_candidate')g.invalid=true;}
      for(const g of groups.values()){const values=g.values.sort((a,b)=>a-b),count=values.length,median=count?(values[Math.floor((count-1)/2)]+values[Math.floor(count/2)])/2:null;const section=make('div','detail-section');section.append(make('h3','',g.instance));phaseFacts(section,[['Cohort',short(g.cohort)||'Unknown'],['Eligible full runs',String(count)],['Median first run',seconds(median)],['Observed range',count?`${seconds(values[0])} – ${seconds(values.at(-1))}`:'—'],['Numerical review',g.invalid?'Required':'No recorded rejection']]);target.append(section);}
      add(target,make('p','table-note','These are separate instance/cohort observations, never a pooled score. Final comparison requires repeated candidate and parent runs under the same policy.'),commitLink(a.sha));
    }
  }

  function renderGraph(){
    $('graph-history').disabled=$('graph-scope').value!=='all';
    if(!G.initialized&&S.data?.team_search?.schema==='feyer-team-search-v1')$('graph-scope').value='team';
    const config={team:$('graph-scope').value==='team',campaign:$('graph-scope').value==='campaign'?S.campaign:null,history:$('graph-scope').value==='all'?$('graph-history').checked:S.campaign==='history',evaluations:$('graph-evaluations').checked};
    const graph=SearchDAG.layout(SearchDAG.build(S.data||{},config),$('graph-direction').value);
    const signature=JSON.stringify(graph);
    if(signature===G.signature)return;
    const oldIds=G.graph?.nodes.map(n=>n.id).join('|');G.signature=signature;G.graph=graph;
    const activeNode=document.activeElement?.dataset?.node;
    const container=clear('graph-nodes'),lines=clear('graph-edges');
    container.style.width=`${graph.width}px`;container.style.height=`${graph.height}px`;lines.setAttribute('width',graph.width);lines.setAttribute('height',graph.height);
    const defs=svg('defs'),marker=svg('marker',{id:'dag-arrow',viewBox:'0 0 10 10',refX:9,refY:5,markerWidth:6,markerHeight:6,orient:'auto-start-reverse'});marker.append(svg('path',{d:'M 0 0 L 10 5 L 0 10 z',fill:'#79879a'}));defs.append(marker);lines.append(defs);
    const byId=new Map(graph.nodes.map(n=>[n.id,n]));
    for(const e of graph.edges){const a=byId.get(e.source),b=byId.get(e.target);const down=graph.orientation==='down',x1=down?a.x+a.width/2:a.x+a.width,y1=down?a.y+a.height:a.y+a.height/2,x2=down?b.x+b.width/2:b.x,y2=down?b.y:b.y+b.height/2,mid=down?(y1+y2)/2:(x1+x2)/2;const path=down?`M ${x1} ${y1} C ${x1} ${mid}, ${x2} ${mid}, ${x2} ${y2-4}`:`M ${x1} ${y1} C ${mid} ${y1}, ${mid} ${y2}, ${x2-4} ${y2}`;const p=svg('path',{d:path,class:`dag-edge${e.grouping?' grouping':''}`,'marker-end':'url(#dag-arrow)'});p.dataset.source=e.source;p.dataset.target=e.target;const title=svg('title');title.textContent=`${a.title} → ${b.title}: ${e.label}`;p.append(title);lines.append(p);}
    for(const n of graph.nodes){const b=make('button',`dag-node node-${n.type}${n.valid?' node-valid':''}${n.failed?' node-failed':''}`);b.type='button';b.dataset.node=n.id;b.style.left=`${n.x}px`;b.style.top=`${n.y}px`;b.style.width=`${n.width}px`;b.style.height=`${n.height}px`;b.setAttribute('aria-label',`${human(n.type)}: ${n.title}. ${n.subtitle}. ${n.status||''}`);b.title=`${n.title}\n${n.subtitle}\n${n.status||''}`;add(b,make('span','node-kind',human(n.type)),make('strong','node-title',n.title),make('span','node-subtitle',n.subtitle),make('span','node-status',n.status||'Recorded'));b.addEventListener('click',()=>selectGraphNode(n.id));container.append(b);}
    if(G.selected&&!byId.has(G.selected))G.selected=null;
    $('graph-empty').hidden=graph.nodes.length>1;
    $('graph-workspace').dataset.warnings=String(graph.warnings.length);
    if(graph.warnings.length){$('notice').hidden=false;$('notice').textContent=[...new Set(graph.warnings)].join(' ');}
    graphScale(G.scale,false);paintGraphSelection();renderGraphDetail();
    if(activeNode){const button=[...container.children].find(b=>b.dataset.node===activeNode);button?.focus({preventScroll:true});}
    if(!G.initialized&&S.view==='graph'){
      G.initialized=true;requestAnimationFrame(openGraph);
    }else if(oldIds!==graph.nodes.map(n=>n.id).join('|')&&G.selected)centerNode(G.selected);
  }
  for(const id of ['graph-scope','graph-history','graph-evaluations','graph-direction'])$(id).addEventListener('change',()=>{G.selected=null;renderGraph();fitGraph();});
  new ResizeObserver(()=>{if(G.graph)graphScale(G.scale,false);}).observe($('graph-viewport'));
  $('graph-fit').addEventListener('click',fitGraph);
  $('graph-reset').addEventListener('click',()=>graphScale(1));
  $('graph-minus').addEventListener('click',()=>graphScale(G.scale/1.2));
  $('graph-plus').addEventListener('click',()=>graphScale(G.scale*1.2));
  $('graph-close').addEventListener('click',()=>{selectGraphNode(null);});
  $('graph-find').addEventListener('input',paintGraphSelection);
  $('graph-find').addEventListener('keydown',e=>{if(e.key==='Enter'){const match=[...$('graph-nodes').children].find(b=>b.classList.contains('search-match'));if(match){selectGraphNode(match.dataset.node);centerNode(match.dataset.node);match.focus({preventScroll:true});}}});
  $('graph-viewport').addEventListener('keydown',e=>{if(e.key==='Escape'){selectGraphNode(null);}if((e.key==='+'||e.key==='=')&&G.graph){e.preventDefault();graphScale(G.scale*1.2);}if(e.key==='-'&&G.graph){e.preventDefault();graphScale(G.scale/1.2);}});
  $('graph-fullscreen').addEventListener('click',()=>{const expanded=$('graph').classList.toggle('graph-expanded');$('graph-fullscreen').textContent=expanded?'Exit expanded view':'Expand';$('graph-fullscreen').setAttribute('aria-pressed',String(expanded));});

  let selectedProfile='';
  const profileKey=r=>JSON.stringify([r.instance,r.job_id,r.candidate_sha,r.profile]);
  function renderProfiler(){
    const reports=list(S.data?.profiler_reports),source=S.data?.profiler_source,query=$('profiler-filter').value.trim().toLowerCase();
    const matching=reports.filter(r=>[r.job_id,r.candidate_sha,r.instance].join(' ').toLowerCase().includes(query)).sort((a,b)=>(stamp(b.observed_at)||0)-(stamp(a.observed_at)||0));
    const select=clear('profiler-select'),target=clear('profiler-detail');
    if(!matching.some(r=>profileKey(r)===selectedProfile))selectedProfile=matching.length?profileKey(matching.find(r=>r.status==='ok'&&r.eligible_full)||matching[0]):'';
    for(const r of matching)select.append(new Option(`${short(r.candidate_sha)} · ${short(r.job_id)} · ${r.profile||'unknown'} · ${r.instance||'instance unrecorded'}`,profileKey(r)));
    select.value=selectedProfile;
    $('profiler-source').textContent=!reports.length?`Profiler unavailable${source?.error?` · ${source.error}`:''}`:`${reports.length} recorded reports · ${source?.observed_at?`${source.stale?'stale file observation':'file observed'} ${time(source.observed_at)}`:'source freshness unknown'}${source?.error?` · ${source.error}`:''}`;
    const r=matching.find(r=>profileKey(r)===selectedProfile);
    if(!r){target.append(make('p','empty',reports.length?'No reports match this job or commit.':'No profiler export is connected. This does not imply zero runtime or a completed profile.'));return;}
    const heading=make('div','detail-header'),identity=make('div');add(identity,make('h3','',`Commit ${short(r.candidate_sha)} · job ${short(r.job_id)}`),make('p','',`${r.instance||'Instance not recorded'} · cohort ${short(r.cohort_digest)||'not recorded'}`));add(heading,identity,pill(r.status==='conflicting_artifacts'?'Conflicting artifacts':r.status==='invalid_report'?'Invalid timing report':r.eligible_full?'Eligible full observation':'Not full validated',r.eligible_full?'valid':''));target.append(heading);
    phaseFacts(target,[['Complete first run',seconds(r.first_run_seconds)],['Recorded phase sum',seconds(r.phase_sum_seconds)],['Unattributed time',seconds(r.unattributed_seconds)],['Job wall time',seconds(r.job_wall_seconds)]]);
    target.append(make('p','table-note','This is one observed job, not a confirmed winner. Phase contributions locate measured cost; they do not identify an unmeasured source-code hotspot or predict a realized optimization gain.'));
    if(r.status==='ok'){
      const chart=make('div','profiler-phases');chart.append(make('h3','','First-run phase contributions'));
      for(const phase of [...list(r.phases)].sort((a,b)=>(b.seconds??0)-(a.seconds??0))){const row=make('div','profiler-phase'),meter=make('meter');meter.min=0;meter.max=1;meter.value=numeric(phase.share)?Math.max(0,Math.min(1,phase.share)):0;meter.setAttribute('aria-label',`${human(phase.name||phase.key)}: ${numeric(phase.share)?(phase.share*100).toFixed(1)+'%':'share unavailable'}`);add(row,make('span','',human(phase.name||phase.key)),meter,make('span','number',seconds(phase.seconds)),make('span','number',numeric(phase.share)?`${(phase.share*100).toFixed(1)}%`:'—'));chart.append(row);}target.append(chart);
    }
    const notes=[...list(r.limits),...list(r.issues)];for(const note of notes)target.append(make('p','meta-line',typeof note==='string'?note:JSON.stringify(note)));
    add(target,commitLink(r.candidate_sha));disclosure(target,'Warm timings (separate measurement)',r.warm_timing||{},'profile-warm');disclosure(target,'Validation and complete profiler record',r,'profile-record');
  }
  $('profiler-select').addEventListener('change',e=>{selectedProfile=e.target.value;renderProfiler();});
  $('profiler-filter').addEventListener('input',renderProfiler);

  function render() {
    const focused=document.activeElement?.id;
    const opened=[...document.querySelectorAll('details[open]')].map(n=>n.dataset.key);
    const c=current(), notice=$('notice');
    const pending=list(c?.lanes).some(l=>l.inflight_candidate), errors=list(c?.alerts);
    notice.hidden=true;
    if(S.data?.demo){notice.textContent='Demo data · synthetic research and measurements for frontend development.';notice.hidden=false;}
    else if(S.data?.snapshot){notice.textContent='Saved snapshot · this is a static observation, not live host status.';notice.hidden=false;}
    else if(S.data?.storage?.free_bytes<100_000_000){notice.textContent='Local storage is almost full. New result logging may be interrupted.';notice.hidden=false;}
    else if(pending&&c?.controller?.process_alive===false){notice.textContent='The local controller has stopped with work still pending. Remote results remain available; see technical details.';notice.hidden=false;}
    else if(S.data?.queue?.enabled&&S.data.queue.stale&&S.data.queue.error){notice.textContent='The AMD connection is unavailable. Showing the last recorded results.';notice.hidden=false;}
    $('round-caption').textContent=c?`${statusLabel(c)}${c.source_updated_at?` · last evidence ${time(c.source_updated_at)}`:''}`:'No search evidence available.';
    renderProfiler();renderTeam();renderGraph();renderSummary();renderNow();drawTable($('latest'),rows().filter(r=>r.kind!=='seed').slice(-3).reverse(),true);renderWorkflow();renderResults();renderTechnical();
    for(const d of document.querySelectorAll('details[data-key]'))d.open=opened.includes(d.dataset.key);
    if(focused&&document.activeElement===document.body&&$(focused))$(focused).focus({preventScroll:true});
    $('freshness').textContent=`${S.data?.snapshot?'Saved snapshot · source time':S.data?.demo?'Synthetic demo · example time':'Read-only · refreshed'} ${time(S.data?.generated_at)}${S.data?.queue?.enabled?` · AMD ${S.data.queue.stale?'last observation':'connected'}`:''}`;
  }
  function showView(view) {
    if(!['graph','overview','workflow','profiler','results'].includes(view))view='graph';S.view=view;
    for(const id of ['graph','overview','workflow','profiler','results'])$(id).hidden=id!==view;
    const index=['graph','overview','workflow','profiler','results'].indexOf(view);$('navigation').setAttribute('active-tab-index',String(index));if(customElements.get('p-tabs-bar'))$('navigation').activeTabIndex=index;
    for(const button of document.querySelectorAll('[data-view]'))button.setAttribute('aria-selected',String(button.dataset.view===view));
    document.body.classList.toggle('showing-graph',view==='graph');
    if(view==='graph'&&G.graph&&!G.initialized){G.initialized=true;requestAnimationFrame(openGraph);}

  }
  async function refresh() {
    if(S.fetching)return;S.fetching=true;
    try {const response=await fetch('/api/state',{cache:'no-store'});if(!response.ok)throw new Error(`HTTP ${response.status}`);const data=await response.json();if(!Array.isArray(data.campaigns))throw new Error('Unexpected data');S.data=data;options();render();$('connection').textContent=data.demo?'Synthetic demo':data.snapshot?'Saved snapshot':`Updated ${time(data.generated_at)}`;}
    catch(e){$('connection').textContent='Connection unavailable';$('notice').hidden=false;$('notice').textContent='The dashboard cannot refresh. Any visible results are the last successful observation.';}
    finally{S.fetching=false;}
  }
  $('campaign').addEventListener('change',e=>{S.campaign=e.target.value;S.selected=null;render();});
  document.querySelector('.brand').addEventListener('click',e=>{e.preventDefault();showView('graph');window.scrollTo({top:0,behavior:'smooth'});});
  for(const b of document.querySelectorAll('[data-view]'))b.addEventListener('click',()=>showView(b.dataset.view));
  $('navigation').addEventListener('update',e=>{if(e.target===$('navigation'))showView(['graph','overview','workflow','profiler','results'][e.detail.activeTabIndex]);});
  for(const a of document.querySelectorAll('p-accordion'))a.addEventListener('update',e=>{if(e.target===a)a.open=e.detail.open;});
  $('show-workflow').addEventListener('click',()=>showView('workflow'));$('show-results').addEventListener('click',()=>showView('results'));
  $('result-filter').addEventListener('change',e=>{S.filter=e.target.value;renderResults();});
  $('technical-toggle').addEventListener('click',()=>{$('technical').hidden=!$('technical').hidden;$('technical-toggle').textContent=$('technical').hidden?'Technical details':'Hide technical details';if(!$('technical').hidden)$('technical').scrollIntoView({behavior:'smooth'});});
  document.addEventListener('visibilitychange',()=>{if(!document.hidden)refresh();});
  showView(location.hash.slice(1));refresh();setInterval(()=>{if(!document.hidden)refresh();},5000);
})();
