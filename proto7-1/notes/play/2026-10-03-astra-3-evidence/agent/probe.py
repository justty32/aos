"""Offline third-play probes; run from any cwd. No real model or external network."""
import json, os, resource, shutil, signal, subprocess, sys, tempfile, threading, time
from pathlib import Path
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

BASE = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(BASE / 'lib'))
from aos7_fs import read_json, write_json
import aos7_agent_tools, aos7_llm
OUT = Path(__file__).resolve().parent

def dump(name, obj):
    write_json(str(OUT / name), obj)

def wait(fn, timeout=15):
    end = time.monotonic() + timeout
    while time.monotonic() < end:
        v = fn()
        if v:
            return v
        time.sleep(.02)
    raise RuntimeError('timeout: ' + repr(fn))

def worker(node):
    before = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    t = time.perf_counter()
    mem = aos7_agent_tools.memory(node, 1)
    print(json.dumps(dict(ms=(time.perf_counter()-t)*1000, peak_rss_kib=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
                         baseline_peak_kib=before, returned_bytes=len(json.dumps(mem).encode()),
                         recent_count=len(mem['recent_letters']), file_chars={k:len(v) for k,v in mem['my_files'].items()})))

def memory_probe(root):
    node = root / 'memory'
    node.mkdir()
    samples = []
    for count in (0, 1024, 16384):
        with (node/'sent.jsonl').open('w') as f:
            for i in range(count):
                f.write(json.dumps({'to':'peer','at':f'{i:08d}','body':'x'*4096})+'\n')
            f.write(json.dumps({'to':'peer','at':'99999999','body':'last'})+'\n')
        runs = [json.loads(subprocess.check_output([sys.executable,__file__,'--memory-worker',str(node)])) for _ in range(3)]
        samples.append(dict(old_letters=count, history_bytes=(node/'sent.jsonl').stat().st_size, runs=runs))
    (node/'sent.jsonl').write_text('')
    (node/'work').mkdir()
    with (node/'work/large.txt').open('w') as f:
        for _ in range(32): f.write('z'*1048576)
    large = json.loads(subprocess.check_output([sys.executable,__file__,'--memory-worker',str(node)]))
    dump('memory.json',dict(history=samples, large_work_file_bytes=33554432, large_work_result=large))

class Handler(BaseHTTPRequestHandler):
    def log_message(self, *args): pass
    def do_POST(self):
        data=json.loads(self.rfile.read(int(self.headers['Content-Length'])))
        self.server.calls.append(data)
        n=len(self.server.calls)
        if self.server.hold_first and n == 1: self.server.gate.wait(20)
        content=self.server.responses[min(n-1,len(self.server.responses)-1)]
        obj={'choices':[{'message':{'content':content}}], 'usage':{'total_tokens':17}}
        raw=json.dumps(obj).encode()
        try:
            self.send_response(200); self.send_header('Content-Type','application/json'); self.end_headers(); self.wfile.write(raw)
        except (BrokenPipeError,ConnectionResetError): pass

def server(responses, hold=False):
    s=ThreadingHTTPServer(('127.0.0.1',0),Handler)
    s.calls=[];s.responses=responses;s.hold_first=hold;s.gate=threading.Event()
    t=threading.Thread(target=s.serve_forever,daemon=True);t.start()
    return s,t,{'url':f'http://127.0.0.1:{s.server_port}/v1','model':'offline-fixture','timeout_s':15}

def retry_probe():
    out=[]
    for replies in [['.','[{"tool":"none"}]'],['.','.'],['[]']]:
        s,t,llm=server(replies)
        try:
            res=aos7_llm.think({'llm':llm},None,[],'a')
            out.append(dict(replies=replies, result=res, request_count=len(s.calls), last_messages=s.calls[-1]['messages']))
        finally: s.shutdown();s.server_close();t.join()
    dump('retry.json',out)

def live_probe(root):
    root=root/'live';root.mkdir()
    s,thread,llm=server(['[{"tool":"none"}]'],True)
    for nid,cmd in [('team','aos7-kernel'),('team/a','aos7-agent'),('team/w','aos7-agent')]:
        node=root/nid
        write_json(str(node/'.aos/timeline.json'),{'interval_ms':160})
        write_json(str(node/'.aos/tasks.json'),{'tasks':[{'name':'main','mode':'keep','argv':[str(BASE/'bin'/cmd)]}]})
    write_json(str(root/'team/kernel.json'),{'members':['a','w'],'stuck_rounds':2})
    write_json(str(root/'team/a/agent.json'),{'llm':llm})
    write_json(str(root/'team/a/goal.json'),{'say_first':{'to':'team/w','body':'test'}})
    write_json(str(root/'team/w/agent.json'),{'llm':'fake','wake':{'rounds':10,'unless':'work/DONE'}})
    log=(root/'daemon.log').open('w')
    p=subprocess.Popen([sys.executable,str(BASE/'bin/aos7-daemon'),str(root)],stdout=log,stderr=log,start_new_session=True)
    def tasks(n): return sorted((root/n/'.aos/tasks').glob('*'))
    def state(n):
        ts=tasks(n)
        if not ts:return {}
        return read_json(str(ts[-1]/'state.json'),{}) or {}
    def status():return read_json(str(root/'.aosd/status.json'),{}) or {}
    def ctl(op,node):
        write_json(str(root/'.aosd/ctl'/f'probe-{time.time_ns()}.json'),{'op':op,'node':node,'by':'astra3-file-only','why':'offline probe'})
    try:
        wait(lambda: len(s.calls)==1)
        old=wait(lambda: next((t for t in tasks('team/a') if (read_json(str(t/'progress.json'),{}) or {}).get('llm_since')),None))
        wait(lambda: (status().get('nodes',{}).get('team/a',{}).get('round',0))>=10)
        before={x:read_json(str(old/x)) for x in ['state.json','progress.json','pid.json','tock.json']}
        before['task_count']=len(tasks('team/a'))
        os.kill(before['pid.json']['pid'],signal.SIGKILL)
        wait(lambda:len(s.calls)>=2)
        new=wait(lambda:next((t for t in tasks('team/a') if t != old and (read_json(str(t/'state.json'),{}) or {}).get('from')==old.name),None))
        wait(lambda:(read_json(str(new/'progress.json'),{}) or {}).get('state')=='idle')
        after={'old':{x:read_json(str(old/x)) for x in ['state.json','progress.json','exit.json','ended.json']},
               'new':{x:read_json(str(new/x)) for x in ['state.json','progress.json','usage.json']},'http_calls':len(s.calls)}
        s.gate.set()
        dump('kill-think.json',{'before_kill':before,'after_recovery':after,
                              'kernel_decisions':[(t/'decisions.jsonl').read_text() for t in tasks('team') if (t/'decisions.jsonl').exists()]})
        # Freeze only by writing ctl; wait for settled pause before judging wake.
        ctl('pause','team/w')
        wait(lambda:status().get('nodes',{}).get('team/w',{}).get('phase')=='paused')
        time.sleep(.1)
        w=tasks('team/w')[0]
        pre={x:read_json(str(w/x)) for x in ['state.json','progress.json','usage.json','tock.json']}
        status_pre=status()
        time.sleep(1.2)
        post={x:read_json(str(w/x)) for x in pre}
        # Read-only cat: inspect state, heartbeat, daemon pause reason/receipt.
        files=[w/'state.json',w/'progress.json',w/'tock.json',root/'.aosd/paused.json']
        receipts=list((root/'.aosd/ctl-done').glob('probe-*.json')); files+=receipts
        text=''.join(f'$ cat {f.relative_to(root)}\n'+subprocess.check_output(['cat',str(f)],text=True)+'\n' for f in files)
        (OUT/'s01-cat.txt').write_text(text)
        ctl('resume','team/w')
        wait(lambda:(read_json(str(w/'usage.json'),{}) or {}).get('calls',0)>(post['usage.json'] or {}).get('calls',0))
        resumed={x:read_json(str(w/x)) for x in pre}
        (root/'team/w/work').mkdir(exist_ok=True)
        (root/'team/w/work/DONE').write_text('done')
        time.sleep(.5)
        calls=(read_json(str(w/'usage.json'),{}) or {}).get('calls',0)
        time.sleep(2)
        dump('wake-pause.json',dict(before_pause_wait=pre,after_pause_wait=post,unchanged=pre==post,resumed=resumed,
                                   calls_after_unless=calls,calls_later=(read_json(str(w/'usage.json'),{}) or {}).get('calls',0),
                                   paused_round=status_pre['nodes']['team/w']['round']))
        dump('llm-trace-samples.json', {str(t.relative_to(root)):{name:(t/name).read_text()[:12000]
             for name in ['llm.jsonl','trace.jsonl','out.log'] if (t/name).exists()} for t in [old,new,w]})
    finally:
        s.gate.set()
        if p.poll() is None:
            write_json(str(root/'.aosd/ctl/stop.json'),{'op':'stop','kill':True})
            try:p.wait(15)
            except subprocess.TimeoutExpired:os.killpg(p.pid,signal.SIGKILL);p.wait()
        # Emergency cleanup limited to this experimental root's recorded process groups.
        for f in root.glob('**/pid.json'):
            obj=read_json(str(f),{}) or {}
            for pid in [obj.get('pgid')]:
                if pid:
                    try:os.killpg(pid,signal.SIGKILL)
                    except ProcessLookupError:pass
        log.close();s.shutdown();s.server_close();thread.join()
        dump('live-cleanup.json',dict(daemon_exit=p.returncode,root=str(root)))

def main():
    if len(sys.argv)>1 and sys.argv[1]=='--memory-worker':worker(sys.argv[2]);return
    root=Path(tempfile.mkdtemp(prefix='astra3-agent-'))
    try:
        if '--live-only' not in sys.argv:retry_probe();memory_probe(root)
        live_probe(root)
    finally:
        shutil.rmtree(root)
        dump('cleanup.json',dict(root=str(root),removed=not root.exists()))

if __name__=='__main__':main()
