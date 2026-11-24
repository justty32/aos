"""aos-tools 的登記檔：讀一份（解指示詞）、照 $override 一層層疊成用的那份、列被 null 關掉的名字、找名字或路徑、寫回（aos-json 或新建）。"""
import json, os, subprocess

from aos import directive_value   # 指示詞交給 aos-directive 解的共用版
from .common import ENV_KEY_RE, Fail, norm_loc, read_json
from .tooldef import CACHE_FILE


OVERRIDE_KEY = "$override"     # 覆蓋檔指向底檔的 key（使用者 11-10 K1「現在就寫 $override」；收成一個常數，只改這裡與 help）


def blame(path, where, err):
    """整格解指示詞失敗時，逐個工具再解一次，說出是哪一個（11-10 aos-tools-cli 甲8；只在失敗路徑做，仍整份報錯）。
    第一次的 aos-json 已經說過哪裡解不開，這裡再解時不再印它的 stderr。找不到是誰＝什麼都不做（照原錯報）。"""
    try:
        with open(path, encoding="utf-8") as f:
            raw = json.load(f)
    except (OSError, ValueError):
        return
    group = raw.get(where) if isinstance(raw, dict) else None
    if not isinstance(group, dict):
        return
    for name in sorted(group):
        target = "%s#/%s/%s" % (path, where, name)
        try:
            r = subprocess.run(["aos-json", "get", "--follow", "--resolve", target], stdin=subprocess.DEVNULL,
                               stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        except OSError:
            return
        if r.returncode != 0:
            raise Fail("DirectiveBad", "tool %s (%s): directives cannot be resolved (aos-json exited %d)" % (name, target, r.returncode))


def read_layer(reg, raw=None):
    """一份登記檔 → (原文整份, 解完指示詞的 tools 物件, 底檔指標原樣值或 None)。檔不在＝空的。
    tools 只解 #/tools 那一格（aos-json get --follow --resolve；$ref 拆檔照 lv0），$override 由這支自己解（read_bases）。"""
    if raw is None:
        if not os.path.exists(reg):
            return {}, {}, None
        try:
            raw, tools = read_json(reg, "tools", "RegistryBad")
        except Fail as e:
            if e.code == "DirectiveBad":
                blame(reg, "tools", e)
            raise
    else:
        tools = raw.get("tools") if isinstance(raw, dict) else None
    if not isinstance(raw, dict):
        raise Fail("RegistryBad", "%s must be a JSON object ({\"tools\": {...}})" % reg)
    if "add" in raw or "rm" in raw:
        raise Fail("RegistryBad", "%s: top-level add / rm are not registry keys (a registry is {\"%s\"?: BASE, \"tools\": {...}}; "
                   "an entry whose value is null is not a tool)" % (reg, OVERRIDE_KEY))
    if tools is None:
        tools = {}
    if not isinstance(tools, dict):
        raise Fail("RegistryBad", "%s: tools must be an object (name -> {\"path\": ...} or null)" % reg)
    return raw, tools, raw.get(OVERRIDE_KEY)


def read_bases(reg, pointer):
    """$override 的值 → [底檔絕對路徑…]。單一路徑或陣列（使用者 11-10「$override希望能支援array…跟$ref一樣」）；
    每個元素收字串（相對從 reg 的資料夾算、絕對）或指示詞物件（每次用到才交 aos-directive 解）。空陣列＝沒有底檔。"""
    where = "%s#/%s" % (reg, OVERRIDE_KEY)
    items = pointer if isinstance(pointer, list) else [pointer]
    folder = os.path.dirname(os.path.abspath(reg))
    out = []
    for i, item in enumerate(items):
        at = where + ("/%d" % i if isinstance(pointer, list) else "")
        if isinstance(item, dict):
            try:
                item = directive_value.resolve({"v": item}, folder, reg).get("v")   # #/… ＝ reg 自己；stderr 不吞：aos-directive 自己說哪裡解不開
            except directive_value.Error as e:
                if e.code == "CommandMissing":
                    raise Fail(e.code, "%s has directives that need aos-directive, which cannot start: %s" % (at, e.cause))
                out.append((Fail("DirectiveBad", "%s: directives cannot be resolved (aos-directive exited %d)" % (at, e.returncode)
                                 if e.returncode is not None else "%s: directives cannot be resolved (%s)" % (at, e)), at))
                continue
        if not isinstance(item, str) or not item or "\0" in item:
            out.append((Fail("RegistryBad", "%s must be a path string, a directive resolving to one, or an array of those" % at), at))
            continue
        base = os.path.normpath(os.path.join(folder, item))
        if not os.path.isfile(base):                 # 11-24：疊進來的那份不在＝只少那份（layers 記進 SKIPPED），不是整份壞
            out.append((Fail("PathMissing", "%s: %s does not exist" % (at, base)), at))
            continue
        out.append((base, at))
    return out


# 11-24（使用者「pack檔壞掉，那我是希望就是這個pack檔內的工具不能用，其他都可以用」）：$override 疊進來的某一份不在、不是合法 JSON、
# 形狀不對或指示詞解不開＝跳過那一份（它的工具不在清單上）、其他照疊；跳過的記在這裡（[{at, file?, code, reason}]），
# ls 印出來、stderr 一行 warning。頂層那份（交給 aos-tools 的 F）自己壞照舊整份報錯。環（chain loops）與 aos-directive 起不來照舊整份報錯。
SKIPPED = []
SKIP_CODES = ("PathMissing", "RegistryBad", "DirectiveBad", "ReadFailed")


def _skip(at, base, e):
    rec = {"at": at, "code": e.code, "reason": str(e)}
    if base:
        rec["file"] = base
    if not any(r["at"] == rec["at"] and r["reason"] == rec["reason"] for r in SKIPPED):   # 同一次執行可能疊好幾遍
        SKIPPED.append(rec)


def patch(acc, layer, reg):
    """一層疊上去（補丁式往下合）：物件逐 key 合，其餘（字串、數字、null…）整個蓋過去。合併沒有刪除：
    null 跟別的值一樣蓋過去、key 還在（使用者 11-10 改口：「null就是null，我們不做rm功能」「寫成 null，讀的人當它不是工具」）；
    值是 null 的工具格在 finish 才當「不是工具」。acc＝{名: {"entry": 合好的格, "origin": {格名: 寫它的那份檔}, "last": 檔} 或 {"null": 檔}}。"""
    for name, e in layer.items():
        if e is None:
            acc[name] = {"null": reg}
            continue
        if not isinstance(e, dict):
            raise Fail("RegistryBad", "%s: tools/%s must be an object ({\"path\": ...}) or null" % (reg, name))
        cur = acc.get(name)
        if cur is None or "null" in cur:             # 前面沒有、或被 null 蓋過：從空的開始（null 不是物件，不往下合）
            cur = acc[name] = {"entry": {}, "origin": {}}
        for k, v in e.items():
            if isinstance(v, dict) and isinstance(cur["entry"].get(k), dict):
                merged = dict(cur["entry"][k])
                merged.update(v)                     # env 之類再往下一層；裡面的 null 也只是值
                cur["entry"][k] = merged
            else:
                cur["entry"][k] = v
            cur["origin"][k] = reg
        cur["last"] = reg


def layers(reg, raw=None, chain=()):
    """reg 展開成照順序的疊加序列 [(檔, tools)…]：每個底檔先遞迴展開成它自己的序列，照 $override 陣列順序接起來，最後接 reg 自己的
    （使用者 11-10「照順序疊，後面蓋前面」）。同一份經兩條路被引到（菱形）＝序列裡出現兩次、照樣疊，不算環；
    環以真實路徑判，只看往上那幾層（跟 $ref 陣列同）。"""
    real = os.path.realpath(reg)
    if real in chain:
        raise Fail("RegistryBad", "%s chain loops: %s" % (OVERRIDE_KEY, " -> ".join(list(chain[chain.index(real):]) + [real])))
    raw, tools, pointer = read_layer(reg, raw)
    seq = []
    if pointer is not None:
        for base, at in read_bases(reg, pointer):
            if isinstance(base, Fail):
                _skip(at, None, base)
                continue
            try:
                seq += layers(base, None, chain + (real,))
            except Fail as e:
                if e.code == "RegistryBad" and "chain loops" in str(e):
                    raise
                if e.code in SKIP_CODES:
                    _skip(at, base, e)
                    continue
                raise Fail(e.code, "%s (from %s)" % (e, at))
    return seq + [(reg, tools)]


def merged_tools(reg, raw=None):
    """reg 疊完整條序列之後的 {名: 合好的格}（含被 null 蓋過的名字）。"""
    acc = {}
    for f, tools in layers(reg, raw):
        patch(acc, tools, f)
    return acc


def finish(merged):
    """合好的格 → {名: {path(絕對，從寫 path 的那份檔算), entry, field, src, stored, env_file?…}}；壞的＝RegistryBad。
    值是 null 的工具格不算工具；工具格裡值是 null 的欄位（env、env_file、cache、env 裡的變數）＝當沒設。"""
    out = {}
    for name, t in merged.items():
        if "null" in t:
            continue
        origin = t["origin"]
        e = {k: v for k, v in t["entry"].items() if v is not None}
        if isinstance(e.get("env"), dict):
            e["env"] = {k: v for k, v in e["env"].items() if v is not None}
        where = "%s#/tools/%s" % (t["last"], name)
        if not isinstance(e.get("path"), str) or not e["path"]:
            raise Fail("RegistryBad", "%s: tools/%s needs \"path\": non-empty string (after merging what it overrides)" % (t["last"], name))
        if "cache" in e and e["cache"] is not False:     # 11-10 步 2：快取搬到 $AOS_STACK/tooldef_cache.json，登記格只記 false
            raise Fail("RegistryBad", "%s/cache must be false (no cache); cached definitions live in $AOS_STACK/%s"
                       % (where, CACHE_FILE))
        env = e.get("env", {})
        if not isinstance(env, dict) or not all(isinstance(k, str) and ENV_KEY_RE.match(k) and isinstance(v, str) and "\0" not in v
                                              for k, v in env.items()):
            raise Fail("RegistryBad", "%s/env must be an object of NAME -> string without NUL (NAME like LANG)" % where)
        ef = e.get("env_file")                       # 11-10 步 3：只記位置，call 才讀（指示詞已跟整格一起解開）
        if "env_file" in e and (not isinstance(ef, str) or not ef or "\0" in ef):
            raise Fail("RegistryBad", "%s/env_file must be a non-empty path string (or a directive resolving to one)" % where)
        if "uses" in e:                              # 11-24：成功叫過幾次就從清單拿掉（add --uses）；call 照它倒數、到 0 刪那格
            u = e["uses"]
            if not isinstance(u, int) or isinstance(u, bool) or u < 1:
                raise Fail("RegistryBad", "%s/uses must be a whole number >= 1 (successful calls left before it is taken off the list)" % where)
        pfile = origin["path"]
        out[name] = {"path": norm_loc(os.path.dirname(os.path.abspath(pfile)), e["path"]), "entry": e,
                     "field": "%s#/tools/%s/path" % (pfile, name), "src": "%s#/tools/%s" % (pfile, name),
                     "stored": stored_value(pfile, name, "path", e["path"])}
        if "uses" in e:
            out[name]["uses"], out[name]["uses_file"] = e["uses"], origin["uses"]
        if ef:
            efile = origin["env_file"]
            out[name]["env_file"] = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(efile)), ef))
            out[name]["env_file_src"] = "%s#/tools/%s" % (efile, name)
            out[name]["env_file_stored"] = stored_value(efile, name, "env_file", ef)
    return out


def stored_value(reg, name, key, resolved):
    """ls -l 的 STORED：那份檔裡寫的原樣值（指示詞就是那段 JSON）；那格是 $ref 之類拿不到原文時用解完的。"""
    try:
        with open(reg, encoding="utf-8") as f:
            raw = json.load(f)
        v = raw["tools"][name][key]
        return v if v is not None else resolved
    except (OSError, ValueError, KeyError, TypeError):
        return resolved


def nulled(reg):
    """ls -l 用（11-10 晚使用者「3.顯示」）：疊完仍是 null 的名字 → (寫 null 的那份檔, 它蓋掉的那格解成的絕對路徑或 None)。"""
    acc, out = {}, {}
    for f, tools in layers(reg):
        before = {n: dict(acc[n]) for n in tools if n in acc}
        patch(acc, tools, f)
        for n, e in tools.items():
            if e is None:
                hid = None
                if n in before and "null" not in before[n]:
                    try:
                        hid = finish({n: before[n]})[n]["path"]
                    except Fail:
                        hid = None
                elif n in out:
                    hid = out[n][1]
                out[n] = (f, hid)
            else:
                out.pop(n, None)
    return {n: v for n, v in out.items() if n in acc and "null" in acc[n]}


def load_tools(reg):
    """用的那份：reg 疊完它 $override 的底檔（沒有＝就是 reg；檔不在＝空的）。"""
    return finish(merged_tools(reg))


def base_tools(reg):
    """reg 的底檔們疊起來的樣子（不含 reg 自己的、不含被 null 蓋過的）；add --replace 用它找要用 null 蓋掉的欄位，rm 用它判要寫 null 還是刪 key。"""
    raw, _tools, pointer = read_layer(reg)
    if pointer is None:
        return {}
    return {n: t for n, t in merged_tools(reg, dict(raw, tools={})).items() if "null" not in t}


def own_tools(reg):
    """reg 自己 tools 那格的原文（不解指示詞；$ref 拆檔時那格不是名字表＝回 None，寫入照舊交 aos-json --follow）。"""
    try:
        with open(reg, encoding="utf-8") as f:
            raw = json.load(f)
    except (OSError, ValueError):
        return {}
    t = raw.get("tools") if isinstance(raw, dict) else None
    if t is None:
        return {}
    return t if isinstance(t, dict) and "$ref" not in t else None


def match(tools, xxx):
    """名字優先；不是登記過的名字就當路徑（從 cwd 算），找指到那裡的。"""
    if xxx in tools:
        return [xxx]
    p = norm_loc(os.getcwd(), xxx)
    names = sorted(n for n, t in tools.items() if t["path"] == p)
    if not names:
        raise Fail("ToolMissing", "%s is not a registered tool name, and no tool points to that path" % xxx)
    return names


def aos_json(args):
    try:
        r = subprocess.run(["aos-json"] + args, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL)
    except OSError as e:
        raise Fail("CommandMissing", "editing the registry needs aos-json, which cannot start: %s" % e)
    if r.returncode != 0:
        raise Fail("WriteFailed", "aos-json %s exited %d" % (args[0], r.returncode))


def write_new(reg, obj):
    tmp = os.path.join(os.path.dirname(os.path.abspath(reg)), ".%s.%d.tmp" % (os.path.basename(reg), os.getpid()))
    try:
        with open(tmp, "w", encoding="utf-8") as f:
            f.write(json.dumps(obj, ensure_ascii=False, indent=1) + "\n")
        os.replace(tmp, reg)                         # N-05：先寫暫存再改名
    except OSError as e:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise Fail("WriteFailed", "cannot write %s: %s" % (reg, e))


def resolve_path_value(value, folder):
    """登記格的 path 值（字串或指示詞物件）→ 絕對路徑；指示詞交給 aos-directive 解（每次用到才解、不寫回），解完的相對路徑從 folder 算。"""
    if isinstance(value, dict):
        try:
            value = directive_value.resolve({"path": value}, folder).get("path")   # stderr 不吞：aos-directive 自己說哪裡解不開
        except directive_value.Error as e:
            if e.code == "CommandMissing":
                raise Fail(e.code, "--path-json has directives that need aos-directive, which cannot start: %s" % e.cause)
            raise Fail("DirectiveBad", "--path-json %s cannot be resolved (aos-directive exited %d)" % (json.dumps(value), e.returncode)
                       if e.returncode is not None else "--path-json %s cannot be resolved (%s)" % (json.dumps(value), e))
    if not isinstance(value, str) or not value:
        raise Fail("ArgumentsBad", "--path-json must be a non-empty path string or a directive object resolving to one (got %s)" % json.dumps(value))
    return norm_loc(folder, value)

def use_once(reg, name):
    """call 成功一次（11-24 add --uses）：寫著 uses 的那份檔（reg）裡那格倒數一；剩 1 時改成刪掉那格（底檔有同名的就又看得到）。
    同一份檔的倒數用 flock 排隊（旁邊的 .<檔名>.uses.lock）。回剩下的次數（0＝拿掉了）。那格已經不在或沒有 uses＝None。"""
    import fcntl
    lock = os.path.join(os.path.dirname(os.path.abspath(reg)), ".%s.uses.lock" % os.path.basename(reg))
    with open(lock, "a") as held:
        fcntl.flock(held, fcntl.LOCK_EX)
        _, tools, _ = read_layer(reg)
        entry = tools.get(name) if isinstance(tools, dict) else None
        left = entry.get("uses") if isinstance(entry, dict) else None
        if not isinstance(left, int) or isinstance(left, bool) or left < 1:
            return None
        if left > 1:
            aos_json(["set", "--follow", "%s#/tools/%s/uses" % (reg, name), str(left - 1)])
            return left - 1
        aos_json(["del", "--follow", "%s#/tools/%s" % (reg, name)])
        return 0


def write_entry(reg, name, entry):
    """只寫 reg 那一格（檔在＝aos-json set --follow --parents，穿過 $ref 改被參照的那份；不在＝新建 {"tools": {…}}）。"""
    if os.path.exists(reg):
        aos_json(["set", "--follow", "--parents", "%s#/tools/%s" % (reg, name), json.dumps(entry, ensure_ascii=False)])
    else:
        make_dir_of(reg)
        write_new(reg, {"tools": {name: entry}})


def make_dir_of(reg):
    try:
        os.makedirs(os.path.dirname(os.path.abspath(reg)), exist_ok=True)
    except OSError as e:
        raise Fail("WriteFailed", "cannot create the dir of %s: %s" % (reg, e))
