"""Rerun: python3 proto7-2/notes/play/2026-10-09-astra-7-infra-evidence/core3/r803.py"""
import sys
sys.dont_write_bytecode = True
from common import *

def probe(c):
    c.node(empty=True)
    d=c.daemon()
    before=c.nodes()
    (c.root/'rules').write_text('write:*/.aosd/nodes.json:EIO\n')
    failed=c.ctl('register')
    time.sleep(.1)
    c.check('failed register returns false',failed['ok'],False)
    c.check('failed register leaves disk unchanged',c.nodes(),before)
    c.check('failed register absent from status','a' in c.status().get('nodes',{}),False)
    c.data['register_failed']={'nodes':c.nodes(),'status':c.status()}
    (c.root/'rules').write_text('')
    c.check('register retry succeeds',c.ctl('register')['ok'])
    c.running()
    c.check('register retry status ids equal disk ids',sorted(c.status()['nodes']),sorted(c.nodes()['nodes']))
    before=c.nodes()
    (c.root/'rules').write_text('write:*/.aosd/nodes.json:EIO\n')
    failed=c.ctl('unregister')
    time.sleep(.1)
    c.check('failed unregister returns false',failed['ok'],False)
    c.check('failed unregister leaves disk unchanged',c.nodes(),before)
    c.check('failed unregister preserves timeline','a' in c.status()['nodes'])
    c.check('failed unregister does not retire',c.status()['nodes']['a']['phase']!='unregistering')
    c.data['unregister_failed']={'nodes':c.nodes(),'status':c.status()}
    (c.root/'rules').write_text('')
    c.check('unregister retry succeeds',c.ctl('unregister')['ok'])
    wait(lambda:'a' not in c.status().get('nodes',{}) and not c.nodes().get('reaping'),what='retirement')
    c.check('unregister retry status ids equal disk ids',sorted(c.status()['nodes']),sorted(c.nodes()['nodes']))
    c.ctl('stop',node=None,kill=True); d.wait(15)
    c.daemon()
    c.check('restart registry matches disk',sorted(c.status()['nodes']),sorted(c.nodes()['nodes']))
    hits=(c.root/'hits').read_text().splitlines()
    c.data['injection']={'rules':'write:*/.aosd/nodes.json:EIO','hits':hits}
    c.check('both write failures actually injected',len(hits)>=2)

if __name__ == '__main__':
    run_cases([('r803',probe)])
