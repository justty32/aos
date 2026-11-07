"""知識庫共用的找根、節點與 JSON Pointer 定址、讀取、摘要與子節點列舉。"""
import json
import os
import re

from tool_io import die

SEGMENT = re.compile(r"^[a-z0-9_-]+$")
LEAF_EXTS = (".md", ".json")

CFG_NAME = "_memory.json"      # 工具資料夾裡的設定檔（定義配的）：{"base": "<知識庫路徑>"}，相對＝從這個資料夾算


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
        if not isinstance(c, dict) or not isinstance(c.get("base"), str) or not c["base"]:
            die("CfgBad", "%s must be an object with a non-empty string key base" % cfg)
        real = os.path.realpath(os.path.join(here, c["base"]))   # 絕對路徑時 join 直接用它
        if not os.path.isdir(real):
            die("MemoryMissing", "%s base resolves to %s, which is not a directory" % (cfg, real))
        return real
    m = os.environ.get("AOS_MEMORY", "")
    if not m:
        die("MemoryMissing", "no %s next to the tool and AOS_MEMORY is not set or empty" % CFG_NAME)
    base = os.environ.get("AOS_DAEMON") or os.getcwd()
    real = os.path.realpath(os.path.join(base, m))
    if not os.path.isdir(real):
        die("MemoryMissing", "AOS_MEMORY resolves to %s, which is not a directory" % real)
    return real


def parse_path(p):
    """回段的 list（根＝[]）；不合規＝PathBad。"""
    if p is not None and not isinstance(p, str):
        die("PathBad", "node path must be a string")
    if p is None or p == "" or p == "/":
        return []
    p = p.strip("/")                 # 目錄裡資料夾節點印成 `me/`，腦照抄也算對（11-05 Haiku 實測：五題裡四題先寫了尾巴的 /）
    if p == "":
        return []
    segs = p.split("/")
    for s in segs:
        if not SEGMENT.match(s):
            die("PathBad", "%r is not a node path (segments joined by /, each [a-z0-9_-]+; empty or / is the root)" % p)
    return segs


def parse_read_path(path):
    """read 可附 #/RFC6901 指標；其他工具仍使用純節點 parse_path。"""
    if not isinstance(path, str) or "#" not in path:
        return parse_path(path), None
    node, pointer = path.split("#", 1)
    if not pointer.startswith("/") or re.search(r"~(?![01])", pointer):
        die("PathBad", "JSON pointer must start with / and use only ~0 or ~1 escapes")
    return parse_path(node), pointer


def read_pointer(kind, where, pointer):
    """只對 JSON 葉解 RFC6901 指標，回該位置的 JSON 值。"""
    if kind != "leaf" or not where.endswith(".json"):
        die("TargetBad", "JSON pointers require a .json leaf node")
    try:
        value = json.loads(read_text(kind, where))
    except ValueError as error:
        die("FileBad", "invalid JSON in %s: %s" % (where, error))
    for token in pointer[1:].split("/"):
        token = token.replace("~1", "/").replace("~0", "~")
        if isinstance(value, dict) and token in value:
            value = value[token]
        elif (isinstance(value, list) and re.fullmatch(r"0|[1-9][0-9]*", token)
              and len(token) <= len(str(len(value))) and int(token) < len(value)):
            value = value[int(token)]
        else:
            die("PointerMissing", "JSON pointer %s not found" % pointer)
    return value


def show(segs):
    return "/".join(segs) if segs else "/"


def locate(root, segs):
    """回 (kind, 磁碟路徑)：("dir", 資料夾) 或 ("leaf", .md／.json 檔)；都沒有＝None。"""
    d = os.path.join(root, *segs) if segs else root
    if os.path.isdir(d):
        return ("dir", d)
    f = leaf_file(d) if segs else None
    return ("leaf", f) if f else None


def leaf_file(base):
    """<base>.md 或 <base>.json（.md 優先）；都沒有＝None。"""
    return next((base + x for x in LEAF_EXTS if os.path.isfile(base + x)), None)


def read_text(kind, where, strict=True):
    f = os.path.join(where, "README.md") if kind == "dir" else where
    if kind == "dir" and not os.path.isfile(f):
        return ""
    try:
        with open(f, "rb") as h:
            return h.read().decode("utf-8")
    except (OSError, UnicodeDecodeError) as e:
        if strict:
            die("ReadFailed", "cannot read %s: %s" % (f, e))
        return ""


def title_summary(text, f=""):
    """.md：第一行 # 標題、其後第一個非空行＝摘要；.json：頂層物件的 title／summary 字串鍵。"""
    if f.endswith(".json"):
        try:
            obj = json.loads(text)
        except ValueError:
            obj = None
        if not isinstance(obj, dict):
            return "", ""
        t, s = obj.get("title"), obj.get("summary")
        return (t if isinstance(t, str) else ""), (s if isinstance(s, str) else "")
    lines = text.splitlines()
    title, rest = "", lines
    if lines and lines[0].startswith("# "):
        title, rest = lines[0][2:].strip(), lines[1:]
    summary = next((l.strip() for l in rest if l.strip()), "")
    return title, summary


def children(kind, where):
    """回 [(名, 是資料夾)]，照名字排序；同名的資料夾與 .md 只留資料夾（定址也是先找資料夾）。"""
    if kind != "dir":
        return []
    try:
        entries = os.listdir(where)
    except OSError as e:
        die("ReadFailed", "cannot list %s: %s" % (where, e))
    found = {}
    for e in entries:
        if e.startswith(".") or e.startswith("_") or e == "README.md":
            continue
        full = os.path.join(where, e)
        if os.path.isdir(full):
            name, is_dir = e, True
        elif e.endswith(LEAF_EXTS) and os.path.isfile(full):
            name, is_dir = os.path.splitext(e)[0], False
        else:
            continue
        if not SEGMENT.match(name):             # 定址不到的名字不列（列了腦也讀不到）
            continue
        if is_dir or name not in found:
            found[name] = is_dir
    return sorted(found.items())


def node_or_die(root, segs):
    hit = locate(root, segs)
    if hit is not None:
        return hit
    up = segs[:-1]                              # 往上找到第一個在的祖先，列它的子節點
    while up and locate(root, up) is None:
        up = up[:-1]
    names = [n + "/" if d else n for n, d in children(*locate(root, up))]
    die("NodeMissing", "node %s not found; children of %s: %s" % (show(segs), show(up), ", ".join(names) or "(none)"))

