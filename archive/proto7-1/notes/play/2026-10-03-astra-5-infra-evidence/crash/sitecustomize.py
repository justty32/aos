"""Fault injection only: freeze exact filesystem boundary, or raise ENOSPC.

Loaded only when the probe explicitly sets PYTHONPATH and A4_FAULT.
No product source is modified. SIGSTOP gives the controller a deterministic
opportunity to SIGKILL the selected process (or its daemon).
"""
import os, sys, json, signal

cfg = json.loads(os.environ.get('A4_FAULT', '{}'))
if cfg and os.path.basename(sys.argv[0]) == cfg['prog']:
    import fcntl
    if cfg['op'] == 'append_jsonl':
        sys.path.insert(0, cfg['lib'])
        import aos7_fs
        target = aos7_fs
    else:
        target = fcntl if cfg['op'] == 'flock' else os
    original = getattr(target, cfg['op'])
    count = 0
    def fault(*args, **kwargs):
        global count
        path = str(args[1] if cfg['op'] == 'replace' else args[0])
        match = (cfg['op'] == 'flock' or path.endswith(cfg['suffix']))
        if cfg.get('onceglob') and os.path.exists(cfg['marker']): match = False
        if match:
            count += 1
        fire = match and count == cfg.get('nth', 1)
        if fire and cfg.get('action') == 'enospc':
            raise OSError(28, 'injected ENOSPC at os.' + cfg['op'], path)
        if fire and cfg.get('when') == 'before':
            with open(cfg['marker'], 'w') as f:
                json.dump({'pid': os.getpid(), 'path': path, 'args': [str(a) for a in args]}, f)
            os.kill(os.getpid(), signal.SIGSTOP)
        result = original(*args, **kwargs)
        if fire and cfg.get('when') == 'after':
            with open(cfg['marker'], 'w') as f:
                json.dump({'pid': os.getpid(), 'path': path, 'args': [str(a) for a in args]}, f)
            os.kill(os.getpid(), signal.SIGSTOP)
        return result
    setattr(target, cfg['op'], fault)
