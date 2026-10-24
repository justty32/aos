# common.py - file-tools 各工具共用：讀 stdin 的 arguments、路徑限制在 $AOS_WS、輸出一律 JSON、錯誤照慣例
# 各工具的 _entry 用 sys.path 加上 file-tools 這層（照 _entry 的真實位置，符號連結掛進 agent 的 tools/ 也找得到）再 import。
import json, os, sys, time

TOOL = os.path.basename(os.path.dirname(os.path.realpath(sys.argv[0])))   # 工具名＝資料夾名
AOS_MARKS = ("_entry", "_entry.json", "_metainfo", "_metainfo.json", ".env", "tool.json", "loop.json", "fsm.json")
JSON_KEYS_MAX = 12          # ls 給 JSON 檔頂層 key 最多幾個
TRASH = ".trash"            # 刪除＝搬進 $AOS_WS/.trash/


def die(code, reason):
    """錯：stderr 一行「工具名: 代號 原因」、stdout 一份 {"error": 同一行}（給腦看）、退 1。"""
    line = "%s: %s %s" % (TOOL, code, reason)
    print(line, file=sys.stderr)
    out({"error": line})
    sys.exit(1)


def out(obj):
    print(json.dumps(obj, ensure_ascii=False, separators=(",", ":")))


def args(required=()):
    if not WS:
        die("WsMissing", "沒設定 AOS_WS 或不是資料夾")
    try:
        a = json.loads(sys.stdin.read() or "{}")
    except ValueError as e:
        die("ArgumentsBad", "stdin 不是 JSON：%s" % e)
    if not isinstance(a, dict):
        die("ArgumentsBad", "arguments 要是物件")
    for k in required:
        if not isinstance(a.get(k), str) or not a[k]:
            die("ArgumentsBad", "缺 %s（要一個字串）" % k)
    return a


_ws = os.environ.get("AOS_WS")
WS = os.path.realpath(_ws) if _ws and os.path.isdir(_ws) else None


def resolve(rel, root_ok=True):
    """工作資料夾裡的真實路徑；解開 .. 與符號連結後跑出去＝PathBad。回 (絕對路徑, 給人看的相對路徑)。"""
    p = os.path.realpath(os.path.join(WS, rel))
    if os.path.commonpath([WS, p]) != WS or (p == WS and not root_ok):
        die("PathBad", "%s 在工作資料夾外面" % rel)
    return p, (os.path.relpath(p, WS) if p != WS else ".")


def resolve_link(rel):
    """同 resolve，但最後一節是符號連結時不解開它（搬、刪連結本身）。"""
    head, tail = os.path.split(os.path.normpath(rel))
    parent, _ = resolve(head or ".")
    p = os.path.join(parent, tail)
    if tail in ("", ".", "..") or p == WS:
        die("PathBad", "%s 不能是工作資料夾本身" % rel)
    return p, os.path.relpath(p, WS)


def kind(p):
    if os.path.islink(p):
        return "link"
    return "dir" if os.path.isdir(p) else "file"


def iso(t):
    return time.strftime("%Y-%m-%dT%H:%M:%S", time.localtime(t))


def json_summary(v):
    """一個 JSON 值的一句摘要：型別＋大小（物件幾個 key、陣列幾項、字串幾字），純值短的直接給。"""
    if isinstance(v, dict):
        return {"type": "object", "keys": len(v)}
    if isinstance(v, list):
        return {"type": "array", "items": len(v)}
    if isinstance(v, str) and len(v) > 80:
        return {"type": "string", "chars": len(v), "head": v[:60]}
    names = {type(None): "null", bool: "boolean", int: "number", float: "number", str: "string"}
    return {"type": names[type(v)], "value": v}


def aos_marks(d):
    try:
        names = set(os.listdir(d))
    except OSError:
        return []
    return [m for m in AOS_MARKS if m in names]


def write_atomic(p, data, rel):
    """先寫 . 開頭的暫存檔再改名（N-05）；蓋舊檔留住權限。"""
    tmp = os.path.join(os.path.dirname(p), "." + os.path.basename(p) + ".tmp")
    try:
        with open(tmp, "wb") as f:
            f.write(data)
        if os.path.exists(p):
            os.chmod(tmp, os.stat(p).st_mode & 0o7777)
        os.replace(tmp, p)
    except OSError as e:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        die("WriteFailed", "%s：%s" % (rel, e.strerror))
