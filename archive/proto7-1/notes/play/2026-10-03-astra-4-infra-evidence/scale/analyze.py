import json, pathlib, statistics, time
P=pathlib.Path(__file__).parent

def stats(xs):
 if not xs:return {'n':0}
 x=sorted(xs);return {'n':len(x),'p50':round(statistics.median(x),3),'p95':round(x[min(len(x)-1,int(len(x)*.95))],3),'max':round(x[-1],3)}
out=[]
for key in ['10','10-repeat','50','100','200','200-empty','200-empty-confirm']:
 sf=P/f'summary-{key}.json'
 if not sf.exists():continue
 s=json.loads(sf.read_text());samples=json.loads((P/f'samples-{key}.json').read_text()); rows=[]
 for f in sorted(P.glob(f'timings-{key}-[0-9][0-9].jsonl')):rows += [json.loads(l) for l in f.read_text().splitlines()]
 start=samples[0]['mono'];stop=start+s['sample_wall_s'];active=[r for r in rows if r['end']<=stop]
 ticks=sorted([r for r in rows if r['prog']=='aos7-tick'],key=lambda r:r['end'])[:s['tick_ms']['n']];tocks=sorted([r for r in rows if r['prog']=='aos7-tock'],key=lambda r:r['end'])[:s['tock_ms']['n']];intervals=[];starts=[]
 for node in sorted(set(r['node'] for r in ticks)):
  ts=sorted(r['end'] for r in ticks if r['node']==node);intervals += [(b-a)*1000 for a,b in zip(ts,ts[1:])];starts.append((ts[0]-start)*1000)
 status=[r['end'] for r in rows if r['prog']=='status']
 all_cpu=s['aggregate_cpu_s_including_shutdown'];denom=s['sample_wall_s']+s.get('shutdown_and_analysis_wall_s',s.get('stop_wall_s',0))
 a={'key':key,'start_epoch_approx_from_monotonic':time.time()-time.monotonic()+start,'tick_end_interval_ms':stats(intervals),'initial_tick_end_delay_ms':stats(starts),'nodes_with_completed_tick':len(starts),'first_status_after_start_ms':round((min(status)-start)*1000,3) if status else None,'file_count_without_3_probe_files':s['file_count_final']-3,'aggregate_cpu_equivalent_cores_including_shutdown_analysis':round(all_cpu/denom,2),'phase':{}}
 for label,lo,hi in [('first5s',start,start+5),('last5s',stop-5,stop)]:
  a['phase'][label]={name:stats([(r['end']-r['start'])*1000 for r in rr if lo<=r['end']<hi]) for name,rr in [('tick_ms',ticks),('tock_ms',tocks)]}
 if 'stop_wall_s'in s:
  s['shutdown_and_analysis_wall_s']=s.pop('stop_wall_s');sf.write_text(json.dumps(s,ensure_ascii=False,indent=2)+'\n')
 out.append(a)
(P/'analysis.json').write_text(json.dumps(out,ensure_ascii=False,indent=2)+'\n')
print(json.dumps(out,indent=2))
