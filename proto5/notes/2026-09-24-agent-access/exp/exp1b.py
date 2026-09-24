"""實驗 1b：cwd 換掉之後，其他欄位的 $ref 相對誰；幾種繞法。先跑 exp1.py 建目錄。"""
import json
import os
import sys

sys.path.insert(0, '/home/lorkhan/repo/simple_tools/aos/.claude/worktrees/agent-ac1cb383e848a770e/proto5/lib')
import aos_inst  # noqa: E402

S = os.path.dirname(os.path.abspath(__file__))
amy = S + '/amy'


def t(label, meta):
    try:
        d = aos_inst.load_obj(meta, amy)
        envs = {k: v.replace(S, '$S') for k, v in d['envs'].items()}
        print(label, 'OK cwd=%s envs=%s' % (d['cwd'].replace(S, '$S'), envs))
    except aos_inst.InstError as e:
        print(label, 'ERR', e.code, e.msg.replace(S, '$S'))


with open(amy + '/access.json', 'w') as f:
    json.dump({"ws": S + "/ws-A", "allow": S + "/ws-A:" + S + "/shared"}, f)
t('8  envs 用 $ref:"" 指 /cwd     :', {"argv": ["x"], "cwd": {"$ref": "access.json#/ws"},
                                       "envs": {"AOS_WS": {"$ref": "", "$at": "/cwd"}}})
t('9  envs 寫 ../amy/access.json  :', {"argv": ["x"], "cwd": {"$ref": "access.json#/ws"},
                                       "envs": {"AOS_WS": {"$ref": "../amy/access.json#/ws"}}})
t('10 沒寫 cwd，envs 相對家       :', {"argv": ["x"], "envs": {"AOS_ALLOW": {"$ref": "access.json#/allow"}}})
