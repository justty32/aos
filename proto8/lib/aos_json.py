"""aos_json - 腦用的 json 工具一族共用的程式：簡單組 json_get／ls／search／len／set／add／del、複雜組 jsonx_get／ls／search／set／add／del 的殼都叫這裡的 main(op)（json_multi_get／set、jsonx_multi_get／set 轉 aos_json_multi）。

使用者 11-12（thinking 2026-11/12/json-tools）：「建議做成一個aos_json工具……做兩套」、兩套選 A——簡單組只收路徑＋值、值照字面、
不碰 $ref／$env／解析文字；複雜組另名，才有指示詞解開與否、穿過 $ref、值從文字或另一格來（圖紙 01-規劃 D1～D24）。
路徑一律一整串 `檔#/指標`（N-45／N-62：第一個 # 切；指標照 RFC 6901、跟 aos-json／$ref 同一套——`x.json` 是整份，`x.json#/` 是名字為空字串的那個 key，使用者 11-12「按照標準寫法」；`x.json#` 不收、照 aos-json 報錯，11-12 代定），檔相對 $AOS_WS、絕對照用。
自己不開檔：讀＝`aos-json get／ls／search`、寫＝`aos-json set／append／add／del`（原子寫入、只重寫變的那一塊；ls／search／add 的邏輯 11-12 搬進 aos-json，這裡只管參數、上限與訊息換成參數名）；簡單組寫入帶 `--raw`（指示詞物件當普通物件）。
aos-json 的 stderr 原樣透出，它退 1 時接它錯誤行的代號與原因（C-52 例外：給腦用的工具轉接下層最後一行），沒那行＝CommandFailed。
上限（json_get 的 max_bytes、ls／search 的 limit）：呼叫參數 › 環境變數 AOS_JSON_MAX_BYTES／AOS_JSON_MAX_ITEMS（tools.json 工具格 env 蓋過行程環境）› 預設 8000／200。
輸出給腦：值一行緊湊 JSON；寫入 `ok 路徑`；不是值的結果用方括號行（`[too big]`、`[more]`、`[no match]`）退 0；錯照 lib 契約兩邊一行、退 1。"""
import json
import os
import re
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


SIMPLE = {"get": "json_get", "ls": "json_ls", "search": "json_search", "len": "json_len", "set": "json_set", "add": "json_add", "del": "json_del"}


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
        # 交給 aos-json 的寫法：照腦給的字面、aos-json 在工作區跑（RUN_CWD），它的錯誤行才不帶本機絕對路徑（11-12 線 errpath，
        # 使用者「json那個可以修」）；開頭是 - 的補 ./，免得被當旗標。
        self.arg = "./" + self.file if self.file.startswith("-") else self.file
        self.toks = [t.replace("~1", "/").replace("~0", "~") for t in ptr[1:].split("/")] if ptr else []
        self.bare_hash = cut >= 0 and not ptr
        if self.bare_hash:                              # `x.json#` 不剝 #，原樣交給 aos-json、照它的規則報錯（11-12 代定）
            aos_json(["get", self.arg + "#"], t=self)
            die("PointerBad", "%s: # must be followed by /" % path)

    def spec(self, ptr=None):
        ptr = self.ptr if ptr is None else ptr
        return self.arg + ("#" + ptr if ptr else "")

    def shown(self, ptr=None):
        ptr = self.ptr if ptr is None else ptr
        return self.file + ("#" + ptr if ptr else "")

    def parent_ptr(self):
        return self.ptr[:self.ptr.rfind("/")]


def run_cwd():
    """aos-json 在哪跑：$AOS_WS（相對路徑就從這裡算，同 tool_io.ws_path）；沒設＝照目前目錄（這時只會有絕對路徑走到這）。"""
    ws = os.environ.get("AOS_WS")
    return ws if ws and os.path.isdir(ws) else None


def aos_json(argv, value=NO, t=None):
    """叫 aos-json；退 0 回 stdout。退 1 轉它最後一行的代號與原因（腦給的寫法、./ 補的換回去、旗標換成參數名）。"""
    stdin = None if value is NO else json.dumps(value, ensure_ascii=False)
    try:
        r = subprocess.run(["aos-json"] + argv, input=stdin, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, cwd=run_cwd())
    except OSError as e:
        die("LaunchFailed", "aos-json failed to start (aos-json must be on PATH): %s" % e.strerror)
    if r.returncode == 0:
        return r.stdout
    sys.stderr.write(r.stderr)
    for line in reversed(r.stderr.splitlines()):
        if line.startswith("aos-json: error: "):
            code, _, reason = line[len("aos-json: error: "):].partition(" ")
            if t is not None:
                reason = reason.replace(t.arg, t.file)
            reason = re.sub(r" \(usage: aos-json .*\)$", "", reason)        # 腦叫的是工具，不是 aos-json 的命令列
            reason = (reason.replace("add --parents", 'give "parents": true')
                      .replace("add --follow", 'use jsonx_get/jsonx_set with "follow": true')
                      .replace("(use append to add at the end)", "(write /- at the end of the path to append)")
                      .replace("; use set to", "; use json_set to")
                      .replace("--offset must", "offset must").replace("--limit must", "limit must"))
            if code == "FileMissing" and t is not None and t.ptr:
                reason += " (create it first, e.g. json_set %s with value {})" % t.file
            if code == "WriteFailed" and t is not None and not os.path.isdir(os.path.dirname(t.real) or "."):
                reason += "; folder %s does not exist, create it first" % (os.path.dirname(t.file) or ".")   # 照腦給的字面印
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
    n = {"object": "key", "array": "item", "string": "char"}.get(kind(v))
    return "%d %s%s" % (len(v), n, "" if len(v) == 1 else "s") if n else compact(v)


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


def do_get(args, t, flags):
    v = read(t, flags=flags)
    text = compact(v)
    cap = limit(args, "max_bytes", "AOS_JSON_MAX_BYTES", MAX_BYTES)
    if args.get("full") or len(text.encode()) <= cap:
        return text
    return ('[too big] %s, %s, %d bytes (max_bytes %d). List it: json_ls %s. Or get a deeper path, or give "full": true.'
            % (kind(v), size(v), len(text.encode()), cap, t.shown()))


def page(lines, total, offset, cap, hint=None):
    """分頁＋`[more]` 行（index_view 用；json_ls／json_search 的在 aos-json 裡）。"""
    shown = lines[offset:offset + cap]
    if offset + cap < total:
        shown.append("[more] %d to %d of %d shown; %s" % (offset, offset + len(shown) - 1, total,
                                                       hint or 'next: "offset": %d' % (offset + cap)))
    return shown


def ours(text, t):
    """aos-json 印的路徑換回腦給的寫法（開頭是 - 的檔交給 aos-json 時補了 ./）。"""
    if t.arg == t.file:
        return text
    return "\n".join(t.file + line[len(t.arg):] if line.startswith(t.arg) else line for line in text.split("\n"))


def do_ls(args, t, flags=()):
    """json_ls：交給 `aos-json ls`（11-12 搬下去，輸出同原本的 Python）；這裡只管參數與上限、把 --offset 說成參數名。"""
    offset = args.get("offset", 0)
    if type(offset) is not int:
        die("ArgumentsBad", "offset must be a non-negative integer")
    cap = args["limit"] if type(args.get("limit")) is int else limit(args, "limit", "AOS_JSON_MAX_ITEMS", MAX_ITEMS)   # 範圍由 aos-json 驗（只在有孩子時）
    argv = ["ls"] + list(flags) + (["--long"] if args.get("long") else []) + ["--offset", str(offset), "--limit", str(cap), t.spec()]
    return re.sub(r"next: --offset (\d+)$", r'next: "offset": \1', ours(aos_json(argv, t=t).removesuffix("\n"), t))


def do_search(args, t, flags=()):
    """json_search：交給 `aos-json search`（往下前序、--up 逐層祖先、--follow／--resolve 從穿過／解開後那格找）。"""
    if "key" not in args and "value" not in args:
        die("ArgumentsBad", "give key, value, or both")
    if flags and args.get("up"):                        # 祖先跨檔說不清，不配 up
        die("ArgumentsBad", "up does not work with follow or resolve")
    if not isinstance(args.get("key", ""), str):
        die("ArgumentsBad", "key must be a string")
    argv = (["search"] + list(flags) + (["--key", args["key"]] if "key" in args else [])
            + (["--value", compact(args["value"])] if "value" in args else [])
            + (["--contains"] if args.get("contains") else []) + (["--up"] if args.get("up") else [])
            + ["--limit", str(limit(args, "limit", "AOS_JSON_MAX_ITEMS", MAX_ITEMS)), t.spec()])
    return ours(aos_json(argv, t=t).removesuffix("\n"), t).replace('give a bigger --limit', 'give a bigger "limit"')


def do_len(args, t, flags=()):
    """json_len（使用者 11-11「json_len」）：物件＝key 數、陣列＝項數、字串＝字元數（code point，同 json_ls 的 chars）；純值沒有長度。"""
    v = read(t, flags=flags)
    if not isinstance(v, (dict, list, str)):
        die("TargetBad", "%s is %s; only objects, arrays and strings have a length" % (t.shown(), "a " + kind(v) if kind(v) != "null" else "null"))
    return str(len(v))


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
    """json_add：交給 `aos-json add`（物件加新 key、已有＝KeyExists；陣列 /N 插中間、/- 接尾；整份檔已在＝KeyExists）。它印實際寫到的位置。"""
    v = value_of(args, t, directives)
    out = aos_json(["add"] + write_flags(args, directives) + (["--parents"] if args.get("parents") else []) + [t.spec()], v, t)
    return "ok " + ours(out.removesuffix("\n"), t)


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
    """殼的入口：op＝get／ls／search／len／set／add／del（directives＝複雜組 jsonx_*）或 multi_get／multi_set（交給 aos_json_multi）。"""
    if op.startswith("multi_"):
        import aos_json_multi
        return aos_json_multi.main(op[len("multi_"):], directives)
    name = ("jsonx_" + op) if directives else SIMPLE[op]
    start(name)
    args = tool_io.arguments("path")
    t = Target(args["path"])
    if op in ("get", "ls", "search", "len"):
        out = {"get": do_get, "ls": do_ls, "search": do_search, "len": do_len}[op](args, t, read_flags(args, directives))
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
