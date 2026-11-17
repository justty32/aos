// Verify the real rounds UI layout, data, live updates, and offline snapshot behavior without dependencies.
const assert=require('node:assert/strict');
const {boot}=require('./rounds_dom.cjs');
const clone=v=>JSON.parse(JSON.stringify(v));
const ts=i=>`2026-11-07T${String(9+i).padStart(2,'0')}:00:00+08:00`;
function round(name,statuses,report=false) {
  const events=statuses.map((status,i)=>({ts:ts(i),status,text:`${name} event ${i} <script>alert(1)</script>`,links:['proto8/example.md','https://example.test/source'],round:name}));
  const counts={};for(const e of events)counts[e.status]=(counts[e.status]||0)+1;
  return {name,first_ts:events[0].ts,last_ts:events.at(-1).ts,status:statuses.at(-1),counts,events_count:events.length,decisions_count:counts.decision||0,blocked:statuses.at(-1)==='blocked',asks_open:2,events,...(report?{report_url:'reports/alpha/second.html',report_file_url:'reports/alpha/second.html'}:{})};
}
const state={generated_at:ts(8),eli5:{main:{lines:{alpha:{text:'A plain explanation. More detail.'}}}},lines:[{id:'alpha',title:'Alpha work',current_round:'Second',rounds:[round('First',['start','done']),round('Second',['start','decision','done','handoff','ask','decision','done','blocked'],true)]},{id:'beta',title:'Beta work',current_round:null,rounds:[]}]};
const one=(root,s)=>{const n=root.querySelector(s);assert.ok(n,`Missing ${s}`);return n;};
const all=(root,s)=>root.querySelectorAll(s);
(async()=>{
  const page=await boot(clone(state)),d=page.document;
  one(one(d,'.site-bar'),'.shell.site-bar-inner');one(d,'nav.page-nav');assert.match(one(d,'nav.page-nav').textContent,/看板/);assert.match(one(d,'nav.page-nav').textContent,/細節/);
  assert.equal(one(d,'a[aria-current="page"]').textContent,'Alpha work');
  const mast=one(d,'header.masthead');one(mast,'.shell');one(mast,'.eyebrow');one(mast,'h1 br');one(mast,'h1 span');assert.equal(one(mast,'.lead').textContent,state.eli5.main.lines.alpha.text);one(mast,'.meta');one(mast,'.status-pill');assert.match(one(mast,'.meta').textContent,/待你裁 4/);
  one(d,'.nav-band nav.shell.section-nav');one(d,'main.shell');one(d,'footer.shell.footer');
  const sections=all(d,'section.report-section');assert.equal(sections.length,2);assert.equal(sections[0].id,'round-1');assert.equal(sections[1].id,'round-0');
  const second=sections[0],first=sections[1],svg=one(second,'svg.diagram');one(svg,'title');one(svg,'desc');one(svg,'.kicker');one(svg,'.line');one(svg,'.blue-box');one(svg,'.warm-box');one(svg,'.t');one(svg,'.sub');one(svg,'.tiny');one(svg,'.bar');one(svg,'.bar-warm');
  assert.equal(all(svg,'.t').length,6);const titles=all(svg,'.t').map(n=>n.textContent);assert.ok(titles[0].startsWith('Second event 2'));assert.ok(titles.at(-1).startsWith('Second event 7'));
  const copy=one(second,'.section-copy');assert.match(one(copy,'.chapter').textContent,/02.*Second/);one(copy,'h2');one(copy,'.conclusion strong');one(copy,'details.fold summary');one(copy,'.fold-body');one(copy,'p.source');
  assert.equal(one(second,'.report-button').getAttribute('href'),'reports/alpha/second.html');assert.equal(all(first,'.report-button').length,0);
  assert.equal(all(second,'.round-event').length,11); // Eight full events, two decisions, one blocked event.
  assert.equal(all(second,'.event-links a').length,0);assert.match(one(second,'.event-links').textContent,/https:\/\/example.test\/source/);
  assert.equal(all(d,'script').length,2);assert.match(second.textContent,/<script>alert\(1\)<\/script>/);
  const rows=all(one(second,'table'),'tr');const numbers=Object.fromEntries(rows.map(r=>[one(r,'th').textContent,one(r,'td').textContent]));
  assert.equal(numbers['事件數'],'8');assert.equal(numbers['代定'],'2');assert.equal(numbers['待你裁未答'],'2');assert.equal(numbers['歷時'],'7 小時 0 分');
  assert.equal(page.intervals.find(i=>i.ms===5000)?.ms,5000);assert.ok(page.requests.length);
  const fold=one(second,'details');fold.open=true;
  const initialHeading=one(second,'h2');await page.poll(clone(state));assert.equal(one(d,'#round-1'),second);assert.equal(one(second,'h2'),initialHeading);assert.equal(one(second,'details'),fold);
  const changed=clone(state);changed.lines[0].rounds[1].events.push({ts:ts(9),status:'progress',text:'x'.repeat(50),links:[],round:'Second'});changed.lines[0].rounds[1].events_count++;
  await page.poll(changed);assert.equal(one(d,'#round-0'),first);assert.equal(one(d,'#round-1'),second);assert.notEqual(one(second,'h2'),initialHeading);assert.equal(one(second,'h2').textContent,'x'.repeat(40)+'…');assert.equal(one(second,'details').open,true);
  assert.equal(page.window.scrollX,13);assert.equal(page.window.scrollY,287);
  one(d,'button[data-details="expand"]').click();assert.ok(all(d,'details').every(n=>n.open));one(d,'button[data-details="collapse"]').click();assert.ok(all(d,'details').every(n=>!n.open));
  page.location.hash='#round-1-events';page.listeners.hashchange();assert.equal(one(d,'#round-1-events').open,true);assert.ok(one(d,'#round-1-events').scrolled);
  await page.poll(changed);assert.equal(page.location.hash,'#round-1-events');assert.equal(one(d,'#round-1-events').open,true);
  one(d,'#round-1-events').open=false;const afterCollapse=clone(changed);afterCollapse.lines[0].rounds[1].events_count++;await page.poll(afterCollapse);assert.equal(one(d,'#round-1-events').open,false);assert.equal(page.location.hash,'#round-1-events');
  const offline=await boot(clone(state),{protocol:'file:'});assert.equal(offline.requests.length,0);assert.equal(offline.intervals.length,0);assert.match(one(offline.document,'#connection.snapshot').textContent,/快照/);one(offline.document,'.report-button');
  for(const report_url of ['', 'javascript:alert(1)', '//outside.test/report']){const unsafe=clone(state);unsafe.lines[0].rounds[1].report_url=report_url;const p=await boot(unsafe);assert.equal(all(p.document,'.report-button').length,0);}
  const noEli5=clone(state);delete noEli5.eli5;const fallback=await boot(noEli5,{protocol:'file:'});assert.equal(all(fallback.document,'.lead').length,0);assert.equal(one(fallback.document,'h1 span').textContent,state.lines[0].rounds[1].events.at(-1).text);
  const reopened=clone(state);reopened.lines[0].current_round='First';reopened.lines[0].rounds[0].events.push({ts:ts(9),status:'progress',text:'Reopened earlier round. Entire latest event.',links:[],round:'First'});reopened.lines[0].rounds[0].last_ts=ts(9);reopened.lines[0].rounds[0].status='progress';delete reopened.eli5;const reopenedPage=await boot(reopened,{protocol:'file:'});assert.match(one(reopenedPage.document,'h1').textContent,/First/);assert.equal(one(reopenedPage.document,'h1 span').textContent,'Reopened earlier round. Entire latest event.');
  const empty=await boot({lines:[]},{protocol:'file:'});one(empty.document,'.round-empty');assert.equal(all(empty.document,'section.report-section').length,0);
  const noRounds=await boot(clone(state),{protocol:'file:',search:'?line=beta'});one(noRounds.document,'.round-empty');assert.equal(all(noRounds.document,'section.report-section').length,0);
  const noSnapshot=await boot(null,{protocol:'file:'});one(noSnapshot.document,'.round-empty');
  console.log('Rounds DOM checks passed: reference layout, milestone ordering, counts, report links, safe text, live identity/folds/hash/scroll, controls, snapshots, and empty states.');
})().catch(e=>{console.error(e);process.exitCode=1;});
