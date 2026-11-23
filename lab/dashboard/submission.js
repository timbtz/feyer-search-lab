/* Read-only exact-source dossier. Evidence never promotes a candidate automatically. */
const SubmissionReport = (() => {
  const list = value => Array.isArray(value) ? value : [];
  const numeric = value => typeof value === 'number' && Number.isFinite(value);
  const seconds = value => numeric(value) ? `${value.toFixed(3)} s` : 'Not recorded';
  function transferPairs(candidate) {
    const pairs = [];
    for (const artifact of list(candidate?.artifacts)) {
      const receipt = artifact.data;
      if (receipt?.schema !== 'feyer-official-transfer-run-v1' || receipt.candidate_sha !== candidate.sha) continue;
      for (const run of list(receipt.checks).filter(r => r.name === 'candidate' && r.sha === candidate.sha)) {
        const reference = list(receipt.checks).find(r => r.name === 'reference' && r.setup === run.setup && r.sha === receipt.reference_sha);
        const comparison = list(receipt.comparisons).find(r => r.setup === run.setup);
        pairs.push({setup:run.setup, run, reference, comparison, scope:receipt.timing_scope,
          source:artifact.path, ranking_eligible:receipt.ranking_eligible === true,
          saved: numeric(reference?.total_seconds) && numeric(run.total_seconds) ? reference.total_seconds-run.total_seconds : null});
      }
    }
    return pairs;
  }
  function evidenceStatus(data) {
    if (data?.passed === false) return 'Needs review';
    if (data?.passed === true) return 'Passed in recorded scope';
    if (data?.status) return String(data.status).replaceAll('_',' ');
    if (data?.validation?.passed === false) return 'Validation failed';
    return 'Recorded evidence';
  }
  function benchmarkRuns(candidate) {
    return list(candidate?.artifacts).filter(a => a.data?.source?.commit === candidate.sha &&
      a.data.source.modified === false && numeric(a.data?.timing_seconds?.end_to_end) &&
      list(a.data.phases).length).map(a => {
        const logPath = a.path.endsWith('/report.json') ? a.path.replace(/report\.json$/, 'stdout.log') : a.path.replace(/\.json$/, '/stdout.log');
        return {artifact:a, report:a.data, log:list(candidate.artifacts).find(x=>x.path===logPath),
          label:a.path.replace(/^.*\/fastest\//,'')};
      });
  }
  function defaultCandidate(dossier) {
    return list(dossier?.candidates).find(c=>c.sha===dossier?.selected_sha)?.sha || list(dossier?.candidates)[0]?.sha;
  }
  function filteredJobs(data, query) {
    const q = query.trim().toLowerCase();
    return list(data?.jobs).filter(r => !q || [r.id,r.sha,r.agent,r.branch,r.direction,r.hypothesis,r.status,r.profile,r.official_check,r.strict_check].join(' ').toLowerCase().includes(q))
      .sort((a,b)=>(b.updated_at||b.created_at||0)-(a.updated_at||a.created_at||0));
  }
  if (typeof document === 'undefined') return {transferPairs,evidenceStatus,filteredJobs,benchmarkRuns,defaultCandidate};
  const el = (tag, cls, text) => {const node=document.createElement(tag);if(cls)node.className=cls;if(text!==undefined)node.textContent=String(text);return node;};
  const $ = id => document.getElementById(id);
  const link = (text,url) => {const a=el('a','',text);a.href=url;a.target='_blank';a.rel='noopener noreferrer';return a;};
  const details = (parent,title,key) => {const d=el('details','dossier-disclosure');d.dataset.key=key;d.append(el('summary','',title));parent.append(d);return d;};
  const raw = (parent,title,data,key) => {const d=details(parent,title,key);d.append(el('pre','evidence-json',typeof data==='string'?data:JSON.stringify(data,null,2)));return d;};
  const table = (parent,headers,rows) => {const wrap=el('div','dossier-table-wrap'),t=el('table','dossier-table'),thead=el('thead'),tr=el('tr');headers.forEach(v=>tr.append(el('th','',v)));thead.append(tr);t.append(thead);const body=el('tbody');rows.forEach(row=>{const r=el('tr');row.forEach(v=>r.append(el('td','',v)));body.append(r);});t.append(body);wrap.append(t);parent.append(wrap);};
  let state=null, selected=null, signature='', jobLimit=30;
  function renderCandidate() {
    const dossier=state?.submission, candidates=list(dossier?.candidates);
    const select=$('submission-select');
    if(!select)return;
    if(!candidates.some(c=>c.sha===selected))selected=defaultCandidate(dossier);
    const optionsKey=candidates.map(c=>c.sha+c.title).join();
    if(select.dataset.signature!==optionsKey){select.replaceChildren();for(const c of candidates){const option=el('option','',`${c.sha.slice(0,8)} · ${c.title}`);option.value=c.sha;select.append(option);}select.dataset.signature=optionsKey;}
    select.value=selected||'';
    const c=candidates.find(c=>c.sha===selected),target=$('submission-detail');
    const next=JSON.stringify([dossier,c?.sha]);if(next===signature)return;signature=next;
    target.replaceChildren();
    if(!c){target.append(el('p','empty','No submission dossier in this snapshot. Refresh the evidence export to include exact source and transfer audits.'));return;}
    target.append(el('p','dossier-selection',dossier.selection_status||'Final selection not recorded.'),el('h2','',c.title),el('p','',c.summary));
    const identity=el('p','meta-line');identity.append('Exact revision ',link(c.sha,`https://github.com/timbtz/feyer-search-lab/commit/${c.sha}`),' · Baseline ',link(dossier.baseline_sha.slice(0,12),`https://github.com/timbtz/feyer-search-lab/commit/${dossier.baseline_sha}`));target.append(identity);
    const stats=el('div','dossier-stats');for(const [value,label] of [[list(c.files).length,'changed source files'],[list(c.files).reduce((n,f)=>n+f.added,0),'added lines'],[list(c.files).reduce((n,f)=>n+f.removed,0),'removed lines'],[list(c.artifacts).length,'retained evidence artifacts']]){const box=el('div');box.append(el('strong','',value),el('span','',label));stats.append(box);}target.append(stats);
    for(const issue of list(c.issues))target.append(el('p','notice',issue));
    target.append(el('h3','','Measured transfer results'));
    const pairs=transferPairs(c);
    if(pairs.length){table(target,['Setup','Reference first run','Candidate first run','Observed decrease','Official check','Strict arrays'],pairs.map(p=>[p.setup,seconds(p.reference?.total_seconds),seconds(p.run.total_seconds),seconds(p.saved),p.run.official?.passed===true?'Passed':p.run.official?.passed===false?'Failed':'Unknown',p.comparison?.passed===true?'Passed':p.comparison?.passed===false?'Needs review':'Unknown']));target.append(el('p','meta-line',pairs[0].scope));target.append(el('p','meta-line','One fresh-process pair per setup in this table. Warm repetitions are separate. These support receipts do not establish queue promotion or isolated savings for individual code changes.'));}
    else target.append(el('p','muted','No exact-candidate official transfer receipt recorded. See archived checks below.'));
    const runs=benchmarkRuns(c);
    target.append(el('h3','','Detailed benchmark runs and logs'),el('p','muted','Each row is a separate fresh-process report for this exact revision. Expand it for all first-run phases, warm repetitions, validation and the associated stdout log. Diagnostic and failed-launch logs remain in the audit archive below.'));
    if(runs.length)table(target,['Recorded run','First run','Trace / lower / compile','Warm median','Log'],runs.map(r=>[r.label,seconds(r.report.timing_seconds.end_to_end),seconds(r.report.timing_seconds.trace_lower_and_compile),seconds(r.report.timing_seconds.runtime_median),r.log?(r.log.truncated===false?'Complete retained log':'Retained log excerpt'):'Not retained']));
    else target.append(el('p','muted','No detailed benchmark reports retained for this revision.'));
    for(const r of runs){
      const d=details(target,`${r.label} · ${seconds(r.report.timing_seconds.end_to_end)} first run · phases and log`,`benchmark-${c.sha}-${r.artifact.path}`);
      d.append(el('p','meta-line',`Source ${r.report.source.commit} · measured ${r.report.measured_at_utc||'time not recorded'} · ${r.report.benchmark}`));
      table(d,['First-run phase','Seconds'],r.report.phases.map(p=>[p.name||p.key,seconds(p.seconds)]));
      table(d,['Warm repetition','Seconds'],list(r.report.timing_seconds.runtime_samples).map((t,i)=>[i+1,seconds(t)]));
      if(r.log){d.append(el('h4','',r.log.truncated===false?'Complete retained stdout log':'Retained stdout excerpt'),el('pre','evidence-json',r.log.data));}
      else d.append(el('p','meta-line','No matching stdout artifact was retained.'));
      raw(d,'Validation, environment and complete timing report',r.report,`benchmark-report-${c.sha}-${r.artifact.path}`);
    }
    target.append(el('h3','','What changed in the implementation'),el('p','muted','Each explanation links to exact source lines at this revision. Timing is measured for whole candidates and benchmark phases; individual lines have no measured speedup attribution.'));
    const concepts=el('div','dossier-concepts');
    for(const [i,concept] of list(c.concepts).entries()){
      const card=el('article','surface-card dossier-concept');card.append(el('p','eyebrow',concept.target),el('h4','',concept.title));
      const before=el('p');before.append(el('strong','','Before: '),concept.before);const after=el('p');after.append(el('strong','','Now: '),concept.after);card.append(before,after);
      for(const ref of list(concept.refs)){
        const file=list(c.files).find(f=>f.path===ref.path),symbol=file?.symbols?.[ref.symbol];
        if(symbol){const row=el('p','source-reference');row.append(link(`${ref.path}:${symbol.start}–${symbol.end} · ${ref.symbol}`,`${file.source_url}#L${symbol.start}-L${symbol.end}`));const b=el('button','text-button','Show changed lines');b.type='button';b.addEventListener('click',()=>{const d=$(`source-${c.sha}-${ref.path.replaceAll('/','-')}`);if(d){d.open=true;d.scrollIntoView({block:'start',behavior:'smooth'});}});row.append(b);card.append(row);}
        else card.append(el('p','meta-line',`${ref.path} · ${ref.symbol} · source location unavailable`));
      }
      concepts.append(card);
    }target.append(concepts);
    target.append(el('h3','','Line-by-line source changes'),el('p','muted','Full diff against the fixed baseline. Old and new line numbers are shown separately. Green lines were added; red lines were removed.'));
    for(const file of list(c.files)){
      const d=details(target,`${file.path} · +${file.added} / −${file.removed}`,`code-${c.sha}-${file.path}`);d.id=`source-${c.sha}-${file.path.replaceAll('/','-')}`;
      const links=el('p','source-reference');links.append(link('Baseline source',file.baseline_url),' · ',link('Candidate source',file.source_url));d.append(links);
      for(const hunk of list(file.hunks)){
        const pre=el('pre','source-diff');pre.setAttribute('aria-label',`${file.path}, baseline line ${hunk.old_start}, candidate line ${hunk.new_start}`);
        pre.append(el('span','diff-heading',`@@ baseline ${hunk.old_start} / candidate ${hunk.new_start} @@\n`));
        for(const line of list(hunk.lines)){const row=el('span',`diff-line diff-${line.kind}`);row.append(el('span','diff-number',line.old??''),el('span','diff-number',line.new??''),el('span','diff-sign',line.kind==='added'?'+':line.kind==='removed'?'−':' '),el('span','',line.text+'\n'));pre.append(row);}d.append(pre);
      }
    }
    target.append(el('h3','','Audits, phase timings and retained logs'),el('p','muted','Artifacts keep their recorded verdicts, tolerance policies and scope. File observation time is not a new measurement. Association without an embedded SHA is explicitly labelled.'));
    for(const [i,a] of list(c.artifacts).entries()){
      const d=details(target,`${a.path.replace(/^.*\/fastest\//,'')} · ${typeof a.data==='string'?(a.truncated===false?'Complete retained log':'Log excerpt'):evidenceStatus(a.data)}`,`artifact-${c.sha}-${a.path}`);
      d.append(el('p','meta-line',`${a.path} · ${a.identity_status.replaceAll('_',' ')} · observed ${new Date(a.observed_at*1000).toLocaleString()}`));
      if(a.data?.scope||a.data?.timing_scope)d.append(el('p','',a.data.scope||a.data.timing_scope));
      if(list(a.data?.phases).length)table(d,['Phase','Seconds'],a.data.phases.map(p=>[p.name||p.key,seconds(p.seconds)]));
      const checks=list(a.data?.checks).filter(x=>x.passed===false||x.status==='failed');if(checks.length)d.append(el('p','notice',`${checks.length} recorded checks need review. Inspect the exact tolerances and results below.`));
      raw(d,typeof a.data==='string'?'Read log excerpt':'Read complete retained record',a.data,`artifact-raw-${c.sha}-${i}`);
    }
    const jobsButton=el('button','graph-action','Inspect evaluator runs for this revision');jobsButton.addEventListener('click',()=>{$('archive-query').value=c.sha;jobLimit=30;renderJobs();$('tab-archive').click();});target.append(jobsButton);
  }
  function renderJobs(){
    if(!$('archive-list'))return;
    const rows=filteredJobs(state,$('archive-query').value),target=$('archive-list');target.replaceChildren();$('archive-count').textContent=`${rows.length} matching runs · showing ${Math.min(jobLimit,rows.length)}. Screen/full and official/strict outcomes remain separate.`;
    for(const r of rows.slice(0,jobLimit)){
      const d=details(target,`${r.sha?.slice(0,8)||'Unknown SHA'} · ${r.profile||'Unknown profile'} · ${seconds(r.metrics?.total)} · ${r.status||'Unknown'}`,`archive-${r.id}`);
      d.append(el('p','',r.recorded_feedback?.summary||r.hypothesis||'No recorded hypothesis'),el('p','meta-line',`${r.id} · ${r.branch||'Unknown branch'} · Official: ${r.official_check||'unknown'} · Strict: ${r.strict_check||'unknown'}`));
      if(r.sha)d.append(link('Exact code revision',`https://github.com/timbtz/feyer-search-lab/commit/${r.sha}`));
      if(r.phases)table(d,['First-run phase','Seconds'],Object.entries(r.phases).map(([key,value])=>[key,seconds(value)]));
      if(r.log_tail)raw(d,'Evaluator log excerpt',r.log_tail,`archive-log-${r.id}`);else d.append(el('p','meta-line','No retained log excerpt for this run.'));
      raw(d,'Validation, warm timings and provenance',r,`archive-raw-${r.id}`);
    }
    $('archive-more').hidden=rows.length<=jobLimit;
  }
  let initialized=false;
  function render(data){state=data;if(!initialized){$('submission-select')?.addEventListener('change',e=>{selected=e.target.value;signature='';renderCandidate();});$('archive-query')?.addEventListener('input',()=>{jobLimit=30;renderJobs();});$('archive-more')?.addEventListener('click',()=>{jobLimit+=30;renderJobs();});initialized=true;}renderCandidate();renderJobs();}
  return {render,transferPairs,evidenceStatus,filteredJobs,benchmarkRuns,defaultCandidate};
})();
if(typeof module!=='undefined')module.exports=SubmissionReport;
