"""agent_spec_lib - agent.py 裡的「庫」（命名空間第一刀）：隨 aos 發的 std（腦看到短名）與 defs.lib("名", 根) 宣告的別的庫（工具自動帶「名_」）；包在編譯時讀出來、展開成一支支工具（靜態連結進 tools.json；動態連結見 pack 的 link）。

設計稿 thinking/2026-11/19/aos-ns-1119/（03 的 B、05、07 使用者裁定）；施工紀錄 thinking/2026-11/19/aos-ns-第一刀.md。
庫＝一個長相固定的資料夾：<根>/packs/<名>.json（工具包）、<根>/tools/<路徑>/（工具夾）。std 先不搬（07 第 4 題 b）：根＝$AOS_HOME，
包在 lib/packs、工具在 lib/tools、hook 組與 fsm 格在 templates/<範本>/（Argon A6：不搬時 std 是三個固定位置的特例）。
解析全在編譯時做完（「C 與 .o」）：編譯時一定要讀得到庫根，讀不到＝SpecBad（Argon A3）；json 裡只寫全路徑（指示詞或絕對路徑），不留庫名；動態連結時 $override 寫的是包檔的全路徑，名字照包裡的（所以只有不改名的包能動態）。
別的庫的路徑在 agent.py 明寫（07 第 6 題：使用者 11-19「先明寫，以後有需要再去弄-I。」）；包怎麼連結是編譯選項
（07 第 7 題：「或者說，用選項吧，gcc那樣」），預設靜態（選項框「預設靜態 (Recommended)」）。
寫錯照 agent_spec 的規矩：回 {"kind": "bad"} 記著，.dry_run()／.compile()／defs.main 再報一行 SpecBad。
"""
import json, os, posixpath, re

from aos import agent_spec_parts as parts
from aos.agent_spec_hooks import Hooks               # hook 那塊 11-20 第 3 刀拆到 agent_spec_hooks（線 aos-pylib-k3-1120）

PREFIX_RE = re.compile(r"[A-Za-z0-9_-]*\Z")       # 腦叫工具的名字只准英數、_、-，前綴也一樣
STOCK_CELLS = (("idle", "idle", {0: "think", 10: "idle"}, None),       # templates/agent-fsm/fsm.json 那四格，格的程式借範本那份
               ("think", "brain", {0: "wait", 10: "idle"}, None),
               ("wait", "wait", {0: "act", 10: "wait", 11: "think"}, None),
               ("act", "act", {0: "think", 10: "idle"}, 0))


def _bad(msg):
    return {"kind": "bad", "bad": msg}


def _spec():
    from aos import agent_spec          # 用的時候 agent_spec 早已載完（它 import 這支）
    return agent_spec


def _join(root, sub):
    """庫根（絕對路徑字串或指示詞）接一段庫裡的相對路徑。"""
    if isinstance(root, dict):
        return {"$env": root["$env"], "$path": posixpath.normpath(root.get("$path", "") + "/" + sub)}
    return os.path.normpath(os.path.join(root, sub))


def _shown(root):
    return "$%s%s" % (root["$env"], root.get("$path", "")) if isinstance(root, dict) else root


class Lib:
    """一個庫。name＝agent.py 裡叫它的名字（只在這支檔裡有效，不進任何全域表）；prefix＝它的工具在腦那邊的名字前綴。"""

    def __init__(self, name, root, packs="packs", tools="tools", prefix=None, bad=None):
        self.name, self.root, self.packs_sub, self.tools_sub, self.bad = name, root, packs, tools, bad
        self.prefix = name + "_" if prefix is None else prefix

    def __repr__(self):
        return "<library %s at %s>" % (self.name, _shown(self.root))

    def _where(self, sub, call):
        """庫裡某一段在這台機器上的真路徑；讀不到＝(None, 錯誤訊息)。"""
        root = self.root
        if isinstance(root, dict):
            base = os.environ.get(root["$env"])
            if not base:
                return None, "%s reads %s, but %s is not set (set it when you run agent.py)" % (
                    call, _shown(_join(root, sub)), root["$env"])
            root = base + root.get("$path", "")
        if not os.path.isdir(root):
            return None, "%s: the root of library %s, %s, is not a folder" % (call, self.name, root)
        return os.path.join(root, sub), None

    def _full(self, value, call):
        """包裡寫的路徑 → 全路徑：指示詞、絕對路徑原樣；相對路徑照 aos-tools 的算法從包檔那夾算起，改寫成庫根底下的全路徑（不能出庫根）。"""
        if not isinstance(value, str) or not value or os.path.isabs(value):
            return value, None                          # 空字串、非字串：交給 defs.tool 照它的規矩報
        rel = posixpath.normpath(self.packs_sub + "/" + value)
        if rel == ".." or rel.startswith("../"):
            return None, "%s: path %r leaves the library root; write it inside the library or as a directive" % (call, value)
        return _join(self.root, rel), None

    def pack(self, name, prefix=None, rename=None, exclude=None, link=None):
        """讀這個庫的 packs/<name>.json，展開成 {腦看到的名字: 工具格}。名字＝rename 給的、否則 prefix＋包裡的名字（prefix 預設：std 空、別的庫「庫名_」）；
        exclude＝不要的（包裡的名字）。link＝這個包怎麼連結（None＝照整支 agent.py 的選項 --static／--dynamic，預設靜態）：
        靜態＝編譯時把工具一支支複製進 tools.json，包之後多加的要重新編譯才拿得到；動態＝tools.json 只寫 $override 指這個包、執行時才讀
        （使用者 11-19「或者說，用選項吧，gcc那樣」；怎麼寫進 tools.json 在 agent_spec_parts.tools_json）。不論哪種，編譯時都讀包、查撞名。"""
        call = "%s.pack(%r)" % (self.name, name)
        if self.bad:
            return _bad(self.bad)
        if link not in (None, "static", "dynamic"):
            return _bad("%s: link must be \"static\" or \"dynamic\" (or left out: the --static / --dynamic option of agent.py)" % call)
        if not isinstance(name, str) or not parts.PACK_RE.match(name):
            return _bad("%s: the pack name must be a pack file name without .json, like \"look\"" % call)
        prefix = self.prefix if prefix is None else prefix
        if not isinstance(prefix, str) or not PREFIX_RE.match(prefix):
            return _bad("%s: prefix must be letters, digits, _ or - (the brain sees it as part of each tool name)" % call)
        rename = {} if rename is None else rename
        exclude = [] if exclude is None else exclude
        if not isinstance(rename, dict) or not all(isinstance(k, str) and isinstance(v, str) for k, v in rename.items()):
            return _bad("%s: rename must be a dict {name in the pack: new name}, like {\"read\": \"my_read\"}" % call)
        if not isinstance(exclude, (list, tuple)) or not all(isinstance(n, str) for n in exclude):
            return _bad("%s: exclude must be a list of tool names in the pack, like [\"grep\"]" % call)
        where, err = self._where(self.packs_sub, call)
        if err:
            return _bad(err)
        path = os.path.join(where, name + ".json")
        shown = _shown(_join(self.root, "%s/%s.json" % (self.packs_sub, name)))
        if not os.path.isfile(path):
            have = sorted(f[:-5] for f in os.listdir(where) if f.endswith(".json")) if os.path.isdir(where) else []
            return _bad("%s: there is no %s (packs of %s: %s)" % (call, shown, self.name, ", ".join(have) or "none"))
        try:
            with open(path, encoding="utf-8") as f:
                raw = json.load(f)
        except (OSError, ValueError) as e:
            return _bad("%s: cannot read %s: %s" % (call, shown, e))
        tools = raw.get("tools") if isinstance(raw, dict) else None
        if not isinstance(tools, dict) or "$override" in raw:
            return _bad("%s: %s is not a pack agent.py can copy in: it needs {\"tools\": {...}} and no $override" % (call, shown))
        for what, names in (("rename", list(rename)), ("exclude", list(exclude))):
            for n in names:
                if not isinstance(tools.get(n), dict):
                    return _bad("%s: %s %r: the pack has no tool %s (tools: %s)" % (call, what, n, n, ", ".join(sorted(tools))))
        if set(rename) & set(exclude):
            return _bad("%s: %s is in both rename and exclude" % (call, sorted(set(rename) & set(exclude))[0]))
        out, left_out = {}, {}
        for n, e in tools.items():
            if e is None:                               # null ＝ 不是工具（照 aos-tools）
                continue
            if not isinstance(e, dict):
                if n in exclude:
                    continue
                return _bad("%s: tool %s in %s must be an object ({\"path\": ...})" % (call, n, shown))
            entry = dict(e)
            for key in ("path", "env_file"):
                if key in entry:
                    entry[key], err = self._full(entry[key], "%s, tool %s" % (call, n))
                    if err and n not in exclude:
                        return _bad(err)
            if n in exclude:                            # 動態連結時執行期照樣讀得到它：記著，tools_json 要寫 null 拿掉
                left_out[n] = entry
                continue
            final = rename.get(n, prefix + n)
            if final in out:
                return _bad("%s: two tools of the pack end up as %s; rename one of them" % (call, final))
            t = _spec().tool(final, entry.pop("path", None), **entry)
            if t["kind"] == "bad":
                return _bad("%s, tool %s: %s" % (call, n, t["bad"]))
            out[final] = t["entry"]
        return {"kind": "pack", "lib": self.name, "name": name, "tools": out, "link": link,
                "file": _join(self.root, "%s/%s.json" % (self.packs_sub, name)),     # 動態連結時 $override 寫這個
                "as_is": prefix == "" and not rename,                                  # 名字跟包裡一樣：動態連結才做得到
                "left_out": left_out}

    def tool(self, path, name=None, **more):
        """這個庫的一支工具（tools/<path>，例 std.tool("base/read")）；名字預設＝prefix＋夾名。也可當 defs.tool 的路徑：defs.tool("read", my.tool("read"))。"""
        call = "%s.tool(%r)" % (self.name, path)
        if self.bad:
            return _bad(self.bad)
        if (not isinstance(path, str) or not path or os.path.isabs(path) or ".." in path.split("/")
                or posixpath.normpath(path) == "."):
            return _bad("%s: give the tool folder relative to the library's tools folder, like \"base/read\"" % call)
        path = posixpath.normpath(path)
        where, err = self._where(self.tools_sub, call)
        if err:
            return _bad(err)
        if not os.path.isdir(os.path.join(where, path)):
            return _bad("%s: there is no tool folder %s" % (call, _shown(_join(self.root, self.tools_sub + "/" + path))))
        return _spec().tool(self.prefix + posixpath.basename(path) if name is None else name,
                            _join(self.root, self.tools_sub + "/" + path), **more)


class Std(Lib):
    """隨 aos 發的庫 std：沒搬（07 第 4 題 b），根＝$AOS_HOME；工具名不帶前綴（07 第 2 題 b）。hook 組與 fsm 格今天寄在範本名底下。"""

    def __init__(self):
        Lib.__init__(self, "std", {"$env": "AOS_HOME", "$path": ""}, packs="lib/packs", tools="lib/tools", prefix="")

    def hooks(self, template="agent-fsm"):
        """某個範本被勾清單 hookeds.json 的那組 hook（agent-fsm、eca-claude、eca-pi）。編譯時從 $AOS_HOME/templates/<template>/hookeds.json
        讀出來抄進這夾的 hookeds.json（範本改了，下次重新編譯跟著變；11-21 起檔名 hookeds.json、不再包一層 hooks）。
        回一個帶來源標記的 dict（agent_spec_hooks.Hooks）：跟另一組（另一個範本、defs.load 的 HOOKS）同名又不同＝SpecBad。"""
        call = "std.hooks(%r)" % (template,)
        if not isinstance(template, str) or not parts.PACK_RE.match(template):
            return _bad("%s: give a template name, like \"agent-fsm\"" % call)
        where, err = self._where("templates", call)
        if err:
            return _bad(err)
        try:
            with open(os.path.join(where, template, "hookeds.json"), encoding="utf-8") as f:
                table = json.load(f)
            if isinstance(table, dict):
                table = {n: e for n, e in table.items() if n != "description"}
        except FileNotFoundError:
            have = sorted(t for t in os.listdir(where) if os.path.isfile(os.path.join(where, t, "hookeds.json"))) \
                if os.path.isdir(where) else []
            return _bad("%s: there is no $AOS_HOME/templates/%s/hookeds.json (templates with hooks: %s)"
                        % (call, template, ", ".join(have) or "none"))
        except (OSError, ValueError, AttributeError) as e:
            return _bad("%s: cannot read $AOS_HOME/templates/%s/hookeds.json: %s" % (call, template, e))
        if not isinstance(table, dict):
            return _bad("%s: $AOS_HOME/templates/%s/hookeds.json is not a JSON object of hooks" % (call, template))
        return Hooks(table, call, ["templates/%s/hookeds.json" % template])   # 帶標記的一組：std.hooks()["timer"] 取一格（繼承第一刀）

    def fsm(self, group="agent-fsm"):
        """agent-fsm 範本那四格（idle、think、wait、act），格的程式借 $AOS_HOME/templates/agent-fsm/ 那份（不抄、編譯時不讀）。"""
        if group != "agent-fsm":
            return _bad("std.fsm(%r): std has one state machine, \"agent-fsm\"" % (group,))
        spec = _spec()
        return spec.fsm("idle", [spec.state(n, ["python3", _join(self.root, "templates/agent-fsm/%s.py" % prog)], nxt, timeout_ms=t)
                                 for n, prog, nxt, t in STOCK_CELLS])


std = Std()


def lib(name, root):
    """宣告別的庫：my = defs.lib("my", defs.env("AOS_WS", "/lib/my"))。根＝絕對路徑或指示詞（defs.env／defs.home），編譯時一定要讀得到；
    庫名只在這支 agent.py 裡有效，它的工具在腦那邊叫「庫名_工具名」。"""
    if not isinstance(name, str) or not parts.PACK_RE.match(name):
        return Lib(str(name), "/", bad="defs.lib(%r): the library name must be lowercase letters, digits, _ or -, like \"my\"" % (name,))
    if name == "std":
        return Lib(name, "/", bad="defs.lib(\"std\"): std comes with aos; use defs.std, or give this library another name")
    spec = _spec()
    if not (isinstance(root, str) and os.path.isabs(root)) and not spec._is_directive(root):
        return Lib(name, "/", bad="defs.lib(%r): the root must be an absolute path or defs.env(VAR, PATH) / defs.home(PATH), got %r" % (name, root))
    out = Lib(name, root)
    _, err = out._where("", "defs.lib(%r)" % name)
    if err:
        out.bad = err
    return out
