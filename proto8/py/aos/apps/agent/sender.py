# aos/apps/agent/sender.py - say／chat 的寄件人：--from ＞ $AOS_STACK 落在表上哪一隻的 stack ＞ 登入名；只有外部 coding agent（eca）的信帶寄件人。
"""11-13 使用者裁「a2a這個按照建議」「say/chat被當成不是使用者打的，我覺得可以」：對 eca 說的話補上真正的寄件人——誰下的指令寫誰。
寄件人放在信 body 的 name（OpenAI user message 自己的選填欄），aos-eca-turn 拿去當訊息信封的署名、不接進 history。
目標不是 eca（定義沒有 cli.json）＝信照舊不帶 name（那種 agent 的 idle 把 body 原樣接進 history、再送給模型端點，不多塞欄位）。"""
import getpass
import os

from aos import ws as aos_ws
from aos.agentlib import cli_a2a
from .common import Fail, bad_args, table, under
from .system import eca_kind

FLAG = {"--from": "from"}
# 11-24（ops 意見 ③，使用者「那四條也照推薦做」）：寄件人是另一隻 agent（$AOS_STACK 落在表上某一隻的 stack 裡）或明給了 --from，
# 訊息本文前面接「[say from 名字] 」，fsm 與 eca 收到的、進 history 的都看得出是誰說的（不會把上層 agent 的提醒當成使用者說的）。
# 人在終端直接打的（沒有 --from、$AOS_STACK 不在表上）不加：沒有這個前綴＝使用者本人。
class Who(str):
    """寄件人名字；tagged＝它是另一隻 agent 或明給的 --from（本文要接「[say from 名字] 」）。"""
    tagged = False


def _who(name, tagged):
    w = Who(name)
    w.tagged = tagged
    return w


def sender(opts, help):
    """--from NAME（不合格＝ArgumentsBad）＞ $AOS_STACK 在表上某一隻的 stack 裡＝那隻的名字（agent 的工具或它的 CLI 下的指令）＞ 登入名（人）。"""
    name = opts.get("from")
    if name is not None:
        if not cli_a2a.name_ok(name):
            raise bad_args(help, "--from must be one line of at most %d characters without \" < > &" % cli_a2a.NAME_MAX)
        return _who(name, True)
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
            return _who(hit[0], True)
    try:
        name = getpass.getuser()
    except (KeyError, OSError):
        name = ""
    return name if cli_a2a.name_ok(name) else "user"


def tag(text, name):
    """寄件人是 agent 或明給 --from（sender 回的 Who.tagged）＝本文前接「[say from 名字] 」；人在終端打的、或本文以「[aos] 」開頭
    （aos 工具的通知，例 fork 的開場；11-24 test_fork 抓到）照原樣。"""
    if text.startswith("[aos] "):                    # aos 自己的通知（fork 開場、[aos] new_mail…）本來就說了不是使用者，不再疊一層
        return text
    return "[say from %s] %s" % (name, text) if getattr(name, "tagged", False) and name else text


def put(a, text, name):
    """寄一則到 a 的 queue；a 是 eca 才帶寄件人（body 的 name）；本文照 tag 帶來源。回信件名稱。"""
    return aos_ws.put(a.stack, tag(text, name), name if eca_kind(a.row.get("def") or "") else None)
