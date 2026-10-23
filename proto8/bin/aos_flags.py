"""aos_flags：命令列旗標解析（aos-exec、aos-loop、aos-daemon、aos-fsm 共用；10-21 plan L1）、設定檔讀取與 run／val 的寫法（10-21 傍晚）。純標準庫。

    import aos_flags
    opts, rest = aos_flags.parse(argv, {"--ws": "ws"})   # 錯丟 aos_flags.Error(原因)；e.code＝錯誤代號

規則（10-21 ideas § 3）：`[旗標...] XXX [args...]`——第一個不是旗標的參數（不以 - 開頭，或就是 -）起全部是 rest
（rest[0]＝XXX，之後原樣，不再解析旗標）；`--` 結束旗標（XXX 可以 - 開頭）。帶值的旗標寫 `--x V` 或 `--x=V`，
重複給＝最後一個算。opts＝{旗標表的值: 字串}。
不帶值的旗標（開關，10-22 `--dotenv-override`）另給一張表 switches：給了＝opts[值] 是 True，重複給＝一樣，寫 `--x=V`＝Error。不認得的旗標、旗標缺值＝Error；有沒有 XXX 由呼叫者自己判斷（rest 可能是空的）。
錯誤訊息怎麼印也是呼叫者的事（各程式自己印 `程式名: Usage usage: …（原因）`）。

錯誤代號（10-23 照 impls，使用者 10-22「錯誤訊息多代號也遵循」）：Error 帶 code——parse 的錯一律 Usage；
load_cfg：讀不到 ReadFailed、不是 JSON JsonSyntax、# 後不是 /、指不到 FieldType；target：FieldType。"""


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
                raise Error("%s 不帶值" % name, "Usage")
            opts[switches[name]] = True
            i += 1
            continue
        if name not in flags:
            raise Error("不認得的旗標 %s" % name, "Usage")
        if not eq:
            i += 1
            if i == len(argv):
                raise Error("%s 缺值" % name, "Usage")
            val = argv[i]
        opts[flags[name]] = val
        i += 1
    return opts, argv[i:]


def load_cfg(spec):
    """讀設定檔（aos-loop、aos-daemon、aos-fsm 的唯一位置參數；10-21 傍晚 ideas § 9）：`檔` 或 `檔#/指標`。
    第一個 # 就切、# 後面要是 /（同 aos-exec 的入口路徑，N-62）；指標照 JSON pointer（~1＝/、~0＝~）。
    第一行是 `#!` 就跳過（10-22 使用者要 Python 照 C++ 版的寬鬆，原本報錯）。
    回那個位置的值（不驗是不是物件，呼叫者自己驗）。讀不到、不是 JSON、# 後不是 /、指不到＝Error。"""
    import json
    path, hashed, ptr = spec.partition("#")
    if hashed and not ptr.startswith("/"):
        raise Error("設定檔 %s 的 # 後面要接 /" % spec, "FieldType")
    try:
        with open(path, encoding="utf-8") as f:
            text = f.read()
        if text.startswith("#!"):
            text = text.partition("\n")[2]
        doc = json.loads(text)
    except OSError as e:
        raise Error("讀不到或不是 JSON：%s（%s）" % (path, e), "ReadFailed")
    except ValueError as e:   # 不是 UTF-8 也算
        raise Error("讀不到或不是 JSON：%s（%s）" % (path, e), "JsonSyntax")
    for tok in ptr[1:].split("/") if hashed else ():
        tok = tok.replace("~1", "/").replace("~0", "~")
        if isinstance(doc, dict) and tok in doc:
            doc = doc[tok]
        elif isinstance(doc, list) and tok.isdigit() and (tok == "0" or not tok.startswith("0")) \
                and int(tok) < len(doc):
            doc = doc[int(tok)]
        else:
            raise Error("設定檔指不到：%s" % spec, "FieldType")
    return doc


def target(v, what):
    """run／val（10-21 傍晚 ideas § 9）：字串＝aos-exec 的目標；陣列＝[目標, 參數...]（元素都要是字串、不能是空的）。
    回 (目標, [參數...])；寫法不對丟 Error。"""
    if isinstance(v, str):
        return v, []
    if isinstance(v, list) and v and all(isinstance(a, str) for a in v):
        return v[0], v[1:]
    raise Error("%s 要是 aos-exec 的目標（字串）或 [目標, 參數...]（非空字串陣列）" % what, "FieldType")
