"""optkit_common - optkit 各工具與 run／accept 共用（round4-selfopt.md § 1；同 lib/agent/agent_tool.py 的做法：不是工具、是模組，工具用 realpath 找到 optkit 這層再 import）。

環境（optkit/run 設好、經節點的 loop 一路傳到工具）：
  OPTKIT_TREE      拷貝樹根（galtxt-a 的拷貝；工具的路徑都從這裡算）
  OPTKIT_SUBTREE   被優化的子樹（相對樹根，例 writer、writer/tools/voice）
  OPTKIT_ALLOW     白名單（JSON 陣列；run 從**原樹**的 _metainfo.opt_writes 算好——拷貝裡改 _metainfo 加寬沒用）
  OPTKIT_ORIG      原樹根（只用來判「這個資料夾原本有沒有」：新建的工具資料夾才准整個寫）
  OPTKIT_HELDOUT   驗證集的 detail（JSON 陣列；templates.distilled.json 追加這些＝HeldOut 拒）
  OPTKIT_RUNS／OPTKIT_QUESTIONS／OPTKIT_CELL／OPTKIT_EPOCH  opt_history 讀的訓練小格、opt_try 能跑的題、這次 selfopt 的小格、第幾個 epoch
白名單語法（作者寫在 _metainfo.opt_writes，相對那棵子樹）：
  "檔"                     整檔可改
  "檔#/指標"               只准改 JSON 的那個位置（其餘位置解析後相等）
  "檔#/指標#append"／"檔#append"  只准追加（dict 舊鍵值不變、list 舊的是前綴、純量不變；遞迴）
  "資料夾/*/"              只准**新建**子資料夾（裡面什麼都准；原本就有的子資料夾不算）
optkit/deny.json 優先於白名單：always 永遠拒；unless_named 除非白名單逐字點名（例 voice 的 _entry）。
全部標準庫；不寫 __pycache__。"""
import hashlib, json, os, re, sys

sys.dont_write_bytecode = True
HERE = os.path.dirname(os.path.realpath(__file__))
STRIP_ENV = ("GALTXT_OPT", "GALTXT_FAKE_OPT", "AOS_WS", "AOS_ENTRY", "AOS_STACK", "AOS_CF")
MAX_BYTES = 50 * 1024


class Bad(Exception):
    """(代號, 原因)"""


def die(name, code, reason):
    line = "%s: %s %s" % (name, code, str(reason).replace("\n", " "))
    print(line, file=sys.stderr)
    print(line)                                  # stdout 也印：stdout 是給腦看的結果（lib/README 規則 3）
    sys.exit(1)


def args_in(name):
    raw = sys.stdin.read()
    try:
        a = json.loads(raw) if raw.strip() else {}
    except ValueError as e:
        die(name, "ArgumentsBad", "stdin 不是 JSON：%s" % e)
    if not isinstance(a, dict):
        die(name, "ArgumentsBad", "stdin 要是 JSON 物件")
    return a


def env(name):
    tree, sub = os.environ.get("OPTKIT_TREE"), os.environ.get("OPTKIT_SUBTREE")
    if not tree or not sub:
        die(name, "EnvMissing", "沒設定 OPTKIT_TREE／OPTKIT_SUBTREE（optkit 只在 optkit/run 開的沙箱裡用）")
    try:
        allow = json.loads(os.environ.get("OPTKIT_ALLOW") or "[]")
        heldout = json.loads(os.environ.get("OPTKIT_HELDOUT") or "[]")
    except ValueError as e:
        die(name, "EnvMissing", "OPTKIT_ALLOW／OPTKIT_HELDOUT 不是 JSON：%s" % e)
    return {"tree": os.path.abspath(tree), "sub": sub.strip("/"), "allow": allow, "heldout": heldout,
            "orig": os.environ.get("OPTKIT_ORIG"), "runs": os.environ.get("OPTKIT_RUNS"),
            "questions": os.environ.get("OPTKIT_QUESTIONS"), "cell": os.environ.get("OPTKIT_CELL"),
            "epoch": os.environ.get("OPTKIT_EPOCH")}


def clean_env(extra=None):
    """給 opt_try／opt_test 的子行程：拿掉優化模式與 optkit 的環境（不然拷貝裡的寫手也進優化模式）"""
    e = {k: v for k, v in os.environ.items() if k not in STRIP_ENV and not k.startswith("OPTKIT_")}
    e.update(extra or {})
    return e


def load_deny():
    with open(os.path.join(HERE, "deny.json"), encoding="utf-8") as f:
        return json.load(f)


def _rx(pattern):
    out, i = "", 0
    while i < len(pattern):
        c = pattern[i]
        if pattern.startswith("**/", i):
            out, i = out + "(?:.*/)?", i + 3
            continue
        if pattern.startswith("**", i):
            out, i = out + ".*", i + 2
            continue
        out += "[^/]*" if c == "*" else "[^/]" if c == "?" else re.escape(c)
        i += 1
    return re.compile("^" + out + "$")


def match(rel, patterns):
    return next((p for p in patterns if _rx(p).match(rel)), None)


def resolve(name, tree, path, deny=None):
    """路徑從拷貝樹根算 → (絕對路徑, 相對樹根)。出了樹根（../、絕對路徑、捷徑解開後在外面）＝PathBad；read_deny＝PathDenied。"""
    if not isinstance(path, str) or not path.strip():
        die(name, "ArgumentsBad", "path 要是非空字串")
    p = os.path.normpath(os.path.join(tree, path))
    rel = os.path.relpath(p, tree)
    real_tree = os.path.realpath(tree)
    if rel == "." or rel.startswith(".."):
        die(name, "PathBad", "%s 不在拷貝樹裡" % path)
    rp = os.path.realpath(p)
    if not (rp + "/").startswith(real_tree + "/"):
        die(name, "PathBad", "%s 解開捷徑後在拷貝樹外（%s）" % (path, rp))
    deny = deny if deny is not None else load_deny()
    hit = match(rel, deny.get("read_deny", []))
    if hit:
        die(name, "PathDenied", "%s 碰不得（%s）" % (rel, hit))
    return p, rel


# ---------------------------------------------------------------- 白名單

def allow_entries(orig, sub):
    """原樹 sub 與它底下每棵子樹（不穿捷徑）的 _metainfo.opt_writes → 正規化成相對樹根的條目字串"""
    out = []
    base = os.path.join(orig, sub)
    for d, subs, files in os.walk(base):
        subs[:] = sorted(s for s in subs if not os.path.islink(os.path.join(d, s)) and s != "__pycache__")
        try:
            with open(os.path.join(d, "_metainfo"), encoding="utf-8") as f:
                meta = json.load(f)
        except (OSError, ValueError):
            continue
        for w in meta.get("opt_writes") or [] if isinstance(meta, dict) else []:
            path, sep, sel = w.partition("#")
            norm = os.path.normpath(os.path.join(os.path.relpath(d, orig), path))
            if path.endswith("/"):
                norm += "/"
            out.append(norm + (sep + sel if sep else ""))
    return out


def parse_entry(e):
    path, _, sel = e.partition("#")
    append = sel.endswith("append")
    ptr = sel[:-len("append")].rstrip("#") if append else sel
    return path, ptr, append


def named(rel, allow):
    return any(parse_entry(e)[0] == rel for e in allow)


def new_dir_of(rel, allow, orig):
    """rel 在某個「資料夾/*/」條目底下、而且那個子資料夾原樹沒有 → 回那個子資料夾（相對樹根）；否則 None"""
    for e in allow:
        path, _, _ = parse_entry(e)
        if not path.endswith("*/"):
            continue
        parent = path[:-2].rstrip("/")
        if rel.startswith(parent + "/"):
            head = rel[len(parent) + 1:].split("/")[0]
            if head and "/" in rel[len(parent) + 1:] and not os.path.lexists(os.path.join(orig, parent, head)):
                return parent + "/" + head
    return None


def _tokens(ptr):
    return [t.replace("~1", "/").replace("~0", "~") for t in ptr.split("/")[1:]] if ptr else []


MISSING = object()


def _get(obj, toks):
    for t in toks:
        if isinstance(obj, dict) and t in obj:
            obj = obj[t]
        elif isinstance(obj, list) and t.isdigit() and int(t) < len(obj):
            obj = obj[int(t)]
        else:
            return MISSING
    return obj


def _mask(obj, toks):
    """把指標位置換成同一個記號（不存在就略過）；回新物件"""
    if not toks:
        return "\0masked"
    obj = json.loads(json.dumps(obj))
    cur = obj
    for t in toks[:-1]:
        cur = _get(cur, [t])
        if cur is MISSING:
            return obj
    last = toks[-1]
    if isinstance(cur, dict):
        cur[last] = "\0masked"
    elif isinstance(cur, list) and last.isdigit() and int(last) < len(cur):
        cur[int(last)] = "\0masked"
    return obj


def appended(old, new):
    if old is MISSING:
        return True
    if new is MISSING:
        return False
    if isinstance(old, dict):
        return isinstance(new, dict) and all(k in new and appended(v, new[k]) for k, v in old.items())
    if isinstance(old, list):
        return isinstance(new, list) and len(new) >= len(old) and new[:len(old)] == old
    return old == new


def check_change(rel, old, new, allow, deny, orig, heldout=(), sub=None):
    """一個變動檔（old／new 是 bytes，None＝不存在）過白名單 → None（准）或拒的原因字串"""
    if sub and rel == sub + "/opt_log.jsonl":           # opt_note 的檔：只准追加
        return None if new is not None and (old is None or new.startswith(old)) else "opt_log.jsonl 只准追加"
    if new is None:
        return "不准刪檔"
    if new_dir_of(rel, allow, orig):
        return None                                      # 新建的工具資料夾：裡面什麼都准（_entry、_metainfo 是這次的腦寫的）
    hit = match(rel, deny.get("always", []))
    if hit:
        return "deny.json always（%s）" % hit
    hit = match(rel, deny.get("unless_named", []))
    if hit and not named(rel, allow):
        return "deny.json unless_named（%s），白名單沒逐字點名" % hit
    sels = [parse_entry(e) for e in allow if parse_entry(e)[0] == rel]
    if not sels:
        return "不在白名單"
    if any(not ptr and not app for _, ptr, app in sels):
        return None
    try:
        a = json.loads(old.decode("utf-8")) if old is not None else {}
        b = json.loads(new.decode("utf-8"))
    except (ValueError, UnicodeDecodeError) as e:
        return "白名單只准改 JSON 的某處，但改完不是 JSON（%s）" % e
    for _, ptr, app in sels:
        toks = _tokens(ptr)
        if app and not appended(_get(a, toks), _get(b, toks)):
            return "%s 只准追加（舊的鍵值要原樣留著）" % (ptr or "整檔")
        a, b = _mask(a, toks), _mask(b, toks)
    if a != b:
        return "白名單只准改 %s，其他位置也變了" % "、".join((p or "整檔") for _, p, _ in sels)
    if rel.endswith("templates.distilled.json") and heldout:
        olds = set((json.loads(old.decode("utf-8")) if old else {}).get("by_detail") or {})
        bad = sorted(set(heldout) & (set((json.loads(new.decode("utf-8"))).get("by_detail") or {}) - olds))
        if bad:
            return "HeldOut：驗證集的 detail 不准蒸進模板（%s）" % "、".join(bad)
    return None


def guarded_write(name, e, p, rel, new):
    """opt_edit／opt_write／opt_extract 落檔前：過白名單（WriteDenied）再寫；既有檔保留權限位"""
    if not e["orig"]:
        die(name, "EnvMissing", "沒設定 OPTKIT_ORIG")
    if os.path.islink(p):
        die(name, "WriteDenied", "%s 是捷徑，不准透過它寫" % rel)
    old = read_bytes(p)
    why = check_change(rel, old, new, e["allow"], load_deny(), e["orig"], e["heldout"], e["sub"])
    if why:
        die(name, "WriteDenied", "%s：%s" % (rel, why))
    os.makedirs(os.path.dirname(p), exist_ok=True)
    mode = os.stat(p).st_mode & 0o7777 if old is not None else None
    tmp = os.path.join(os.path.dirname(p), "." + os.path.basename(p) + ".opt")
    with open(tmp, "wb") as f:
        f.write(new)
    if mode is not None:
        os.chmod(tmp, mode)
    os.replace(tmp, p)


def read_bytes(p):
    try:
        if os.path.islink(p):
            return ("\0link " + os.readlink(p)).encode("utf-8")
        with open(p, "rb") as f:
            return f.read()
    except FileNotFoundError:
        return None


def sha(b):
    return None if b is None else hashlib.sha256(b).hexdigest()


def walk_files(root, skip_top=(), ignore=()):
    """root 底下每個檔與捷徑（相對路徑；捷徑不穿過去）"""
    out = set()
    for d, subs, files in os.walk(root):
        rel_d = os.path.relpath(d, root)
        keep = []
        for s in subs:
            r = os.path.normpath(os.path.join(rel_d, s))
            if rel_d == "." and s in skip_top:
                continue
            if os.path.islink(os.path.join(d, s)):
                out.add(r)
            else:
                keep.append(s)
        subs[:] = keep
        for n in files:
            out.add(os.path.normpath(os.path.join(rel_d, n)))
    return {r for r in out if not match(r, ignore)}


COPY_SKIP = (".git", "plan", "meta", "optkit", "__pycache__")


def diff(orig, copy, deny):
    """原樹 vs 拷貝：[(相對路徑, 舊 bytes|None, 新 bytes|None)]，照路徑排；plan／meta／optkit 不比（拷貝裡沒有或是捷徑）"""
    ign = deny.get("ignore", [])
    a, b = walk_files(orig, COPY_SKIP, ign), walk_files(copy, COPY_SKIP, ign)
    out = []
    for r in sorted(a | b):
        x, y = read_bytes(os.path.join(orig, r)), read_bytes(os.path.join(copy, r))
        if x != y:
            out.append((r, x, y))
    return out


def anchors(orig, copy, deny, allow):
    """尺與測試（deny.json anchors）：原樹有的每個錨檔，拷貝裡 sha256 要一樣；白名單逐字點名的（例 voice/_entry）不算錨"""
    bad = []
    for r in sorted(walk_files(orig, COPY_SKIP, deny.get("ignore", []))):
        if match(r, deny.get("anchors", [])) and not named(r, allow):
            if sha(read_bytes(os.path.join(orig, r))) != sha(read_bytes(os.path.join(copy, r))):
                bad.append(r)
    return bad


def cell_prefix(rel):
    """data/ 底下的 JSON → cells.py 的 id 前綴（data/templates.distilled.json → tpld；data/cast/yuzu.json → cast.yuzu）；其他 None"""
    parts = rel.split("/")
    if parts[0] != "data" or not rel.endswith(".json") or "bench" in parts:
        return None
    stem = [p[:-5] if p.endswith(".json") else p for p in parts[1:]]
    alias = {"templates": "tpl", "templates.distilled": "tpld"}
    return alias.get(".".join(stem), ".".join(stem))


def fresh(base):
    os.makedirs(base, exist_ok=True)
    n = len(os.listdir(base)) + 1
    while True:
        cell = os.path.join(base, "%03d" % n)
        try:
            os.mkdir(cell)
            return cell
        except FileExistsError:
            n += 1


def append_line(path, obj):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "a", encoding="utf-8") as f:
        f.write(json.dumps(obj, ensure_ascii=False) + "\n")


def save(path, obj):
    tmp = os.path.join(os.path.dirname(path), "." + os.path.basename(path))   # N-05
    with open(tmp, "w", encoding="utf-8") as f:
        f.write(json.dumps(obj, ensure_ascii=False, indent=1) + "\n")
    os.replace(tmp, path)


def now():
    import datetime
    return datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")
