#!/usr/bin/env python3
"""Offline deterministic Q4 and agent-test cleanup probes. Only own /tmp/astra5-node-* roots."""
import errno
import io
import json
import os
from pathlib import Path
import shutil
import signal
import subprocess
import sys
import tempfile
import threading
import time
import unittest
from unittest import mock

BASE = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(BASE / 'lib'))
sys.path.insert(0, str(BASE / 'tests'))
import aos7_daemon as daemon
import aos7_task as task
from aos7_fs import read_json, write_json

OUT = Path(__file__).resolve().parent
RESULTS = []

def wait(pred, seconds=3):
    end = time.monotonic() + seconds
    while time.monotonic() < end:
        val = pred()
        if val:
            return val
        time.sleep(.01)
    raise AssertionError('wait timeout')

def own_pids(root):
    found = []
    for p in Path('/proc').iterdir():
        if not p.name.isdigit():
            continue
        try:
            env = (p / 'environ').read_bytes().split(b'\0')
            if ('AOS7_ROOT=' + root).encode() in env and task.pid_alive(int(p.name)):
                found.append(int(p.name))
        except OSError:
            pass
    return found

def cleanup(root, d=None, known=()):
    if d:
        d.stop(False)
        for tl in d.timelines.values():
            tl.join(2)
        for th in d.reapers:
            th.join(3)
    for p in set(own_pids(root)) | set(known):
        if p == os.getpid():
            raise AssertionError('refusing to kill self')
        try:
            os.kill(p, signal.SIGKILL)
        except ProcessLookupError:
            pass
    time.sleep(.1)
    shutil.rmtree(root, ignore_errors=True)
    assert not own_pids(root), 'own processes remain'

def node_case(kind):
    root = tempfile.mkdtemp(prefix='astra5-node-' + kind + '-')
    node = os.path.join(root, 'n')
    d = None
    pids = []
    try:
        write_json(os.path.join(node, '.aos', 'timeline.json'), {'interval_ms':100})
        d = daemon.Daemon(root)
        d.paused.add('n')
        d.scan()  # Real Timeline exists but paused, so no action subprocess needed.
        if kind.endswith('unsampled'):
            d.live_of('n', d.timelines['n'])
        argv = [sys.executable, '-c', 'import time; time.sleep(60)']
        if kind.startswith('env_scrub'):
            argv = ['env', '-u', 'AOS7_NODE', '-u', 'AOS7_TID'] + argv
        tid = task.start_task(root, 'n', {'name':'sleep', 'argv':argv}, 1)
        pd = wait(lambda: read_json(os.path.join(task.task_dir(node, tid), 'pid.json')))
        pids.extend([pd['pid'], pd['runner_pid']])
        if not kind.endswith('unsampled'):
            d.live_of('n', d.timelines['n'])
        known_before = dict(d._pids.get('n', {}))
        io_before = d.io_errors
        if kind == 'rename_gap':
            # Exact scan inside a temporary rename window, then restore immediately.
            os.rename(node, os.path.join(root, '.hidden'))
            d.scan()
            os.rename(os.path.join(root, '.hidden'), node)
        elif kind == 'estale_walk':
            real_scandir = os.scandir
            def faulty_scandir(path):
                if os.fspath(path) == node:
                    raise OSError(errno.ESTALE, 'simulated remote mount stale handle', node)
                return real_scandir(path)
            with mock.patch('os.scandir', faulty_scandir):
                d.guard(d.scan)
        elif kind == 'timeline_eio':
            # Real isfile swallows stat OSError and reports False.
            real_stat = os.stat
            def faulty_stat(path, *a, **kw):
                if os.fspath(path) == os.path.join(node, '.aos', 'timeline.json'):
                    raise OSError(errno.EIO, 'simulated remote stat I/O error')
                return real_stat(path, *a, **kw)
            with mock.patch('os.stat', faulty_stat):
                d.guard(d.scan)
        elif kind == 'atomic_replace':
            def replace_loop():
                for i in range(1000):
                    write_json(os.path.join(node, '.aos', 'timeline.json'), {'interval_ms':i + 1})
            writer = threading.Thread(target=replace_loop)
            writer.start()
            for _ in range(500):
                d.scan()
            writer.join()
        else:
            shutil.rmtree(node)
            d.scan()
        for th in d.reapers:
            th.join(3)
        time.sleep(.15)
        result = {'case':kind, 'root':root, 'pid':pd, 'known_before':known_before,
                  'task_alive_after':task.pid_alive(pd['pid']), 'node_still_exists':os.path.isdir(node),
                  'node_in_daemon': 'n' in d.timelines, 'io_errors_delta':d.io_errors-io_before,
                  'log': [json.loads(x) for x in Path(root, '.aosd/log.jsonl').read_text().splitlines()]}
        RESULTS.append(result)
    finally:
        cleanup(root, d, pids)

def orphan_test():
    # Run the original test; only delay process startup and choose our owned tmp prefix.
    import test_agent
    captured = []
    roots = []
    real_popen = subprocess.Popen
    real_mkdtemp = tempfile.mkdtemp
    def delayed_popen(args, **kw):
        wrapper = 'import os,sys,time;time.sleep(.5);os.execv(sys.argv[1],sys.argv[1:])'
        p = real_popen([sys.executable, '-c', wrapper] + args, **kw)
        captured.append(p)
        return p
    def owned_tmp(*a, **kw):
        r = real_mkdtemp(prefix='astra5-node-agent-test-')
        roots.append(r)
        return r
    stream = io.StringIO()
    try:
        with mock.patch.object(test_agent.subprocess, 'Popen', delayed_popen), mock.patch.object(test_agent.tempfile, 'mkdtemp', owned_tmp):
            result = unittest.TextTestRunner(stream=stream).run(test_agent.RoundsFlag('test_rounds_n_exits'))
        time.sleep(.7)
        p = captured[0]
        RESULTS.append({'case':'original_rounds_test_delayed_start', 'success':result.wasSuccessful(),
                        'test_output':stream.getvalue(), 'root':roots[0], 'root_exists_after_cleanup':os.path.exists(roots[0]),
                        'agent_pid':p.pid, 'agent_alive_after_cleanup':p.poll() is None,
                        'proc_environment_still_refers_to_deleted_root':p.pid in own_pids(roots[0])})
    finally:
        for p in captured:
            p.terminate()
            try:
                p.communicate(timeout=2)
            except subprocess.TimeoutExpired:
                p.kill()
                p.communicate()
        for r in roots:
            cleanup(r)

def demo_exception():
    sys.path.insert(0, str(BASE / 'demo'))
    import play
    root = tempfile.mkdtemp(prefix='astra5-node-demo-error-')
    captured = []
    real_popen = subprocess.Popen
    real_write = play.fs.write_json
    def capture(*a, **kw):
        p = real_popen(*a, **kw)
        captured.append(p)
        return p
    def bad_stop(path, obj):
        if str(path).endswith('/zz-play-stop.json'):
            raise OSError(errno.EIO, 'simulated failure writing demo stop')
        return real_write(path, obj)
    try:
        write_json(os.path.join(root,'n/.aos/timeline.json'), {'interval_ms':100})
        write_json(os.path.join(root,'n/agent.json'), {'llm':'fake'})
        write_json(os.path.join(root,'n/.aos/tasks.json'),
                   {'tasks':[{'name':'agent','mode':'keep','argv':[str(BASE/'bin/aos7-agent'),'--rounds','100000']}]})
        raised = None
        with mock.patch.object(play.subprocess, 'Popen', capture), mock.patch.object(play.fs, 'write_json', bad_stop):
            try:
                play.run(root, .5, True)
            except OSError as e:
                raised = repr(e)
        live_before_delete = own_pids(root)
        daemon_alive = captured[0].poll() is None
        shutil.rmtree(root)
        time.sleep(.5)
        RESULTS.append({'case':'demo_stop_write_error', 'root':root, 'error':raised,
                        'daemon_alive_after_exception':daemon_alive, 'task_processes_before_root_delete':live_before_delete,
                        'daemon_alive_after_root_delete':captured[0].poll() is None,
                        'root_recreated_after_delete':os.path.exists(root),
                        'tasks_after_delete':own_pids(root)})
    finally:
        for p in captured:
            if p.poll() is None:
                p.terminate()
                try:
                    p.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    p.kill()
                    p.wait()
        cleanup(root)

if __name__ == '__main__':
    for kind in ('rename_gap','estale_walk','timeline_eio','atomic_replace','env_scrub_sampled','env_scrub_unsampled','normal_unsampled'):
        node_case(kind)
    orphan_test()
    demo_exception()
    (OUT/'results.json').write_text(json.dumps(RESULTS, ensure_ascii=False, indent=2) + '\n')
    print(json.dumps(RESULTS, ensure_ascii=False, indent=2))
