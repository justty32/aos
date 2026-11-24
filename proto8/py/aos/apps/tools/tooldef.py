"""aos-tools 讀工具定義：判種類（dir／json／exe）、讀 _tooldef 與 _metainfo（兩處淺合併）、可執行檔問 --tooldef 與 $AOS_STACK 裡的快取。"""
import json, os, signal, subprocess

from aos import flags as aos_flags
from aos.daemon_ctl.entry import is_program   # 11-10 two-machines：看內容判型（/mnt/c 每檔 0777），同 aos-exec
from .common import NAME, Fail, read_json, split_ptr

TOOLDEF_TIMEOUT_S = 10


def check_tooldef(td, where):
    if not isinstance(td, dict):
        raise Fail("ToolDefBad", "%s: tool definition must be a JSON object" % where)
    if "description" in td and not isinstance(td["description"], str):
        raise Fail("ToolDefBad", "%s: tool definition description must be a string" % where)
    if "parameters" in td and not isinstance(td["parameters"], dict):
        raise Fail("ToolDefBad", "%s: tool definition parameters must be an object (JSON Schema)" % where)
    return td


def read_meta(read):
    """讀 _metainfo（read() 照 read_json 丟 Fail）→ (值, None) 或讀不了時 (None, 那個 Fail)：壞掉的 _metainfo 先不報，交給 merge_tooldef 決定。"""
    try:
        return read(), None
    except Fail as e:
        return None, e


def merge_tooldef(meta, mwhere, outside, owhere, meta_err=None):
    """11-12 metainfo（N-69 推薦讀法）：_metainfo 裡的 tooldef 為底、獨立的 _tooldef 蓋上去——頂層鍵淺合併，同名整鍵外面贏
    （parameters 整鍵換、不往下合 schema）。兩處各自先驗形狀（錯的句子指明哪一處）；兩處都沒有＝None。
    _metainfo 壞了（讀不了、tooldef 不是物件；meta_err＝讀的時候的錯）而外面那份可用＝提醒一行、略過裡面（比照使用者 11-12
    對 index_view 的裁定「_metainfo.json 壞掉時，index_view 對那個資料夾不該直接報錯。」）；外面沒有＝照舊丟那個錯。"""
    if outside is not None:
        outside = check_tooldef(outside, owhere)
    try:
        if meta_err is not None:
            raise meta_err
        inside = check_tooldef(meta["tooldef"], mwhere) if isinstance(meta, dict) and "tooldef" in meta else None
    except Fail as e:
        if outside is None:
            raise
        aos_flags.warn(NAME, "%s; skipped, using %s" % (e, owhere))
        return outside
    if inside is None:
        return outside
    return inside if outside is None else {**inside, **outside}


def stamp(path):
    st = os.stat(path)
    return "%d-%d" % (st.st_mtime_ns, st.st_size)


def run_tooldef(path):
    # 自成行程群組：逾時整群收掉（只殺直接的子行程會把它起的孫行程留著繼續跑，11-04 夜 C 線）
    try:
        p = subprocess.Popen([path, "--tooldef"], cwd=os.path.dirname(path), stdin=subprocess.DEVNULL,
                             stdout=subprocess.PIPE, start_new_session=True)
    except OSError as e:
        raise Fail("ToolDefBad", "%s --tooldef cannot run (an executable needs a #! line): %s" % (path, e))
    try:
        out, _ = p.communicate(timeout=TOOLDEF_TIMEOUT_S)
    except subprocess.TimeoutExpired:
        try:
            os.killpg(p.pid, signal.SIGKILL)
        except OSError:
            pass
        p.wait()
        raise Fail("ToolDefBad", "%s --tooldef did not finish within %d s (process group killed)" % (path, TOOLDEF_TIMEOUT_S))
    if p.returncode != 0:
        raise Fail("ToolDefBad", "%s --tooldef exited %d (no --tooldef support?)" % (path, p.returncode))
    try:
        return json.loads(out.decode("utf-8"))
    except ValueError as e:
        raise Fail("ToolDefBad", "%s --tooldef output is not JSON: %s" % (path, e))

def read_object(path):
    """檔#/指標 那個物件（解指示詞，aos-json get --follow --resolve）；指不到＝PathMissing、不是物件＝ToolDefMissing。"""
    try:
        r = subprocess.run(["aos-json", "get", "--follow", "--resolve", path], stdout=subprocess.PIPE,
                           stdin=subprocess.DEVNULL, text=True)     # stderr 不吞：aos-json 自己說哪一段不在
    except OSError as e:
        raise Fail("CommandMissing", "%s needs aos-json to read the object, which cannot start: %s" % (path, e))
    if r.returncode != 0:
        raise Fail("PathMissing", "%s does not exist (aos-json get exited %d)" % (path, r.returncode))
    obj = json.loads(r.stdout)
    if not isinstance(obj, dict):
        raise Fail("ToolDefMissing", "%s is not a JSON object (a tool there needs a _tooldef key)" % path)
    return obj


def kind_of(path):
    f, ptr = split_ptr(path)
    if ptr is not None:                              # 檔#/指標：檔裡那個物件，跟 JSON 檔同一類（叫＝aos-exec 檔#/指標，cwd＝檔的資料夾）
        if os.path.isfile(f):
            return "json"
        raise Fail("PathMissing", "%s does not exist (the file before #/ is missing)" % path)
    if os.path.isdir(path):
        return "dir"
    if os.path.isfile(path):
        return "exe" if is_program(path) else "json"
    raise Fail("PathMissing", "%s does not exist (or is neither a file nor a dir)" % path)


def first_file(d, names):
    for n in names:
        if os.path.isfile(os.path.join(d, n)):
            return os.path.join(d, n)
    return None


CACHE_FILE = "tooldef_cache.json"


def cache_file():
    """可執行檔定義快取的位置：$AOS_STACK/tooldef_cache.json（11-10 aos-tools-cli 步 2，使用者 Q2「快取搬到 stack 裡」）。
    AOS_STACK 沒設、或不是資料夾＝None（不讀不寫不建）。"""
    stack = os.environ.get("AOS_STACK")
    if not stack or not os.path.isdir(stack):
        return None
    return os.path.join(stack, CACHE_FILE)


def read_cache(cf):
    """快取檔 → {絕對路徑: {stamp, tooldef}}；不在、壞了（不是 JSON、不是物件）＝當沒有（可重建，下次整份重寫）。"""
    try:
        with open(cf, encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, ValueError):
        return {}
    return data if isinstance(data, dict) else {}


def write_cache(cf, data):
    """先寫暫存再改名；寫不了只是少了快取，不算這支的錯（不印、不退非 0）。"""
    tmp = "%s.%d.tmp" % (cf, os.getpid())
    try:
        with open(tmp, "w", encoding="utf-8") as f:
            f.write(json.dumps(data, ensure_ascii=False) + "\n")
        os.replace(tmp, cf)
    except OSError:
        try:
            os.unlink(tmp)
        except OSError:
            pass


def exe_tooldef(path):
    """可執行檔的定義：stack 有快取且 stamp（mtime 奈秒＋大小）相符就用，否則重跑 --tooldef 並寫回快取檔。"""
    cf = cache_file()
    if cf is None:
        return run_tooldef(path)
    key, s = os.path.abspath(path), stamp(path)
    data = read_cache(cf)
    hit = data.get(key)
    if isinstance(hit, dict) and hit.get("stamp") == s and isinstance(hit.get("tooldef"), dict):
        return hit["tooldef"]
    td = run_tooldef(path)
    data = read_cache(cf)                            # 跑 --tooldef 的這段時間別人可能寫過，重讀再併
    data[key] = {"stamp": s, "tooldef": td}
    write_cache(cf, data)
    return td


def inspect(path, cache=None):
    """登記對象 → {kind, tooldef, metainfo?}；不符合要求丟 Fail。cache＝登記格的 cache（只收 False）：
    False＝不用快取（11-03 --no-cache）：exe 每次重跑 --tooldef、不讀不寫快取檔；dir／json 碰到 False＝RegistryBad。
    其餘 exe 的快取在 $AOS_STACK/tooldef_cache.json（exe_tooldef）。"""
    kind = kind_of(path)
    if cache is False and kind != "exe":
        raise Fail("RegistryBad", "%s is %s; \"cache\": false is only for executables (exe)" % (path, kind))
    out = {"kind": kind}
    if kind == "dir":
        m = first_file(path, ("_metainfo.json",))
        meta, err = read_meta(lambda: read_json(m, None, "ToolDefBad")[1]) if m else (None, None)
        p = first_file(path, ("_tooldef.json",))   # 11-04 起只認帶 .json 的（資料檔帶副檔名；_entry 是程式才不帶）
        td = merge_tooldef(meta, "%s#/tooldef" % m, read_json(p, None, "ToolDefBad")[1] if p else None, p, err)
        if td is None:
            raise Fail("ToolDefMissing", "%s is a dir and needs _tooldef.json inside, or a tooldef key in _metainfo.json (_tooldef without .json is not accepted)" % path)
        out["tooldef"] = td
    elif kind == "json" and split_ptr(path)[1] is not None:
        obj = read_object(path)
        meta = obj.get("_metainfo")
        td = merge_tooldef(meta, path + "/_metainfo/tooldef", obj.get("_tooldef"), path + "/_tooldef")
        if td is None:
            raise Fail("ToolDefMissing", "%s is a JSON object and needs a _tooldef key (or _metainfo.tooldef)" % path)
        out["tooldef"] = td
    elif kind == "json":
        try:
            raw, td = read_json(path, "_tooldef", "ToolDefBad")
        except Fail as e:
            if e.code != "ToolDefBad":
                raise
            raise Fail(e.code, "%s; a file without exec permission is read as JSON (python/executables need chmod +x and a #! line)" % e)
        meta, err = read_meta(lambda: read_json(path, "_metainfo", "ToolDefBad")[1]) if isinstance(raw, dict) and "_metainfo" in raw else (None, None)
        td = merge_tooldef(meta, path + "#/_metainfo/tooldef", td, path + "#/_tooldef", err)
        if not isinstance(raw, dict) or td is None:
            raise Fail("ToolDefMissing", "%s is a JSON file (no exec permission) and needs a top-level _tooldef or _metainfo.tooldef (python/executables need chmod +x)" % path)
        out["tooldef"] = td
    else:
        td = run_tooldef(path) if cache is False else exe_tooldef(path)
        out["tooldef"] = check_tooldef(td, path + " --tooldef")
        meta = None
    if isinstance(meta, dict):
        out["metainfo"] = meta
    return out


def describe(name, t):
    try:
        info = inspect(t["path"], t["entry"].get("cache"))
    except Fail as e:
        raise Fail(e.code, "tool %s (%s, from %s): %s" % (name, t["path"], t.get("field", "?"), e))
    out = {"name": name, "kind": info["kind"], "path": t["path"], "tooldef": info["tooldef"]}
    if "metainfo" in info:
        out["metainfo"] = info["metainfo"]
    if "uses" in t:                                  # 11-24 add --uses：給腦的說明後面接一句還剩幾次（ls --json 給 fsm 與 aos-mcp 的就是這份）
        n = t["uses"]
        d = out["tooldef"].get("description") if isinstance(out["tooldef"], dict) else None
        note = "(Taken off your tool list after %d more successful call%s.)" % (n, "" if n == 1 else "s")
        if isinstance(out["tooldef"], dict):
            out["tooldef"] = dict(out["tooldef"], description=(d.rstrip() + " " if isinstance(d, str) and d.strip() else "") + note)
        out["uses"] = n
    return out
