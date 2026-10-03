from common import *
import aos7_mount

REAPED=0
def reap_adopted():
    global REAPED
    for pid,st in descendants().items():
        if st["state"]=="Z" and st["ppid"]==os.getpid():
            try:
                if os.waitpid(pid,os.WNOHANG)[0]:REAPED+=1
            except ChildProcessError:pass

def measure(s,p,t0):
    reap_adopted()
    ds=descendants();live={pid:v for pid,v in ds.items() if v['state']!='Z'}
    fds={};fd_unreadable=[]
    for pid in live:
        try:fds[str(pid)]=len(list(pathlib.Path('/proc',str(pid),'fd').iterdir()))
        except OSError:fd_unreadable.append(pid)
    count=logical=allocated=logs=done=old=0
    for base,dirs,files in os.walk(s.root):
        for name in files:
            q=pathlib.Path(base)/name
            try:st=q.lstat()
            except OSError:continue
            count+=1;logical+=st.st_size;allocated+=st.st_blocks*512
            if name.endswith('.log') or name.endswith('.jsonl'):logs+=st.st_size
            if '/ctl-done/' in str(q):done+=1
            if '/tasks-old/' in str(q) and name=='birth.json':old+=1
    rounds={f'n{i:02}':read(s.root/f'n{i:02}/.aos/round.json',{}).get('round',0) for i in range(20)}
    st=read(s.root/'.aosd/status.json',{})
    return dict(seconds=round(time.monotonic()-t0,2),harness_adopted_reaped=REAPED,rounds=rounds,round_sum=sum(rounds.values()),processes=len(live),zombies=len(ds)-len(live),fd_total=sum(fds.values()),fd_unreadable=fd_unreadable,daemon_fd=fds.get(str(p.pid)),files=count,bytes=logical,allocated_bytes=allocated,log_bytes=logs,ctl_done=done,tasks_old=old,io_errors=st.get('io_errors'),daemon_alive=p.poll() is None)

def main(s):
    worker=[sys.executable,'-c','import time;time.sleep(1800)']
    for i in range(20):
        items=[{'name':'keep','mode':'keep','argv':worker}]
        if i<5:items.append({'name':'each','mode':'each','argv':['true']})
        if i==19:items.append({'name':'subd','mode':'keep','argv':['aos7-daemon','$AOS7_SUBROOT'],'subroot':'n19/sub','allow_stop':True})
        n=s.root/f'n{i:02}'
        write(n/'.aos/tasks.json',{'tasks':items})
        write(n/'.aos/timeline.json',{'interval_ms':2000,'keep_ended_rounds':3})
    write(s.root/'n19/sub/w/.aos/tasks.json',{'tasks':[{'name':'child','mode':'keep','argv':worker}]})
    write(s.root/'n19/sub/w/.aos/timeline.json',{'interval_ms':2000})
    p=s.start();wait(lambda:read(s.root/'.aosd/status.json'));t0=time.monotonic();samples=[];events=[]
    for minute in range(11):
        deadline=t0+minute*60
        while time.monotonic()<deadline:
            reap_adopted();time.sleep(max(0,min(.2,deadline-time.monotonic())))
        sample=measure(s,p,t0);samples.append(sample)
        save('longrun-clean-progress',{'samples':samples,'events':events,'pid':p.pid,'root':str(s.root)})
        print('minute',minute,'rounds',sample['round_sum'],'fd',sample['daemon_fd'],'processes',sample['processes'],flush=True)
        if minute==10:break
        n=s.root/f'n{minute%5:02}'
        write(n/f'.aos/spawn/burst-{minute}.json',{'name':f'spawn{minute}','argv':['true']})
        live=[d for d in (n/'.aos/tasks').glob('keep-*') if task.task_state(str(d))=='live']
        if live:
            d=live[-1];reload=minute%2==1
            if reload:
                items=read(n/'.aos/tasks.json')['tasks'];items[0]['argv']=worker+[str(minute)];write(n/'.aos/tasks.json',{'tasks':items})
            write(d/'ctl.json',{'op':'restart','reload':reload});events.append({'minute':minute,'task':str(d.relative_to(s.root)),'reload':reload})
        target=s.root/'n10'
        live=[d for d in (target/'.aos/tasks').glob('keep-*') if task.task_state(str(d))=='live']
        if live:aos7_mount.request(str(live[-1]),f'n11/box{minute}')
        for op in ('wake','pause','resume'):
            write(s.root/f'.aosd/ctl/{minute}-{op}.json',{'op':op,'node':'n18'})
    before=descendants();write(s.root/'.aosd/ctl/final-stop.json',{'op':'stop','kill':True});stop=time.monotonic()
    rc=p.wait(timeout=30);time.sleep(.3)
    survivors={pid:v for pid,v in descendants().items() if v['state']!='Z'}
    receipts=[]
    for q in s.root.rglob('ctl-done.json'):
        r=read(q,{})
        if r.get('op')=='restart':receipts.append({'path':str(q.relative_to(s.root)),'result':r.get('result')})
    return {'duration_seconds':round(time.monotonic()-t0,2),'samples':samples,'events':events,'restart_receipts':receipts,'stop_rc':rc,'stop_seconds':round(time.monotonic()-stop,3),'product_live_survivors':survivors,'child_round':read(s.root/'n19/sub/w/.aos/round.json'),'mount_count':len(read(s.root/'n10/.aos/tasks/keep-r1/birth.json',{}).get('mounts',{}))}
if __name__=='__main__':case('longrun-clean',main)
