"""aos_json - 腦用的 json 工具一族共用的程式：簡單組 json_get／ls／search／set／add／del、複雜組 jsonx_get／ls／search／set／add／del 的殼都叫這裡的 main(op)（json_multi_get／set 轉 aos_json_multi）。

使用者 11-12（thinking 2026-11/12/json-tools）：「建議做成一個aos_json工具……做兩套」、兩套選 A——簡單組只收路徑＋值、值照字面、
不碰 $ref／$env／解析文字；複雜組另名，才有指示詞解開與否、穿過 $ref、值從文字或另一格來（圖紙 01-規劃 D1～D24）。
路徑一律一整串 `檔#/指標`（N-45／N-62：第一個 # 切；指標照 RFC 6901、跟 aos-json／$ref 同一套——`x.json` 是整份，`x.json#/` 是名字為空字串的那個 key，使用者 11-12「按照標準寫法」；`x.json#` 不收、照 aos-json 報錯，11-12 代定），檔相對 $AOS_WS、絕對照用。
自己不開檔：讀＝`aos-json get`、寫＝`aos-json set／append／del`（原子寫入、只重寫變的那一塊）；簡單組寫入帶 `--raw`（指示詞物件當普通物件）。
aos-json 的 stderr 原樣透出，它退 1 時接它錯誤行的代號與原因（C-52 例外：給腦用的工具轉接下層最後一行），沒那行＝CommandFailed。
上限（json_get 的 max_bytes、ls／search 的 limit）：呼叫參數 › 環境變數 AOS_JSON_MAX_BYTES／AOS_JSON_MAX_ITEMS（tools.json 工具格 env 蓋過行程環境）› 預設 8000／200。
輸出給腦：值一行緊湊 JSON；寫入 `ok 路徑`；不是值的結果用方括號行（`[too big]`、`[more]`、`[no match]`）退 0；錯照 lib 契約兩邊一行、退 1。"""
import json
import os
import subprocess
import sys

import tool_io

MAX_BYTES, MAX_ITEMS = 8000, 200
NO = object()                                   # 沒有值（null 也是值）
MULTI = False                                   # json_multi_* 逐格做時為 True：錯改成丟 Failed，由 aos_json_multi 記成那一格的結果


class Failed(Exception):
    def __init__(self, code, reason):
        super().__init__(code, reason)
        self.code, self.reason = code, reason


def die(code, reason):
    if MULTI:
        raise Failed(code, reason)
    tool_io.die(code, reason)


SIMPLE = {"get": "json_get", "ls": "json_ls", "search": "json_search", "set": "json_set", "add": "json_add", "del": "json_del"}


class Target:
    """一整串路徑切成：給腦看的檔名、真的檔、指標（"" ＝整份，只有不帶 # 的 `x.json`）。指標原樣交給 aos-json 解（RFC 6901），這裡只切檔名、拆層給走訪用。"""
    def __init__(self, path):
        cut = path.find("#")
        self.file, ptr = (path, "") if cut < 0 else (path[:cut], path[cut + 1:])
        if not self.file:
            die("PointerBad", "%s: no file name before # (write FILE#/POINTER, e.g. cfg.json#/a)" % path)
        if ptr and not ptr.startswith("/"):
            bare = ptr.strip("'\"\\ ")
            hint = "; it has quotes around it, write %s#%s" % (self.file, bare) if bare.startswith("/") else ""
            die("PointerBad", "%s: after # the pointer must start with /%s" % (path, hint))
        self.ptr = ptr
        self.real = tool_io.ws_path(self.file)
        self.toks = [t.replace("~1", "/").replace("~0", "~") for t in ptr[1:].split("/")] if ptr else []
        self.bare_hash = cut >= 0 and not ptr
        if self.bare_hash:                              # `x.json#` 不剝 #，原樣交給 aos-json、照它的規則報錯（11-12 代定）
            aos_json(["get", self.real + "#"], t=self)
            die("PointerBad", "%s: # must be followed by /" % path)

    def spec(self, ptr=None):
        ptr = self.ptr if ptr is None else ptr
        return self.real + ("#" + ptr if ptr else "")

    def shown(self, ptr=None):
        ptr = self.ptr if ptr is None else ptr
        return self.file + ("#" + ptr if ptr else "")

    def parent_ptr(self):
        return self.ptr[:self.ptr.rfind("/")]


def esc(key):
    return str(key).replace("~", "~0").replace("/", "~1")


def aos_json(argv, value=NO, t=None):
    """叫 aos-json；退 0 回 stdout。退 1 轉它最後一行的代號與原因（真檔路徑換回腦給的寫法、旗標換成參數名）。"""
    stdin = None if value is NO else json.dumps(value, ensure_ascii=False)
    try:
        r = subprocess.run(["aos-json"] + argv, input=stdin, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    except OSError as e:
        die("LaunchFailed", "aos-json failed to start (aos-json must be on PATH): %s" % e.strerror)
    if r.returncode == 0:
        return r.stdout
    sys.stderr.write(r.stderr)
    for line in reversed(r.stderr.splitlines()):
        if line.startswith("aos-json: error: "):
            code, _, reason = line[len("aos-json: error: "):].partition(" ")
            if t is not None:
                reason = reason.replace(t.real, t.file)
            reason = (reason.replace("add --parents", 'give "parents": true')
                      .replace("add --follow", 'use jsonx_get/jsonx_set with "follow": true')
                      .replace("(use append to add at the end)", "(write /- at the end of the path to append)"))
            if code == "FileMissing" and t is not None and t.ptr:
                reason += " (create it first, e.g. json_set %s with value {})" % t.file
            if t is not None and t.bare_hash:
                reason += "; use FILE alone for the whole document: %s" % t.file
            die(code, reason)
    die("CommandFailed", "aos-json %s exited %d (reason on stderr)" % (argv[0], r.returncode))


def read(t, ptr=None, flags=()):
    return json.loads(aos_json(["get"] + list(flags) + [t.spec(ptr)], t=t))


def compact(v):
    return json.dumps(v, ensure_ascii=False, separators=(",", ":"))


def kind(v):
    return ("null" if v is None else "boolean" if isinstance(v, bool) else "number" if isinstance(v, (int, float))
            else "string" if isinstance(v, str) else "array" if isinstance(v, list) else "object")


def size(v):
    """型別＋自然長度（物件 keys、陣列 items、字串 chars）；純值直接是值。"""
    n = {"object": "keys", "array": "items", "string": "chars"}.get(kind(v))
    return "%d %s" % (len(v), n) if n else compact(v)


def columns(v):
    """long 欄：型別 TAB 大小（容器與字串再多 bytes）。"""
    cols = [kind(v), size(v)]
    if isinstance(v, (dict, list, str)):
        cols.append("%d bytes" % len(compact(v).encode()))
    return "\t".join(cols)


def limit(args, key, env, default):
    if key in args:
        if type(args[key]) is not int or args[key] < 1:
            die("ArgumentsBad", "%s must be a positive integer" % key)
        return args[key]
    text = os.environ.get(env)
    if text is None:
        return default
    if text.isdigit() and int(text) > 0:
        return int(text)
    tool_io.warn("%s=%s is not a positive integer; using %d" % (env, text, default))
    return default


def same(a, b):
    """JSON 相等、型別要一樣（1 不等於 "1"、true 不等於 1）。"""
    if kind(a) != kind(b):
        return False
    if isinstance(a, list):
        return len(a) == len(b) and all(same(x, y) for x, y in zip(a, b))
    if isinstance(a, dict):
        return a.keys() == b.keys() and all(same(a[k], b[k]) for k in a)
    return a == b


def do_get(args, t, flags):
    v = read(t, flags=flags)
    text = compact(v)
    cap = limit(args, "max_bytes", "AOS_JSON_MAX_BYTES", MAX_BYTES)
    if args.get("full") or len(text.encode()) <= cap:
        return text
    return ('[too big] %s, %s, %d bytes (max_bytes %d). List it: json_ls %s. Or get a deeper path, or give "full": true.'
            % (kind(v), size(v), len(text.encode()), cap, t.shown()))


def head(v):
    return "%s, %s" % (kind(v), size(v)) if isinstance(v, (dict, list, str)) else "%s %s" % (kind(v), compact(v))


def page(lines, total, offset, cap, hint=None):
    shown = lines[offset:offset + cap]
    if offset + cap < total:
        shown.append("[more] %d to %d of %d shown; %s" % (offset, offset + len(shown) - 1, total,
                                                       hint or 'next: "offset": %d' % (offset + cap)))
    return shown


def do_ls(args, t, flags=()):
    v = read(t, flags=flags)
    out = [head(v) + (" (index 0..%d)" % (len(v) - 1) if isinstance(v, list) and v else "")]
    if isinstance(v, (dict, list)):
        items = list(v.items()) if isinstance(v, dict) else list(enumerate(v))
        offset = args.get("offset", 0)
        if type(offset) is not int or offset < 0:
            die("ArgumentsBad", "offset must be a non-negative integer")
        rows = [esc(k) + ("\t" + columns(x) if args.get("long") else "") for k, x in items]
        out += page(rows, len(rows), offset, limit(args, "limit", "AOS_JSON_MAX_ITEMS", MAX_ITEMS))
    return "\n".join(out)


def do_search(args, t, flags=()):
    if "key" not in args and "value" not in args:
        die("ArgumentsBad", "give key, value, or both")
    key, has_value, want, contains = args.get("key"), "value" in args, args.get("value"), bool(args.get("contains"))

    def hit(k, x):
        if key is not None:
            if not isinstance(k, str) or not (key in k if contains else key == k):
                return False
        if has_value:
            if contains and isinstance(want, str):
                return isinstance(x, str) and want in x
            return same(want, x)
        return True

    def members(node, ptr):
        items = node.items() if isinstance(node, dict) else enumerate(node) if isinstance(node, list) else ()
        return [(k, x, "%s/%s" % (ptr, esc(k))) for k, x in items]

    if flags:                                           # jsonx_search：從穿過／解開後的那格往下找；祖先跨檔說不清，不配 up
        if args.get("up"):
            die("ArgumentsBad", "up does not work with follow or resolve")
        node, chain = read(t, flags=flags), []
    else:
        read(t)                                         # 指不到照轉 aos-json 的錯
        doc = read(t, ptr="")
        node, chain = doc, [(doc, "")]
        for tok in t.toks:                              # 原文照走（同 aos-json get 不加 --follow）
            node = node[int(tok)] if isinstance(node, list) else node[tok]
            chain.append((node, chain[-1][1] + "/" + esc(tok)))
    found = []
    if args.get("up"):
        for anc, ptr in reversed(chain[:-1]):
            found += [(p, x) for k, x, p in members(anc, ptr) if hit(k, x)]
    else:
        def down(here, ptr):                            # 照檔裡的順序（前序）
            for k, x, p in members(here, ptr):
                if hit(k, x):
                    found.append((p, x))
                down(x, p)
        down(node, t.ptr)
    if not found:
        return "[no match]"
    rows = ["%s\t%s" % (t.shown(p), columns(x)) for p, x in found]
    return "\n".join(page(rows, len(rows), 0, limit(args, "limit", "AOS_JSON_MAX_ITEMS", MAX_ITEMS),
                          'narrow the path or give a bigger "limit"'))


def value_of(args, t, directives):
    """寫入的值：簡單組只收 value（照字面）；複雜組 value／text／from 剛好一個，resolve 時先解指示詞。"""
    given = [k for k in ("value", "text", "from") if k in args]
    if len(given) != 1:
        die("ArgumentsBad", "give exactly one of value, text, from" if directives else "missing value (any JSON)")
    if given[0] == "value":
        v = args["value"]
    elif given[0] == "text":
        if not isinstance(args["text"], str):
            die("ArgumentsBad", "text must be a string")
        try:
            v = json.loads(args["text"])
        except ValueError as e:
            die("TextBad", "text is not JSON: %s" % e)
    else:
        if not isinstance(args["from"], str) or not args["from"]:
            die("ArgumentsBad", "from must be FILE#/POINTER")
        src = Target(args["from"])
        return read(src, flags=["--resolve"] if args.get("resolve") else [])
    if args.get("resolve") and isinstance(v, (dict, list)):
        try:
            r = subprocess.run(["aos-directive"], input=json.dumps(v, ensure_ascii=False), text=True,
                               stdout=subprocess.PIPE, cwd=os.path.dirname(os.path.abspath(t.real)) or ".")
        except OSError as e:
            die("LaunchFailed", "aos-directive failed to start (must be on PATH): %s" % e.strerror)
        if r.returncode != 0:
            die("DirectiveBad", "aos-directive exited %d (its error line is above)" % r.returncode)
        v = json.loads(r.stdout)
    return v


def write_flags(args, directives):
    if not directives:
        return ["--raw"]
    return (["--follow"] if args.get("follow") else []) + (["--check"] if args.get("check") else [])


def append(t, v, wf, rf):
    parent = Target(t.shown(t.parent_ptr()))
    arr = read(parent, flags=rf)
    if not isinstance(arr, list):
        die("TargetBad", "%s is %s, not an array; - only works at the end of an array path" % (parent.shown(), kind(arr)))
    aos_json(["append"] + wf + [parent.spec()], v, t)
    return "ok %s/%d" % (parent.shown(), len(arr))


def do_set(args, t, directives):
    v = value_of(args, t, directives)
    wf = write_flags(args, directives)
    rf = ["--follow"] if "--follow" in wf else []
    if t.toks and t.toks[-1] == "-":
        return append(t, v, wf, rf)
    aos_json(["set"] + wf + (["--parents"] if args.get("parents") else []) + [t.spec()], v, t)
    return "ok " + t.shown()


def do_add(args, t, directives):
    v = value_of(args, t, directives)
    wf = write_flags(args, directives)
    rf = ["--follow"] if "--follow" in wf else []
    if not t.toks:
        if os.path.exists(t.real):
            die("KeyExists", "%s already exists; use json_set to replace the whole file" % t.file)
        aos_json(["set"] + wf + [t.spec()], v, t)
        return "ok " + t.file
    last = t.toks[-1]
    if last == "-":
        return append(t, v, wf, rf)
    parent = Target(t.shown(t.parent_ptr()))
    try:
        r = subprocess.run(["aos-json", "get"] + rf + [parent.spec()], text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    except OSError as e:
        die("LaunchFailed", "aos-json failed to start (aos-json must be on PATH): %s" % e.strerror)
    if r.returncode != 0:
        if not args.get("parents"):
            read(parent, flags=rf)                     # 照轉 aos-json 的錯（PointerMissing、FileMissing…）
        aos_json(["set"] + wf + ["--parents", t.spec()], v, t)
        return "ok " + t.shown()
    par = json.loads(r.stdout)
    if isinstance(par, dict):
        if last in par:
            hint = "; to add an item to that array write %s/-" % t.shown() if isinstance(par[last], list) else "; use json_set to change it"
            die("KeyExists", "%s already exists%s" % (t.shown(), hint))
        aos_json(["set"] + wf + [t.spec()], v, t)
        return "ok " + t.shown()
    if isinstance(par, list):
        if not last.isdigit() or (len(last) > 1 and last[0] == "0") or int(last) > len(par):
            die("PointerMissing", "%s: array has %d items; insert at 0..%d or write /- to append" % (t.shown(), len(par), len(par)))
        i = int(last)
        if i == len(par):
            return append(t, v, wf, rf)
        aos_json(["set"] + wf + [parent.spec()], par[:i] + [v] + par[i:], t)
        return "ok " + t.shown()
    die("TargetBad", "%s is %s; it cannot hold a key or item" % (parent.shown(), kind(par)))


def do_del(args, t, directives=False):
    if not t.toks:
        die("TargetBad", "will not delete a whole file (use remove or trash)")
    flags = (["--follow"] if args.get("follow") else []) if directives else ["--raw"]
    aos_json(["del"] + flags + [t.spec()], t=t)
    return "ok " + t.shown()


def read_flags(args, directives):
    """複雜組讀的旗標：follow 穿過 $ref、resolve 解開指示詞（都要腦明講）；簡單組不帶。"""
    if not directives:
        return []
    return (["--follow"] if args.get("follow") else []) + (["--resolve"] if args.get("resolve") else [])


def main(op, directives=False):
    """殼的入口：op＝get／ls／search／set／add／del（directives＝複雜組 jsonx_*）或 multi_get／multi_set（交給 aos_json_multi）。"""
    if op.startswith("multi_"):
        import aos_json_multi
        return aos_json_multi.main(op[len("multi_"):])
    name = ("jsonx_" + op) if directives else SIMPLE[op]
    start(name)
    args = tool_io.arguments("path")
    t = Target(args["path"])
    if op in ("get", "ls", "search"):
        out = {"get": do_get, "ls": do_ls, "search": do_search}[op](args, t, read_flags(args, directives))
    elif op == "set":
        out = do_set(args, t, directives)
    elif op == "add":
        out = do_add(args, t, directives)
    else:
        out = do_del(args, t, directives)
    print(out)


def start(name):
    tool_io.start(name, "usage: %s < ARGUMENTS.json   (a tool: run it with aos-exec; relative paths start at $AOS_WS)\n"
                        "Result on stdout. On error: one line \"%s: error: CODE reason\" on stderr and stdout, exit 1.\n" % (name, name))
