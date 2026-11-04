from common import *
def main():
    progress=read(OUT/'longrun-clean-progress.json');root=pathlib.Path(progress['root']);res=[]
    for i in range(20):
        nid=f'n{i:02}';n=root/nid;rs=rows(n/'.aos/rounds.jsonl');rounds=[r['round'] for r in rs];ended=[e['tid'] for r in rs for e in r.get('ended',[])];counts={}
        for tid in ended:counts[tid]=counts.get(tid,0)+1
        res.append({'node':nid,'closed_count':len(rounds),'first':min(rounds,default=0),'last':max(rounds,default=0),'duplicate_rounds':len(rounds)-len(set(rounds)),'missing_rounds':[x for x in range(1,max(rounds,default=0)+1) if x not in rounds],'duplicate_ended':{k:v for k,v in counts.items() if v>1},'summary_errors':[r for r in rs if r.get('errors') or r.get('tasks_error')][:3]})
    log=rows(root/'.aosd/log.jsonl')
    save('longrun-invariants',{'sample_seconds':progress['samples'][-1]['seconds'],'scope':'live read near end; no atomic whole-tree snapshot','nodes':res,'action_errors':[r for r in log if r.get('ev') in ('tick','tock') and r.get('rc')][:5],'io_error_count':sum(r.get('ev')=='io-error' for r in log)})
if __name__=='__main__':main()
