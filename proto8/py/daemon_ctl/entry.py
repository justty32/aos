"""daemon_ctl 入口：保留目標與 argv 寫法，讀取直接 loop 設定並組成掛子信。"""
import json
import os

from .base import Fail


def abs_target(t, base):
    """相對的目標接在 base 後面（`檔#/指標` 只動 # 前面；絕對的、只有 #/… 的不動）。"""
    f, h, p = t.partition("#")
    if f and not f.startswith("/"):
        f = os.path.abspath(os.path.join(base, f))
    return f + h + p


def read_loop(path):
    """讀一份 loop.json（第一行 #! 跳過）→ 物件；讀不了、不是 JSON＝LoopBad。"""
    try:
        with open(path, encoding="utf-8") as fh:
            text = fh.read()
        if text.startswith("#!"):
            text = text.split("\n", 1)[1] if "\n" in text else ""
        cfg = json.loads(text)
    except (OSError, ValueError) as e:
        raise Fail("LoopBad", "%s is unreadable or not JSON: %s" % (path, e))
    if not isinstance(cfg, dict):
        raise Fail("LoopBad", "%s must be a JSON object" % path)
    return cfg


def read_entry_json(path):
    """入口找法用：讀一份沒 +x 的檔當 JSON（第一行 #! 跳過）。讀不了、不是 JSON＝EntryBad（aos-exec 也會這樣報）。"""
    try:
        with open(path, encoding="utf-8") as fh:
            text = fh.read()
    except OSError as e:
        raise Fail("EntryBad", "cannot read %s: %s" % (path, e))
    if text.startswith("#!"):
        text = text.split("\n", 1)[1] if "\n" in text else ""
    try:
        return json.loads(text)
    except ValueError as e:
        raise Fail("EntryBad", "%s is not JSON: %s" % (path, e))


def pointer(v, ptr, where):
    """JSON pointer（RFC 6901，N-62）：ptr＝"" 或 "/a/b"。指不到＝EntryBad（判型用，不細分 EntryMissing）。"""
    if ptr == "":
        return v
    if not ptr.startswith("/"):
        raise Fail("EntryBad", "%s: # must be followed by /" % where)
    for tok in ptr[1:].split("/"):
        tok = tok.replace("~1", "/").replace("~0", "~")
        if isinstance(v, dict) and tok in v:
            v = v[tok]
        elif isinstance(v, list) and tok.isdigit() and int(tok) < len(v):
            v = v[int(tok)]
        else:
            raise Fail("EntryBad", "%s points nowhere" % where)
    return v


def find_loop(xxx):
    """add 的自動識別（11-04，four-elements 08 步 7；使用者「拿掉，不應該看特定檔案。add這塊，就是看最終指向的json的內部結構。」）：
    照 aos-exec 的找法（N-61／N-62 的子集）走到入口，看最後指到的 JSON 長怎樣。回 (loop 設定物件, 它所在的檔, 它在檔裡的指標, 相對路徑的起點)，
    exec 型回 None。不看檔名（loop.json 這個名字不出現在這裡）；.env 不讀（只判型、不是真的跑），$ref／$env 不解。
      資料夾＝XXX/$AOS_ENTRY（預設 _entry；沒有再找 .json）；可執行檔（+x）＝exec 型；
      JSON：所有陣列原樣交 aos-exec，不認程式名；字串＝轉向（從這份檔的資料夾算）再來一遍；
      物件有 argv＝單子＝exec 型；物件沒 argv、有 exec＝它就是 loop 設定；沒 argv 沒 exec＝取 js[$AOS_ENTRY] 再來（同一份檔、指標往下）。
    繞圈＝EntryBad；路徑不在＝PathMissing。"""
    ent = os.environ.get("AOS_ENTRY") or "_entry"
    seen = set()
    path, _, ptr = abs_target(xxx, os.getcwd()).partition("#")
    while True:
        key = (os.path.realpath(path), ptr)
        if key in seen:
            raise Fail("EntryBad", "the entry of %s loops (%s#%s)" % (xxx, path, ptr))
        seen.add(key)
        if os.path.isdir(path):
            if ptr:
                raise Fail("EntryBad", "%s is a folder and cannot take #/" % path)
            nxt = os.path.join(path, ent)
            if not os.path.exists(nxt) and os.path.isfile(nxt + ".json"):
                nxt += ".json"
            if not os.path.exists(nxt):
                return None   # 找不到入口：當 exec 型交給 daemon（aos-exec 會報 EntryMissing，寫在小格的 stderr）
            path = nxt
            continue
        if not os.path.isfile(path):
            raise Fail("PathMissing", "%s not found" % path)
        if not ptr and os.access(path, os.X_OK):
            return None   # 可執行檔
        base = os.path.dirname(path)
        v = pointer(read_entry_json(path), ptr, "%s#%s" % (path, ptr))
        while isinstance(v, dict) and "argv" not in v and "exec" not in v:   # 沒 argv 的物件＝當資料夾，取 js[$AOS_ENTRY] 一路往下
            if ent not in v:
                return None
            v = v[ent]
            ptr += "/" + ent.replace("~", "~0").replace("/", "~1")
        if isinstance(v, dict):
            if "argv" in v:
                return None   # 單子
            return v, path, ptr, base   # 有 exec：loop 設定
        if isinstance(v, list):
            return None   # argv 陣列原樣交 aos-exec，不辨認程式名
        if isinstance(v, str):
            path, _, ptr = abs_target(v, base).partition("#")   # 轉向
            continue
        raise Fail("EntryBad", "%s#%s is not an entry (must be a single, an argv array, a string or an object)" % (path, ptr))


def loop_spec(found):
    """loop 型的子項設定：那份 loop 設定（去掉 _entry），相對的 exec 目標照它的資料夾轉絕對；exec 是內嵌單子＝換成指回原處的字串目標。"""
    cfg, path, ptr, base = found
    cfg = dict(cfg)
    cfg.pop("_entry", None)
    ex = cfg.get("exec")
    if isinstance(ex, str):
        cfg["exec"] = abs_target(ex, base)
    elif isinstance(ex, list) and ex and isinstance(ex[0], str):
        cfg["exec"] = [abs_target(ex[0], base)] + ex[1:]
    elif isinstance(ex, dict) and "$ref" not in ex and "$env" not in ex:   # 內嵌單子：指回原檔，AOS_CD 與相對路徑照原地
        cfg["exec"] = path + "#" + ptr + "/exec"
    # 11-04（four-elements 08 步 6「不補名」）：ctl／state／state_flux 不補（aos-loop 自己沒寫＝ctl.json／state.json／state_flux.json）。只有 exec 的 loop 設定
    # 交給 daemon 會被認成 exec 型（題 3：物件只有 exec＝跑一次），所以補一格 "interval_ms": 0——aos-loop 的預設本來就是 0，行為不變
    if set(cfg) <= {"exec", "ws", "stack", "def", "limits"}:   # 同 daemon 的 is_once 認的那幾個 key
        cfg["interval_ms"] = 0
    return cfg



LIMIT_INTS = ("mem_mb", "cpu_s", "procs", "file_mb", "files")   # limits 的正整數 key（同 aos-sandbox、daemon 的 check_limits）；另有 user（字串）



def check_limits(v, where, code):
    """limits（11-05 feat-proto 件 5）：物件，key 只有 LIMIT_INTS（正整數）與 user（非空字串）。錯＝code（宣告 InterfaceBad、--limits ArgumentsBad）。"""
    keys = ", ".join(LIMIT_INTS + ("user",))
    if not isinstance(v, dict):
        raise Fail(code, "%s must be a JSON object such as {\"mem_mb\": 512, \"cpu_s\": 60} (keys: %s), not %s" % (where, keys, json.dumps(v, ensure_ascii=False)))
    for k, x in v.items():
        if k == "user":
            if not isinstance(x, str) or not x:
                raise Fail(code, "user in %s must be a non-empty string (account name), not %s" % (where, json.dumps(x, ensure_ascii=False)))
        elif k in LIMIT_INTS:
            if type(x) is not int or x <= 0:
                raise Fail(code, "%s in %s must be a positive integer, not %s" % (k, where, json.dumps(x, ensure_ascii=False)))
        else:
            raise Fail(code, "unknown key %s in %s (keys: %s)" % (k, where, keys))
    return v



def add_letter(xxx, extra=(), name=None, ws=None, stack=None, def_dir=None, limits=None, envs=None, auto_restart=False):
    """判型並組成掛子信；給定的路徑從目前目錄算起。auto_restart＝True：那一列多 "auto_restart": true（daemon 的 key，
    放在列的頂層、跟 exec／ws 同層；loop 型、exec 型、帶 envs 的都一樣，two-machines 06）；False＝不寫這個 key。"""
    xxx = abs_target(xxx, os.getcwd())
    path = xxx.partition("#")[0]
    if not os.path.exists(path):
        raise Fail("PathMissing", "%s not found" % path)
    found = find_loop(xxx)
    if found and extra:
        raise Fail("ArgumentsBad", "loop type (the entry of %s leads to loop config %s) takes no arguments; put them in that config's exec" % (path, found[1]))
    if ws is not None:
        if not ws:
            raise Fail("ArgumentsBad", "--ws must not be empty")
        ws = os.path.abspath(ws)   # 從呼叫當下的 cwd 算（daemon 會從它自己的 cwd 算，所以這裡先轉）
        if not os.path.isdir(ws):
            raise Fail("PathMissing", "--ws is not a folder: %s" % ws)
    if stack is not None:
        if not stack:
            raise Fail("ArgumentsBad", "--stack must not be empty")
        stack = os.path.abspath(stack)   # 同 --ws 從呼叫當下的 cwd 算；在不在不驗（daemon 起它時建）
    name = name or os.path.basename(path.rstrip("/"))
    if found:
        spec = loop_spec(found)
    else:
        spec = {"exec": [xxx] + list(extra) if extra else xxx}
    if envs:
        if not isinstance(envs, dict) or any(not isinstance(k, str) or not k or "=" in k or "\0" in k
                                             or not isinstance(v, str) or "\0" in v for k, v in envs.items()):
            raise Fail("ArgumentsBad", "envs must be an object of environment names and string values")
        target = spec["exec"]
        if isinstance(target, dict):
            # 指示詞／內嵌單子透過原設定位置執行，保留其相對路徑基準。
            target = found[1] + "#" + found[2] + "/exec"
        argv = target if isinstance(target, list) else [target]
        spec["exec"] = {"argv": ["aos-exec", "--"] + argv, "envs": dict(envs)}
    spec["def"] = os.path.abspath(path)   # 11-04（使用者「那就b。」）：定義資料夾，daemon 記進表的 def 欄
    if def_dir is not None:          # 11-05：aos-agent 的定義宣告了 entry（XXX＝定義裡的那個入口）時，def 另給
        if not def_dir or not os.path.isdir(def_dir):
            raise Fail("PathMissing", "--def is not a folder: %s" % def_dir)
        spec["def"] = os.path.abspath(def_dir)
    if ws:
        spec["ws"] = ws
    if stack:
        spec["stack"] = stack
    if limits is not None:
        spec["limits"] = limits     # 11-05：原樣（{}＝不限、蓋過 daemon 的預設）
    if limits is not None:
        check_limits(limits, "limits", "ArgumentsBad")
    if auto_restart:
        spec["auto_restart"] = True
    return name, {"procs_added": {name: spec}}
