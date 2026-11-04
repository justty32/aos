"""實驗 1：用現有指示詞把 workspace 映射寫在 access.json，工具 _meta 用 $ref 取。
不起 daemon／kernel，只呼叫 aos_inst.load_obj（aos-agent 送件時就是用它解 _meta）。"""
import json
import os
import shutil
import sys

sys.path.insert(0, '/home/lorkhan/repo/simple_tools/aos/.claude/worktrees/agent-ac1cb383e848a770e/proto5/lib')
import aos_inst  # noqa: E402

S = os.path.dirname(os.path.abspath(__file__))
amy = S + '/amy'
for d in ('amy', 'ws-A', 'ws-B', 'util-tools'):
    shutil.rmtree(S + '/' + d, ignore_errors=True)
    os.makedirs(S + '/' + d)
open(amy + '/secret.txt', 'w').write('secret-of-amy\n')
open(amy + '/info.json', 'w').write('{"_metainfo":{"_type":"llm_agent","_version":1}}\n')
open(S + '/ws-A/a.txt', 'w').write('in-A\n')
open(S + '/ws-B/b.txt', 'w').write('in-B\n')
os.symlink('../amy', S + '/ws-A/sneaky')


def put(path, obj):
    with open(path, 'w') as f:
        json.dump(obj, f)


def try_load(label, meta, env=None):
    try:
        d = aos_inst.load_obj(meta, amy, env=env)
        print(label, 'OK  cwd=%s argv=%s envs=%s' % (d['cwd'], d['argv'], d['envs']))
        return d
    except aos_inst.InstError as e:
        print(label, 'ERR', e.code, e.msg)


put(amy + '/access.json', {"ws": S + "/ws-A"})
meta = {"argv": ["tools/base/read"], "cwd": {"$ref": "access.json#/ws"},
        "envs": {"AOS_WS": {"$ref": "access.json#/ws"}}}
try_load('1 cwd 從 access.json   :', meta)
put(amy + '/access.json', {"ws": S + "/ws-B"})
try_load('2 改 access.json 一行後:', meta)
print('  -> argv[0] 仍是相對路徑 tools/base/read，exec 時相對新的 cwd 找，會 127')

put(S + '/util-tools/bash-edit-a.meta.json',
    {"argv": ["/abs/util-tools/bin/edit"], "cwd": {"$ref": "access.json#/ws"}})
try_load('3 _meta 整份 $ref 共用檔:', {"$ref": "../util-tools/bash-edit-a.meta.json"})

fmt = {"argv": [{"$fmt": {"$val": "${h}/tools/base/read", "h": {"$env": "AOS_AGENT_HOME"}}}]}
try_load('4 沒有家路徑可取       :', fmt, env={})
try_load('5 若 aos-agent 給家路徑:', fmt, env={"AOS_AGENT_HOME": amy})

put(amy + '/access.json', {"ws": S + "/ws-B", "allow": ["ws-B", "other"]})
try_load('6 陣列塞進環境變數     :', {"argv": ["x"], "envs": {"AOS_ALLOW": {"$ref": "access.json#/allow"}}})
try_load('7 陣列塞進 argv        :', {"argv": ["x", {"$ref": "access.json#/allow"}]})
put(amy + '/access.json', {"ws": S + "/ws-A"})
