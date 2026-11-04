"""Rerun: python3 proto7-2/notes/play/2026-10-09-astra-7-infra-evidence/core3/author.py

Author comparisons only; subprocesses run unittest once per requested file.
TMPDIR isolates all author-created temporary files beneath our own /tmp root.
"""
import sys
sys.dont_write_bytecode = True
from common import *

def probe(c,module):
    env=dict(c.env,TMPDIR=str(c.root),PYTHONPATH=str(TOP/'tests')+':'+str(TOP/'tests/core'))
    p=c.start([sys.executable,'-m','unittest','-v',module],env=env,name=module)
    code=p.wait(600)
    c.data['command']=[sys.executable,'-m','unittest','-v',module]
    c.data['log']=(c.root/(module+'-0.log')).read_text()
    c.check('author comparison suite exit',code,0)

if __name__=='__main__':
    run_cases([('author-ctl',lambda c:probe(c,'test_ctl')),('author-daemon',lambda c:probe(c,'test_daemon'))])
