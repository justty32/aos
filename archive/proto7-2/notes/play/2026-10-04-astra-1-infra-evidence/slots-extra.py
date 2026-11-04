#!/usr/bin/env python3
import sys,os,time,pathlib,tempfile,json
from unittest.mock import patch
HERE=pathlib.Path(__file__).resolve().parent;TOP=HERE.parents[2]
os.environ['PYTHONDONTWRITEBYTECODE']='1';tempfile.tempdir=str(HERE);sys.path.insert(0,str(TOP/'tests'))
from base import CoreCase
from aos7_fs import read_json,read_jsonl,write_json
import aos7_tock
out={};c=CoreCase();c.setUp();root=c.root
try:
    node=c.mknode('a',[{'name':'history','mode':'keep','argv':[sys.executable,str(TOP/'modules'/'history.py')]}])
    c.itick();c.wait_pid(node,'history');hp=pathlib.Path(node)/'history'/'a.jsonl'
    original=aos7_tock.write_json;observations=[]
    def delay_summary(path,obj):
        if str(path).endswith('/last-round.json'):
            time.sleep(.2)  # widen real tock notification -> summary publication window
            observations.append({'publishing_round':obj['round'],'rows_before_summary':read_jsonl(hp),'notified_round':read_json(pathlib.Path(c.slot(node,'history'))/'tock.json')['round']})
        return original(path,obj)
    with patch.object(aos7_tock,'write_json',side_effect=delay_summary):
        c.itock();c.itick();c.itock()
    time.sleep(.1)
    out['history_notification_before_commit']={'observations':observations,'final_summary_round':c.last_round(node)['round'],'final_history_rows':read_jsonl(hp),'injection':'200ms delay only at actual last-round.json write; real history process and actual tick/tock'}
    c.set_tasks(node,[{'name':'m','mode':'keep','argv':['sleep','60'],'mounts':{'declared':'allowed/one'}}],mount_allow=['allowed'])
    c.itick();c.wait_pid(node,'m');sd=pathlib.Path(c.slot(node,'m'))
    write_json(sd/'mount-req'/'dynamic.json',{'name':'dynamic','path':'allowed/dynamic'})
    write_json(sd/'mount-req'/'bad.json',{'name':'bad','path':'denied'})
    c.itock();c.itick()
    out['mount_runtime']={'accepted':read_json(sd/'mount-done'/'dynamic.json'),'refused':read_json(sd/'mount-done'/'bad.json'),'remaining_requests':os.listdir(sd/'mount-req')}
    c.set_tasks(node,[{'name':'m','mode':'keep','argv':['sleep','59'],'mounts':{'declared':'allowed/new'}}],mount_allow=['allowed'])
    write_json(sd/'ctl.json',{'op':'restart','reload':True,'run':c.birth(node,'m')['run']});c.itock();c.itick();c.wait_pid(node,'m')
    out['reload_mounts']={'birth':{k:c.birth(node,'m').get(k) for k in ['run','restart_of','argv','mounts']},'receipt':read_json(sd/'ctl-done.json'),'links':{p.name:os.readlink(p) for p in (sd/'mnt').iterdir()},'mount_done_cleared':not (sd/'mount-done').exists()}
finally:
    c.doCleanups();out['cleanup_root_removed']=not os.path.exists(root)
(HERE/'slots-extra.json').write_text(json.dumps(out,ensure_ascii=False,indent=2)+'\n')
