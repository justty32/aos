"""agent_spec_load - defs.load(路徑)：一支 agent.py 衍生自另一支（繼承第一刀，線 aos-inherit-cut1-1119）：跑底那支，它最後的 defs.main 只交出那隻 Agent，正規化成一份新的 Agent 交回。

設計稿 thinking/2026-11/19/aos-inherit-1119/（04 乙修正版、06、07 採納表、08 使用者裁定）；紀錄 thinking/2026-11/19/aos-inherit-第一刀.md；規範 N-70（繼承只在編譯時）。
交回物件、欄位小寫（編譯程式庫第 2 刀，線 aos-pylib-k2-1120；使用者 11-20 選項框「小寫」）：base.description、base.system、base.tools、base.llm、base.fsm、
base.meta、base.interfaces、base.hooks、base.files、base.loop（第 4 刀第二筆），與 base.pack(prefix=, rename=, exclude=)；交回的是 aos/agent_spec_agent.Agent，本身也能 .compile(夾)。
只在 agent.py 重新編譯時發生：編出的 json 照舊整份、沒有上一層；執行期一行不動。只收明寫的路徑（不搜尋），相對路徑從叫它的那支 agent.py 的夾算（REPL 從 cwd）。
載入期間：底在自己的一份 __main__ 下跑（runpy），載完還原 sys.path 與新進 sys.modules 的非 aos 模組（07 A4）；a 載 b、b 載 a＝SpecBad。
底的欄位：tools＝一個帶來源名的包（拿掉的留墓碑 None）、hooks＝agent_spec_hooks.Hooks（帶標記；沒宣告＝空組、當作沒宣告）、fsm＝Fsm（eca 版＝None）、
meta＝dict、interfaces／files＝dict 或 None；底裡的相對路徑（工具 path／env_file、hook handler、狀態格 argv 裡底那夾真有的檔）照底那夾換算（07 A5）。
底的 @fn.tool／@fn.hook 函數（編譯程式庫第 3 刀，線 aos-pylib-k3-1120）那格帶著 fn_spec.KEY、不換算：衍生那支編譯時在自己的夾重抽一份 fn/<名>.py，不指回底那夾（N-70）。
底的 defs.extern（第 4 刀，線 aos-pylib-k4-1120，設計稿 aos-pylib-plan-1120/05）：目標在底那夾外面＝欄位照樣是那個 extern（記下從哪夾算，衍生那支編譯時換算）；
在底那夾裡面（同夾的手寫檔）＝用到那一欄才報 SpecBad（不用就不擋）。錯一律丟 SpecBad；在 agent.py 最外層沒人接時，這裡裝的 sys.excepthook 印成一行「名: error: SpecBad …」、退 1（07 A3）。
"""
import json, os, posixpath, runpy, sys, traceback

from aos import flags
from aos import agent_spec_parts as parts
from aos import agent_spec_hooks as hook_parts
from aos.agent_spec_agent import Agent, Fsm, FIELDS
from aos.fn_spec import KEY as FN_KEY
from aos.spec_base import SpecBad, DefBad

_chain = []          # 正在載入的檔（真路徑），最外面那支（叫第一個 defs.load 的）排第一
_got = {}            # 真路徑 → defs.main 交出的物件
_hook = []           # 裝過的 excepthook（只裝一次）


def hand_over(script, unit, bad=None):
    """defs.main 問：叫我的這支正在被 defs.load 載入嗎？是＝收下物件、回 True（defs.main 直接回）；交的不對（bad）＝SpecBad。"""
    if len(_chain) < 2 or _chain[-1] != script:
        return False
    if bad:
        raise SpecBad(bad)
    if script in _got:
        raise SpecBad("%s calls defs.main(...) twice" % script)
    _got[script] = unit
    return True


def _prog():
    arg0 = sys.argv[0] if sys.argv and sys.argv[0] not in ("", "-c", "-") else ""
    if not arg0:
        return "agent_spec"
    if os.path.basename(arg0) == "agent.py":
        return os.path.basename(os.path.dirname(os.path.realpath(arg0)))
    return os.path.splitext(os.path.basename(arg0))[0]


def _install_hook():
    """agent.py 最外層沒人接的 SpecBad／DefBad 印成一行（其他例外照舊交給原本的 excepthook）。REPL 裡同樣一行、不殺行程。"""
    if _hook:
        return
    before = sys.excepthook

    def one_line(kind, value, tb):
        if issubclass(kind, (SpecBad, DefBad)):
            sys.stderr.write(flags.error_line(_prog(), "SpecBad" if issubclass(kind, SpecBad) else "DefBad", str(value)) + "\n")
            sys.stderr.flush()
        else:
            before(kind, value, tb)
    sys.excepthook = one_line
    _hook.append(one_line)


def _where(path, here, shown):
    """defs.load 的路徑 → (底那支 agent.py 的真路徑, 底那夾（給換算相對路徑用：絕對路徑字串或指示詞）)。"""
    spec = sys.modules["aos.agent_spec"]
    if spec._is_directive(path):
        base = os.environ.get(path["$env"])
        if not base:
            raise SpecBad("%s: %s is not set (set it when you run agent.py)" % (shown, path["$env"]))
        full, root = base + path.get("$path", ""), path
    elif isinstance(path, str) and path:
        full = os.path.normpath(os.path.join(here, path))
        root = full
    else:
        raise SpecBad("defs.load(%r): give the folder of another agent.py: a path like \"../reviewer\" (from the folder of this "
                      "agent.py), an absolute path, or defs.env(VAR, PATH)" % (path,))
    if os.path.isdir(full):
        file = os.path.join(full, "agent.py")
    elif os.path.isfile(full) and full.endswith(".py"):
        file = full
        root = os.path.dirname(full) if isinstance(root, str) else dict(root, **{"$path": posixpath.dirname(root.get("$path", ""))})
    else:
        raise SpecBad("%s: %s is not a folder" % (shown, full))
    if not os.path.isfile(file):
        raise SpecBad("%s: there is no %s (defs.load builds on a definition written as agent.py)" % (shown, file))
    return os.path.realpath(file), root


def _line(error, file):
    """例外發生在底那支檔的第幾行（最深的那一格）。"""
    lines = [f.lineno for f in traceback.extract_tb(error.__traceback__) if os.path.realpath(f.filename) == file]
    return " line %d" % lines[-1] if lines else ""


def load(path):
    """跑另一支 agent.py，交回它宣告的欄位（Base）。只在 agent.py 重新編譯時用；每次重跑、不留快取。"""
    _install_hook()
    caller = sys._getframe(1).f_code.co_filename
    here = os.path.dirname(os.path.realpath(caller)) if os.path.isfile(caller) else os.getcwd()
    shown = "defs.load(%r)" % (path,)
    file, root = _where(path, here, shown)
    chain = list(_chain) or [os.path.realpath(caller)]
    if file in chain:
        raise SpecBad("%s: the agent.py files load each other in a circle: %s" % (shown, " -> ".join(chain[chain.index(file):] + [file])))
    saved_chain, saved_path, saved_mods = list(_chain), list(sys.path), set(sys.modules)
    _chain[:] = chain + [file]
    sys.path.insert(0, os.path.dirname(file))      # 跟 python3 跑一支檔一樣：它那夾排第一（同夾的 import helper 拿到它自己的）
    try:
        try:
            runpy.run_path(file, run_name="__main__")
        except (SpecBad, DefBad) as e:
            raise SpecBad("%s: %s" % (shown, e)) from None
        except SystemExit as e:
            raise SpecBad("%s: %s stopped (exit %s) while it was loaded" % (shown, file, e.code)) from None
        except Exception as e:
            raise SpecBad("%s: %s%s: %s: %s" % (shown, file, _line(e, file), type(e).__name__, e)) from None
        if file not in _got:
            raise SpecBad("%s: %s never calls defs.main(...) (an agent.py that only calls .compile(...) hands nothing over), "
                          "so there is nothing to build on" % (shown, file))
        if not isinstance(_got[file], Agent):
            raise SpecBad("%s: %s hands defs.main a %s, not an agent (defs.Agent(...)), so there is nothing to build on"
                          % (shown, file, type(_got[file]).__name__))
        try:
            return _based(shown, file, root, _got[file])
        except SpecBad as e:
            raise SpecBad("%s: %s (fix the declaration in %s)" % (shown, e, file)) from None
    finally:
        _got.pop(file, None)
        _chain[:] = saved_chain
        sys.path[:] = saved_path
        for name in set(sys.modules) - saved_mods:
            if name != "aos" and not name.startswith("aos."):
                del sys.modules[name]


def _copy(value):
    return json.loads(json.dumps(value))


def _moved(value, root):
    """底裡的相對路徑 → 從底那夾算的全路徑（底那夾是指示詞就寫成指示詞，同 Lib._full）。非字串、空字串、絕對路徑原樣。"""
    if not isinstance(value, str) or not value or os.path.isabs(value):
        return value
    if isinstance(root, dict):
        return {"$env": root["$env"], "$path": posixpath.normpath(root.get("$path", "") + "/" + value)}
    return os.path.normpath(os.path.join(root, value))


def _anchored(ext, folder):
    """底的 defs.extern 記號 → 帶 from（相對路徑從哪一夾算）的一份，衍生那支編譯時再換算成從自己那夾算；目標在底那夾裡面＝None（接不上，N-70）。
    底自己也是衍生來的（記號已帶 from）＝照它的 from 算。相對路徑從底那支 agent.py 的夾算（它預設編譯進的那一夾）。"""
    start = ext.get("from", folder)
    target = os.path.realpath(os.path.join(start, ext["target"]))
    home = os.path.realpath(folder)
    if target == home or target.startswith(home + os.sep):
        return None
    return dict(ext, **{"from": start})


def _based(shown, file, root, given):
    """底交出的 Agent → 一份新的 Agent（欄位驗過、拷貝過、底裡的相對路徑換算過；每次是新的一份，改了不影響別人）。
    extern 連到底那夾裡面的欄位不設，一碰就 SpecBad；連到夾外的照樣是 extern（帶 from）。"""
    values = {f: given.__dict__.get(f) for f in FIELDS}
    inner = dict(given.__dict__.get("_hand", {}))                # 底自己也是 defs.load 來的：它那一層就接不上的，這裡照樣接不上
    out = Agent.__new__(Agent)
    out.__dict__.update(_shown=shown, path=os.path.dirname(file), _hand={})
    folder, hand = out.path, out._hand
    for field, value in values.items():
        if field in inner:
            hand[field] = inner[field]
            continue
        parts.raise_bad(value)
        if parts.kind(value) == "extern":                       # 第 4 刀（設計稿 05、Argon A8）：連到底那夾外面＝照樣交出、記下從哪夾算；裡面＝用到才 SpecBad
            values[field] = ext = _anchored(value, folder)
            if ext is None:
                hand[field] = value["target"]
    description = values["description"]
    if not isinstance(description, str) or not description.strip():
        raise SpecBad("description must be a non-empty string")
    out.description = description.strip()
    skip = set(hand)                                            # 下面不再處理的欄：接不上的、連到夾外的（照樣是 extern）
    for field in ("system", "tools", "llm", "fsm", "hooks"):
        if field not in hand and parts.kind(values[field]) == "extern":
            setattr(out, field, _copy(values[field]))
            skip.add(field)
    if "system" not in skip:
        if not isinstance(values["system"], str):
            raise SpecBad("system must be a string or defs.extern(...)")
        out.system = values["system"]
    if "tools" not in skip:
        tools = values["tools"]
        if not isinstance(tools, (list, tuple)) and parts.kind(tools) != "pack":
            raise SpecBad("tools must be a list or defs.extern(...)")
        table, origins = parts.stack_tools([tools] if parts.kind(tools) == "pack" else tools)
        for entry in table.values():
            for key in ("path", "env_file"):
                if entry is not None and key in entry and FN_KEY not in entry:     # 函數工具：衍生那支自己重抽
                    entry[key] = _moved(entry[key], root)
        out.tools = {"kind": "pack", "lib": "defs.load", "name": shown, "label": shown, "origins": list(origins), "tools": _copy(table)}
    if "llm" not in skip:
        if not isinstance(values["llm"], dict):
            raise SpecBad("llm must be a dict or defs.extern(...)")
        out.llm = _copy(values["llm"])
    if "fsm" not in skip:
        fsm = values["fsm"]
        if fsm is not None and parts.kind(fsm) != "fsm":
            raise SpecBad("fsm must come from defs.fsm(...), std.fsm() or defs.extern(...)")
        out.fsm = None if fsm is None else Fsm(_copy(fsm))
        for cell in (out.fsm or {"states": {}})["states"].values():       # argv 裡只換底那夾真有的檔（"python3" 這種指令不動）
            run = cell.get("exec")
            if isinstance(run, dict) and isinstance(run.get("argv"), list):
                run["argv"] = [_moved(a, root) if isinstance(a, str) and a and not os.path.isabs(a)
                               and os.path.exists(os.path.join(folder, a)) else a for a in run["argv"]]
    if values["meta"] is not None and not isinstance(values["meta"], dict):
        raise SpecBad("meta must be a dict")
    out.meta = _copy(values["meta"] or {})
    for field in ("interfaces", "files"):
        value = values[field]
        if value is not None and not isinstance(value, dict):
            raise SpecBad("%s must be a dict" % field)
        setattr(out, field, None if value is None else _copy(value))
    loop = values["loop"]                                       # defs.loop(...)（第 4 刀第二筆）：跟別的欄一樣，寫 loop=base.loop 才帶過來
    if loop is not None and parts.kind(loop) != "loop":
        raise SpecBad("loop must come from defs.loop(interval_ms=...)")
    out.loop = None if loop is None else _copy(loop)
    if "hooks" not in skip:
        hooks = hook_parts.no_hooks(values["hooks"])
        if hooks is None:
            out.hooks = hook_parts.Hooks({}, "the hooks of %s" % shown, declared=False)
        else:
            table, origins = hook_parts.stack_hooks(hooks)
            table = _copy(table)
            for entry in table.values():
                if entry is not None and "handler" in entry and FN_KEY not in entry:
                    entry["handler"] = _moved(entry["handler"], root)
            out.hooks = hook_parts.Hooks(table, "the hooks of %s" % shown, origins)
    return out
