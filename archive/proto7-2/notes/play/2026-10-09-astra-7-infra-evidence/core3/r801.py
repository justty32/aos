"""Rerun: python3 proto7-2/notes/play/2026-10-09-astra-7-infra-evidence/core3/r801.py"""
import sys
sys.dont_write_bytecode = True
from common import *

def probe(c):
    node = c.node()
    hook = c.root/'gate_hooks.py'
    hook.write_text('''import importlib.util, os, time
from pathlib import Path
s=importlib.util.spec_from_file_location('original_hooks', %r)
h=importlib.util.module_from_spec(s); s.loader.exec_module(h)
inject=h.inject
def test_point(name):
    h.test_point(name)
    if name == 'runner-before-popen':
        gate=Path(os.environ['AOS7_TEST_CORE3_GATE'])
        gate.with_suffix('.entered').write_text(str(os.getpid()))
        while not gate.exists(): time.sleep(.01)
''' % str(HOOKS))
    env = dict(c.env, AOS7_TEST_HOOKS=str(hook), AOS7_TEST_CORE3_GATE=str(c.root/'release'))
    c.cli('aos7-tick', c.root, 'a', env=env)
    entered = wait(lambda: (c.root/'release.entered').exists(), what='runner before Popen')
    sd = node/'.aos/tasks/s'
    birth = read(sd/'birth.json')
    runner = ident(birth['runner']['pid'])
    c.data['injection'] = {'point':'runner-before-popen', 'entered':entered, 'runner':runner,
                           'pid_json_absent':not (sd/'pid.json').exists(), 'matching_processes':scan(node=node,tid='s')}
    write(sd/'ctl.json', {'op':'kill','run':1,'by':'core3'})
    c.cli('aos7-tock', c.root, 'a')
    result = read(sd/'ctl-done.json')['result']
    c.check('pre-Popen kill ok:false', result['ok'], False)
    c.check('pre-Popen message begins unknown', result['msg'].startswith('unknown'))
    c.check('pre-Popen request retained', (sd/'ctl.json').exists())
    c.check('runner remains same live process', alive(runner))
    c.data['first_receipt'] = result
    # tick retries the retained request while still gated; then release and tock retries successfully.
    c.cli('aos7-tick', c.root, 'a')
    (c.root/'release').touch()
    task = c.ready()
    wait(lambda: read(sd/'pid.json'), what='pid publication')
    c.cli('aos7-tock', c.root, 'a')
    result = read(sd/'ctl-done.json')['result']
    c.data.update(second_receipt=result, task_before=task, task_after=ident(task['pid']))
    c.check('released kill succeeds', result['ok'])
    c.check('request removed after successful kill', (sd/'ctl.json').exists(), False)
    c.check('PID + starttime is no longer non-zombie live', alive(task), False)
    c.check('no same-run task remains', [p for p in scan(node=node,tid='s') if p['run']=='1'], [])

if __name__ == '__main__':
    run_cases([('r801-%d'%i,probe) for i in range(1,4)])
