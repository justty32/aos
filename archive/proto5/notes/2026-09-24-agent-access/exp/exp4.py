"""實驗 4：只用現有指示詞＋bwrap，把 base 的 bash／read 關進 /work/ws。
用 aos-agent 真正的送件函式 tool_inst() 產生 inst，再用真的 aos-exec 跑（不起 daemon／kernel）。先跑 exp1.py、exp2.sh。"""
import json
import os
import shutil
import subprocess
import sys

P5 = '/home/lorkhan/repo/simple_tools/aos/.claude/worktrees/agent-ac1cb383e848a770e/proto5'
sys.path.insert(0, P5 + '/lib')
from pathlib import Path  # noqa: E402

from aos_agent_batch import tool_inst  # noqa: E402

S = os.path.dirname(os.path.abspath(__file__))
amy = Path(S + '/amy')
shutil.rmtree(amy / 'tools', ignore_errors=True)
(amy / 'tools').mkdir(parents=True)
shutil.copytree(S + '/amy-tools-base', amy / 'tools' / 'base')
(amy / 'tools' / 'base' / 'config.json').write_text('{"root": "/work/ws"}')   # 工具在牢裡看到的根
(amy / 'work').mkdir(exist_ok=True)


def meta(tool):
    return {"argv": ["bwrap", "--unshare-all", "--die-with-parent", "--new-session",
                     "--ro-bind", "/usr", "/usr", "--symlink", "usr/bin", "/bin", "--symlink", "usr/lib", "/lib",
                     "--symlink", "usr/lib", "/lib64", "--proc", "/proc", "--dev", "/dev", "--tmpfs", "/tmp",
                     "--ro-bind", "tools/base", "/opt/base",
                     "--bind", {"$ref": "access.json#/ws"}, "/work/ws", "--chdir", "/work/ws",
                     "--clearenv", "--setenv", "PATH", "/usr/bin", "--setenv", "HOME", "/work/ws",
                     "python3", "/opt/base/" + tool],
            "envs": {"$opt": "clear", "$val": {"PATH": "/usr/bin"}}}


def run(label, tool, args):
    name = 'exp-%s' % tool
    (amy / 'work' / (name + '.in')).write_text(json.dumps(args))
    inst = tool_inst(meta(tool), amy, name, dict(os.environ))
    path = amy / 'work' / (name + '.inst.json')
    path.write_text(json.dumps(inst))
    env = dict(os.environ, PATH=P5 + '/cli:' + os.environ['PATH'])
    r = subprocess.run(['aos-exec', str(path)], env=env, capture_output=True, text=True)
    out = (amy / 'work' / (name + '.out')).read_text().strip().splitlines()
    print(label, '| exit', r.returncode, '|', (out[-1] if out else '').replace(S, '$S'), r.stderr.strip()[:80])


for ws in ('ws-A', 'ws-B'):
    (amy / 'access.json').write_text(json.dumps({"ws": S + '/' + ws}))
    print('-- access.json ws =', ws)
    run('bash pwd; ls            ', 'bash', {"command": "pwd; ls | tr '\\n' ' '"})
    run('bash cat ../../amy/...  ', 'bash', {"command": "cat ../amy/secret.txt; cat %s/amy/secret.txt; echo end" % S})
    run('bash 看環境變數          ', 'bash', {"command": "echo K=$AOS_KERNEL_HOME"})
    run('read ../self            ', 'read', {"path": "../self/info.json"})
