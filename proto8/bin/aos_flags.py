"""aos_flags：命令列旗標解析（10-21 plan L1）。純標準庫。
10-23 起只剩 aos-tick 用（使用者「python版本可以刪掉了。aos-exec/loop/daemon都用C++」，fsm 也改 C++、tick 先留 Python）：
Python 版 aos-exec、aos-loop、aos-daemon、aos-fsm 刪了，只有它們用的 load_cfg（設定檔讀取）、target（val 的寫法）跟著拿掉，在 git 歷史。

    import aos_flags
    opts, rest = aos_flags.parse(argv, {"--ws": "ws"})   # 錯丟 aos_flags.Error(原因)；e.code＝錯誤代號

規則（10-21 ideas § 3）：`[旗標...] XXX [args...]`——第一個不是旗標的參數（不以 - 開頭，或就是 -）起全部是 rest
（rest[0]＝XXX，之後原樣，不再解析旗標）；`--` 結束旗標（XXX 可以 - 開頭）。帶值的旗標寫 `--x V` 或 `--x=V`，
重複給＝最後一個算。opts＝{旗標表的值: 字串}。
不帶值的旗標（開關，10-22 `--dotenv-override`）另給一張表 switches：給了＝opts[值] 是 True，重複給＝一樣，寫 `--x=V`＝Error。不認得的旗標、旗標缺值＝Error；有沒有 XXX 由呼叫者自己判斷（rest 可能是空的）。
錯誤訊息怎麼印也是呼叫者的事（各程式自己印 `程式名: 代號 usage: …（原因）`）。

錯誤代號（代號照 10-23 命名統合（thinking/2026-10-23-naming）；使用者 10-22「錯誤訊息多代號也遵循」）：Error 帶 code——
parse：不認得的旗標 FlagUnknown、其他（缺值、開關帶值）ArgumentsBad。"""


class Error(Exception):
    def __init__(self, msg, code):
        super().__init__(msg)
        self.code = code


def parse(argv, flags, switches=None):
    opts, i, switches = {}, 0, switches or {}
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
                raise Error("%s 不帶值" % name, "ArgumentsBad")
            opts[switches[name]] = True
            i += 1
            continue
        if name not in flags:
            raise Error("不認得的旗標 %s" % name, "FlagUnknown")
        if not eq:
            i += 1
            if i == len(argv):
                raise Error("%s 缺值" % name, "ArgumentsBad")
            val = argv[i]
        opts[flags[name]] = val
        i += 1
    return opts, argv[i:]

