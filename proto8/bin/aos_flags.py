"""aos_flags：命令列旗標解析（aos-exec、aos-loop、aos-daemon 共用；10-21 plan L1）。純標準庫。

    import aos_flags
    opts, rest = aos_flags.parse(argv, {"--ws": "ws"})   # 錯丟 aos_flags.Error(原因)

規則（10-21 ideas § 3）：`[旗標...] XXX [args...]`——第一個不是旗標的參數（不以 - 開頭，或就是 -）起全部是 rest
（rest[0]＝XXX，之後原樣，不再解析旗標）；`--` 結束旗標（XXX 可以 - 開頭）。旗標都帶一個值：`--x V` 或 `--x=V`，
重複給＝最後一個算。opts＝{旗標表的值: 字串}。不認得的旗標、旗標缺值＝Error；有沒有 XXX 由呼叫者自己判斷（rest 可能是空的）。
錯誤訊息怎麼印也是呼叫者的事（各程式自己印 `程式名: usage: …（原因）`）。"""


class Error(Exception):
    pass


def parse(argv, flags):
    opts, i = {}, 0
    while i < len(argv):
        a = argv[i]
        if a == "--":
            i += 1
            break
        if not a.startswith("-") or a == "-":
            break
        name, eq, val = a.partition("=")
        if name not in flags:
            raise Error("不認得的旗標 %s" % name)
        if not eq:
            i += 1
            if i == len(argv):
                raise Error("%s 缺值" % name)
            val = argv[i]
        opts[flags[name]] = val
        i += 1
    return opts, argv[i:]
