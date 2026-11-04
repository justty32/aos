"""Real tick/tock CLI fault probes; synthetic metadata, no LLM. Run from any cwd."""
import ctypes, json, os, shutil, signal, subprocess, sys, tempfile, time
from pathlib import Path

OUT = Path(__file__).resolve().parent
REPO = next(p for p in OUT.parents if (p / 'proto7-1/lib').is_dir())
BIN = REPO / 'proto7-1/bin'
ctypes.CDLL(None).prctl(36, 1, 0, 0, 0)

def put(p, v):
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(v))

def run(root, prog):
    p = subprocess.run([sys.executable, str(BIN/prog), str(root), 'n'], capture_output=True, text=True, timeout=5)
    return {'prog': prog, 'rc': p.returncode, 'stdout': p.stdout, 'stderr': p.stderr}

def snap(root):
    return {str(p.relative_to(root)): p.read_text() for p in root.rglob('*.json') if p.is_file()}

def one(case):
    root = Path(tempfile.mkdtemp(prefix='astra5-robustness-'))
    a = root/'n/.aos'
    result = {'case': case, 'root': str(root)}
    try:
        put(a/'timeline.json', {'interval_ms': 100})
        good = {'name':'good', 'argv':['/bin/true']}
        put(a/'tasks.json', {'tasks':[good]})
        if case == 'numeric-name':
            put(a/'tasks.json', {'tasks':[{'name':123,'argv':['/bin/true']}, good]})
        else:
            td = a/'tasks/a-r0'
            put(td/'birth.json', {'name':'a', 'tid':'a-r0', 'round':0})
            if case == 'ctl-receipt-dir':
                put(td/'exit.json', {'code':0})
                put(td/'ctl.json', {'op':'not-an-op'})
                (td/'ctl-done.json').mkdir()
            else:
                put(td/'mount-req/x.json', {'name':'x','path':'inbox'})
                (td/'mount-done/x.json').mkdir(parents=True)
        result['initial'] = snap(root)
        result['rounds'] = []
        for _ in range(3):
            tick = run(root, 'aos7-tick')
            time.sleep(.05)
            tock = run(root, 'aos7-tock')
            result['rounds'].append({'tick':tick, 'tock':tock, 'files':snap(root)})
        result['mount_request_exists'] = (a/'tasks/a-r0/mount-req/x.json').exists()
        result['mount_receipt_is_file'] = (a/'tasks/a-r0/mount-done/x.json').is_file()
    finally:
        killed=[]
        for p in Path('/proc').iterdir():
            if not p.name.isdigit() or int(p.name)==os.getpid(): continue
            try:
                if str(root).encode() in (p/'cmdline').read_bytes() or b'AOS7_ROOT='+str(root).encode() in (p/'environ').read_bytes().split(b'\0'):
                    os.kill(int(p.name),signal.SIGKILL); killed.append(int(p.name))
            except OSError: pass
        deadline=time.monotonic()+2
        while time.monotonic()<deadline:
            try:
                pid,_=os.waitpid(-1,os.WNOHANG)
                if not pid: time.sleep(.02)
            except ChildProcessError: break
        shutil.rmtree(root)
        result['cleanup']={'killed':killed, 'space_removed':not root.exists()}
    (OUT/(case+'.json')).write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
    print(case, [r['tick']['rc'] for r in result['rounds']], [r['tock']['rc'] for r in result['rounds']])

for case in ('numeric-name','ctl-receipt-dir','mount-receipt-dir'): one(case)
