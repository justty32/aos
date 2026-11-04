from common import *
import statistics

def scale(s,count):
    for i in range(count):s.node('n%03d'%i)
    t0=time.monotonic();p=s.start();first=None;ats=[];discover={};pending=None;lat=[];errors=[]
    end=t0+15;nextctl=t0+.5;maxseen=0
    while time.monotonic()<end:
        t=time.monotonic();st=read(s.root/'.aosd/status.json')
        if st:
            if first is None:first=t-t0
            if not ats or ats[-1][1]!=st.get('at'):ats.append((t,st.get('at')))
            ns=st.get('nodes',{});maxseen=max(maxseen,len(ns))
            for n,v in ns.items():
                if v.get('round',0)>0:discover.setdefault(n,t-t0)
        if pending:
            rec=read(s.root/'.aosd/ctl-done'/pending[0])
            if rec:lat.append((t-pending[1])*1000);pending=None;nextctl=t+.5
        elif t>=nextctl:
            fn='ctl-%d.json'%time.time_ns();write(s.root/'.aosd/ctl'/fn,{'op':'wake','node':'n000'});pending=(fn,time.monotonic())
        time.sleep(.01)
    t=time.monotonic();write(s.root/'.aosd/ctl/zz-stop.json',{'op':'stop','kill':True});wait(lambda:read(s.root/'.aosd/ctl-done/zz-stop.json'),20);stop=(time.monotonic()-t)*1000;p.wait(20)
    logs=rows(s.root/'.aosd/log.jsonl');ticks={n:0 for n in ['n%03d'%i for i in range(count)]}
    for r in logs:
        if r.get('ev')=='tick' and not r.get('rc') and r.get('node') in ticks:ticks[r['node']]+=1
    return {'nodes':count,'window_s':15,'first_status_s':round(first,3) if first is not None else None,'max_nodes_visible_during_window':maxseen,'nodes_round_positive_during_window':len(discover),'last_first_round_s':round(max(discover.values()),3) if discover else None,'completed_ticks_before_stop_including_drain':ticks,'ctl_ms':[round(x,1) for x in lat],'ctl_max_ms':round(max(lat),1) if lat else None,'status_max_observed_gap_ms':round(max(b[0]-a[0] for a,b in zip(ats,ats[1:]))*1000,1),'stop_receipt_ms':round(stop,1),'rc':p.returncode}

def flood(s):
    s.node();write(s.root/'.aosd/paused.json',{'paused':['n']})
    for i in range(10000):write(s.root/'.aosd/ctl'/('w%05d.json'%i),{'op':'wake','node':'n'})
    p=s.start();wait(lambda:(s.root/'.aosd/ctl-done/w00000.json').exists());t=time.monotonic();write(s.root/'.aosd/ctl/000-stop.json',{'op':'stop','kill':True})
    wait(lambda:read(s.root/'.aosd/ctl-done/000-stop.json'));lat=(time.monotonic()-t)*1000;p.wait(10)
    return {'wake_count':10000,'stop_ms':round(lat,1),'pending_after_stop':len(list((s.root/'.aosd/ctl').iterdir())),'rc':p.returncode,'note':'stop sorts before backlog; sent only after first wake receipt'}

if __name__=='__main__':
    case('ctl-flood',flood)
    for n in (20,200):case('scale-'+str(n),lambda s,n=n:scale(s,n))
