/* Read-only presentation of existing campaign evidence. PDS v4 supplies UI primitives. */
'use strict';
(() => {
  const $ = id => document.getElementById(id);
  const REPO = 'https://github.com/timbtz/feyer-search-lab';
  const S = {data:null, campaign:'', view:'overview', step:0, selected:null, filter:'all', fetching:false};
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
  function render() {
    const focused=document.activeElement?.id;
    const opened=[...document.querySelectorAll('details[open]')].map(n=>n.dataset.key);
    const c=current(), notice=$('notice');
    const pending=list(c?.lanes).some(l=>l.inflight_candidate), errors=list(c?.alerts);
    notice.hidden=true;
    if(S.data?.storage?.free_bytes<100_000_000){notice.textContent='Local storage is almost full. New result logging may be interrupted.';notice.hidden=false;}
    else if(pending&&c?.controller?.process_alive===false){notice.textContent='The local controller has stopped with work still pending. Remote results remain available; see technical details.';notice.hidden=false;}
    else if(S.data?.queue?.enabled&&S.data.queue.stale&&S.data.queue.error){notice.textContent='The AMD connection is unavailable. Showing the last recorded results.';notice.hidden=false;}
    $('round-caption').textContent=c?`${statusLabel(c)}${c.source_updated_at?` · last evidence ${time(c.source_updated_at)}`:''}`:'No search evidence available.';
    renderSummary();renderNow();drawTable($('latest'),rows().filter(r=>r.kind!=='seed').slice(-3).reverse(),true);renderWorkflow();renderResults();renderTechnical();
    for(const d of document.querySelectorAll('details[data-key]'))d.open=opened.includes(d.dataset.key);
    if(focused&&document.activeElement===document.body&&$(focused))$(focused).focus({preventScroll:true});
    $('freshness').textContent=`Read-only · refreshed ${time(S.data?.generated_at)}${S.data?.queue?.enabled?` · AMD ${S.data.queue.stale?'last observation':'connected'}`:''}`;
  }
  function showView(view) {
    if(!['overview','workflow','results'].includes(view))view='overview';S.view=view;
    for(const id of ['overview','workflow','results'])$(id).hidden=id!==view;
    const index=['overview','workflow','results'].indexOf(view);$('navigation').setAttribute('active-tab-index',String(index));if(customElements.get('p-tabs-bar'))$('navigation').activeTabIndex=index;
    for(const button of document.querySelectorAll('[data-view]'))button.setAttribute('aria-selected',String(button.dataset.view===view));

  }
  async function refresh() {
    if(S.fetching)return;S.fetching=true;
    try {const response=await fetch('/api/state',{cache:'no-store'});if(!response.ok)throw new Error(`HTTP ${response.status}`);const data=await response.json();if(!Array.isArray(data.campaigns))throw new Error('Unexpected data');S.data=data;options();render();$('connection').textContent=`Updated ${time(data.generated_at)}`;}
    catch(e){$('connection').textContent='Connection unavailable';$('notice').hidden=false;$('notice').textContent='The dashboard cannot refresh. Any visible results are the last successful observation.';}
    finally{S.fetching=false;}
  }
  $('campaign').addEventListener('change',e=>{S.campaign=e.target.value;S.selected=null;render();});
  document.querySelector('.brand').addEventListener('click',e=>{e.preventDefault();showView('overview');window.scrollTo({top:0,behavior:'smooth'});});
  for(const b of document.querySelectorAll('[data-view]'))b.addEventListener('click',()=>showView(b.dataset.view));
  $('navigation').addEventListener('update',e=>{if(e.target===$('navigation'))showView(['overview','workflow','results'][e.detail.activeTabIndex]);});
  for(const a of document.querySelectorAll('p-accordion'))a.addEventListener('update',e=>{if(e.target===a)a.open=e.detail.open;});
  $('show-workflow').addEventListener('click',()=>showView('workflow'));$('show-results').addEventListener('click',()=>showView('results'));
  $('result-filter').addEventListener('change',e=>{S.filter=e.target.value;renderResults();});
  $('technical-toggle').addEventListener('click',()=>{$('technical').hidden=!$('technical').hidden;$('technical-toggle').textContent=$('technical').hidden?'Technical details':'Hide technical details';if(!$('technical').hidden)$('technical').scrollIntoView({behavior:'smooth'});});
  document.addEventListener('visibilitychange',()=>{if(!document.hidden)refresh();});
  showView(location.hash.slice(1));refresh();setInterval(()=>{if(!document.hidden)refresh();},5000);
})();
