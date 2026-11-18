"""aos-tools 各段共用的小零件：名字、錯誤型別 Fail、名字與變數名的規則、讀登記檔類 JSON（有指示詞交 aos-json 解）、檔#/指標的拆與接。"""
import json, os, re, subprocess

NAME = "aos-tools"
ENV_KEY_RE = re.compile(r"[A-Za-z_][A-Za-z0-9_]*\Z")              # \Z 不是 $：$ 會放過結尾的換行
NAME_RE = re.compile(r"^[A-Za-z0-9_-]{1,64}$")


class Fail(Exception):
    def __init__(self, code, reason):
        super().__init__(reason)
        self.code = code


def has_directive(v):
    if isinstance(v, dict):
        return "$ref" in v or "$env" in v or any(has_directive(x) for x in v.values())
    if isinstance(v, list):
        return any(has_directive(x) for x in v)
    return False


def read_json(path, key, bad):
    """讀 path（key＝None 讀整份，否則讀頂層那個 key）；有指示詞就交給 aos-json 解（只解讀的那一格，N-45）。
    回 (原文整份, 值)；key 不在＝值是 None。讀不了、不是 JSON＝bad 代號。"""
    try:
        with open(path, encoding="utf-8") as f:
            raw = json.load(f)
    except (OSError, ValueError) as e:
        raise Fail(bad, "%s is unreadable or not JSON: %s" % (path, e))
    if not has_directive(raw):
        if key is None:
            return raw, raw
        return raw, (raw.get(key) if isinstance(raw, dict) else None)
    if key is not None and isinstance(raw, dict) and key not in raw and "$ref" not in raw:
        return raw, None
    target = path + ("#/" + key if key is not None else "")
    try:
        r = subprocess.run(["aos-json", "get", "--follow", "--resolve", target], stdout=subprocess.PIPE,
                           stdin=subprocess.DEVNULL, text=True)     # stderr 不吞：aos-json 自己說哪裡解不開
    except OSError as e:
        raise Fail("CommandMissing", "%s has directives that need aos-json, but aos-json cannot start: %s" % (path, e))
    if r.returncode != 0:
        raise Fail("DirectiveBad", "%s: directives cannot be resolved (aos-json exited %d)" % (target, r.returncode))
    return raw, json.loads(r.stdout)


def split_ptr(path):
    """位置 檔.json#/指標（11-10 深夜 tools-def，使用者「2.收」）→ (檔, "/指標")；沒有 #/＝(path, None)。指標原樣（RFC 6901，~1＝/、~0＝~）。"""
    f, sep, p = path.partition("#/")
    return (f, "/" + p) if sep else (path, None)


def norm_loc(folder, value):
    """相對從 folder 算、normpath 只動檔那段；#/ 後面原樣接回（跟 aos-exec 一樣：指標指的是檔裡那個物件）。"""
    f, ptr = split_ptr(value)
    f = os.path.normpath(os.path.join(folder, f))
    return f if ptr is None else f + "#" + ptr


def ptr_name(ptr):
    """檔#/指標 的預設工具名＝指標最後一段（解 ~1、~0）。"""
    return ptr.rsplit("/", 1)[-1].replace("~1", "/").replace("~0", "~")
