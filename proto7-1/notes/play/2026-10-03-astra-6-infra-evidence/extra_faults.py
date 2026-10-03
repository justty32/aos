from common import *

def interval(s):
    n=s.node();write(n/'.aos/timeline.json',{'interval_ms':10**309});d=s.start()
    wait(lambda:(read(s.root/'.aosd/status.json',{}) or {}).get('nodes',{}).get('n',{}).get('round',0)>=1)
    before=read(s.root/'.aosd/status.json')['nodes']['n'];write(n/'.aos/timeline.json',{'interval_ms':100});write(s.root/'.aosd/ctl/wake.json',{'op':'wake','node':'n'})
    wait(lambda:(read(s.root/'.aosd/status.json',{}) or {}).get('nodes',{}).get('n',{}).get('round',0)>=3)
    after=read(s.root/'.aosd/status.json')['nodes']['n'];return {'before':before,'after':after,'daemon_alive':d.poll() is None}

def partial_summary(s):
    n=s.node(items=[{'name':'one','mode':'keep','argv':['/bin/true']}]);s.run('aos7-tick');wait(lambda:read(n/'.aos/tasks/one-r1/exit.json'))
    hook=s.root/'hook';hook.mkdir();mark=s.root/'mark';(hook/'sitecustomize.py').write_text('''import os,sys,json,signal
if os.path.basename(sys.argv[0])=='aos7-tock':
 sys.path.insert(0,os.environ['A6_LIB'])
 import aos7_fs
 orig=aos7_fs.append_jsonl
 def torn(path,obj):
  if str(path).endswith('/rounds.jsonl'):
   with open(path,'a') as f:
    f.write(json.dumps(obj)[:24]);f.flush();os.fsync(f.fileno())
   open(os.environ['A6_MARK'],'w').write('partial bytes persisted')
   os.kill(os.getpid(),signal.SIGSTOP)
  return orig(path,obj)
 aos7_fs.append_jsonl=torn
''')
    p=s.start('aos7-tock','n',env={'PYTHONPATH':str(hook),'A6_LIB':str(LIB),'A6_MARK':str(mark)})
    wait(lambda:mark.exists());prefix=(n/'.aos/rounds.jsonl').read_text();p.kill();p.wait()
    replay=s.run('aos7-tock');raw=(n/'.aos/rounds.jsonl').read_text();r=read(n/'.aos/round.json');ended=read(n/'.aos/tasks/one-r1/ended.json');valid=rows(n/'.aos/rounds.jsonl')
    write(n/'.aos/tasks.json',{'tasks':[]});s.run('aos7-tick');s.run('aos7-tock');later=rows(n/'.aos/rounds.jsonl')
    return {'injection':'persist first 24 JSON characters, SIGSTOP, controller SIGKILL; models partial regular-file append, not atomic full append','prefix':prefix,'retry':replay,'raw_after_retry':raw,'valid_rows_after_retry':valid,'round_after_retry':r,'ended_mark':ended,'later_valid_rows':later}

if __name__=='__main__':case('interval-live',interval);case('partial-summary',partial_summary)
