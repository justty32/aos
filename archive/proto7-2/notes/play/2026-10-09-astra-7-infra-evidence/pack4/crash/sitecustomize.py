"""External failure injector; no production module or persisted budget data is edited."""
import os, json, signal, builtins, errno
_orig_replace = os.replace
_orig_open = builtins.open
_orig_os_open = os.open
_mode = os.environ.get('QA_MODE')
_target = os.environ.get('QA_TARGET')
_marker = os.environ.get('QA_MARKER')
def mark(info):
    with _orig_open(_marker, 'a') as f:
        f.write(json.dumps(dict(pid=os.getpid(), **info))+'\n')
def classify(dst, obj):
    dst = os.fspath(dst)
    name = os.path.basename(dst)
    if name == 'ledger.json': return 'ledger-'+ ('init' if not obj.get('log') else obj['log'][-1]['op'])
    if name == 'backend.json': return 'backend'
    if '/gateway/' in dst: return 'gateway-'+str(obj.get('stage'))
    if '/receipts/' in dst: return 'receipt-'+str(obj.get('op'))
    if '/inbox/' in dst: return 'inbox-'+str(obj.get('op'))
    if name == 'out.json': return 'output'
    return name
def replace(src, dst, *args, **kwargs):
    with _orig_open(src) as f: obj=json.load(f)
    hit=classify(dst,obj)==_target
    if hit and _mode=='before':
        mark(dict(mode=_mode,target=_target,dst=str(dst),src=str(src)))
        os.kill(os.getpid(),signal.SIGKILL)
    out=_orig_replace(src,dst,*args,**kwargs)
    if hit and _mode=='after':
        mark(dict(mode=_mode,target=_target,dst=str(dst),src=str(src)))
        os.kill(os.getpid(),signal.SIGKILL)
    return out
def fault_open(file, mode='r', *args, **kwargs):
    if isinstance(file,(str,bytes,os.PathLike)) and 'r' in mode and os.fspath(file).endswith(_target):
        mark(dict(mode='EIO',target=_target,path=str(file)))
        raise OSError(errno.EIO,'QA injected read failure',str(file))
    return _orig_open(file,mode,*args,**kwargs)
if _mode in ('before','after'): os.replace=replace
def fault_os_open(file, flags, *args, **kwargs):
    if isinstance(file,(str,bytes,os.PathLike)) and os.fspath(file).endswith(_target):
        mark(dict(mode='EIO',target=_target,path=str(file)))
        raise OSError(errno.EIO,'QA injected read failure',str(file))
    return _orig_os_open(file,flags,*args,**kwargs)
if _mode=='EIO': os.open=fault_os_open
