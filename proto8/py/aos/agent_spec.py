"""agent_spec - 給人寫 agent 定義的輔助（寫 agent.py 的人叫它 defs）：defs.Agent(...) 宣告一隻 agent，.compile(夾) 編出一份掛得上去的定義夾、.dry_run() 只算；這裡是宣告用的小函式與 agent.py 最後一行的 defs.main(物件)。

使用者 11-18：「讓我不必在那邊mkdir半天」；11-19 定調：「agent.py產出東西後，產出後的東西就跟他沒關係了。好比C語言和.o之間的關係。」
所以再編譯＝直接蓋：不記指紋、不寫記號、沒有 --force／--status；產出後的 json 誰都能照常改，下次編譯被蓋回去（設計稿 thinking/2026-11/19/aos-compile-庚/）。
寫定義變成物件（編譯程式庫第 2 刀，線 aos-pylib-k2-1120；設計稿 thinking/2026-11/20/aos-pylib-plan-1120/01、02）：使用者 11-20 選項框
「.compile(夾) 寫檔、.dry_run() 只算」「小寫」：agent.py 寫 a = defs.Agent("說明", system=…, tools=[…], llm={…}, fsm=…, hooks=…) 再 defs.main(a)；
指令 --compile [--static|--dynamic] [夾] 編譯＋寫、--dry-run 只印不寫（旗標不變）。Agent、Fsm 的本體在 aos/agent_spec_agent.py，
各份檔怎麼算、怎麼驗在 aos/agent_spec_parts.py，命令列殼與 Unit 在 aos/spec_unit.py，例外與寫檔後端在 aos/spec_base.py。
名字 defs：from aos.py.agent import defs（使用者 11-19「就 aos.py.agent.defs 吧」；檔不搬、模組名不改）。

宣告用的小函式（寫錯不在當下丟，記成 bad，.dry_run()／.compile()／defs.main 再報 SpecBad）：
  Agent(說明, system=, tools=, llm=, fsm=None, hooks=None, meta=None, interfaces=None, files=None)  一隻 agent；不給 fsm＝只填現成定義夾的內容檔（eca 版）
  std                 隨 aos 發的庫（aos/agent_spec_lib.py）：std.pack(名, prefix=, rename=, exclude=, link=)、std.tool("base/read", name=None, **其他)、
                      std.fsm()＝agent-fsm 範本的四格、std.hooks(範本="agent-fsm")＝那個範本 hooks.json 的那組 hook
  lib(庫名, 根)        別的庫：my = defs.lib("my", defs.env("AOS_WS", "/lib/my"))；my.pack／my.tool 同上，工具名自動帶「庫名_」
  tool(名, 路徑, **其他) 單一個工具；路徑也可給 my.tool(...)（只拿它的路徑）；同名蓋掉包裡那支。drop(名)＝從展開的包裡拿掉那支
  home(路徑)／env(變數, 路徑)  指示詞 {"$env": …, "$path": …}，原樣吐、不展開
  state(名, argv, next, timeout_ms=None)、fsm(起點, [state…])  fsm 回 Fsm：放進 Agent(fsm=…)，或自己 .compile(夾, name="fsm.json")
  extern(檔名)         這份檔自己手寫：interfaces.json 指到它、不編、不蓋（system／tools／llm／fsm／hooks 都可用）
  load(路徑)           衍生（本體 aos/agent_spec_load.py）：base = defs.load("../reviewer") 跑那支 agent.py，交回它交給 defs.main 的那隻（新的一份）；
                       tools=[base.tools, defs.drop(...)]、hooks=[base.hooks, {名: {**base.hooks[名], 鍵: 值}}]、fsm=defs.fsm(base.fsm, [...], drop=[...])、
                       base.pack(prefix=, rename=, exclude=)；只在編譯時算，編出的 json 整份、不記上一層（N-70）
main(物件)：agent.py 最後一行；--compile [資料夾]、--dry-run、--help，都沒有＝ArgumentsBad 帶用法（P-44）；Agent 的前兩個可加 --static（預設）／--dynamic。
"""
import json, os, sys

from aos import flags
from aos import spec_base, spec_unit
from aos.spec_base import SpecBad, DefBad  # noqa: F401（對外的名字：defs.SpecBad、defs.DefBad）
from aos import agent_spec_parts as parts
from aos.agent_spec_parts import WHAT, LLM_KEYS, OWN_FILES, SKELETON, RUNTIME_FILES  # noqa: F401（對外的名字）
from aos.agent_spec_agent import Agent, Fsm
from aos.agent_spec_lib import std, lib  # noqa: F401（對外的名字：defs.std、defs.lib）
from aos import agent_spec_load as loader
from aos.agent_spec_load import load  # noqa: F401（對外的名字：defs.load）

PUBLIC = ("Agent", "main", "load", "std", "lib", "tool", "drop", "extern", "home", "env", "state", "fsm", "SpecBad", "DefBad")
HELP = """\
usage: python3 agent.py --compile [--static | --dynamic] [FOLDER] | --dry-run [--static | --dynamic] | --help
Compile agent.py into an aos agent definition (a folder of JSON files), like a C compiler
turning a .c file into a .o file. agent.py declares the agent as an object and ends with
defs.main(it): agent = defs.Agent("what it does", system=..., tools=[...], llm={...}, fsm=std.fsm()).
  --compile [FOLDER]  compile and write the definition files into FOLDER (default: the folder
                      of agent.py). Compiling again overwrites, as a whole, every file agent.py
                      declares; _metainfo.json keeps keys agent.py does not set; README.md is
                      written only when it is missing; every other file is left alone.
  --dry-run           compile and print everything --compile would write, as one JSON object
                      {"file name": content}, and write nothing.
  --static            (the default) link tool packs statically: their tools are copied into
                      tools.json one by one; a tool added to a pack later needs a recompile.
  --dynamic           link tool packs dynamically: tools.json names the pack files ($override)
                      and aos reads them when the agent runs; a tool added to a pack later shows
                      up at the agent's next brain call, without recompiling. A pack whose tools
                      get a prefix or rename= (a library other than std, by default), and the
                      tools of defs.load, are still linked statically, with a warning.
                      One pack: std.pack("look", link="dynamic") / link="static".
With fsm given, agent.py writes the whole definition (skeleton included). Without fsm
(defs.Agent(..., system=, tools=, llm=) only), it fills only the content files (system, tools, llm,
hooks) of a definition that already has its skeleton, under the names its interfaces.json gives.
Packs (std.pack, or .pack of a library from defs.lib) are read when agent.py runs (also when they are
linked dynamically, to check the tool names), so AOS_HOME, and any variable a library root uses, must be set.
To build on another agent.py: base = defs.load("../other") runs it and gives back the agent it hands to
defs.main; write tools=[base.tools, defs.drop("x")], hooks=[base.hooks, {...}], fsm=defs.fsm(base.fsm, [...]);
it is worked out now, so the files written are whole and do not name the other one (README: "Build on").
Without defs.main (a build script, the REPL): agent.dry_run() gives the files, agent.compile(FOLDER) writes them.
Then mount it: aos-agent ctl add FOLDER.
On a wrong declaration: one line "NAME: error: SpecBad ..." on stderr, exit 1, nothing written.
"""


def __getattr__(name):
    if name.startswith("__"):
        raise AttributeError(name)
    raise AttributeError("defs has no %s (it has %s)" % (name, ", ".join(PUBLIC)))


def _bad(msg):
    return {"kind": "bad", "bad": msg}


def _is_directive(v):
    return isinstance(v, dict) and isinstance(v.get("$env"), str) and bool(v["$env"]) and isinstance(v.get("$path", ""), str)


def _is_path(v):
    return (isinstance(v, str) and bool(v)) or _is_directive(v)


def home(path):
    """$AOS_HOME 底下的路徑：home("/lib/tools/base/read") → {"$env": "AOS_HOME", "$path": "/lib/tools/base/read"}。"""
    return env("AOS_HOME", path)


def env(var, path):
    """某個環境變數底下的路徑：env("AOS_WS", "/tools/x") → {"$env": "AOS_WS", "$path": "/tools/x"}；編譯時不展開。"""
    return {"$env": var, "$path": path}


def tool(name, path, **more):
    """單一個工具；more（env、env_file…）原樣寫進那一格；aos-tools 合併時會擋的（env、env_file、cache）這裡先擋。
    path 也可以是某個庫的 .tool(...)：只拿它的路徑（defs.tool("read", my.tool("read"))＝用 my 那支、叫 read）。"""
    if not isinstance(name, str) or not parts.TOOL_RE.match(name):
        return _bad("tool name %r must be 1-64 letters, digits, _ or -" % (name,))
    if parts.kind(path) == "bad":
        return path
    if parts.kind(path) == "tool":
        path = path["entry"]["path"]
    if not _is_path(path):
        return _bad("tool %s must have a path: a string, or defs.home(\"/lib/tools/...\") / defs.env(VAR, PATH) / std.tool(\"base/read\")" % name)
    e = more.get("env", {})
    if not isinstance(e, dict) or not all(isinstance(k, str) and parts.ENV_KEY_RE.match(k) and isinstance(v, str) for k, v in e.items()):
        return _bad("tool %s: env must be a dict of NAME -> string, like {\"LANG\": \"C\"}" % name)
    if "env_file" in more and not _is_path(more["env_file"]):
        return _bad("tool %s: env_file must be a non-empty path string or defs.home(...) / defs.env(...)" % name)
    if "cache" in more and more["cache"] is not False:
        return _bad("tool %s: cache can only be False" % name)
    return {"kind": "tool", "name": name, "entry": dict({"path": path}, **more)}


def drop(name):
    """把展開的包裡的某個工具拿掉（腦看到的名字；tools.json 裡就沒有那格）。"""
    if not isinstance(name, str) or not parts.TOOL_RE.match(name):
        return _bad("defs.drop(%r): the tool name must be 1-64 letters, digits, _ or -" % (name,))
    return {"kind": "drop", "name": name}


def extern(filename):
    """這份檔自己手寫：interfaces.json 指到它，agent.py 不編、不蓋。"""
    if (not isinstance(filename, str) or not filename or os.path.isabs(filename) or ".." in filename.split("/")
            or os.path.normpath(filename) == "."):
        return _bad("extern(%r): give a file name relative to the definition folder, like \"system.txt\"" % (filename,))
    return {"kind": "extern", "file": os.path.normpath(filename)}


def _state_name_bad(name):
    return not isinstance(name, str) or not name or name != name.strip() or "\n" in name


_LEFT_OUT = object()


def state(name, argv=_LEFT_OUT, next=_LEFT_OUT, timeout_ms=None):
    """狀態機的一格：跑 argv（字串或 defs.home(...) 的串列），退出碼 → 下一格（{0: "think", 10: "idle"}；"*"＝其他碼；字串＝只有 0）。
    argv、next 單獨用時要給齊；在 defs.fsm(base.fsm, [...]) 裡換底的同名格時可以只給要換的（沒給的沿用底那格；繼承第一刀）。"""
    if _state_name_bad(name):
        return _bad("state name %r must be a non-empty string without leading or trailing spaces or newlines" % (name,))
    partial = argv is _LEFT_OUT or next is _LEFT_OUT
    exec_, cell = {}, {}
    if argv is not _LEFT_OUT:
        if not isinstance(argv, (list, tuple)) or not argv or not all(_is_path(a) for a in argv):
            return _bad("state %s: argv must be a non-empty list of strings or defs.home(...) paths, like [\"python3\", \"idle.py\"]" % name)
        exec_["argv"] = list(argv)
    if timeout_ms is not None:
        if not isinstance(timeout_ms, int) or isinstance(timeout_ms, bool) or timeout_ms < 0:
            return _bad("state %s: timeout_ms must be a whole number of milliseconds >= 0 (0 = no limit)" % name)
        exec_["timeout_ms"] = timeout_ms
    cell["exec"] = exec_
    if next is not _LEFT_OUT:
        nxt = _next(name, next)
        if parts.kind(nxt) == "bad":
            return nxt
        cell["next"] = nxt
    return {"kind": "state", "name": name, "cell": cell, "partial": partial}


def _next(name, next):
    if isinstance(next, str):
        return next
    if isinstance(next, dict) and next:
        nxt = {}
        for code, target in next.items():
            if code == "*" or (isinstance(code, int) and not isinstance(code, bool) and 0 <= code <= 255):
                nxt[str(code)] = target
            else:
                return _bad("state %s: exit code %r in next must be a whole number 0-255 or \"*\"" % (name, code))
        if "0" not in nxt and "*" not in nxt:
            return _bad("state %s: next must have exit code 0 or \"*\" (exit code 0 must always lead somewhere)" % name)
        return nxt
    return _bad("state %s: next must be a state name, or a dict {exit code: state name} like {0: \"think\"}" % name)


def fsm(start, states, drop=()):
    """狀態機：起點＋各格（defs.state(...) 的串列）→ Fsm（寫錯也是 Fsm，記著 bad）。下一格、起點都要在表上（aos-fsm 開跑時查的同一套）。
    第一個參數給底的狀態機（defs.load(...).fsm、std.fsm()）＝換格（繼承第一刀）：drop 的格拿掉，同名格只換有給的欄位，新名的格加上（要給齊），整張重驗。"""
    return Fsm(_fsm(start, states, drop))


def _fsm(start, states, drop):
    if parts.kind(start) == "bad":
        return start
    if parts.kind(start) == "fsm":
        return _refit(start, states, drop)
    if start is None:
        return _bad("defs.fsm: the start is None: give the name of the start state, or the fsm of a loaded agent.py "
                    "(an agent without fsm, like an eca body, has fsm None: there is no state machine to build on)")
    if drop:
        return _bad("defs.fsm: drop= only works on a state machine to build on, like defs.fsm(base.fsm, [...], drop=[\"act\"])")
    if not isinstance(states, (list, tuple)) or not states:
        return _bad("fsm needs a non-empty list of defs.state(...)")
    table = {}
    for s in states:
        if parts.kind(s) == "bad":
            return s
        if parts.kind(s) != "state":
            return _bad("each item of fsm states must come from defs.state(...), got %r" % (s,))
        if s["name"] in table:
            return _bad("state %s is declared twice" % s["name"])
        if s.get("partial"):
            return _bad("state %s needs both argv and next (only defs.fsm(base.fsm, [...]) takes a state with some left out)" % s["name"])
        table[s["name"]] = s["cell"]
    return _checked(start, table)


def _refit(base, states, drop):
    """defs.fsm(底, [...], drop=)：底那張表的一份拷貝上換格。"""
    table = json.loads(json.dumps(base["states"]))
    if not isinstance(states, (list, tuple)):
        return _bad("defs.fsm(base, states): states must be a list of defs.state(...) (it can be empty)")
    if isinstance(drop, str) or not isinstance(drop, (list, tuple)) or not all(isinstance(d, str) for d in drop):
        return _bad("defs.fsm(base, ..., drop=...): drop must be a list of state names, like [\"act\"]")
    for d in drop:
        if d not in table:
            return _bad("defs.fsm(base, ..., drop=[%r]): the base has no state %s (states: %s)" % (d, d, ", ".join(table)))
        del table[d]
    seen = set()
    for s in states:
        if parts.kind(s) == "bad":
            return s
        if parts.kind(s) != "state":
            return _bad("each item of fsm states must come from defs.state(...), got %r" % (s,))
        if s["name"] in seen:
            return _bad("state %s is declared twice" % s["name"])
        seen.add(s["name"])
        if s["name"] in table:
            cell = table[s["name"]]
            cell.setdefault("exec", {}).update(s["cell"]["exec"])
            if "next" in s["cell"]:
                cell["next"] = s["cell"]["next"]
        elif s.get("partial"):
            return _bad("state %s is not in the base (states: %s), so it needs both argv and next" % (s["name"], ", ".join(table)))
        else:
            table[s["name"]] = s["cell"]
    if base["start"] not in table:
        return _bad("defs.fsm(base, ...): the start state %s is dropped; a state machine needs its start" % base["start"])
    return _checked(base["start"], table)


def _checked(start, table):
    if not isinstance(start, str) or start not in table:
        return _bad("fsm start %r is not one of the states (%s)" % (start, ", ".join(table)))
    for name, cell in table.items():
        targets = [cell["next"]] if isinstance(cell["next"], str) else list(cell["next"].values())
        for t in targets:
            if not isinstance(t, str) or t not in table:
                return _bad("state %s: next state %r is not one of the states (%s)" % (name, t, ", ".join(table)))
    return {"kind": "fsm", "start": start, "states": table}


def main(*args, **kw):
    """agent.py 的最後一行：defs.main(defs.Agent(...))（或一張 defs.fsm(...)：只編 fsm.json）。只收一個物件。
    被 defs.load 載入時：不讀 argv、不寫檔、不退出，只把物件交給 defs.load。被普通 import（叫它的模組不是 __main__）：印一行 warning、什麼都不做
    （繼承第一刀：以前會照 argv 寫進底那夾、退 0，衍生那支根本沒跑；aos-inherit-1119/02 結論 5）。"""
    caller = sys._getframe(1)
    script = os.path.realpath(caller.f_code.co_filename)
    prog = spec_base.prog_name(script, "agent.py")
    unit = args[0] if len(args) == 1 and not kw else None
    bad = None
    if not isinstance(unit, spec_unit.Unit):
        if kw:
            got = "keyword arguments %s" % ", ".join("%s=" % k for k in kw)
        elif len(args) != 1:
            got = "%d arguments" % len(args)
        else:
            got = "a value of type %s" % type(args[0]).__name__
        bad = ("defs.main takes one thing to compile: an agent, defs.main(defs.Agent(\"what it does\", system=..., tools=[...], "
               "llm={...}, fsm=...)), or a state machine from defs.fsm(...); got %s" % got)
    if loader.hand_over(script, unit, bad):
        return
    if caller.f_globals.get("__name__") != "__main__":
        flags.warn(prog, "%s was imported, not run, so its defs.main(...) does nothing; to build on another agent.py, "
                         "use base = defs.load(\"its folder\")" % script)
        return
    if bad:
        flags.die(prog, "SpecBad", "%s (fix the declaration in %s)" % (bad, os.path.basename(script)))
    spec_unit.main(unit, script, "agent.py", HELP)
