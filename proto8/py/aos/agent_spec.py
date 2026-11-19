"""agent_spec - 給人寫 agent 定義的輔助：在一支 agent.py 裡宣告說明、system、工具、腦設定、狀態機，就生出一份掛得上去的定義夾（_entry、body.json、loop.json、fsm.json、interfaces.json、tools.json、llm.json、system.txt、_metainfo.json 的自己的鍵、README.md 種子）。

使用者 11-18：「讓我不必在那邊mkdir半天」；11-19 定調：「agent.py產出東西後，產出後的東西就跟他沒關係了。好比C語言和.o之間的關係。」
所以重生＝直接蓋：不記指紋、不寫記號、沒有 --force／--status；產出後的 json 誰都能照常改，下次重生被蓋回去（設計稿 thinking/2026-11/19/aos-compile-庚/ 03～06、10）。
純標準庫；寫法與分層照同夾的 tool_spec（宣告寫錯先記著、生成前報一行 SpecBad；每份檔暫存檔＋改名）。找法同 tool_spec：骨架 templates/agent-python/agent.py 的開頭幾行。

宣告用的小函式（寫錯不在當下丟，記成 bad，defs()／main 再報 SpecBad）：
  pack(名)            疊一個工具包＝tools.json 的 $override 加 {"$env": "AOS_HOME", "$path": "/lib/packs/名.json"}
  tool(名, 路徑, **其他) 單一個工具＝tools.json 的 tools[名]＝{"path": 路徑, **其他}
  no(名)              從包裡拿掉＝tools[名]＝null
  home(路徑)／env(變數, 路徑)  指示詞 {"$env": …, "$path": …}，原樣吐、不展開
  state(名, argv, next, timeout_ms=None)、fsm(起點, [state…])、stock_fsm()＝借 agent-fsm 範本的四格
  by_hand(檔名)        這份檔自己手寫：interfaces.json 指到它、不生、不蓋（SYSTEM／TOOLS／LLM／FSM 都可用）
兩個可單獨叫的函式：
  defs(description, system, tools, llm, fsm, meta=None, interfaces=None) → {檔名: 內容}（驗完才回；錯丟 SpecBad）
  write_defs(folder, files) → 寫了哪些（字串串列）；宣告到的檔直接蓋，_metainfo.json 只設自己的鍵，README.md 不在才寫，其他檔不碰
main(...)：agent.py 最後一行；--write-defs [資料夾]、--defs、--help，都沒有＝ArgumentsBad 帶用法（P-44）。"""
import json, os, re, sys

from aos import flags

LLM_KEYS = ["model", "temperature", "top_p", "max_tokens", "seed", "presence_penalty", "frequency_penalty", "stop"]
STOCK_CELLS = (("idle", "idle", {0: "think", 10: "idle"}, None),       # templates/agent-fsm/fsm.json 那四格，格的程式借範本那份
               ("think", "brain", {0: "wait", 10: "idle"}, None),
               ("wait", "wait", {0: "act", 10: "wait", 11: "think"}, None),
               ("act", "act", {0: "think", 10: "idle"}, 0))
PACK_RE = re.compile(r"[a-z0-9][a-z0-9_-]*\Z")
TOOL_RE = re.compile(r"[A-Za-z0-9_-]{1,64}\Z")                        # aos-tools 的 NAME_RE
ENV_KEY_RE = re.compile(r"[A-Za-z_][A-Za-z0-9_]*\Z")                  # aos-tools 的 ENV_KEY_RE
RUNTIME_FILES = ("ctl.json", "state.json", "state_flux.json", "history.jsonl")   # loop／腦跑起來寫的檔名，by_hand 不能用
OWN_FILES = {"tools": "tools.json", "llm": "llm.json", "system": "system.txt", "fsm": "fsm.json"}
SKELETON = ("_entry", "body.json", "loop.json", "interfaces.json")
WHAT = {"_entry": "Register this agent with the current daemon (aos-agent ctl add).",
        "body.json": "Run this agent's loop: aos-loop with loop.json.",
        "loop.json": "Run the state machine in %s every tick and expose public control, state and state flux files.",
        "fsm.json": "The state machine of this agent: which program each state runs, and the next state by exit code.",
        "tools.json": "Tools this agent can call.",
        "llm.json": "Brain settings of this agent: model names a brain pack of the llm kernel (none = the kernel's default)."}
HELP = """\
usage: python3 agent.py --write-defs [FOLDER] | --defs | --help
Make an aos agent definition from the declarations in agent.py.
  --write-defs [FOLDER]  write the definition files into FOLDER (default: the folder of agent.py).
                         Files that agent.py declares are overwritten as a whole, every time;
                         _metainfo.json keeps keys agent.py does not set; README.md is written only
                         when it is missing; every other file is left alone.
  --defs                 print everything --write-defs would write, as one JSON object
                         {"file name": content}, and write nothing.
Then mount it: aos-agent ctl add FOLDER.
On a wrong declaration: one line "NAME: error: SpecBad ..." on stderr, exit 1, nothing written.
"""


class SpecBad(Exception):
    """宣告本身寫錯；訊息寫成怎麼改。"""


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
    """某個環境變數底下的路徑：env("AOS_WS", "/tools/x") → {"$env": "AOS_WS", "$path": "/tools/x"}；生成時不展開。"""
    return {"$env": var, "$path": path}


def pack(name):
    """疊一個工具包（$AOS_HOME/lib/packs/<name>.json）。"""
    if not isinstance(name, str) or not PACK_RE.match(name):
        return _bad("pack name %r must be a pack file name without .json, like \"look\"" % (name,))
    return {"kind": "pack", "name": name}


def tool(name, path, **more):
    """單一個工具；more（env、env_file…）原樣寫進那一格；aos-tools 合併時會擋的（env、env_file、cache）這裡先擋。"""
    if not isinstance(name, str) or not TOOL_RE.match(name):
        return _bad("tool name %r must be 1-64 letters, digits, _ or -" % (name,))
    if not _is_path(path):
        return _bad("tool %s must have a path: a string, or ag.home(\"/lib/tools/...\") / ag.env(VAR, PATH)" % name)
    e = more.get("env", {})
    if not isinstance(e, dict) or not all(isinstance(k, str) and ENV_KEY_RE.match(k) and isinstance(v, str) for k, v in e.items()):
        return _bad("tool %s: env must be a dict of NAME -> string, like {\"LANG\": \"C\"}" % name)
    if "env_file" in more and not _is_path(more["env_file"]):
        return _bad("tool %s: env_file must be a non-empty path string or ag.home(...) / ag.env(...)" % name)
    if "cache" in more and more["cache"] is not False:
        return _bad("tool %s: cache can only be False" % name)
    return {"kind": "tool", "name": name, "entry": dict({"path": path}, **more)}


def no(name):
    """把包裡的某個工具拿掉（tools.json 的 tools[name] = null）。"""
    if not isinstance(name, str) or not TOOL_RE.match(name):
        return _bad("ag.no(%r): the tool name must be 1-64 letters, digits, _ or -" % (name,))
    return {"kind": "no", "name": name}


def by_hand(filename):
    """這份檔自己手寫：interfaces.json 指到它，agent.py 不生、不蓋。"""
    if not isinstance(filename, str) or not filename or os.path.isabs(filename) or ".." in filename.split("/")             or os.path.normpath(filename) == ".":
        return _bad("by_hand(%r): give a file name relative to the definition folder, like \"system.txt\"" % (filename,))
    return {"kind": "by_hand", "file": os.path.normpath(filename)}


def _state_name_bad(name):
    return not isinstance(name, str) or not name or name != name.strip() or "\n" in name


def state(name, argv, next, timeout_ms=None):
    """狀態機的一格：跑 argv（字串或 ag.home(...) 的串列），退出碼 → 下一格（{0: "think", 10: "idle"}；"*"＝其他碼；字串＝只有 0）。"""
    if _state_name_bad(name):
        return _bad("state name %r must be a non-empty string without leading or trailing spaces or newlines" % (name,))
    if not isinstance(argv, (list, tuple)) or not argv or not all(_is_path(a) for a in argv):
        return _bad("state %s: argv must be a non-empty list of strings or ag.home(...) paths, like [\"python3\", \"idle.py\"]" % name)
    if isinstance(next, str):
        nxt = next
    elif isinstance(next, dict) and next:
        nxt = {}
        for code, target in next.items():
            if code == "*" or (isinstance(code, int) and not isinstance(code, bool) and 0 <= code <= 255):
                nxt[str(code)] = target
            else:
                return _bad("state %s: exit code %r in next must be a whole number 0-255 or \"*\"" % (name, code))
        if "0" not in nxt and "*" not in nxt:
            return _bad("state %s: next must have exit code 0 or \"*\" (exit code 0 must always lead somewhere)" % name)
    else:
        return _bad("state %s: next must be a state name, or a dict {exit code: state name} like {0: \"think\"}" % name)
    exec_ = {"argv": list(argv)}
    if timeout_ms is not None:
        if not isinstance(timeout_ms, int) or isinstance(timeout_ms, bool) or timeout_ms < 0:
            return _bad("state %s: timeout_ms must be a whole number of milliseconds >= 0 (0 = no limit)" % name)
        exec_["timeout_ms"] = timeout_ms
    return {"kind": "state", "name": name, "cell": {"exec": exec_, "next": nxt}}


def fsm(start, states):
    """狀態機：起點＋各格（ag.state(...) 的串列）。下一格、起點都要在表上（aos-fsm 開跑時查的同一套）。"""
    if not isinstance(states, (list, tuple)) or not states:
        return _bad("fsm needs a non-empty list of ag.state(...)")
    table = {}
    for s in states:
        if isinstance(s, dict) and s.get("kind") == "bad":
            return s
        if not isinstance(s, dict) or s.get("kind") != "state":
            return _bad("each item of fsm states must come from ag.state(...), got %r" % (s,))
        if s["name"] in table:
            return _bad("state %s is declared twice" % s["name"])
        table[s["name"]] = s["cell"]
    if not isinstance(start, str) or start not in table:
        return _bad("fsm start %r is not one of the states (%s)" % (start, ", ".join(table)))
    for name, cell in table.items():
        targets = [cell["next"]] if isinstance(cell["next"], str) else list(cell["next"].values())
        for t in targets:
            if not isinstance(t, str) or t not in table:
                return _bad("state %s: next state %r is not one of the states (%s)" % (name, t, ", ".join(table)))
    return {"kind": "fsm", "start": start, "states": table}


def stock_fsm():
    """agent-fsm 範本那四格（idle、think、wait、act），格的程式借 $AOS_HOME/templates/agent-fsm/ 那份（不抄）。"""
    return fsm("idle", [state(n, ["python3", home("/templates/agent-fsm/%s.py" % prog)], nxt, timeout_ms=t)
                        for n, prog, nxt, t in STOCK_CELLS])


def _pick(value, what, kinds):
    if isinstance(value, dict) and value.get("kind") == "bad":
        raise SpecBad(value["bad"])
    if isinstance(value, dict) and value.get("kind") == "by_hand":
        return value
    if not kinds(value):
        raise SpecBad(what)
    return None


def _tools_json(tools):
    if _pick(tools, "TOOLS must be a list of ag.pack(...), ag.tool(...), ag.no(...), or ag.by_hand(\"tools.json\")",
             lambda v: isinstance(v, (list, tuple))):
        return None
    packs, entries = [], {}
    for t in tools:
        if isinstance(t, dict) and t.get("kind") == "bad":
            raise SpecBad(t["bad"])
        if not isinstance(t, dict) or t.get("kind") not in ("pack", "tool", "no"):
            raise SpecBad("each item of TOOLS must come from ag.pack(...), ag.tool(...) or ag.no(...), got %r" % (t,))
        if t["kind"] == "pack":
            if t["name"] in packs:
                raise SpecBad("pack %s is listed twice" % t["name"])
            home_dir = os.environ.get("AOS_HOME")
            if home_dir and not os.path.isfile(os.path.join(home_dir, "lib", "packs", t["name"] + ".json")):
                have = sorted(f[:-5] for f in os.listdir(os.path.join(home_dir, "lib", "packs")) if f.endswith(".json")) \
                    if os.path.isdir(os.path.join(home_dir, "lib", "packs")) else []
                raise SpecBad("there is no pack %s in $AOS_HOME/lib/packs (packs: %s)" % (t["name"], ", ".join(have) or "none"))
            packs.append(t["name"])
            continue
        if t["name"] in entries:
            raise SpecBad("tool %s is listed twice" % t["name"])
        entries[t["name"]] = t["entry"] if t["kind"] == "tool" else None
    if None in entries.values() and not packs:
        raise SpecBad("ag.no(...) takes a tool out of a pack, but TOOLS has no ag.pack(...): add the pack or drop the ag.no")
    out = {"description": WHAT["tools.json"]}
    if packs:
        out["$override"] = [home("/lib/packs/%s.json" % p) for p in packs]
    if entries or not packs:
        out["tools"] = entries
    return out


def _llm_json(llm, keys):
    if _pick(llm, "LLM must be a dict like {\"model\": \"luna\"} ({} = the kernel's default), or ag.by_hand(\"llm.json\")",
             lambda v: isinstance(v, dict)):
        return None
    for k in llm:
        if k != "description" and k not in keys:
            raise SpecBad("LLM key %r is not one of llm_keys (%s)" % (k, ", ".join(keys)))
    if "model" in llm and (not isinstance(llm["model"], str) or not llm["model"]):
        raise SpecBad("LLM model must be a non-empty string: the name of a brain pack of the llm kernel, like \"luna\"")
    return dict({"description": WHAT["llm.json"]}, **llm)


def _interfaces(over, files, description):
    agent = {"entry": "body.json", "tools": files["tools"], "llm": files["llm"], "llm_keys": list(LLM_KEYS),
             "history": "history.jsonl", "system": files["system"]}
    out = {"description": description, "aos-agent": agent}
    if over is None:
        return out
    if not isinstance(over, dict):
        raise SpecBad("INTERFACES must be a dict laid over the default interfaces.json, like {\"aos-observed\": {\"file\": \"observed.jsonl\"}}")
    for key, value in over.items():
        if key == "aos-agent" and value is None:
            raise SpecBad("INTERFACES cannot remove aos-agent: without it the folder is not an agent")
        if key == "aos-agent":
            if not isinstance(value, dict):
                raise SpecBad("INTERFACES aos-agent must be a dict (a value of None removes a default key)")
            for k, v in value.items():
                if k in ("entry", "tools", "llm", "system"):
                    raise SpecBad("INTERFACES aos-agent %s is set by agent.py; to point it at a file you write yourself use ag.by_hand(...)" % k)
                if v is None:
                    agent.pop(k, None)
                else:
                    agent[k] = v
        elif value is None:
            out.pop(key, None)
        else:
            out[key] = value
    return out


def defs(description, system, tools, llm, fsm, meta=None, interfaces=None):
    """宣告 → {檔名: 內容}（json 是 dict、文字是字串；_metainfo.json 只有 agent.py 設的鍵、README.md 是種子）。全部驗完才回，錯丟 SpecBad。"""
    if not isinstance(description, str) or not description.strip():
        raise SpecBad("DESCRIPTION must be a non-empty string: one sentence saying what the agent does")
    description = description.strip()
    files = dict(OWN_FILES)
    hand = {}
    for what, value in (("system", system), ("tools", tools), ("llm", llm), ("fsm", fsm)):
        if isinstance(value, dict) and value.get("kind") == "by_hand":
            files[what] = hand[what] = value["file"]
    names = set(SKELETON) | set(RUNTIME_FILES) | {"_metainfo.json", "README.md"} | {OWN_FILES[w] for w in OWN_FILES if w not in hand}
    for what, name in hand.items():
        if name in names or list(hand.values()).count(name) > 1:
            raise SpecBad("by_hand(%r) for %s clashes with a file agent.py writes, a file the running agent writes, or another by_hand; pick another name" % (name, what.upper()))
    if _pick(system, "SYSTEM must be a string (the system text) or ag.by_hand(\"system.txt\")", lambda v: isinstance(v, str)):
        system = None
    if _pick(fsm, "FSM must come from ag.fsm(...), ag.stock_fsm() or ag.by_hand(\"fsm.json\")",
             lambda v: isinstance(v, dict) and v.get("kind") == "fsm"):
        fsm = None
    face = _interfaces(interfaces, files, description)
    keys = face.get("aos-agent", {}).get("llm_keys", LLM_KEYS)
    if not isinstance(keys, list) or not all(isinstance(k, str) for k in keys):
        raise SpecBad("INTERFACES aos-agent llm_keys must be a list of strings")
    tools_out, llm_out = _tools_json(tools), _llm_json(llm, keys)
    if meta is not None and not isinstance(meta, dict):
        raise SpecBad("META must be a dict like {\"cost\": {\"time_ms\": 60000}, \"resource\": [\"llm\"]}")
    for k in ("summary", "lineage"):
        if meta and k in meta:
            raise SpecBad("META must not set %s (%s)" % (k, "it comes from DESCRIPTION" if k == "summary" else "agent_def new writes it"))
    out = {"_entry": {"description": WHAT["_entry"], "argv": ["aos-agent", "ctl", "add", {"$env": "AOS_CD"}],
                      "cwd": {"$env": "AOS_WS"}},
           "body.json": {"description": WHAT["body.json"], "argv": ["aos-loop", "loop.json"]},
           "loop.json": {"description": WHAT["loop.json"] % files["fsm"], "exec": files["fsm"], "interval_ms": 300,
                         "ctl": "ctl.json", "state": "state.json", "state_flux": "state_flux.json"}}
    if fsm is not None:
        out["fsm.json"] = {"description": WHAT["fsm.json"], "_entry": ["aos-fsm", {"$env": "AOS_CF"}],
                           "start": fsm["start"], "states": fsm["states"]}
    out["interfaces.json"] = face
    if tools_out is not None:
        out["tools.json"] = tools_out
    if llm_out is not None:
        out["llm.json"] = llm_out
    if system is not None:
        out["system.txt"] = system
    out["_metainfo.json"] = dict({"summary": description}, **(meta or {}))
    out["README.md"] = description + "\n"
    try:                                    # 跟宣告的物件脫鉤（之後改宣告不影響回傳值）；也確認都能寫成合法 JSON（NaN 不算）
        return json.loads(json.dumps(out, allow_nan=False))
    except (TypeError, ValueError) as e:
        raise SpecBad("a declared value cannot be written as JSON (%s); use strings, numbers, lists and dicts" % e)


def _text(value):
    return value if isinstance(value, str) else json.dumps(value, ensure_ascii=False, indent=2) + "\n"


def write_defs(folder, files):
    """files（defs() 的回傳）寫進 folder；回給人看的字串串列。先讀好 _metainfo.json、全部寫成暫存檔，最後連著改名；
    寫暫存檔時失敗＝刪掉暫存檔、夾裡不變；改名時才失敗（極少）＝前面幾份已換上、每份各自完整，重跑一次就好（設計稿 07）。OSError 照丟（main 報 WriteFailed）；_metainfo.json 不是 JSON 物件＝ValueError（main 報 DefBad）。"""
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
            except (OSError, ValueError, UnicodeError) as e:
                raise ValueError("cannot read %s, so its other keys cannot be kept: %s" % (path, e))
            if not isinstance(old, dict):
                raise ValueError("%s is not a JSON object, so its other keys cannot be kept" % path)
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
        for (name, path, _), tmp in zip(plan, tmps):
            os.replace(tmp, path)
    finally:
        for tmp in tmps:
            if os.path.exists(tmp):
                os.unlink(tmp)
    done = ["wrote %s" % os.path.join(folder, name) for name, _, _ in plan]
    if "README.md" in files and len(plan) < len(files):
        done.append("kept %s (it is already there)" % os.path.join(folder, "README.md"))
    return done


def main(description, system, tools, llm, fsm, meta=None, interfaces=None):
    """agent.py 的最後一行：ag.main(DESCRIPTION, SYSTEM, TOOLS, LLM, FSM)。"""
    script = os.path.realpath(sys._getframe(1).f_code.co_filename)
    base = os.path.basename(script)
    prog = os.path.basename(os.path.dirname(script)) if base == "agent.py" else os.path.splitext(base)[0]
    argv = sys.argv[1:]
    usage = "usage: python3 %s --write-defs [FOLDER] | --defs | --help" % base
    if argv[:1] in (["--help"], ["-h"]):
        sys.stdout.write(HELP.replace("agent.py", base))
        sys.exit(0)
    if not argv:
        flags.die(prog, "ArgumentsBad", "give --write-defs or --defs (%s)" % usage)
    if argv[0] not in ("--write-defs", "--defs"):
        flags.die(prog, "FlagUnknown", "%s (%s)" % (argv[0], usage))
    if len(argv) > (2 if argv[0] == "--write-defs" else 1):
        flags.die(prog, "ArgumentsBad", "too many arguments: %s (%s)" % (" ".join(argv), usage))
    try:
        files = defs(description, system, tools, llm, fsm, meta, interfaces)
    except SpecBad as e:
        flags.die(prog, "SpecBad", "%s (fix the declaration in %s)" % (e, base))
    if argv[0] == "--defs":
        print(json.dumps(files, ensure_ascii=False, indent=2))
        sys.exit(0)
    folder = argv[1] if len(argv) > 1 else os.path.dirname(script)
    try:
        lines = write_defs(folder, files)
    except ValueError as e:
        flags.die(prog, "DefBad", str(e))
    except OSError as e:
        flags.die(prog, "WriteFailed", "cannot write the definition into %s: %s" % (folder, e))
    for line in lines:
        print(line)
    print("agents that use this definition see the change from their next brain call (state machine and loop changes: from their next tick or restart)")
    sys.exit(0)
