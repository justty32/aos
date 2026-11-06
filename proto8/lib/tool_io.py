"""tool_io - lib 工具共用的開頭：schema 生成 --help、旗標映射 stdin JSON 與最小型別檢查、Ctrl-C、錯誤行／提醒行、查工作區、兩鐘期限。

使用者 11-05 裁「收成共用模組」（thinking 2026-11-05 stdio-unify § 剩下的；原則「統一成單一介面，這樣只需要改介面」）：
錯誤行與提醒行的格式只寫在這裡，各工具不自己拼字串。不是工具（沒有 _entry），是 lib 最底下的共用模組；純標準庫。

工具怎麼找到它（lib/docs/01 規則 9）：先找工具自己的資料夾（複製出 lib 的工具，把這支一起複製進去），再找 lib/（工具資料夾往上兩層）：
    HERE = os.path.dirname(os.path.realpath(__file__))
    sys.path[:0] = [HERE, os.path.dirname(os.path.dirname(HERE))]
    import tool_io
沙箱裡要看得到這支：綁工具資料夾時把它也綁唯讀（例 cmd/aos-sandbox/examples/bash-boxed/sandbox.json 的 ro）。

旗標映射（thinking/2026-11/05/json-argv 的 03、07 與 J1 任務書）：
_tooldef.json.env 只生成 hub 環境變數說明；parameters 同源生成旗標、說明與 type／required 檢查；旗標優先於 stdin，點路徑只換一葉。
start 不讀參數；arguments 第一次才解析並快取，stdin 是終端就不讀；額外 JSON 鍵忽略、未知旗標報錯。

形狀（lib 契約，lib/docs/01 規則 3、5、5a）：
  錯誤行  「<名>: error: <代號> <原因>」：stderr 一行；給腦用的工具（預設）stdout 也印同一行（stdout 是給腦看的結果）；退 1。
  提醒行  「<名>: warning: <句子>」：只在 stderr、不帶代號。
  --help  argv 在 -- 前有 --help＝手寫說明加上 schema 生成的旗標段，印 stdout、退 0。
  Ctrl-C  不吐 traceback、退 130（有子行程的工具自己再接 SIGINT，先收那一群）。
  讀的人先關了 stdout（EPIPE，例 `| head -c0`）＝照 Unix 預設被 SIGPIPE 打掉、退 141（128＋13），不吐 traceback（11-05 晚邊緣測試）。"""
import copy, json, math, os, signal, sys, textwrap, time

NAME, ECHO = "tool", True
_TOOLDEF, _ARGUMENTS = None, None
_TYPES = {"string", "integer", "number", "boolean", "array", "object", "null"}
_TICK_WARNED = set()


class Error(Exception):
    """純函式的錯誤代號與英文原因，由工具入口轉成錯誤行。"""
    def __init__(self, code, reason):
        self.code = code
        super().__init__(reason)


def _tick_decimal(text, source, positive=False):
    """只收 ASCII 十進位整數，範圍與 C++ 的 long long 相同。"""
    if not text or any(ch < "0" or ch > "9" for ch in text):
        value = -1
    else:
        try:
            value = int(text.lstrip("0") or "0")
        except ValueError:
            value = -1
    if value < (1 if positive else 0) or value > 9223372036854775807:
        kind = "positive" if positive else "non-negative"
        raise Error("TickBad", "%s must be a %s decimal integer within signed 64-bit range" % (source, kind))
    return value


def warn_missing_tick(path, prog=None):
    """缺檔提醒共用快取；命令列與工具在同一行程只印一次。"""
    key = (os.getpid(), path)
    if key not in _TICK_WARNED:
        _TICK_WARNED.add(key)
        warn("AOS_TICK points to a missing file; treating the clock as 0", prog=prog)


def now_tick():
    """沒設 AOS_TICK＝None；缺檔 warning 每行程每路徑一次且當 0；空檔＝0；壞檔＝TickBad。"""
    path = os.environ.get("AOS_TICK")
    if not path:
        return None
    try:
        with open(path, "rb") as f:
            text = f.read().strip(b" \t\n\r\f\v").decode("ascii")
    except FileNotFoundError:
        warn_missing_tick(path)
        return 0
    except (OSError, UnicodeError, ValueError) as e:
        raise Error("TickBad", "cannot read AOS_TICK file %s: %s" % (path, e)) from None
    return _tick_decimal(text, "AOS_TICK file") if text else 0


def tick_interval_ms():
    """AOS_TICK_INTERVAL 的正整數毫秒，沒設或空＝1000。"""
    text = os.environ.get("AOS_TICK_INTERVAL")
    return _tick_decimal(text, "AOS_TICK_INTERVAL", positive=True) if text else 1000


def utc_now_epoch_ms():
    """現在的 UTC epoch 毫秒，可寫檔跨行程比較。"""
    return time.time_ns() // 1000000


def deadline_after(ticks):
    """回 (on_tick, at)；有時鐘數 tick，否則換成 UTC epoch 毫秒。"""
    if not isinstance(ticks, int) or isinstance(ticks, bool) or not -9223372036854775808 <= ticks <= 9223372036854775807:
        raise Error("TickBad", "deadline ticks must be an integer within signed 64-bit range")
    now = now_tick()
    on_tick = now is not None
    if on_tick:
        at = now + ticks
    else:
        duration = ticks * tick_interval_ms()
        if not -9223372036854775808 <= duration <= 9223372036854775807:
            raise Error("TickBad", "deadline duration is outside signed 64-bit range")
        at = utc_now_epoch_ms() + duration
    if not -9223372036854775808 <= at <= 9223372036854775807:
        raise Error("TickBad", "deadline is outside signed 64-bit range")
    return on_tick, at


def expired(deadline):
    """依期限種類判到期；同一行程不應失去時鐘，若失去就回 False。"""
    on_tick, at = deadline
    if on_tick:
        now = now_tick()
        return now is not None and now >= at
    return utc_now_epoch_ms() >= at


def _object(value):
    return value if isinstance(value, dict) else {}


def _strings(value):
    return value if isinstance(value, (list, tuple)) and all(isinstance(x, str) for x in value) else ()


def _properties(schema):
    return _object(_object(schema).get("properties"))


def _type(schema):
    t = _object(schema).get("type")
    if isinstance(t, list):
        t = next((x for x in t if isinstance(x, str) and x != "null"), None)
    return t if isinstance(t, str) and t in _TYPES else None


def _parameters(tooldef):
    return tooldef.get("parameters") if isinstance(tooldef, dict) and isinstance(tooldef.get("parameters"), dict) else None


def load_tooldef(folder):
    """讀定義；缺檔安靜退回無 schema，其餘壞檔只提醒一次。"""
    try:
        with open(os.path.join(folder, "_tooldef.json")) as f:
            td = json.load(f)
        if not isinstance(td, dict):
            raise ValueError("top level must be an object")
        if _parameters(td) is None:
            raise ValueError("parameters must be an object")
        return td
    except FileNotFoundError:
        return None
    except (OSError, ValueError) as e:
        warn("cannot use _tooldef.json (%s); flags are passed as strings" % e)
        return None


def start(name, help_text=None, echo=True, *, tooldef=None):
    """記名字、讀定義、處理說明與訊號；不解析其餘 argv，也不讀 stdin。"""
    global NAME, ECHO, _TOOLDEF, _ARGUMENTS
    NAME, ECHO, _ARGUMENTS = name, echo, None
    _TOOLDEF = tooldef
    if tooldef is None and sys.argv and sys.argv[0]:
        _TOOLDEF = load_tooldef(os.path.dirname(os.path.realpath(sys.argv[0])))
    elif tooldef is not None and _parameters(tooldef) is None:
        warn("cannot use _tooldef.json (parameters must be an object); flags are passed as strings")
        _TOOLDEF = None
    for arg in sys.argv[1:]:
        if arg == "--":
            break
        if arg == "--help":
            print(help_from_tooldef(name, _TOOLDEF, help_text or ""), end="")
            sys.exit(0)
    signal.signal(signal.SIGINT, lambda signum, frame: sys.exit(130))
    signal.signal(signal.SIGPIPE, signal.SIG_DFL)  # stdout 被關＝安靜退 141


def error_line(code, reason):
    return "%s: error: %s %s" % (NAME, code, str(reason).replace("\n", " "))


def die(code, reason, before=""):
    """印錯誤行、退 1。before＝錯誤行之前先印到 stdout 的東西（例 bash 截到一半的輸出）。"""
    line = error_line(code, reason)
    print(line, file=sys.stderr, flush=True)
    if ECHO:
        sys.stdout.write(before + line + "\n")
        sys.stdout.flush()
    sys.exit(1)


def warn(sentence, prog=None):
    name = NAME if prog is None else prog
    print("%s: warning: %s" % (name, str(sentence).replace("\n", " ")), file=sys.stderr, flush=True)


def workspace():
    """$AOS_WS 的真實路徑；沒設或不是資料夾＝WsMissing。"""
    ws = os.environ.get("AOS_WS")
    if not ws or not os.path.isdir(ws):
        die("WsMissing", "AOS_WS is not set or not a directory")
    return os.path.realpath(ws)


def tokenize_flags(argv, kind):
    """順序呼叫 kind；第一個位置參數起（或 -- 後）不再解旗標。"""
    pairs, i = [], 0
    while i < len(argv):
        arg = argv[i]
        if arg == "--":
            return pairs, list(argv[i + 1:])
        if not arg.startswith("-") or arg == "-":
            break
        flag, equals, value = arg.partition("=") if arg.startswith("--") else (arg, "", "")  # 單槓整個是名（P-44）
        k = kind(flag)
        if k not in ("value", "switch"):
            raise Error("FlagUnknown", "unknown flag %s" % flag)
        if k == "switch":
            if equals:
                raise Error("ArgumentsBad", "%s takes no value" % flag)
            value = None
        elif not equals:
            i += 1
            if i == len(argv):
                raise Error("ArgumentsBad", "%s needs a value" % flag)
            value = argv[i]
        pairs.append((flag, value))
        i += 1
    return pairs, list(argv[i:])


def _leaf(schema, path, flag):
    if schema is None:
        return {}
    node = schema
    for i, key in enumerate(path):
        if i and _type(node) not in (None, "object"):
            raise Error("ArgumentsBad", "%s: %s is not an object" % (flag, ".".join(path[:i])))
        if i and not _properties(node):
            return {}                         # 自由物件（object 或沒型別、沒宣告 properties）不替下層宣告型別
        props = _properties(node)
        if key not in props:
            raise Error("FlagUnknown", "unknown flag %s" % flag)
        node = _object(props[key])
    return node


def _flag(schema, flag):
    if not flag.startswith("--"):
        raise Error("FlagUnknown", "unknown flag %s" % flag)
    path = tuple(flag[2:].replace("-", "_").split("."))
    if not all(path):
        raise Error("ArgumentsBad", "bad flag name %s" % flag)
    try:
        return path, _leaf(schema, path, flag), False
    except Error as e:
        if e.code != "FlagUnknown" or not flag.startswith("--no-"):
            raise
        positive = (path[0][3:],) + path[1:]
        try:
            node = _leaf(schema, positive, flag)
        except Error:
            raise e
        if _type(node) != "boolean":
            raise e
        return positive, node, True


def _convert(value, node, flag):
    t = _type(node)
    try:
        if t == "integer":
            return int(value)
        if t == "number":
            try:
                return int(value)
            except ValueError:
                n = float(value)
                if math.isfinite(n):
                    return n
                raise ValueError()
        if t in ("object", "array", "boolean", "null"):
            result = json.loads(value)
            if not _matches(result, t):
                raise ValueError()
            return result
        return value
    except (ValueError, OverflowError):
        label = {"integer": "an integer", "object": "an object as JSON", "array": "an array as JSON"}.get(t, "a %s" % t)
        raise Error("ArgumentsBad", "%s needs %s, got %r" % (flag, label, value)) from None


def _argv_pairs(argv, schema, positional):
    def kind(flag):
        _, node, _ = _flag(schema, flag)
        return "switch" if _type(node) == "boolean" else "value"
    raw, rest = tokenize_flags(argv, kind)
    pairs = []
    for flag, value in raw:
        path, node, negative = _flag(schema, flag)
        t = _type(node)
        item = _object(node.get("items")) if t == "array" else node
        pairs.append((path, not negative if t == "boolean" else _convert(value, item, flag), t == "array"))
    positional = _strings(positional) if schema is not None else ()
    for i, value in enumerate(rest):
        if i >= len(positional):
            raise Error("ArgumentsBad", "unexpected argument %r" % value)
        key = positional[i]
        node = _object(_properties(schema).get(key))
        array = _type(node) == "array"
        pairs.append(((key,), _convert(value, _object(node.get("items")) if array else node, "--" + key), array))
    return pairs


def _merge(arguments, pairs):
    result, arrays = copy.deepcopy(arguments), set()
    for path, value, array in pairs:
        obj = result
        for key in path[:-1]:
            if not isinstance(obj.get(key), dict):
                obj[key] = {}
            obj = obj[key]
        key = path[-1]
        if array:
            if path not in arrays or not isinstance(obj.get(key), list):
                obj[key] = []
            obj[key].append(value)
            arrays.add(path)
        else:
            obj[key] = value
    return result


def argv_to_json(argv, schema, positional=()):
    """純旗標映射；schema 是 parameters，None 表示無 schema。"""
    return _merge({}, _argv_pairs(argv, schema, positional))


def _matches(value, t):
    if t == "integer":
        return not isinstance(value, bool) and (isinstance(value, int) or isinstance(value, float) and value.is_integer())
    if t == "number":
        return isinstance(value, (int, float)) and not isinstance(value, bool)
    return isinstance(value, {"string": str, "boolean": bool, "array": list, "object": dict, "null": type(None)}[t])


def _validate(value, node, path=""):
    node = _object(node)
    if value is None:
        return
    types = node.get("type")
    types = [types] if isinstance(types, str) else types if isinstance(types, list) else []
    types = [t for t in types if isinstance(t, str) and t in _TYPES]
    if types and not any(_matches(value, t) for t in types):
        raise Error("ArgumentsBad", "%s must be %s" % (path, " or ".join(types)))
    if isinstance(value, dict):
        props = _properties(node)
        for key in _strings(node.get("required")):
            if value.get(key) is None:
                enums = _object(props.get(key)).get("enum")
                suffix = "; one of: " + ", ".join(map(str, enums)) if isinstance(enums, list) else ""
                raise Error("ArgumentsBad", "missing %s (required)%s" % (path + "." + key if path else key, suffix))
        for key, child in props.items():
            if key in value:
                _validate(value[key], child, path + "." + key if path else key)
    elif isinstance(value, list) and isinstance(node.get("items"), dict):
        for i, item in enumerate(value):
            _validate(item, node["items"], "%s[%d]" % (path, i))


def arguments(*required):
    """第一次合併 argv 與 stdin 並驗型別；其後回同一份快取。"""
    global _ARGUMENTS
    if _ARGUMENTS is None:
        schema = _parameters(_TOOLDEF)
        try:
            pairs = _argv_pairs(sys.argv[1:], schema, _object(_TOOLDEF).get("positional", ()))
        except Error as e:
            die(e.code, "%s (see %s --help)" % (e, NAME))
        try:
            raw = "" if sys.stdin is None or sys.stdin.isatty() else sys.stdin.read()
            a = json.loads(raw or "{}")
        except ValueError:
            die("ArgumentsBad", "stdin is not JSON")
        if not isinstance(a, dict):
            die("ArgumentsBad", "arguments must be an object")
        a = _merge(a, pairs)
        try:
            _validate(a, schema)
        except Error as e:
            die(e.code, str(e))
        _ARGUMENTS = a
    for k in required:
        if not isinstance(_ARGUMENTS.get(k), str) or not _ARGUMENTS[k]:
            die("ArgumentsBad", "missing %s (a string)" % k)
    return _ARGUMENTS


def help_from_tooldef(name, tooldef, extra=""):
    """手寫說明後接同源旗標段；無手寫說明時也能單獨生成用法。"""
    td, schema = _object(tooldef), _parameters(tooldef)
    description = str(td.get("description", "")).split(". ", 1)[0].rstrip(".")
    heading = textwrap.fill("%s - %s" % (name, description), width=100, subsequent_indent=" " * (len(name) + 3))
    lines = [extra[:-1] if extra.endswith("\n") else extra] if extra else [heading, "usage: %s [FLAGS] < ARGUMENTS.json   (a tool: run it with aos-exec)" % name]
    positional = _strings(td.get("positional"))
    if positional and schema is not None:
        lines.append("Positional: %s (fills %s)" % (" ".join(x.upper() for x in positional), " ".join(json.dumps(x) for x in positional)))
    props = _properties(schema)
    if schema is None:
        lines.append('Flags: no usable _tooldef.json here, so --KEY VALUE sets "KEY" to the string VALUE.')
    elif not props:
        lines.append("Flags: none (_tooldef.json declares no parameters).")
    else:
        lines.append("Flags (generated from _tooldef.json; each sets the same key of the JSON object on stdin):")
        def rows(node, prefix="", indent=2):
            for key, child in _properties(node).items():
                child = _object(child)
                path, t = prefix + key, _type(child)
                item_type = _type(child.get("items"))
                vt = (item_type or "string") if t == "array" else t
                meta = {"string": key.upper(), "integer": "N", "number": "NUM", "object": "JSON", "array": "JSON"}.get(vt, "VALUE")
                flag = "--" + path.replace("_", "-")
                label = flag + (", --no-" + path.replace("_", "-") if t == "boolean" else " " + meta)
                info = "array of " + (item_type or "string") if t == "array" else t or "untyped"
                if "default" in child:
                    info += ", default: " + json.dumps(child["default"])
                if key in _strings(node.get("required")):
                    info += ", required"
                if isinstance(child.get("enum"), list):
                    info += "; one of: " + ", ".join(map(str, child["enum"]))
                if t == "array":
                    info += "; repeat the flag to add items"
                if t == "object":
                    info += ", as JSON text; or set one key with %s.KEY VALUE" % flag
                text = info + ". " + str(child.get("description", ""))
                left = " " * indent + label
                column = max(30 + indent - 2, len(left) + 2)
                lines.extend(textwrap.wrap(text, width=100, initial_indent=left.ljust(column), subsequent_indent=" " * column, break_long_words=False, break_on_hyphens=False))
                if _properties(child):
                    rows(child, path + ".", indent + 2)
        rows(schema)
        lines.extend(["Flags override the stdin JSON; a dotted flag (--a.b V) changes only that nested key.", 'Keys the tool does not know are ignored; a key with "." in its name can only be given on stdin.', "An unknown flag is FlagUnknown; a bad value or a missing required key is ArgumentsBad."])
    if not extra:
        lines.append('Result on stdout. On error: one line "%s: error: CODE reason" on stderr and stdout, exit 1.' % name)
    if _strings(td.get("errors")):
        lines.append("Error codes: " + ", ".join(td["errors"]))
    env = td.get("env")
    if isinstance(env, list) and env and all(isinstance(x, str) for x in env):
        lines.append("Environment: " + ", ".join(env) + " (hub variables this tool needs; not set = <Name>Missing)")
    return "\n".join(lines) + "\n"
