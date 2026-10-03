from common import *
def run(s,kind):
    # Both probes use deterministic local mock services; no LLM or network client.
    env=dict(os.environ,TMPDIR=str(s.root))
    p=subprocess.run([sys.executable,str(PRODUCT/'probes'/kind/'probe.py')],env=env,capture_output=True,text=True,timeout=60)
    return {'rc':p.returncode,'output':p.stdout,'stderr':p.stderr,'live_before_cleanup':{k:v for k,v in descendants().items() if v['state']!='Z'}}
if __name__=='__main__':
    for k in ('namespace','ledger'):case('probe-'+k,lambda s,k=k:run(s,k))
