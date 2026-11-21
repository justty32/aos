"""agent_spec_agent - defs.Agent 與 defs.fsm 回的 Fsm：寫定義變成物件，.dry_run() 算出 {檔名: 內容}、不寫，.compile(夾) 算完寫進夾；loop.json 那段在內部的 _Loop。

編譯程式庫第 2 刀（線 aos-pylib-k2-1120，設計稿 thinking/2026-11/20/aos-pylib-plan-1120/01、02、07b）：使用者 11-20 選項框
「.compile(夾) 寫檔、.dry_run() 只算」「小寫」；今天以前 agent_spec 的 compile()／write()／_names() 搬到這裡當 Agent 的方法，算法與產物一字不變。
建構時只收、不驗（寫錯在 .dry_run()／.compile() 才丟 SpecBad）；編譯不改物件裡的串列與表，同一張 fsm、同一串工具可以放進好幾個 Agent。
defs.load 交回的也是 Agent（本體 aos/agent_spec_load.py）：欄位是普通屬性；tools 是一個包（底的工具疊完）；extern 連到底那夾裡面的欄位一碰就 SpecBad，
連到夾外的照樣是 extern（編譯時換算成從衍生那夾算）。
defs.extern 的連結版（第 4 刀，線 aos-pylib-k4-1120；使用者 11-20「創建一個symlink…編譯的時候就是只生成symlink」）：那一欄出一個 spec_base.Link，
放在預設檔名上（eca 版放 interfaces.json 宣告的名字），--dry-run 印成 {"$symlink": 目標}，寫的那行是「wrote 夾/檔 -> 目標」；檢查在 _links。
活的那隻的遙控器是另一個類別 aos.py.agent.Attached（11-21 改名分開）。只給 aos/agent_spec 用，寫 agent.py 的人叫 defs.Agent。
tools=[…]／hooks=[…] 裡的 @fn.tool／@fn.hook 函數（第 3 刀，線 aos-pylib-k3-1120；使用者 11-20「抽出來」「一起，同一套寫法」）：
_files 最後交給 aos/fn_spec.programs，每個函數多一份 fn/<名>.py（程式檔），tools.json／hooks.json 那格指到它；hook 照 events() 那張表查 fn.block 能不能用。
"""
import json, os

from aos import spec_base
from aos import fn_spec
from aos.spec_unit import Unit
from aos import agent_spec_parts as parts
from aos import agent_spec_hooks as hook_parts
from aos.agentlib import hooks as agent_hooks
from aos.spec_base import SpecBad, DefBad
from aos.agent_spec_parts import WHAT, LLM_KEYS, OWN_FILES, SKELETON, RUNTIME_FILES

FIELDS = ("description", "system", "tools", "llm", "fsm", "hooks", "meta", "interfaces", "files", "loop")
FLAG_IF = {"before_run": {"$env": "AOS_STACK", "$path": "/hook_before_run.flag"},   # loop.json 的 on_before_run_if／on_after_run_if（檔名同 aos.hook_flags.FLAGS）
           "after_run": {"$env": "AOS_STACK", "$path": "/hook_after_run.flag"}}
RENAME_LAST = {"loop.json": 1, "body.json": 2, "interfaces.json": 3, "_entry": 4, "_metainfo.json": 5}   # 改名時被指的檔先換、索引檔最後（其他＝0）
SEE_CHANGE = ("agents that use this definition see the change from their next brain call "
              "(state machine and loop changes: from their next tick or restart)")


def _fsm_json(fsm):
    return {"description": WHAT["fsm.json"], "_entry": ["aos-fsm", {"$env": "AOS_CF"}], "start": fsm["start"], "states": fsm["states"]}


def _plain(out):
    """跟宣告的物件脫鉤（之後改宣告不影響回傳值）；也確認都能寫成合法 JSON（NaN 不算）。"""
    try:
        return json.loads(json.dumps(out, allow_nan=False))
    except (TypeError, ValueError) as e:
        raise SpecBad("a declared value cannot be written as JSON (%s); use strings, numbers, lists and dicts" % e)


class Fsm(dict, Unit):
    """defs.fsm(...)／std.fsm() 回的狀態機：普通 dict（{"kind": "fsm", "start", "states"}；寫錯＝{"kind": "bad"}，先記著）。
    自己就能編譯：.dry_run() → {"fsm.json": 內容}，.compile(夾, name="fsm.json") 只寫那一份（aos-fsm 吃它就能跑）；放進 defs.Agent(fsm=…) 照舊。"""

    def _files(self, folder, warn, name="fsm.json"):
        parts.raise_bad(self)
        if parts.kind(self) != "fsm":
            raise SpecBad("a state machine comes from defs.fsm(...) or std.fsm()")
        if not isinstance(name, str) or not name or "/" in name or name.startswith(".") or name != name.strip():
            raise SpecBad("name=%r: give one plain file name in the folder, like \"fsm.json\"" % (name,))
        return _plain({name: _fsm_json(self)})


def fire(event, fields=()):
    """loop.json 裡發一個 hook 點的單子：aos-hook fire -q --agent $AOS_CD [欄位旗標…] EVENT（照 agent-fsm 範本；
    on_start／on_stop 也走這裡，線 top-1121-hookfire）。"""
    return {"argv": ["aos-hook", "fire", "-q", "--agent", {"$env": "AOS_CD"}] + list(fields) + [event]}


def run_points(fsm_file):
    """有 hooks 的 fsm agent 的 loop.json 多的四鍵：身體（一格）前後經 aos-hook fire --agent 發 before_run／after_run，旗標檔在才跑
    （hook 第 5 刀後半，線 top-1121-hook5；寫法照設計 aos-hook-plan-1120/06：stage 從 stack 的 stage.txt 讀，第一圈還沒有那個檔時用 fsm 的起始格）。"""
    return {"on_before_run": fire("before_run", ["--field-file", {"$env": "AOS_STACK", "$path": "/stage.txt", "$prefix": "stage="},
                                                 "--field-default", {"$ref": fsm_file + "#/start", "$prefix": "stage="}]),
            "on_before_run_if": dict(FLAG_IF["before_run"]),
            "on_after_run": fire("after_run", ["--field-file", {"$env": "AOS_STACK", "$path": "/stage.txt", "$prefix": "next_stage="}]),
            "on_after_run_if": dict(FLAG_IF["after_run"])}


class _Loop:
    """loop.json：每格跑 fsm 那份、公開 ctl／state／state_flux；有 hooks 才接 on_start／on_stop（after_start／after_stop）與
    on_before_run／on_after_run 和兩個 _if（before_run／after_run，run_points）。
    內部的一塊（設計稿 02「loop 與 fsm 在庫裡的地位」）；人能宣告間隔：defs.Agent(..., loop=defs.loop(every_ms=…))（待裁第 8 題「加一個宣告」，
    線 aos-pylib-k4-1120），不給＝300；defs.loop 的其他鍵在這份算完之後原樣蓋上去（11-21「任意鍵照傳」，在 Agent._files）。hook 那幾個鍵由 hook 介面線帶（07「跟 hook 介面線共用的檔」；第 5 刀後半加了 run_points 那四個）。"""

    def __init__(self, fsm_file, hooks, every_ms=300):
        self.fsm_file, self.hooks, self.every_ms = fsm_file, hooks, every_ms

    def json(self):
        loop = {"description": WHAT["loop.json"] % self.fsm_file, "exec": self.fsm_file, "interval_ms": self.every_ms,
                "ctl": "ctl.json", "state": "state.json", "state_flux": "state_flux.json"}
        if self.hooks:
            loop["description"] += WHAT["loop_hooks"]
            loop["on_start"] = fire("after_start")
            loop["on_stop"] = fire("after_stop")
            loop.update(run_points(self.fsm_file))
        return loop


def _names(decl, fsm, hooks, interfaces, folder):
    """回四樣：{種類: 這次用的檔名}、{種類: extern 記號}、files 不能用的檔名、llm_keys（有 fsm＝None，之後照編譯出的 interfaces.json）。
    extern 的那一欄照樣坐在這個檔名上（第 4 刀：連結放在預設檔名、eca 版放在 interfaces.json 宣告的名字），interfaces.json 不再寫手寫檔的名字。"""
    hand = {w: v for w, v in decl.items() if parts.kind(v) == "extern"}
    if fsm is None:
        if interfaces is not None:
            raise SpecBad("interfaces needs fsm: without fsm, interfaces.json belongs to the skeleton you copied; change it by hand")
        if folder is None:
            raise SpecBad("fsm is not given, so this agent fills the content files of an existing definition: give its folder")
        have, keys = parts.existing_names(folder)
        files = {}
        for what in parts.CONTENT:
            if what == "hooks" and hooks is None:
                continue
            if what not in have:
                raise DefBad("%s/interfaces.json declares no %s file, so %s has nowhere to go: add \"%s\" to its aos-agent, "
                             "or give fsm" % (folder, what, what, what))
            files[what] = have[what]
        return files, hand, set(have.values()) | set(files.values()), keys
    files = {w: f for w, f in OWN_FILES.items() if w != "hooks" or hooks is not None}
    return files, hand, set(files.values()), None


def _links(hand, names, folder):
    """extern 的欄位 → {檔名: spec_base.Link(連結裡存的字)}（第 4 刀，設計稿 aos-pylib-plan-1120/05）。相對路徑從連結所在的夾算（通常就是編譯進去的那一夾）；
    defs.load 的底連到底那夾外面的（記號帶 from）＝現在才換算成從這一夾走過去的相對路徑。照字面存，不碰目標；不驗目標的內容。
    SpecBad：沒給夾、繞回連結自己、目標不在、目標是資料夾、fsm 指到別的夾（aos-loop 會把連結解開，把目標那一夾當成定義夾）。"""
    if hand and folder is None:
        raise SpecBad("defs.extern(...) is a link counted from the folder it is compiled into: give the folder, like .dry_run(\"FOLDER\")")
    out = {}
    for what, ext in hand.items():
        name = names[what]
        place = os.path.dirname(os.path.join(folder, name))         # 連結所在的夾
        target = ext["target"]
        if "from" in ext and not os.path.isabs(target):
            target = os.path.relpath(os.path.join(ext["from"], target), place)
        shown = "extern(%r) for %s" % (ext["target"], what)
        seen = os.path.join(place, target)
        me = os.path.join(os.path.realpath(place), os.path.basename(name))
        if me in (os.path.join(os.path.realpath(os.path.dirname(seen)), os.path.basename(seen)), os.path.realpath(seen)):
            stem, ext_ = os.path.splitext(os.path.basename(name))
            raise SpecBad("%s links %s to itself: give the file to link to, like defs.extern(\"%s.hand%s\") for a file of this folder "
                          "kept by hand" % (shown, name, stem, ext_))
        if not os.path.exists(seen):
            raise SpecBad("%s: %s does not exist (seen from %s)" % (shown, target, place))
        if os.path.isdir(seen):
            raise SpecBad("%s: %s is a folder; link to a file" % (shown, target))
        if what == "fsm" and (os.path.isabs(target) or os.path.dirname(os.path.normpath(target))
                              or os.path.normpath(target) in (os.curdir, os.pardir)):
            raise SpecBad("%s: a state machine can only link to a file in the same folder, like defs.extern(\"fsm.hand.json\"): "
                          "aos-loop resolves the link and would run the states as if the target's folder were the definition" % shown)
        out[name] = spec_base.Link(target)
    return out


class Agent(Unit):
    """一隻 agent 的定義：defs.Agent(說明, system=, tools=, llm=, fsm=None, hooks=None, meta=None, interfaces=None, files=None, loop=None)。
    不給 fsm＝只填一份現成定義夾的內容檔（eca 版，要知道夾才算得出：.dry_run(夾)）。命令列 --static／--dynamic 只有它收（link=）。
    loop＝defs.loop(every_ms=…)（loop.json 的間隔；要有 fsm）。"""
    LINKS = True
    AFTER = (SEE_CHANGE,)

    def __init__(self, description, *, system, tools, llm, fsm=None, hooks=None, meta=None, interfaces=None, files=None, loop=None):
        self.description, self.system, self.tools, self.llm, self.fsm = description, system, tools, llm, fsm
        self.hooks, self.meta, self.interfaces, self.files, self.loop = hooks, meta, interfaces, files, loop

    def __getattr__(self, name):              # 只在沒有這個屬性時才來：defs.load 交回的 extern 欄位、寫錯的名字
        hand = self.__dict__.get("_hand", {})
        if name in hand:
            raise SpecBad("%s: %s of %s/agent.py is defs.extern(%r), a link to a file inside that folder, so there is nothing to build "
                          "on (a link to it would make this definition run on another one's file, N-70): write %s yourself"
                          % (self.__dict__["_shown"], name, self.__dict__["path"], hand[name], name))
        raise AttributeError("%s has no %s (it has %s, and .pack(prefix=, rename=, exclude=), .dry_run(), .compile(folder))"
                             % (self._label(), name, ", ".join(FIELDS)))

    def __setattr__(self, name, value):       # 欄位是普通屬性、可以改；寫錯的名字（agent.TOOLS = …）不悄悄收下
        if not name.startswith("_") and name not in FIELDS:
            raise AttributeError("%s has no field %s (fields: %s)" % (self._label(), name, ", ".join(FIELDS)))
        object.__setattr__(self, name, value)

    def _label(self):
        return self.__dict__.get("_shown") or "defs.Agent(%r)" % (self.__dict__.get("description"),)

    def __repr__(self):
        shown = self.__dict__.get("_shown")
        return "<agent.py loaded by %s from %s>" % (shown, self.path) if shown else "<%s>" % self._label()

    def events(self):
        """這隻收的 hook 事件表：agent 的 hooks.EVENTS（11-20 hook 第 3 刀起由 aos 自己帶的宣告合起來算出）。
        不照這隻自己的 hook_points 縮小：掛到這隻不會發的事件照舊掛得上（使用者 11-20 待裁第 5 題「照舊不管」）。"""
        return agent_hooks.EVENTS

    def pack(self, prefix="", rename=None, exclude=None):
        """這隻的 tools 當一個包，可以改名：prefix＝每支前面加、rename＝{原名: 新名}、exclude＝不要的（原名；連墓碑一起不要），同 std.pack。寫錯先記著。"""
        if "tools" in self.__dict__.get("_hand", {}):
            return self.__getattr__("tools")
        call = "%s.pack(...)" % self._label()
        rename = {} if rename is None else rename
        exclude = [] if exclude is None else exclude
        if not isinstance(prefix, str) or not (prefix == "" or all(c.isalnum() or c in "_-" for c in prefix)):
            return {"kind": "bad", "bad": "%s: prefix must be letters, digits, _ or -" % call}
        if not isinstance(rename, dict) or not all(isinstance(k, str) and isinstance(v, str) for k, v in rename.items()):
            return {"kind": "bad", "bad": "%s: rename must be a dict {name in the base: new name}" % call}
        if not isinstance(exclude, (list, tuple)) or not all(isinstance(n, str) for n in exclude):
            return {"kind": "bad", "bad": "%s: exclude must be a list of tool names in the base" % call}
        try:
            table, origins = parts.stack_tools(_tool_list(self.tools))
        except SpecBad as e:
            return {"kind": "bad", "bad": "%s: %s" % (call, e)}
        for what, names in (("rename", list(rename)), ("exclude", list(exclude))):
            for n in names:
                if n not in table:
                    return {"kind": "bad", "bad": "%s: %s %r: the base has no tool %s (tools: %s)" % (
                        call, what, n, n, ", ".join(sorted(table)))}
        out = {}
        for n, entry in table.items():
            if n in exclude:
                continue
            final = rename.get(n, prefix + n)
            if final in out or not parts.TOOL_RE.match(final):
                return {"kind": "bad", "bad": "%s: tool %s ends up as %r: two tools with one name, or not 1-64 letters, digits, _ or -"
                        % (call, n, final)}
            out[final] = json.loads(json.dumps(entry))
        label = self._label() if (prefix, rename, exclude) == ("", {}, []) else "%s.pack(prefix=%r, rename=%r, exclude=%r)" % (
            self._label(), prefix, rename, list(exclude))
        return {"kind": "pack", "lib": "defs.load", "name": self._label(), "label": label, "origins": list(origins), "tools": out}

    def _files(self, folder, warn, link="static"):
        """→ {檔名: 內容}（json 是 dict、文字是字串；_metainfo.json 只有 agent.py 設的鍵、README.md 是種子）。全部驗完才回，錯丟 SpecBad／DefBad。
        fsm=None＝要給 folder（照它現有的 interfaces.json 找檔名），骨架不出。link＝工具包怎麼連結（"static" 預設、"dynamic"）；包上明寫的 link= 優先。"""
        if link not in ("static", "dynamic"):
            raise SpecBad("link must be \"static\" or \"dynamic\", got %r" % (link,))
        description, system, tools, llm, fsm = self.description, self.system, self.tools, self.llm, self.fsm
        meta, interfaces, files = self.meta, self.interfaces, self.files
        if not isinstance(description, str) or not description.strip():
            raise SpecBad("description must be a non-empty string: one sentence saying what the agent does")
        description = description.strip()
        hooks = hook_parts.no_hooks(self.hooks)
        decl = {"system": system, "tools": tools, "llm": llm, "fsm": fsm, "hooks": hooks}
        for value in decl.values():
            parts.raise_bad(value)
        if fsm is not None and parts.pick(fsm, "fsm must come from defs.fsm(...), std.fsm() or defs.extern(\"fsm.hand.json\") (or leave it out: no fsm)",
                                          lambda v: parts.kind(v) == "fsm"):
            fsm_out = None
        else:
            fsm_out = fsm
        names, hand, taken, keys = _names(decl, fsm, hooks, interfaces, folder)
        links = _links(hand, names, folder)
        if parts.pick(system, "system must be a string (the system text) or defs.extern(\"../shared/system.txt\")", lambda v: isinstance(v, str)):
            system = None
        face = None
        if fsm is not None:
            face = parts.interfaces_json(interfaces, names, description)
            keys = face.get("aos-agent", {}).get("llm_keys", LLM_KEYS)
            if not isinstance(keys, list) or not all(isinstance(k, str) for k in keys):
                raise SpecBad("interfaces aos-agent llm_keys must be a list of strings")
        tools_out = None if parts.pick(tools, "tools must be a list of std.pack(...), std.tool(...), defs.tool(...), defs.drop(...) "
                                              "(or a library's .pack / .tool, or the tools of defs.load(...): [base.tools, ...]), "
                                              "or defs.extern(\"../shared/tools.json\")",
                                       lambda v: isinstance(v, (list, tuple)) or parts.kind(v) == "pack") \
            else parts.tools_json(_tool_list(tools), link, warn)
        llm_out = None if parts.pick(llm, "llm must be a dict like {\"model\": \"luna\"} ({} = the kernel's default), or defs.extern(\"../shared/llm.json\")",
                                     lambda v: isinstance(v, dict)) else parts.llm_json(llm, keys)
        hooks_out = None if hooks is None or "hooks" in hand else hook_parts.hooks_json(hooks)
        programs = fn_spec.programs(tools_out, names.get("tools"), hooks_out, names.get("hooks"), self.events())
        extra = parts.extra_files(files, taken) if files is not None else {}
        if meta is not None and not isinstance(meta, dict):
            raise SpecBad("meta must be a dict like {\"cost\": {\"time_ms\": 60000}, \"resource\": [\"llm\"]}")
        if meta and not all(isinstance(k, str) for k in meta):
            raise SpecBad("meta keys must be strings, like {\"cost\": {\"time_ms\": 60000}}")
        if meta and "summary" in meta:
            raise SpecBad("meta must not set summary (it comes from the description)")
        every_ms, loop_keys = 300, {}           # 不給 loop＝跟以前一樣（產物逐 byte 相同）
        if self.loop is not None:
            parts.raise_bad(self.loop)
            if parts.kind(self.loop) != "loop":
                raise SpecBad("loop must come from defs.loop(every_ms=...), got %r" % (self.loop,))
            if fsm is None:
                raise SpecBad("loop needs fsm: without fsm, loop.json belongs to the skeleton you copied; change it there by hand")
            if self.loop.get("every_ms") is not None:
                every_ms = self.loop["every_ms"]
            loop_keys = self.loop.get("keys") or {}
        out = {}
        if fsm is not None:
            out["_entry"] = {"description": WHAT["_entry"], "argv": ["aos-agent", "ctl", "add", {"$env": "AOS_CD"}],
                             "cwd": {"$env": "AOS_WS"}}
            out["body.json"] = {"description": WHAT["body.json"], "argv": ["aos-loop", "loop.json"]}
            out["loop.json"] = {**_Loop(names["fsm"], hooks is not None, every_ms).json(), **loop_keys}   # 任意鍵照傳、你給的蓋過去（11-21）
            if fsm_out is not None:
                out["fsm.json"] = _fsm_json(fsm_out)
            out["interfaces.json"] = face
        for what, value in (("tools", tools_out), ("llm", llm_out), ("system", system), ("hooks", hooks_out)):
            if value is not None:
                out[names[what]] = value
        out.update(extra)
        out["_metainfo.json"] = dict({"summary": description}, **(meta or {}))
        out["README.md"] = description + "\n"
        out = _plain(out)
        for name in programs:                   # fn/<名>.py：程式檔（755），不經 _plain（那會變回普通字串）
            if name in out or name in links:
                raise SpecBad("%s, the program of a function, clashes with a file agent.py writes or an extern; rename the function "
                              "(name=)" % name)
        out.update(programs)
        out.update(links)                       # 連結（第 4 刀）：也不經 _plain
        return out

    def _write(self, folder, files):
        """files 寫進 folder；回給人看的字串串列。這裡只管兩條：先讀好 _metainfo.json、只蓋自己的鍵；README.md 在就不寫。
        其餘交給 spec_base.write_files（暫存檔＋照 RENAME_LAST 改名；寫暫存檔時失敗＝夾裡不變）。OSError 照丟；_metainfo.json 不是 JSON 物件＝DefBad。"""
        plan = {}
        for name, value in files.items():
            path = os.path.join(folder, name)
            if name == "README.md":
                if os.path.lexists(path):
                    continue
            elif name == "_metainfo.json" and os.path.lexists(path):
                try:
                    with open(path, encoding="utf-8") as f:
                        old = json.load(f)
                except ValueError as e:                     # 讀不懂（不是 JSON、不是 utf-8）；讀不到（OSError）照丟
                    raise DefBad("cannot read %s, so its other keys cannot be kept: %s" % (path, e))
                if not isinstance(old, dict):
                    raise DefBad("%s is not a JSON object, so its other keys cannot be kept" % path)
                old.update(value)
                value = old
            plan[name] = value
        spec_base.write_files(folder, plan, last=RENAME_LAST)
        done = ["wrote %s%s" % (os.path.join(folder, name), " -> %s" % value if isinstance(value, spec_base.Link) else "")
                for name, value in plan.items()]
        if "README.md" in files and len(plan) < len(files):
            done.append("kept %s (it is already there)" % os.path.join(folder, "README.md"))
        return done


def _tool_list(tools):
    """tools 可以是一個包（defs.load 交回的 base.tools 單獨用）：當成只有它的串列。"""
    return [tools] if parts.kind(tools) == "pack" else tools
