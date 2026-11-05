"""aos_flags：命令列旗標解析（10-21 plan L1）。純標準庫。
aos 自己的 Python 程式（bin/ 的 aos-tick、aos-tools、aos-daemon-ctl…，extras 的 aos-mcp、aos-grow、aos-sandbox）都用它，
形狀照 CONVENTION P-44「aos 自己程式的命令列形狀」（11-04；C++ 那邊是 aos-util 的 aos::parse_cli）。
Python 版 aos-exec、aos-loop、aos-daemon、aos-fsm 10-23 刪了，只有它們用的 load_cfg（設定檔讀取）、target（目標的寫法）跟著拿掉，在 git 歷史。

    import aos_flags
    opts, rest = aos_flags.parse(argv, {"--ws": "ws"})   # 錯丟 aos_flags.Error(原因)；e.code＝錯誤代號

規則（10-21 ideas § 3）：`[旗標...] XXX [args...]`——第一個不是旗標的參數（不以 - 開頭，或就是 -）起全部是 rest
（rest[0]＝XXX，之後原樣，不再解析旗標）；`--` 結束旗標（XXX 可以 - 開頭）。帶值的旗標寫 `--x V` 或 `--x=V`，
重複給＝最後一個算。opts＝{旗標表的值: 字串}。
不帶值的旗標（開關，10-22 `--dotenv-override`）另給一張表 switches：給了＝opts[值] 是 True，重複給＝一樣，寫 `--x=V`＝Error。
可以重複給、每次都收的旗標（11-04，aos-grow 的 `--take`）另給一張表 multi：opts[值]＝照給的順序的字串串列（沒給＝沒這個 key）。不認得的旗標、旗標缺值＝Error；有沒有 XXX 由呼叫者自己判斷（rest 可能是空的）。
錯誤訊息怎麼印也是呼叫者的事（各程式自己印 `程式名: 代號 usage: …（原因）`）。

錯誤代號（代號照 10-23 命名統合（thinking/2026-10/23/naming）；使用者 10-22「錯誤訊息多代號也遵循」）：Error 帶 code——
parse：不認得的旗標 FlagUnknown、其他（缺值、開關帶值）ArgumentsBad。"""


class Error(Exception):
    def __init__(self, msg, code):
        super().__init__(msg)
        self.code = code


def parse(argv, flags, switches=None, multi=None):
    opts, i, switches, multi = {}, 0, switches or {}, multi or {}
    while i < len(argv):
        a = argv[i]
        if a == "--":
            i += 1
            break
        if not a.startswith("-") or a == "-":
            break
        name, eq, val = a.partition("=")
        if name in switches:
            if eq:
                raise Error("%s takes no value" % name, "ArgumentsBad")
            opts[switches[name]] = True
            i += 1
            continue
        if name not in flags and name not in multi:
            raise Error("unknown flag %s" % name, "FlagUnknown")
        if not eq:
            i += 1
            if i == len(argv):
                raise Error("%s needs a value" % name, "ArgumentsBad")
            val = argv[i]
        if name in multi:
            opts.setdefault(multi[name], []).append(val)
        else:
            opts[flags[name]] = val
        i += 1
    return opts, argv[i:]

