"""agent_spec - 給人寫 agent 定義的輔助：在一支 agent.py 裡宣告說明、system、工具、腦設定、狀態機、hook、其他檔，就編出一份掛得上去的定義夾；不宣告狀態機時只填一份現成定義夾的內容檔（eca 版）。

使用者 11-18：「讓我不必在那邊mkdir半天」；11-19 定調：「agent.py產出東西後，產出後的東西就跟他沒關係了。好比C語言和.o之間的關係。」
所以再編譯＝直接蓋：不記指紋、不寫記號、沒有 --force／--status；產出後的 json 誰都能照常改，下次編譯被蓋回去（設計稿 thinking/2026-11/19/aos-compile-庚/ 03～06、10）。
用語照編譯器（使用者 11-19「要，可以參考那些程式語言的類似的功能的名字」，線 aos-defs-rename2-1119，aos-pylib-1119/07 末節）：
agent.py→那一夾 json 叫「編譯」（compile）；defs.compile 算出、不寫，defs.write 寫進夾；指令 --compile 編譯＋寫、--dry-run 只印不寫。
寫法與分層照同夾的 tool_spec（宣告寫錯先記著、編譯前報一行 SpecBad；每份檔暫存檔＋改名）。找法同 tool_spec：骨架 templates/agent-python/agent.py 的開頭幾行。
寫 agent.py 的人拿到這個模組的名字叫 defs：from aos.py.agent import defs（使用者 11-19「就 aos.py.agent.defs 吧」，線 aos-defs-rename-1119；檔不搬、模組名不改），下面的 defs.xxx 都是它。
各份檔怎麼算、怎麼驗在 aos/agent_spec_parts.py（第三刀拆出去）；這裡是宣告用的小函式、compile、write、main。

宣告用的小函式（寫錯不在當下丟，記成 bad，compile()／main 再報 SpecBad）：
  std                 隨 aos 發的庫（aos/agent_spec_lib.py；命名空間第一刀 aos-ns-cut1-1119）：
    std.pack(名, prefix=, rename=, exclude=, link=)  讀 $AOS_HOME/lib/packs/名.json，展開成一支支工具；靜態連結＝複製進 tools.json（不寫 $override），
                      動態連結（link="dynamic" 或整支 --dynamic）＝tools.json 的 $override 指這個包、執行時才讀（工具包連結選項，線 aos-defs-rename2-1119）
    std.tool("base/read", name=None, **其他)  一支工具 $AOS_HOME/lib/tools/base/read，名字預設＝夾名
    std.fsm()＝借 agent-fsm 範本的四格；std.hooks(範本="agent-fsm")＝那個範本 hooks.json 的那組 hook（編譯時讀、抄進來）
  lib(庫名, 根)        別的庫：my = defs.lib("my", defs.env("AOS_WS", "/lib/my"))；my.pack／my.tool 同上，工具名自動帶「庫名_」
  tool(名, 路徑, **其他) 單一個工具＝tools.json 的 tools[名]＝{"path": 路徑, **其他}；路徑也可給 my.tool(...)（只拿它的路徑）；同名蓋掉包裡那支
  no(名)              從展開的包裡拿掉那支（tools.json 裡就沒有那格）
  （包展開後兩支同名、內容又不同＝SpecBad，不再悄悄蓋；tools_json 在 agent_spec_parts）
  home(路徑)／env(變數, 路徑)  指示詞 {"$env": …, "$path": …}，原樣吐、不展開
  state(名, argv, next, timeout_ms=None)、fsm(起點, [state…])
  by_hand(檔名)        這份檔自己手寫：interfaces.json 指到它、不編、不蓋（SYSTEM／TOOLS／LLM／FSM／HOOKS 都可用）
  load(路徑)           衍生（繼承第一刀 aos-inherit-cut1-1119，本體 aos/agent_spec_load.py）：base = defs.load("../reviewer") 跑那支 agent.py，
                       它的 defs.main 只交出九個欄位；TOOLS 寫 [base.TOOLS, defs.no(...), ...]、HOOKS 寫 [base.HOOKS, {名: {**base.HOOKS[名], 鍵: 值}}]、
                       FSM 寫 defs.fsm(base.FSM, [defs.state(名, 只給要換的)], drop=[...])；只在編譯時算，編出的 json 整份、不記上一層（N-70）
兩個可單獨叫的函式（REPL 裡 defs.compile(...) 再 defs.write(夾, 結果)＝指令 --compile）：
  compile(description, system, tools, llm, fsm=None, meta=None, interfaces=None, hooks=None, files=None, folder=None, link="static", warn=None)
      → {檔名: 內容}（驗完才回；宣告錯丟 SpecBad、夾不對丟 DefBad）。fsm=None＝不宣告狀態機：照 folder 裡現有的
        interfaces.json 找檔名，只出內容檔（system、tools、llm、hooks）、FILES、_metainfo.json、README.md，骨架不碰（第三刀）
  write(folder, files) → 寫了哪些（字串串列）；宣告到的檔直接蓋，_metainfo.json 只設自己的鍵，README.md 不在才寫，其他檔不碰
main(...)：agent.py 最後一行；--compile [資料夾]、--dry-run、--help，都沒有＝ArgumentsBad 帶用法（P-44）；前兩個可加 --static（預設）／--dynamic。
之後的除錯開關（aos-gdb-1119、庚第四刀）要加就加在 compile 的關鍵字參數，不動現有參數的意思。
compile 蓋掉了模組裡內建的 compile()：這個模組自己不用內建那支，要用寫 builtins.compile。"""
import json, os, sys

from aos import flags
from aos import agent_spec_parts as parts
from aos.agent_spec_parts import SpecBad, DefBad, WHAT, LLM_KEYS, OWN_FILES, SKELETON, RUNTIME_FILES  # noqa: F401（對外的名字）
from aos.agent_spec_lib import std, lib  # noqa: F401（對外的名字：defs.std、defs.lib）
from aos import agent_spec_load as loader
from aos.agent_spec_load import load  # noqa: F401（對外的名字：defs.load）

HOOK_FIRE = {"$env": "AOS_HOME", "$path": "/lib/tools/agent/hook_fire/_entry"}   # loop.json 的 on_start／on_stop（照 agent-fsm 範本）
RENAME_LAST = {"loop.json": 1, "body.json": 2, "interfaces.json": 3, "_entry": 4, "_metainfo.json": 5}   # 改名時被指的檔先換、索引檔最後（其他＝0）
HELP = """\
usage: python3 agent.py --compile [--static | --dynamic] [FOLDER] | --dry-run [--static | --dynamic] | --help
Compile agent.py into an aos agent definition (a folder of JSON files), like a C compiler
turning a .c file into a .o file.
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
                      up at the agent's next start, without recompiling. A pack whose tools get
                      a prefix or rename= (a library other than std, by default), and the TOOLS
                      of defs.load, are still linked statically, with a warning.
                      One pack: std.pack("look", link="dynamic") / link="static".
With FSM declared, agent.py writes the whole definition (skeleton included). Without FSM
(defs.main(DESCRIPTION, SYSTEM, TOOLS, LLM)), it fills only the content files (system, tools, llm,
hooks) of a definition that already has its skeleton, under the names its interfaces.json gives.
Packs (std.pack, or .pack of a library from defs.lib) are read when agent.py runs (also when they are
linked dynamically, to check the tool names), so AOS_HOME, and any variable a library root uses, must be set.
To build on another agent.py: base = defs.load("../other") runs it (its defs.main only hands over its
fields) and you write [base.TOOLS, defs.no("x")], [base.HOOKS, {...}], defs.fsm(base.FSM, [...]); it is
worked out now, so the files written are whole and do not name the other one (README: "Build on").
Then mount it: aos-agent ctl add FOLDER.
On a wrong declaration: one line "NAME: error: SpecBad ..." on stderr, exit 1, nothing written.
"""


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


def no(name):
    """把展開的包裡的某個工具拿掉（腦看到的名字；tools.json 裡就沒有那格）。"""
    if not isinstance(name, str) or not parts.TOOL_RE.match(name):
        return _bad("defs.no(%r): the tool name must be 1-64 letters, digits, _ or -" % (name,))
    return {"kind": "no", "name": name}


def by_hand(filename):
    """這份檔自己手寫：interfaces.json 指到它，agent.py 不編、不蓋。"""
    if (not isinstance(filename, str) or not filename or os.path.isabs(filename) or ".." in filename.split("/")
            or os.path.normpath(filename) == "."):
        return _bad("by_hand(%r): give a file name relative to the definition folder, like \"system.txt\"" % (filename,))
    return {"kind": "by_hand", "file": os.path.normpath(filename)}


def _state_name_bad(name):
    return not isinstance(name, str) or not name or name != name.strip() or "\n" in name


_LEFT_OUT = object()


def state(name, argv=_LEFT_OUT, next=_LEFT_OUT, timeout_ms=None):
    """狀態機的一格：跑 argv（字串或 defs.home(...) 的串列），退出碼 → 下一格（{0: "think", 10: "idle"}；"*"＝其他碼；字串＝只有 0）。
    argv、next 單獨用時要給齊；在 defs.fsm(base.FSM, [...]) 裡換底的同名格時可以只給要換的（沒給的沿用底那格；繼承第一刀）。"""
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
    """狀態機：起點＋各格（defs.state(...) 的串列）。下一格、起點都要在表上（aos-fsm 開跑時查的同一套）。
    第一個參數給底的狀態機（defs.load(...).FSM、std.fsm()）＝換格（繼承第一刀）：drop 的格拿掉，同名格只換有給的欄位，新名的格加上（要給齊），整張重驗。"""
    if parts.kind(start) == "bad":
        return start
    if parts.kind(start) == "fsm":
        return _refit(start, states, drop)
    if start is None:
        return _bad("defs.fsm: the start is None: give the name of the start state, or the FSM of a loaded agent.py "
                    "(an agent.py without FSM, like an eca body, has FSM None: there is no state machine to build on)")
    if drop:
        return _bad("defs.fsm: drop= only works on a state machine to build on, like defs.fsm(base.FSM, [...], drop=[\"act\"])")
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
            return _bad("state %s needs both argv and next (only defs.fsm(base.FSM, [...]) takes a state with some left out)" % s["name"])
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


def _names(decl, fsm, hooks, interfaces, folder):
    """回四樣：{種類: 這次用的檔名}、{種類: by_hand 的檔名}、FILES 不能用的檔名、llm_keys（有 FSM＝None，之後照編譯出的 interfaces.json）。"""
    hand = {w: v["file"] for w, v in decl.items() if parts.kind(v) == "by_hand"}
    if fsm is None:
        if interfaces is not None:
            raise SpecBad("INTERFACES needs FSM: without FSM, interfaces.json belongs to the skeleton you copied; change it by hand")
        if folder is None:
            raise SpecBad("FSM is not declared, so agent.py fills the content files of an existing definition: give its folder")
        have, keys = parts.existing_names(folder)
        files = {}
        for what in parts.CONTENT:
            if what == "hooks" and hooks is None:
                continue
            if what not in have:
                raise DefBad("%s/interfaces.json declares no %s file, so %s has nowhere to go: add \"%s\" to its aos-agent, "
                             "or declare FSM" % (folder, what, what.upper(), what))
            if what in hand and hand[what] != have[what]:
                raise SpecBad("by_hand(%r) for %s, but interfaces.json names %r for it; use that name"
                              % (hand[what], what.upper(), have[what]))
            files[what] = have[what]
        return files, hand, set(have.values()) | set(files.values()), keys
    files = {w: f for w, f in OWN_FILES.items() if w != "hooks" or hooks is not None}
    files.update(hand)
    made = set(SKELETON) | set(RUNTIME_FILES) | {"_metainfo.json", "README.md", "agent.py"} | {files[w] for w in files if w not in hand}
    for what, name in hand.items():
        if name in made or list(hand.values()).count(name) > 1:
            raise SpecBad("by_hand(%r) for %s clashes with a file agent.py writes, a file the running agent writes, or another by_hand; pick another name" % (name, what.upper()))
    return files, hand, set(files.values()), None


def compile(description, system, tools, llm, fsm=None, meta=None, interfaces=None, hooks=None, files=None, folder=None,
            link="static", warn=None):
    """宣告 → {檔名: 內容}（json 是 dict、文字是字串；_metainfo.json 只有 agent.py 設的鍵、README.md 是種子）。全部驗完才回，錯丟 SpecBad／DefBad。
    fsm=None＝不宣告狀態機：要給 folder（照它現有的 interfaces.json 找檔名），骨架不出。
    link＝工具包怎麼連結："static"（預設）複製進 tools.json；"dynamic" 寫 $override 指包、執行時才讀；包上明寫的 link= 優先。
    warn＝收提醒的函式（整支 dynamic 時某個包只能靜態之類）；不給＝印一行 "defs.compile: warning: …" 到 stderr。"""
    if link not in ("static", "dynamic"):
        raise SpecBad("link must be \"static\" or \"dynamic\", got %r" % (link,))
    if warn is None:
        warn = lambda msg: flags.warn("defs.compile", msg)  # noqa: E731
    if not isinstance(description, str) or not description.strip():
        raise SpecBad("DESCRIPTION must be a non-empty string: one sentence saying what the agent does")
    description = description.strip()
    hooks = parts.no_hooks(hooks)
    decl = {"system": system, "tools": tools, "llm": llm, "fsm": fsm, "hooks": hooks}
    for value in decl.values():
        parts.raise_bad(value)
    if fsm is not None and parts.pick(fsm, "FSM must come from defs.fsm(...), std.fsm() or defs.by_hand(\"fsm.json\") (or leave it out: no FSM)",
                                      lambda v: parts.kind(v) == "fsm"):
        fsm_out = None
    else:
        fsm_out = fsm
    names, hand, taken, keys = _names(decl, fsm, hooks, interfaces, folder)
    if parts.pick(system, "SYSTEM must be a string (the system text) or defs.by_hand(\"system.txt\")", lambda v: isinstance(v, str)):
        system = None
    face = None
    if fsm is not None:
        face = parts.interfaces_json(interfaces, names, description)
        keys = face.get("aos-agent", {}).get("llm_keys", LLM_KEYS)
        if not isinstance(keys, list) or not all(isinstance(k, str) for k in keys):
            raise SpecBad("INTERFACES aos-agent llm_keys must be a list of strings")
    tools_out = None if parts.pick(tools, "TOOLS must be a list of std.pack(...), std.tool(...), defs.tool(...), defs.no(...) "
                                          "(or a library's .pack / .tool, or the TOOLS of defs.load(...): [base.TOOLS, ...]), "
                                          "or defs.by_hand(\"tools.json\")",
                                   lambda v: isinstance(v, (list, tuple))) else parts.tools_json(tools, link, warn)
    llm_out = None if parts.pick(llm, "LLM must be a dict like {\"model\": \"luna\"} ({} = the kernel's default), or defs.by_hand(\"llm.json\")",
                                 lambda v: isinstance(v, dict)) else parts.llm_json(llm, keys)
    hooks_out = None if hooks is None or "hooks" in hand else parts.hooks_json(hooks)
    extra = parts.extra_files(files, taken | set(hand.values())) if files is not None else {}
    if meta is not None and not isinstance(meta, dict):
        raise SpecBad("META must be a dict like {\"cost\": {\"time_ms\": 60000}, \"resource\": [\"llm\"]}")
    if meta and not all(isinstance(k, str) for k in meta):
        raise SpecBad("META keys must be strings, like {\"cost\": {\"time_ms\": 60000}}")
    for k in ("summary", "lineage"):
        if meta and k in meta:
            raise SpecBad("META must not set %s (%s)" % (k, "it comes from DESCRIPTION" if k == "summary" else "agent_def new writes it"))
    out = {}
    if fsm is not None:
        loop = {"description": WHAT["loop.json"] % names["fsm"], "exec": names["fsm"], "interval_ms": 300,
                "ctl": "ctl.json", "state": "state.json", "state_flux": "state_flux.json"}
        if hooks is not None:
            loop["description"] += WHAT["loop_hooks"]
            loop["on_start"] = {"argv": [HOOK_FIRE, "after_start", {"$env": "AOS_CD"}]}
            loop["on_stop"] = {"argv": [HOOK_FIRE, "after_stop", {"$env": "AOS_CD"}]}
        out["_entry"] = {"description": WHAT["_entry"], "argv": ["aos-agent", "ctl", "add", {"$env": "AOS_CD"}],
                         "cwd": {"$env": "AOS_WS"}}
        out["body.json"] = {"description": WHAT["body.json"], "argv": ["aos-loop", "loop.json"]}
        out["loop.json"] = loop
        if fsm_out is not None:
            out["fsm.json"] = {"description": WHAT["fsm.json"], "_entry": ["aos-fsm", {"$env": "AOS_CF"}],
                               "start": fsm_out["start"], "states": fsm_out["states"]}
        out["interfaces.json"] = face
    for what, value in (("tools", tools_out), ("llm", llm_out), ("system", system), ("hooks", hooks_out)):
        if value is not None:
            out[names[what]] = value
    out.update(extra)
    out["_metainfo.json"] = dict({"summary": description}, **(meta or {}))
    out["README.md"] = description + "\n"
    try:                                    # 跟宣告的物件脫鉤（之後改宣告不影響回傳值）；也確認都能寫成合法 JSON（NaN 不算）
        return json.loads(json.dumps(out, allow_nan=False))
    except (TypeError, ValueError) as e:
        raise SpecBad("a declared value cannot be written as JSON (%s); use strings, numbers, lists and dicts" % e)


def _text(value):
    return value if isinstance(value, str) else json.dumps(value, ensure_ascii=False, indent=2) + "\n"


def write(folder, files):
    """files（compile() 的回傳）寫進 folder；回給人看的字串串列。先讀好 _metainfo.json、全部寫成暫存檔，最後連著改名；
    寫暫存檔時失敗＝刪掉暫存檔、夾裡不變；改名時才失敗（極少）＝前面幾份已換上、每份各自完整，重跑一次就好（設計稿 07）。OSError 照丟（main 報 WriteFailed）；_metainfo.json 不是 JSON 物件＝DefBad。"""
    if not os.path.isdir(folder):
        raise OSError("%s is not a folder" % folder)
    plan = []
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
        plan.append((name, path, _text(value)))
    tmps = []
    try:
        for name, path, text in plan:
            tmp = os.path.join(folder, ".%s.tmp-%d" % (name, os.getpid()))
            tmps.append(tmp)
            with open(tmp, "w", encoding="utf-8") as f:
                f.write(text)
            if os.path.exists(path):
                os.chmod(tmp, os.stat(path).st_mode & 0o7777)
        for (name, path, _), tmp in sorted(zip(plan, tmps), key=lambda p: RENAME_LAST.get(p[0][0], 0)):
            os.replace(tmp, path)
    finally:
        for tmp in tmps:
            try:
                os.unlink(tmp)
            except OSError:
                pass
    done = ["wrote %s" % os.path.join(folder, name) for name, _, _ in plan]
    if "README.md" in files and len(plan) < len(files):
        done.append("kept %s (it is already there)" % os.path.join(folder, "README.md"))
    return done


def main(description, system, tools, llm, fsm=None, meta=None, interfaces=None, hooks=None, files=None):
    """agent.py 的最後一行：defs.main(DESCRIPTION, SYSTEM, TOOLS, LLM, FSM)；不宣告狀態機＝defs.main(DESCRIPTION, SYSTEM, TOOLS, LLM)。
    被 defs.load 載入時：不讀 argv、不寫檔、不退出，只把九個欄位交給 defs.load。被普通 import（叫它的模組不是 __main__）：印一行 warning、什麼都不做
    （繼承第一刀：以前會照 argv 寫進底那夾、退 0，衍生那支根本沒跑；aos-inherit-1119/02 結論 5）。"""
    caller = sys._getframe(1)
    script = os.path.realpath(caller.f_code.co_filename)
    base = os.path.basename(script)
    prog = os.path.basename(os.path.dirname(script)) if base == "agent.py" else os.path.splitext(base)[0]
    if loader.hand_over(script, (description, system, tools, llm, fsm, meta, interfaces, hooks, files)):
        return
    if caller.f_globals.get("__name__") != "__main__":
        flags.warn(prog, "%s was imported, not run, so its defs.main(...) does nothing; to build on another agent.py, "
                         "use base = defs.load(\"its folder\")" % script)
        return
    argv = sys.argv[1:]
    usage = "usage: python3 %s --compile [--static | --dynamic] [FOLDER] | --dry-run [--static | --dynamic] | --help" % base
    if argv[:1] in (["--help"], ["-h"]):
        sys.stdout.write(HELP.replace("agent.py", base))
        sys.exit(0)
    if not argv:
        flags.die(prog, "ArgumentsBad", "give --compile or --dry-run (%s)" % usage)
    if argv[0] not in ("--compile", "--dry-run"):
        flags.die(prog, "FlagUnknown", "%s (%s)" % (argv[0], usage))
    links = [a for a in argv[1:] if a in ("--static", "--dynamic")]
    rest = [a for a in argv[1:] if a not in ("--static", "--dynamic")]
    if len(links) > 1:
        flags.die(prog, "ArgumentsBad", "give one of --static and --dynamic, not %s (%s)" % (" ".join(links), usage))
    unknown = [a for a in rest if a.startswith("-")]
    if unknown:
        flags.die(prog, "FlagUnknown", "%s (%s)" % (unknown[0], usage))
    if len(rest) > (1 if argv[0] == "--compile" else 0):
        flags.die(prog, "ArgumentsBad", "too many arguments: %s (%s)" % (" ".join(argv), usage))
    folder = rest[0] if rest else os.path.dirname(script)
    link = links[0][2:] if links else "static"            # 預設靜態（使用者 11-19 選項框「預設靜態 (Recommended)」）
    try:
        out = compile(description, system, tools, llm, fsm, meta, interfaces, hooks, files, folder,
                      link=link, warn=lambda msg: flags.warn(prog, msg))
    except SpecBad as e:
        flags.die(prog, "SpecBad", "%s (fix the declaration in %s)" % (e, base))
    except DefBad as e:
        flags.die(prog, "DefBad", str(e))
    if argv[0] == "--dry-run":
        print(json.dumps(out, ensure_ascii=False, indent=2))
        sys.exit(0)
    try:
        lines = write(folder, out)
    except DefBad as e:
        flags.die(prog, "DefBad", str(e))
    except OSError as e:
        flags.die(prog, "WriteFailed", "cannot write the definition into %s: %s" % (folder, e))
    for line in lines:
        print(line)
    print("agents that use this definition see the change from their next brain call (state machine and loop changes: from their next tick or restart)")
    sys.exit(0)
