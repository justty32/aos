# aos/apps/comm/common.py - aos-comm 各層共用：這次執行的外層旗標（-s STACK、-d DAEMON）與動作那層的旗標解析（錯誤轉成 comm.Fail）。
from aos import flags as aos_flags
from aos.comm import Fail

CTX = {"prog": "aos-comm", "stack": None, "daemon": None}   # main 填；-s／-d 寫在子命令後也收（aos_flags 寫回外層 opts，main 再抄進來）
ROOT_OPTS = {}


def parse(argv, name, help_text, flags=None, switches=None):
    """動作那層：位置參數後的旗標也收、外層的 -s／-d 也認；-j＝--json。"""
    try:
        opts, rest = aos_flags.parse(argv, flags or {}, switches or {}, help=help_text,
                                     short={"-j": "--json"} if "--json" in (switches or {}) else None)
    except aos_flags.Error as e:
        raise Fail(e.code, "%s (see aos-comm %s --help)" % (e, name))
    CTX["stack"] = ROOT_OPTS.get("stack") or CTX["stack"]
    CTX["daemon"] = ROOT_OPTS.get("daemon") or CTX["daemon"]
    return opts, rest
