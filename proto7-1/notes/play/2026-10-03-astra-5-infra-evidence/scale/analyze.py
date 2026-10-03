"""Derive completion-to-completion cadence (S-08) and first observation timings."""
import json, statistics
from pathlib import Path
B=Path(__file__).resolve().parent

def stats(v):
    v=sorted(v)
    return {'n':len(v),'p50':statistics.median(v),'p95':v[min(len(v)-1,int(.95*len(v)))],'max':max(v)} if v else {'n':0}

out=[]
for count,tag in [(10,''),(50,''),(100,''),(200,''),(200,'-empty'),(200,'-empty-repeat')]:
    file=B/f'summary-{count}{tag}.json'
    if not file.exists(): continue
    s=json.loads(file.read_text())
    sample=json.loads((B/f'samples-{count}{tag}.json').read_text())
    start=s.get('start_mono',sample[0]['mono'])
    end=start+s['sample_wall_s']
    rows=[json.loads(l) for p in sorted(B.glob(f'timings-{count}{tag}-[0-9][0-9].jsonl')) for l in p.read_text().splitlines()]
    ticks=[r for r in rows if r['prog']=='aos7-tick' and r['end']<=end]
    gaps=[]
    for node in {r['node'] for r in ticks}:
        ts=sorted(r['end'] for r in ticks if r['node']==node)
        gaps += [(b-a)*1000 for a,b in zip(ts,ts[1:])]
    out.append({'count':count,'tag':tag,'first_status_s':min(r['end'] for r in rows if r['prog']=='status')-start,
                'time_origin':'exact Popen-before monotonic' if 'start_mono' in s else 'first OS sample, first-status latency lower bound; cutoff approximate',
                'nodes_with_completed_tick':len({r['node'] for r in ticks}),
                'completion_interval_ms':stats(gaps),'completed_ticks_per_node':s['completed_ticks_per_timeline'],
                'ctl_receipt_ms':s['ctl_receipt_ms'],'status_gap_ms':s['status_update_gap_ms'],
                'sample_wall_s':s['sample_wall_s'],'action_nonzero_rc':s['nonzero_action_rc'],
                'daemon_rc':s['daemon_rc'],'tick_ms':s['tick_ms'],'tock_ms':s['tock_ms']})
(B/'analysis.json').write_text(json.dumps(out,ensure_ascii=False,indent=2)+'\n')
for x in out: print(x['count'],x['tag'],round(x['first_status_s'],3),x['nodes_with_completed_tick'],{k:round(v,2) for k,v in x['completion_interval_ms'].items()},x['ctl_receipt_ms'])
