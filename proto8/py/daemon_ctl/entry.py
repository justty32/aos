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


def is_program(path):
    """這個檔要當程式 exec 嗎（同 aos-exec 的 is_program，11-10 two-machines：/mnt/c 每個檔都 0777，不能只看 +x）：
    要 +x，且開頭 `#!` 或 ELF（\\x7fELF），或整份不是 JSON（沒 #! 的腳本，aos-exec 照舊交 sh）。+x 的 JSON＝不是程式。"""
    if not os.access(path, os.X_OK):
        return False
    try:
        with open(path, "rb") as fh:
            data = fh.read()
    except OSError:
        return True   # 讀不了：交給 aos-exec 去 exec、去說為什麼
    if data.startswith(b"#!") or data.startswith(b"\x7fELF"):
        return True
    try:
        json.loads(data.decode("utf-8"))
    except ValueError:
        return True
    return False


def read_entry_json(path):
    """入口找法用：讀一份不是程式（is_program 為假）的檔當 JSON（第一行 #! 跳過）。讀不了、不是 JSON＝EntryBad（aos-exec 也會這樣報）。"""
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
      資料夾＝XXX/$AOS_ENTRY（預設 _entry；沒有再找 .json）；可執行檔（is_program：+x 且 #!／ELF 或不是 JSON）＝exec 型；
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
        if not ptr and is_program(path):
            return None   # 可執行檔（看內容，不只看 +x）
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



def daemon_ref(target, daemon):
    """envs 包的單子 argv 目標（11-10 two-machines TC）：絕對的 `檔#/指標` 寫成 {"$env": "AOS_DAEMON", "$path": 相對 daemon stack}，
    同 aos-daemon 的 daemon_ref——daemon 給子項的 AOS_DAEMON 是它 stack 的真實路徑（解開捷徑、結尾 /），所以基準也解開捷徑、目標照字面；
    不在底下照樣寫 `..`（`$path` 是字串拼接，`..` 由 OS 照實體走）。整棵樹搬家後由 aos-exec 從新的 AOS_DAEMON 拼回，不寫這台的絕對路徑。
    daemon 是 None、目標不是絕對的＝原樣回（舊行為）。"""
    if not daemon or not isinstance(target, str) or not target.startswith("/"):
        return target
    f, h, p = target.partition("#")
    return {"$env": "AOS_DAEMON", "$path": os.path.relpath(f, os.path.realpath(daemon)) + h + p}


class AsIs(str):
    """--ws-json／--stack-json／--path-json 給的純字串（11-10 晚 B01，使用者「add \"xxx\" 就是原樣送」）：照字面放進信、不從呼叫者的 cwd 換算
    （相對的由 daemon 照它自己的 cwd 算，同 daemon.json 裡寫的）；絕對的另記進 as_written、表上原樣存。"""


def path_json(text, flag):
    """--ws-json／--stack-json 的值（11-10 B01，比照 aos-tools --path-json：「給的json字串會直接放入，到使用的時候再解析」）：
    JSON 字串或指示詞物件（$env／$ref，N-45）；別的＝ArgumentsBad。字串照一般路徑處理，物件原樣放進信。"""
    try:
        v = json.loads(text)
    except ValueError as e:
        raise Fail("ArgumentsBad", "%s needs JSON (a string or a directive object such as {\"$env\": \"X\"}): %s" % (flag, e))
    if isinstance(v, str) and v:
        return AsIs(v)
    if isinstance(v, dict) and v and all(isinstance(k, str) and k.startswith("$") for k in v):
        return v
    raise Fail("ArgumentsBad", "%s needs a non-empty JSON string or a directive object such as {\"$env\": \"X\", \"$path\": \"/sub\"}" % flag)


def resolve_here(value, flag):
    """指示詞物件在這台、現在的環境解一次（只為了檢查、不存）；解不開＝ArgumentsBad 指名旗標與寫法。"""
    try:
        import directive_value
        got = directive_value.resolve(value, os.getcwd())
    except Exception as e:   # tool_io.Error 等：轉成這層的錯
        raise Fail("ArgumentsBad", "%s %s does not resolve here: %s" % (flag, json.dumps(value), e))
    if not isinstance(got, str) or not got:
        raise Fail("ArgumentsBad", "%s %s resolves to %r here, not a path" % (flag, json.dumps(value), got))
    return os.path.abspath(got)


def written_under(value, folder, d):
    """value 裡指到 folder 底下的絕對字串（exec 目標、def）改寫成 d 這個 $env 指示詞接上後半段（$path 是字串拼接，N-45）。
    folder 是 d 在這台解出來的資料夾；其他值原樣回。11-10 B01：--path-json 給的定義資料夾，表上記指示詞、每次起再解。"""
    if isinstance(value, str):
        f, h, p = value.partition("#")
        if f == folder or f.startswith(folder + "/"):
            out = dict(d)
            out["$path"] = d.get("$path", "") + f[len(folder):] + h + p
            return out
        return value
    if isinstance(value, list) and value:
        return [written_under(value[0], folder, d)] + list(value[1:])
    return value


def typed_kept(xxx=None, ws=None, stack=None, def_dir=None):
    """命令列上使用者打的字（原字串，還沒轉絕對）→ add_letter 的 kept：以 / 開頭的 ws、stack、xxx〔＝exec 與 def〕、
    def_dir〔＝def，給了就蓋過 xxx 的〕。指示詞（dict）不算（由 daemon 從指示詞自己認）。"""
    kept = set()
    for k, v in (("ws", ws), ("stack", stack)):
        if isinstance(v, str) and v.startswith("/"):
            kept.add(k)
    if isinstance(xxx, str) and xxx.startswith("/"):
        kept |= {"exec", "def"}
    if def_dir is not None:
        kept.discard("def")
        if isinstance(def_dir, str) and def_dir.startswith("/"):
            kept.add("def")
    return kept


def add_letter(xxx, extra=(), name=None, ws=None, stack=None, def_dir=None, limits=None, envs=None, auto_restart=False, daemon=None,
               written=None, kept=None, dotenv_override=False):
    """判型並組成掛子信；給定的路徑從目前目錄算起。auto_restart＝True：那一列多 "auto_restart": true（daemon 的 key，
    放在列的頂層、跟 exec／ws 同層；loop 型、exec 型、帶 envs 的都一樣，two-machines 06）；False＝不寫這個 key。
    dotenv_override＝True：exec 包一張 aos-exec --dotenv-override 的單子，只有啟動定義那一跳的 .env 可蓋已有環境；
    跟 envs 同給＝一張單子同時帶旗標與 envs。沒給旗標、沒給 envs＝exec 照原樣。
    daemon＝收這封信的 daemon 的 stack（選填，11-10）：給了，包的單子裡的目標寫成相對它的 $env 指示詞（daemon_ref）；
    沒給＝照舊寫絕對路徑。
    kept＝使用者在命令列上寫成絕對路徑的格（"ws"、"stack"、"def"、"exec" 的集合；11-10 晚 B01，使用者選「絕對路徑原樣存」）：
    那幾格另記進列的 "as_written"，daemon 表上原樣存、不換算成相對它的 stack。由命令列那層照使用者打的字認（typed_kept）；
    程式自己組的絕對路徑不算，預設空＝照舊（表上換算成相對 daemon 的 stack）。AsIs 的 ws／stack 照字面送。"""
    kept = set(kept or ())
    if written:                      # 定義寫成指示詞（--path-json）＝exec／def 記指示詞，不記絕對
        kept -= {"exec", "def"}
    xxx = abs_target(xxx, os.getcwd())
    path = xxx.partition("#")[0]
    if not os.path.exists(path):
        raise Fail("PathMissing", "%s not found" % path)
    found = find_loop(xxx)
    if found and extra:
        raise Fail("ArgumentsBad", "loop type (the entry of %s leads to loop config %s) takes no arguments; put them in that config's exec" % (path, found[1]))
    if isinstance(ws, dict):        # 11-10 B01：--ws-json 的指示詞原樣進表（daemon 記 as_written、每次起照當下環境再解）
        got = resolve_here(ws, "--ws-json")
        if not os.path.isdir(got):
            raise Fail("PathMissing", "--ws-json resolves to %s here, which is not a folder" % got)
    elif isinstance(ws, AsIs):       # 11-10 晚 B01：純字串照字面送（相對的由 daemon 從它的 cwd 算；在不在由 aos-exec 說）
        ws = str(ws)
    elif ws is not None:
        if not ws:
            raise Fail("ArgumentsBad", "--ws must not be empty")
        ws = os.path.abspath(ws)   # 從呼叫當下的 cwd 算（daemon 會從它自己的 cwd 算，所以這裡先轉）
        if not os.path.isdir(ws):
            raise Fail("PathMissing", "--ws is not a folder: %s" % ws)
    if isinstance(stack, dict):     # 11-10 B01：--stack-json 同上；在不在不驗（daemon 起它時建）
        resolve_here(stack, "--stack-json")
    elif isinstance(stack, AsIs):    # 11-10 晚 B01：同 ws
        stack = str(stack)
    elif stack is not None:
        if not stack:
            raise Fail("ArgumentsBad", "--stack must not be empty")
        stack = os.path.abspath(stack)   # 同 --ws 從呼叫當下的 cwd 算；在不在不驗（daemon 起它時建）
    name = name or os.path.basename(path.rstrip("/"))
    if found:
        spec = loop_spec(found)
    else:
        spec = {"exec": [xxx] + list(extra) if extra else xxx}
    if envs or dotenv_override:
        if envs and (not isinstance(envs, dict) or any(not isinstance(k, str) or not k or "=" in k or "\0" in k
                                             or not isinstance(v, str) or "\0" in v for k, v in envs.items())):
            raise Fail("ArgumentsBad", "envs must be an object of environment names and string values")
        target = spec["exec"]
        if isinstance(target, dict):
            # 指示詞／內嵌單子透過原設定位置執行，保留其相對路徑基準。
            target = found[1] + "#" + found[2] + "/exec"
        argv = list(target) if isinstance(target, list) else [target]
        if "exec" not in kept:      # 使用者寫絕對路徑＝單子裡也照原樣（11-10 晚 B01）
            argv[0] = daemon_ref(argv[0], daemon)   # 參數不動，只換目標
        spec["exec"] = {"argv": ["aos-exec"] + (["--dotenv-override"] if dotenv_override else []) + ["--"] + argv}
        if envs:
            spec["exec"]["envs"] = dict(envs)
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
    if written:                      # 11-10 B01：(指示詞, 它在這台解出的資料夾)——exec 目標與 def 改記指示詞原形
        d, folder = written
        if set(d) - {"$env", "$path"} or "$env" not in d:
            raise Fail("ArgumentsBad", "--path-json takes an {\"$env\": NAME, \"$path\": \"/sub\"} directive (or a plain string), got %s" % json.dumps(d))
        folder = os.path.abspath(folder)
        for key in ("exec", "def"):
            if key in spec:
                spec[key] = written_under(spec[key], folder, d)
    hint = {}                        # 11-10 晚 B01：使用者寫成絕對路徑的格，表上原樣存（daemon 認列的 as_written）
    for key in ("ws", "stack", "def", "exec"):
        if key not in kept:
            continue
        v = spec.get(key)
        if isinstance(v, list) and v:
            v = v[0]
        if isinstance(v, str) and v.startswith("/"):   # 指示詞、單子、只有 #/… 的不記
            hint[key] = v
    if hint:
        spec["as_written"] = hint
    return name, {"procs_added": {name: spec}}
