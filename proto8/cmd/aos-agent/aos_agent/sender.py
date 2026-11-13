# aos_agent/sender.py - say／chat 的寄件人：--from ＞ $AOS_STACK 落在表上哪一隻的 stack ＞ 登入名；只有外部 coding agent（eca）的信帶寄件人。
"""11-13 使用者裁「a2a這個按照建議」「say/chat被當成不是使用者打的，我覺得可以」：對 eca 說的話補上真正的寄件人——誰下的指令寫誰。
寄件人放在信 body 的 name（OpenAI user message 自己的選填欄），aos-eca-turn 拿去當訊息信封的署名、不接進 history。
目標不是 eca（定義沒有 cli.json）＝信照舊不帶 name（那種 agent 的 idle 把 body 原樣接進 history、再送給模型端點，不多塞欄位）。"""
import getpass
import os

import aos_ws
from agent import cli_a2a
from .common import Fail, bad_args, table, under
from .system import eca_kind

FLAG = {"--from": "from"}


def sender(opts, help):
    """--from NAME（不合格＝ArgumentsBad）＞ $AOS_STACK 在表上某一隻的 stack 裡＝那隻的名字（agent 的工具或它的 CLI 下的指令）＞ 登入名（人）。"""
    name = opts.get("from")
    if name is not None:
        if not cli_a2a.name_ok(name):
            raise bad_args(help, "--from must be one line of at most %d characters without \" < > &" % cli_a2a.NAME_MAX)
        return name
    stack = os.environ.get("AOS_STACK") or ""
    if stack:
        try:
            rows = table()
        except Fail:
            rows = {}
        hit = None
        for n, r in rows.items():
            st = r.get("stack")
            if isinstance(st, str) and st and under(stack, st) and (hit is None or len(os.path.realpath(st)) > len(os.path.realpath(hit[1]))):
                hit = (n, st)
        if hit and cli_a2a.name_ok(hit[0]):
            return hit[0]
    try:
        name = getpass.getuser()
    except (KeyError, OSError):
        name = ""
    return name if cli_a2a.name_ok(name) else "user"


def put(a, text, name):
    """寄一則到 a 的 queue；a 是 eca 才帶寄件人。回信件名稱。"""
    return aos_ws.put(a.stack, text, name if eca_kind(a.row.get("def") or "") else None)
