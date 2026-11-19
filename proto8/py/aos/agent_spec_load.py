"""agent_spec_load - ag.load(路徑)：一支 agent.py 衍生自另一支（繼承第一刀，線 aos-inherit-cut1-1119）：跑底那支，它最後的 ag.main 只交出九個欄位，正規化成一份「底」交回。

設計稿 thinking/2026-11/19/aos-inherit-1119/（04 乙修正版、06、07 採納表、08 使用者裁定）；紀錄 thinking/2026-11/19/aos-inherit-第一刀.md；規範 N-70（繼承只在生成時）。
只在 agent.py 重生時發生：生出的 json 照舊整份、沒有上一層；執行期一行不動。只收明寫的路徑（不搜尋），相對路徑從叫它的那支 agent.py 的夾算（REPL 從 cwd）。
載入期間：底在自己的一份 __main__ 下跑（runpy），載完還原 sys.path 與新進 sys.modules 的非 aos 模組（07 A4）；a 載 b、b 載 a＝SpecBad。
底的欄位：TOOLS＝一個帶來源名的包（拿掉的留墓碑 None）、HOOKS＝agent_spec_parts.Hooks（帶標記；沒宣告＝空組、當作沒宣告）、FSM＝ag.fsm 的值（eca 版＝None）、
META＝dict、INTERFACES／FILES＝dict 或 None；底裡的相對路徑（工具 path／env_file、hook handler、狀態格 argv 裡底那夾真有的檔）照底那夾換算（07 A5）。
by_hand 的欄位＝用到那一欄才報 SpecBad（不用就不擋）。錯一律丟 SpecBad；在 agent.py 最外層沒人接時，這裡裝的 sys.excepthook 印成一行「名: error: SpecBad …」、退 1（07 A3）。
"""
import json, os, posixpath, runpy, sys, traceback

from aos import flags
from aos import agent_spec_parts as parts
from aos.agent_spec_parts import SpecBad, DefBad

FIELDS = ("DESCRIPTION", "SYSTEM", "TOOLS", "LLM", "FSM", "META", "INTERFACES", "HOOKS", "FILES")
_chain = []          # 正在載入的檔（真路徑），最外面那支（叫第一個 ag.load 的）排第一
_got = {}            # 真路徑 → ag.main 交出的九個值
_hook = []           # 裝過的 excepthook（只裝一次）


def hand_over(script, values):
    """ag.main 問：叫我的這支正在被 ag.load 載入嗎？是＝收下欄位、回 True（ag.main 直接回）。"""
    if len(_chain) < 2 or _chain[-1] != script:
        return False
    if script in _got:
        raise SpecBad("%s calls ag.main(...) twice" % script)
    _got[script] = values
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
    """ag.load 的路徑 → (底那支 agent.py 的真路徑, 底那夾（給換算相對路徑用：絕對路徑字串或指示詞）)。"""
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
        raise SpecBad("ag.load(%r): give the folder of another agent.py: a path like \"../reviewer\" (from the folder of this "
                      "agent.py), an absolute path, or ag.env(VAR, PATH)" % (path,))
    if os.path.isdir(full):
        file = os.path.join(full, "agent.py")
    elif os.path.isfile(full) and full.endswith(".py"):
        file = full
        root = os.path.dirname(full) if isinstance(root, str) else dict(root, **{"$path": posixpath.dirname(root.get("$path", ""))})
    else:
        raise SpecBad("%s: %s is not a folder" % (shown, full))
    if not os.path.isfile(file):
        raise SpecBad("%s: there is no %s (ag.load builds on a definition written as agent.py)" % (shown, file))
    return os.path.realpath(file), root


def _line(error, file):
    """例外發生在底那支檔的第幾行（最深的那一格）。"""
    lines = [f.lineno for f in traceback.extract_tb(error.__traceback__) if os.path.realpath(f.filename) == file]
    return " line %d" % lines[-1] if lines else ""


def load(path):
    """跑另一支 agent.py，交回它宣告的欄位（Base）。只在 agent.py 重生時用；每次重跑、不留快取。"""
    _install_hook()
    caller = sys._getframe(1).f_code.co_filename
    here = os.path.dirname(os.path.realpath(caller)) if os.path.isfile(caller) else os.getcwd()
    shown = "ag.load(%r)" % (path,)
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
            raise SpecBad("%s: %s never calls ag.main(...), so there is nothing to build on" % (shown, file))
        try:
            return Base(shown, file, root, _got[file])
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


class Base:
    """ag.load 交回的底：DESCRIPTION、SYSTEM、TOOLS、LLM、FSM、META、INTERFACES、HOOKS、FILES 九個欄位（每次是新的一份，改了不影響別人）。"""

    def __init__(self, shown, file, root, values):
        self._shown, self.path, self._hand = shown, os.path.dirname(file), {}
        folder = self.path
        description, system, tools, llm, fsm, meta, interfaces, hooks, files = values
        for field, value in zip(FIELDS, values):
            parts.raise_bad(value)
            if parts.kind(value) == "by_hand":
                self._hand[field] = value["file"]
        if not isinstance(description, str) or not description.strip():
            raise SpecBad("DESCRIPTION must be a non-empty string")
        self.DESCRIPTION = description.strip()
        if "SYSTEM" not in self._hand:
            if not isinstance(system, str):
                raise SpecBad("SYSTEM must be a string or ag.by_hand(...)")
            self.SYSTEM = system
        if "TOOLS" not in self._hand:
            if not isinstance(tools, (list, tuple)):
                raise SpecBad("TOOLS must be a list or ag.by_hand(...)")
            table, origins = parts.stack_tools(tools)
            for entry in table.values():
                for key in ("path", "env_file"):
                    if entry is not None and key in entry:
                        entry[key] = _moved(entry[key], root)
            self._table, self._origins = _copy(table), origins
            self.TOOLS = self.tools()
        if "LLM" not in self._hand:
            if not isinstance(llm, dict):
                raise SpecBad("LLM must be a dict or ag.by_hand(...)")
            self.LLM = _copy(llm)
        if "FSM" not in self._hand:
            if fsm is not None and parts.kind(fsm) != "fsm":
                raise SpecBad("FSM must come from ag.fsm(...), std.fsm() or ag.by_hand(...)")
            self.FSM = None if fsm is None else _copy(fsm)
            for cell in (self.FSM or {"states": {}})["states"].values():       # argv 裡只換底那夾真有的檔（"python3" 這種指令不動）
                run = cell.get("exec")
                if isinstance(run, dict) and isinstance(run.get("argv"), list):
                    run["argv"] = [_moved(a, root) if isinstance(a, str) and a and not os.path.isabs(a)
                                   and os.path.exists(os.path.join(folder, a)) else a for a in run["argv"]]
        if meta is not None and not isinstance(meta, dict):
            raise SpecBad("META must be a dict")
        self.META = _copy(meta or {})
        for field, value in (("INTERFACES", interfaces), ("FILES", files)):
            if value is not None and not isinstance(value, dict):
                raise SpecBad("%s must be a dict" % field)
            setattr(self, field, None if value is None else _copy(value))
        if "HOOKS" not in self._hand:
            hooks = parts.no_hooks(hooks)
            if hooks is None:
                self.HOOKS = parts.Hooks({}, "the HOOKS of %s" % shown, declared=False)
            else:
                table, origins = parts.stack_hooks(hooks)
                table = _copy(table)
                for entry in table.values():
                    if entry is not None and "handler" in entry:
                        entry["handler"] = _moved(entry["handler"], root)
                self.HOOKS = parts.Hooks(table, "the HOOKS of %s" % shown, origins)

    def __getattr__(self, name):
        hand = self.__dict__.get("_hand", {})
        if name in hand:
            raise SpecBad("%s: %s of %s/agent.py is ag.by_hand(%r), a file written by hand, so there is nothing to build on: "
                          "write %s yourself" % (self.__dict__["_shown"], name, self.__dict__["path"], hand[name], name))
        raise AttributeError("%s has no %s (it has %s, and .tools(prefix=, rename=, exclude=))" % (
            self.__dict__.get("_shown", "ag.load(...)"), name, ", ".join(FIELDS)))

    def __repr__(self):
        return "<agent.py loaded by %s from %s>" % (self._shown, self.path)

    def tools(self, prefix="", rename=None, exclude=None):
        """底的 TOOLS 當一個包，可以改名：prefix＝每支前面加、rename＝{原名: 新名}、exclude＝不要的（原名；連墓碑一起不要），同 std.pack。"""
        if "TOOLS" in self._hand:
            return self.__getattr__("TOOLS")
        call = "%s.tools(...)" % self._shown
        rename = {} if rename is None else rename
        exclude = [] if exclude is None else exclude
        if not isinstance(prefix, str) or not (prefix == "" or all(c.isalnum() or c in "_-" for c in prefix)):
            return {"kind": "bad", "bad": "%s: prefix must be letters, digits, _ or -" % call}
        if not isinstance(rename, dict) or not all(isinstance(k, str) and isinstance(v, str) for k, v in rename.items()):
            return {"kind": "bad", "bad": "%s: rename must be a dict {name in the base: new name}" % call}
        if not isinstance(exclude, (list, tuple)) or not all(isinstance(n, str) for n in exclude):
            return {"kind": "bad", "bad": "%s: exclude must be a list of tool names in the base" % call}
        for what, names in (("rename", list(rename)), ("exclude", list(exclude))):
            for n in names:
                if n not in self._table:
                    return {"kind": "bad", "bad": "%s: %s %r: the base has no tool %s (tools: %s)" % (
                        call, what, n, n, ", ".join(sorted(self._table)))}
        out = {}
        for n, entry in self._table.items():
            if n in exclude:
                continue
            final = rename.get(n, prefix + n)
            if final in out or not parts.TOOL_RE.match(final):
                return {"kind": "bad", "bad": "%s: tool %s ends up as %r: two tools with one name, or not 1-64 letters, digits, _ or -"
                        % (call, n, final)}
            out[final] = _copy(entry)
        label = self._shown if (prefix, rename, exclude) == ("", {}, []) else "%s.tools(prefix=%r, rename=%r, exclude=%r)" % (
            self._shown, prefix, rename, list(exclude))
        return {"kind": "pack", "lib": "ag.load", "name": self._shown, "label": label, "origins": list(self._origins), "tools": out}
