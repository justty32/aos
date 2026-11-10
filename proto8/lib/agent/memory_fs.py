"""記憶庫（純 JSON 樹）共用：找根、統一路徑解析與顯示、經 aos-json 讀一個位置、_index 表與 $env 格的認法、自己的簡介、列枝幹、find 逛樹的迴圈防護。

圖紙 proto8/thinking/2026-11/10/json-memory/02、03（使用者 11-10 晚）。統一路徑＝`資料夾/檔.json#/JSON Pointer`（RFC 6901）。
位置在程式裡是 Loc(fs, tokens)：fs＝正規化的絕對路徑（不解捷徑，顯示才會照庫根算相對）；tokens＝None 指整個資料夾／整份檔，否則是指標的段。
表：資料夾的表＝它的 _index.json（整個檔就是表，key 從這個資料夾算）；JSON 物件的表＝它的 _index key（key 從這個物件算，
key 裡 `/` 分段、`~1`＝`/`、`..` 往上一層、跳出檔的根就回到檔所在的資料夾、`#` 之後是指標、`/` 開頭＝絕對路徑）。
格是物件且 _description 是字串＝說明；tags 字串陣列＝標籤；格帶 $env（可加 $path）＝實際指到解出來的那條路徑。
自己的簡介（使用者 11-10「那就是同資料夾下的_description.json啊」）：資料夾＝同資料夾的 _description.json（內容是一個 JSON 字串）；
JSON 物件＝它的 _description key（字串）。兩者都不是子節點（_ 開頭本來就不列）。
單點讀交給 PATH 上的 aos-json（get --follow，有指示詞再 --resolve）；表一律讀原文（不 --resolve，$env 格才留得住）。
aos-json 失敗＝把它最後一行的代號照圖紙 03 的表換成自己的代號、原因照接（lib/docs/01 規則 2 的例外：給腦用的工具轉接下層）。
find 例外：直接用 Python 讀 JSON 逛樹（逐檔起子行程太慢），記走過的（實體路徑, 指標）防繞圈，$env 格只跳一次。
錯誤一律 raise tool_io.Error（代號＋英文原因），由工具入口轉成錯誤行；只有 memory_root 照舊直接 die。"""
import json
import os
import re
import signal
import subprocess
import sys
from collections import namedtuple

from tool_io import Error as ToolError, die

CFG_NAME = "_memory.json"      # 工具資料夾裡的設定檔（定義配的）：{"base": "<知識庫路徑>"}，相對＝從這個資料夾算；base 也可寫指示詞（11-10）


def memory_root(tool_folder=None):
    """知識庫根：① 工具資料夾的 _memory.json 的 base（定義配的、最具體）＞ ② $AOS_MEMORY（daemon／人配的）；都沒有＝MemoryMissing。
    使用者 11-05：「隨意複製，隨意修改，隨意給agent指定、隨意拆卸增添」——知識庫是普通資料夾，不登記。"""
    here = os.environ.get("AOS_CD") or tool_folder or os.path.dirname(os.path.abspath(__file__))
    cfg = os.path.join(here, CFG_NAME)
    if os.path.lexists(cfg):                    # 在但不是檔（資料夾、斷捷徑）＝CfgBad，不默默改用 AOS_MEMORY（11-05 夜第二輪邊緣）
        try:
            with open(cfg, encoding="utf-8") as f:
                c = json.load(f)
        except (OSError, ValueError) as e:
            die("CfgBad", "%s: %s" % (cfg, e))
        base, written = c.get("base") if isinstance(c, dict) else None, ""
        if isinstance(base, dict):              # 11-10 two-machines TC：base 寫指示詞（例 {"$env": "KB", "$path": "x"}），每次用到才解、不寫回
            written = " " + json.dumps(base, ensure_ascii=False)
            from directive_value import resolve_path   # 用到才載：只帶 memory_fs／tool_io 複製出去的舊份照舊能讀字串 base
            try:
                base = resolve_path(base, cfg, "base")
            except ToolError as e:
                die(e.code, str(e))
        if not isinstance(base, str) or not base:
            die("CfgBad", "%s must be an object with a non-empty string key base" % cfg)
        real = os.path.realpath(os.path.join(here, base))   # 絕對路徑時 join 直接用它
        if not os.path.isdir(real):
            die("MemoryMissing", "%s base%s resolves to %s, which is not a directory" % (cfg, written, real))
        return real
    m = os.environ.get("AOS_MEMORY", "")
    if not m:
        die("MemoryMissing", "no %s next to the tool and AOS_MEMORY is not set or empty" % CFG_NAME)
    base = os.environ.get("AOS_DAEMON") or os.getcwd()
    real = os.path.realpath(os.path.join(base, m))
    if not os.path.isdir(real):
        die("MemoryMissing", "AOS_MEMORY resolves to %s, which is not a directory" % real)
    return real


Loc = namedtuple("Loc", "fs tokens")   # tokens: None＝整個資料夾／整份檔；否則 tuple
Cell = namedtuple("Cell", "key target description tags env note")
CHILD = None                           # 正在跑的 aos-json；被 TERM 時先收掉
LIST_LIMIT = 30                        # NodeMissing 附的名字最多幾個

# aos-json 的代號 → 記憶工具的代號（圖紙 03）；沒列的＝呼叫者給的 fallback
CODES = {"FileMissing": "NodeMissing", "PointerMissing": "NodeMissing", "FileBad": "FileBad", "SpecBad": "PathBad",
         "ValueMissing": "ValueBad", "ValueBad": "ValueBad", "TargetBad": "TargetBad", "FollowMissing": "TargetBad",
         "DirectiveBad": "DirectiveBad", "WriteFailed": "WriteFailed"}


def on_term(signum, frame):
    """TERM／Ctrl-C：先收掉 aos-json 再走，退 128＋N。"""
    if CHILD is not None and CHILD.poll() is None:
        CHILD.terminate()
    sys.exit(128 + signum)


def install_signals():
    signal.signal(signal.SIGTERM, on_term)
    signal.signal(signal.SIGINT, on_term)


def esc(token):
    return token.replace("~", "~0").replace("/", "~1")


def unesc(token):
    return token.replace("~1", "/").replace("~0", "~")


def pointer(tokens):
    return "".join("/" + esc(t) for t in tokens)


def parse_pointer(text):
    if not text.startswith("/") or re.search(r"~(?![01])", text):
        raise ToolError("PathBad", "after # comes a JSON Pointer that starts with / and uses only ~0 (~) and ~1 (/) escapes, got #%s" % text)
    return tuple(unesc(t) for t in text[1:].split("/"))


def in_file(loc):
    """這個位置是不是在一份檔裡（表的 key 要當指標段）。"""
    return loc.tokens is not None or not os.path.isdir(loc.fs)


def join(base, key, inside=None):
    """從 base 照統一路徑的寫法走 key；inside＝base 是不是在檔裡（None＝自己看磁碟）。"""
    if inside is None:
        inside = in_file(base)
    fs_part, sharp, ptr = key.partition("#")
    if fs_part.startswith("/"):
        fs, tokens, inside, segs = "/", [], False, fs_part.split("/")
    else:
        fs, tokens, segs = base.fs, list(base.tokens or ()), fs_part.split("/")
    for seg in segs:
        if seg in ("", "."):
            continue
        if seg == "..":
            if inside and tokens:
                tokens.pop()
            elif inside:
                inside, fs = False, os.path.dirname(fs)
            else:
                fs = os.path.dirname(fs)
        elif inside:
            tokens.append(unesc(seg))
        else:
            fs = os.path.join(fs, seg)
    fs = os.path.normpath(fs)
    if sharp:
        if inside:
            raise ToolError("PathBad", "%r: # can only follow a file name, not a key inside JSON" % key)
        return Loc(fs, parse_pointer(ptr))
    return Loc(fs, tuple(tokens) if inside and tokens else None)


def parse(root, path):
    """工具的 path → Loc：相對從庫根算；"" 或 "/"＝根；其他 / 開頭＝檔案系統絕對路徑。"""
    if path is None or path in ("", "/"):
        return Loc(root, None)
    if not isinstance(path, str):
        raise ToolError("PathBad", "path must be a string")
    return join(Loc(root, None), path, False)


def show(root, loc):
    """可以直接貼回 path 的寫法：庫根底下印相對、外面印絕對；資料夾加 /，根＝/。"""
    prefix = root.rstrip("/") + "/"
    s = "" if loc.fs == root else loc.fs[len(prefix):] if loc.fs.startswith(prefix) else loc.fs
    if loc.tokens is not None:
        return s + "#" + pointer(loc.tokens)
    if s == "":
        return "/"
    return s + "/" if os.path.isdir(loc.fs) and not s.endswith("/") else s


def spec(loc):
    return loc.fs + ("#" + pointer(loc.tokens) if loc.tokens is not None else "")


def aos_json(argv, stdin="", fallback="ReadFailed"):
    """跑 aos-json，回 stdout；失敗＝把它最後一行的代號換成自己的、原因照接。"""
    global CHILD
    try:
        CHILD = subprocess.Popen(["aos-json"] + argv, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                 stderr=subprocess.PIPE, text=True, encoding="utf-8")
    except OSError as e:
        raise ToolError("LaunchFailed", "cannot run aos-json (it must be on PATH): %s" % e) from None
    out, err = CHILD.communicate(stdin)
    code = CHILD.returncode
    CHILD = None
    if code == 0:
        return out
    last = ([l for l in err.splitlines() if l.strip()] or [""])[-1]
    m = re.match(r"aos-json: error: (\S+) ?(.*)$", last)
    if not m:
        raise ToolError(fallback, "aos-json exited %d: %s" % (code, last or "(no error line)"))
    raise ToolError(CODES.get(m.group(1), fallback), m.group(2))


def get(loc, resolve=False):
    """一個 .json 位置的值（--follow 穿過路上的 $ref；resolve＝連值裡的指示詞也解開）。"""
    out = aos_json(["get", "--follow"] + (["--resolve"] if resolve else []) + [spec(loc)])
    return json.loads(out)


def has_directive(value):
    if isinstance(value, dict):
        return "$ref" in value or "$env" in value or any(has_directive(v) for v in value.values())
    return isinstance(value, list) and any(has_directive(v) for v in value)


def is_branch(value):
    """有 _index 物件的 JSON 物件＝枝幹（簡介＋表）。"""
    return isinstance(value, dict) and isinstance(value.get("_index"), dict)


def visible(name):
    return not name.startswith((".", "_"))


def folder_table(folder, reader):
    f = os.path.join(folder, "_index.json")
    if not os.path.isfile(f):
        return {}
    table = reader(f)
    if not isinstance(table, dict):
        raise ToolError("FileBad", "%s must be a JSON object (the folder's index)" % f)
    return table


def folder_kids(folder):
    try:
        names = sorted(n for n in os.listdir(folder) if visible(n))
    except OSError as e:
        raise ToolError("ReadFailed", "cannot list %s: %s" % (folder, e)) from None
    return [Loc(os.path.join(folder, n), None) for n in names]


def value_kids(loc, value):
    if isinstance(value, dict):
        return [Loc(loc.fs, (loc.tokens or ()) + (k,)) for k in value if visible(k)]
    if isinstance(value, list):
        return [Loc(loc.fs, (loc.tokens or ()) + (str(i),)) for i in range(len(value))]
    return []


def load(root, loc):
    """讀一個位置 → (kind, value, table, kids)。kind：folder／json／text／binary；table＝表（不是枝幹＝None）。"""
    fs = loc.fs
    if os.path.isdir(fs):
        if loc.tokens is not None:
            raise ToolError("TargetBad", "%s is a folder; # only goes inside a .json file" % show(root, Loc(fs, None)))
        return "folder", None, folder_table(fs, lambda f: get(Loc(f, None))), folder_kids(fs)
    if not os.path.isfile(fs):
        raise missing(root, loc)
    if not fs.endswith(".json"):
        if loc.tokens is not None:
            raise ToolError("TargetBad", "%s is not a .json file; # only goes inside a .json file" % show(root, Loc(fs, None)))
        try:
            with open(fs, "rb") as h:
                raw = h.read()
        except OSError as e:
            raise ToolError("ReadFailed", "cannot read %s: %s" % (fs, e)) from None
        try:
            return "text", raw.decode("utf-8"), None, []
        except UnicodeDecodeError:
            return "binary", len(raw), None, []
    try:
        value = get(loc)
    except ToolError as e:
        raise missing(root, loc) if e.code == "NodeMissing" else e
    if not is_branch(value) and has_directive(value):
        value = get(loc, resolve=True)
    return "json", value, value["_index"] if is_branch(value) else None, value_kids(loc, value)


def missing(root, loc):
    """NodeMissing：附上最近一個在的上一層有哪些（照抄得回 path 的寫法）；/errors.json 這種拿掉開頭 / 就在庫裡的，只提示拿掉。"""
    prefix = root.rstrip("/") + "/"
    if loc.fs != root and not loc.fs.startswith(prefix) and os.path.lexists(os.path.join(root, loc.fs.lstrip("/"))):
        return ToolError("NodeMissing", "%s not found (a path starting with / is an absolute file system path; "
                         "drop the leading / to start at the memory root)" % show(root, loc))
    up, kids = loc, []
    while True:
        if up.tokens:
            up = Loc(up.fs, up.tokens[:-1] or None)
        elif up.fs == "/":
            break
        else:
            up = Loc(os.path.dirname(up.fs), None)
        if os.path.isdir(up.fs) and up.tokens is None:
            kids = folder_kids(up.fs)
            break
        if os.path.isfile(up.fs) and up.fs.endswith(".json"):
            try:
                kids = value_kids(up, get(up))
                break
            except ToolError:
                continue
    names = [show(root, k) for k in kids]
    more = " …" if len(names) > LIST_LIMIT else ""
    hint = ""
    if loc.tokens is None and any(os.path.isfile(p) for p in parents_of(loc.fs)):
        hint = " (a file is not a folder: write file.json#/key to go inside a .json file)"
    elif loc.tokens is None and loc.fs.startswith(prefix):
        guess = guess_json(root, loc.fs[len(prefix):])
        if guess:
            hint = " (did you mean %s? keep the .json%s)" % (guess, " and put # before the key" if "#" in guess else "")
    return ToolError("NodeMissing", "%s not found; %s has: %s%s%s" % (
        show(root, loc), show(root, up), ", ".join(names[:LIST_LIMIT]) or "(nothing)", more, hint))


def guess_json(root, rel):
    """少寫 .json 的路徑（小模型常把 me.json#/self_tools 寫成 me/self_tools）：猜一個真的在的寫法，沒有＝None。"""
    parts = [p for p in rel.split("/") if p]
    for i in range(len(parts)):
        name = "/".join(parts[:i + 1])
        if not name.endswith(".json") and os.path.isfile(os.path.join(root, name + ".json")):
            rest = parts[i + 1:]
            return name + ".json" + ("#/" + "/".join(rest) if rest else "")
    return None


def parents_of(fs):
    while fs != os.path.dirname(fs):
        fs = os.path.dirname(fs)
        yield fs


def cell_target(base, key, cell, inside):
    """表裡一格指到哪：帶 $env＝解出來的路徑（從表的基準算），否則＝key。"""
    if isinstance(cell, dict) and "$env" in cell:
        from directive_value import resolve   # 用到才載
        d = {k: cell[k] for k in ("$env", "$path") if k in cell}
        if isinstance(d["$env"], str) and not os.environ.get(d["$env"]):   # 先看：沒設就不叫 aos-directive（它的錯誤行會透到 stderr）
            raise ToolError("DirectiveBad", "$env %s is not set" % d["$env"])
        try:
            got = resolve(d, base.fs if os.path.isdir(base.fs) else os.path.dirname(base.fs))
        except ToolError as e:
            raise ToolError("LaunchFailed" if e.code == "CommandMissing" else "DirectiveBad", str(e)) from None
        if not isinstance(got, str) or not got:
            raise ToolError("DirectiveBad", "%s resolves to %s, not a path" % (json.dumps(d), json.dumps(got)))
        return join(base, got, inside)
    return join(base, key, inside)


def cells(base, table, inside):
    """表的每一格 → Cell；指不出去的格 target＝None、note＝原因。"""
    out = []
    for key, cell in table.items():
        c = cell if isinstance(cell, dict) else {}
        desc = c.get("_description") if isinstance(c.get("_description"), str) else ""
        tags = c.get("tags") if isinstance(c.get("tags"), list) else []
        try:
            target, note = cell_target(base, key, cell, inside), ""
        except ToolError as e:
            target, note = None, "%s %s" % (e.code, e)
        out.append(Cell(key, target, desc, [t for t in tags if isinstance(t, str)], "$env" in c, note))
    return out


DESC_FILE = "_description.json"    # 資料夾自己的簡介（內容是 JSON 字串）
DESC_KEY = "_description"          # JSON 物件自己的簡介


def intro(kind, loc, value, reader):
    """這個地方自己的簡介（字串，沒有＝""）：資料夾讀 _description.json（reader 讀整份檔，讀不到＝沒有）、物件讀 _description key。"""
    if kind == "folder":
        f = os.path.join(loc.fs, DESC_FILE)
        if not os.path.isfile(f):
            return ""
        got = reader(f)
    else:
        got = value.get(DESC_KEY) if isinstance(value, dict) else None
    return got if isinstance(got, str) else ""


def without_intro(value):
    """物件拿掉 _description key（read／export 已經把它印在前面）。"""
    return {k: v for k, v in value.items() if k != DESC_KEY} if isinstance(value, dict) else value


def listing(root, loc, kind, table, kids):
    """children:（表）與 not in index:（表沒列、但真的在的）兩段。"""
    lines = ["children:"]
    covered = set()
    for c in cells(loc, table or {}, kind != "folder"):
        if c.target is not None:
            covered.add(c.target)
        where = show(root, c.target) if c.target is not None else c.key
        lines.append(("  %s  %s" % (where, c.description.replace("\n", " "))).rstrip()
                     + ("  [%s]" % c.note if c.note else ""))
    if len(lines) == 1:
        lines[0] = "children: (none)"
    rest = [k for k in kids if k not in covered]
    if rest:
        lines.append("not in index:")
        lines += ["  " + show(root, k) for k in rest]
    return lines
