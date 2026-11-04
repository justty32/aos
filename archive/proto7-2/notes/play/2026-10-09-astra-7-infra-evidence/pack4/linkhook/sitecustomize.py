"""External pre-publication barrier for step-result (uses hard link, not rename).
Rerun: python3 proto7-2/notes/play/2026-10-09-astra-7-infra-evidence/pack4/tmp_probe.py
"""
import json
import os
import time
_link=os.link
def link(src,dst,*a,**kw):
    marker=os.environ.get('PACK4_LINK_MARKER')
    if marker:
        with open(marker,'w') as f:
            json.dump({'pid':os.getpid(),'src':str(src),'dst':str(dst),'point':'before-os.link'},f)
        while not os.path.exists(marker+'.release'): time.sleep(.01)
    return _link(src,dst,*a,**kw)
if os.environ.get('PACK4_LINK_MARKER'): os.link=link
