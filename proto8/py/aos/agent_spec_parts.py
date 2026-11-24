"""agent_spec_parts - agent_spec 的零件：各份定義檔怎麼從宣告算出來、怎麼先驗（tools.json、llm.json、interfaces.json、FILES），以及不宣告 FSM 時照夾裡現有的 interfaces.json 找檔名。

只給 aos/agent_spec.py、agent_spec_agent.py 等用（第三刀 geng3-1119 從 agent_spec 拆出來，免得單檔過 300 行；欄位名與訊息 11-20 第 2 刀改小寫）；對外的名字（WHAT…；SpecBad、DefBad 在 aos/spec_base）由 agent_spec 轉出，agent.py 只認 agent_spec。
驗的規矩不自己發明，照讀那份檔的一方：工具格照 aos-tools 的 registry.finish。hook 那塊（hooks.json）11-20 編譯程式庫第 3 刀拆到 aos/agent_spec_hooks.py。
tools=[…] 裡的 @fn.tool 函數（第 3 刀，線 aos-pylib-k3-1120）＝一支自己寫的工具（同 defs.tool），名字＝name= 或函數名；它的程式由 aos/fn_spec 編譯時抽成 fn/<名>.py。
"""
import json, os, re

from aos import fn_spec
from aos.declared_files import declared_files
from aos import hook_point
from aos.spec_base import SpecBad, DefBad  # noqa: F401（兩個例外在 spec_base，跟 tool_spec 共用；parts.SpecBad 照舊叫得到）

LLM_KEYS = ["model", "reasoning_effort", "temperature", "top_p", "max_tokens", "seed", "presence_penalty", "frequency_penalty",
            "stop"]   # 同 lib/aos/apps/agent_fsm/llm_settings.KEYS（reasoning_effort：11-21 使用者「effort...改叫reasoning_effort吧」）
PACK_RE = re.compile(r"[a-z0-9][a-z0-9_-]*\Z")
TOOL_RE = re.compile(r"[A-Za-z0-9_-]{1,64}\Z")                        # aos-tools 的 NAME_RE
ENV_KEY_RE = re.compile(r"[A-Za-z_][A-Za-z0-9_]*\Z")                  # aos-tools 的 ENV_KEY_RE
RUNTIME_FILES = ("ctl.json", "state.json", "state_flux.json", "history.jsonl")   # loop／腦跑起來寫的檔名，FILES 不能用
OWN_FILES = {"tools": "tools.json", "llm": "llm.json", "system": "system.txt", "fsm": "fsm.json", "hooks": "hookeds.json"}   # hooks＝掛上去的 hook（11-21 起檔名 hookeds.json）
SKELETON = ("_entry", "body.json", "loop.json", "interfaces.json")
HOOK_POINTS = ({"$env": "AOS_HOME", "$path": "/lib/aos/apps/hook/loop_hooks.json"},   # 有 fsm 又有 hooks 時寫進 interfaces.json 最外層的 hooks（宣告，只是參考）
               {"$env": "AOS_HOME", "$path": "/lib/aos/apps/agent_fsm/hooks.json"})
CONTENT = ("system", "tools", "llm", "hooks")                          # 不宣告 FSM 時 agent.py 寫的內容檔（檔名照 interfaces.json）
RESERVED = set(SKELETON) | set(RUNTIME_FILES) | set(OWN_FILES.values()) | {"_metainfo.json", "README.md", "agent.py"}
WHAT = {"_entry": "Register this agent with the current daemon (aos-agent ctl add).",
        "body.json": "Run this agent's loop: aos-loop with loop.json.",
        "loop.json": "Run the state machine in %s every tick and expose public control, state and state flux files.",
        "loop_hooks": " on_start / on_stop fire the after_start / after_stop hooks through aos-hook (a failing hook stops the loop).",
        "loop_run": " on_before_run / on_after_run fire before_run / after_run around each state the same way: they are here because a hook listened to them when this was compiled; one added later needs a recompile and a restart.",
        "loop_norun": " Nothing listened to before_run / after_run when this was compiled, so they are not wired: a hook added for them needs a recompile and a restart.",
        "fsm.json": "The state machine of this agent: which program each state runs, and the next state by exit code.",
        "tools.json": "Tools this agent can call.",
        "llm.json": "Brain settings of this agent: model names a brain pack of the llm kernel (none = the kernel's default).",
        "hookeds.json": "What is hooked on this agent: aos functions run when an event happens; the stack copy of this file overrides it by name, null turns one off."}


def kind(value):
    """宣告小函式回的記號種類（"bad"、"extern"（{"target"}，defs.load 換過的多帶 "from"）、"stock_hooks"（std.hooks 回的）…）；普通值＝None。
    hook 表裡叫 kind 的 hook 值是 dict，不會被認錯。"""
    return value.get("kind") if isinstance(value, dict) and isinstance(value.get("kind"), str) else None


def raise_bad(value):
    if kind(value) == "bad":
        raise SpecBad(value["bad"])


def pick(value, what, ok):
    """defs.extern 的＝回記號；寫錯的＝丟 SpecBad；形狀對＝None。"""
    raise_bad(value)
    if kind(value) == "extern":
        return value
    if not ok(value):
        raise SpecBad(what)
    return None


def stack_tools(tools):
    """TOOLS 疊起來 → ({名字: 工具格，拿掉的＝None（墓碑）}, 說明裡列的包)。包在宣告時已讀出、展開好（aos/agent_spec_lib.py）：明寫的 defs.tool／庫的 .tool
    整格換掉包裡同名那支（故意），defs.drop 拿掉；兩個包展開出同一個名字＝解完的整格完全相同才算同一支（菱形），否則 SpecBad，不再悄悄蓋（命名空間第一刀；
    設計稿 aos-ns-1119/05 第 7 條）。defs.load 的 TOOLS 也是一個包，它拿掉的帶著墓碑來：一邊墓碑、一邊還在＝同樣 SpecBad（繼承第一刀，aos-inherit-1119/07 A1）。
    @fn.tool 的函數＝自己寫的一支（同 defs.tool；第 3 刀），那格帶著 fn_spec.KEY，寫檔前由 fn_spec.programs 換成 {"path": "fn/<名>.py"}。"""
    order, packed, own, drops, packs, origins = [], {}, {}, [], [], []
    for t in tools:
        if callable(t) and not isinstance(t, dict):
            t = fn_spec.tool_item(t)
        raise_bad(t)
        if kind(t) == "extern":
            raise SpecBad("tools: defs.extern(...) stands for the whole field (a link to one tools.json): write tools=defs.extern(...), "
                          "not inside a list")
        if kind(t) not in ("pack", "tool", "drop"):
            raise SpecBad("each item of tools must come from std.pack(...), std.tool(...), defs.tool(...) or defs.drop(...) "
                          "(or .pack / .tool of a library from defs.lib, the tools of defs.load(...), or a function marked @fn.tool), "
                          "got %r" % (t,))
        if t["kind"] == "pack":
            label = t.get("label") or "%s.pack(%r)" % (t["lib"], t["name"])
            if label in packs:
                raise SpecBad("%s is listed twice" % label)
            packs.append(label)
            for o in t.get("origins", [label]):
                if o not in origins:
                    origins.append(o)
            for name, entry in t["tools"].items():
                packed.setdefault(name, []).append((label, entry))
                if name not in order:
                    order.append(name)
            continue
        if t["name"] in own or t["name"] in drops:
            raise SpecBad("tool %s is listed twice" % t["name"])
        if t["kind"] == "tool":
            own[t["name"]] = t["entry"]
        else:
            drops.append(t["name"])
        if t["name"] not in order:
            order.append(t["name"])
    for name in drops:
        if name not in packed:
            raise SpecBad("defs.drop(%r) takes a tool out of the packs, but no pack in tools has a tool %s%s" % (
                name, name, " (packs give: %s)" % ", ".join(sorted(packed)) if packed else ""))
    out = {}
    for name in order:
        if name in drops:
            out[name] = None
            continue
        if name in own:
            out[name] = own[name]
            continue
        (first, entry), rest = packed[name][0], packed[name][1:]
        for label, other in rest:
            if other != entry and None in (entry, other):
                gone, kept = (first, label) if entry is None else (label, first)
                raise SpecBad("tool %s is taken out in %s but kept in %s: say which you mean with defs.drop(%r) or defs.tool(%r, ...)"
                              % (name, gone, kept, name, name))
            if other != entry:
                raise SpecBad("tool %s comes from both %s and %s, and they differ: rename one (prefix= or rename=), "
                              "leave one out (exclude=), or pick one with defs.tool(%r, ...)" % (name, first, label, name))
        out[name] = entry
    return out, origins


def _patch(acc, layer):
    """照 aos-tools 的 registry.patch 疊一層（執行期 tools.json 的 $override 就是這樣合）：格逐欄蓋、欄是物件再往下一層，null＝不是工具。"""
    for name, e in layer.items():
        if e is None:
            acc[name] = None
            continue
        cur = acc.get(name)
        if cur is None:
            cur = acc[name] = {}
        for k, v in e.items():
            if isinstance(v, dict) and isinstance(cur.get(k), dict):
                cur[k] = dict(cur[k], **v)
            else:
                cur[k] = v


def _link_of(t, link, warn):
    """一個包這次怎麼連結："static"／"dynamic"。t["link"]＝包上明寫的（std.pack(..., link=...)），沒寫照整支的 link。
    動態做不到的（名字要改、或 defs.load 的底）：明寫 dynamic＝SpecBad；只是整支 --dynamic＝改靜態並 warn，不悄悄退化。"""
    mode = t.get("link") or link
    if mode != "dynamic":
        return "static"
    label = t.get("label") or "%s.pack(%r)" % (t["lib"], t["name"])
    if "file" not in t:                         # defs.load 的 TOOLS：底的工具疊完的結果，不是一份包檔；編出的 json 不記上一層（N-70）
        warn("%s is linked statically: it is the tools of another agent.py, not a pack file, "
             "and the compiled files do not name the base (N-70)" % label)
        return "static"
    if not t["as_is"]:
        if t.get("link") == "dynamic":
            raise SpecBad("%s: link=\"dynamic\" cannot rename its tools (prefix= or rename=): when the agent runs, aos reads the pack "
                          "as it is; link it statically, or give prefix=\"\" and no rename (a library other than std gets the "
                          "prefix \"<name>_\" unless you give prefix=\"\")" % label)
        warn("%s is linked statically: its tools are renamed (a prefix or rename=), which only static linking can do" % label)
        return "static"
    return "dynamic"


def tools_json(tools, link="static", warn=None):
    """TOOLS → tools.json 的內容：stack_tools 疊完、濾掉墓碑。link＝整支的連結方式（"static" 預設、"dynamic"；使用者 11-19「或者說，用選項吧，gcc那樣」）。
    全靜態：只有 tools 表、沒有 $override，哪幾支、各叫什麼在編譯時定死。有動態連結的包：$override 依 TOOLS 的順序列那些包檔，
    tools 表只寫包給不出的（靜態的包、自己寫的、拿掉的＝null）；寫完照執行期的合法（_patch）在編譯時算一遍，
    算出來跟全靜態那份不一樣（逐欄合併會留下包那格的欄位）＝SpecBad，叫人把那個包改靜態。說明列靜態連結的包、動態連結的包，不提 defs.load 的底。"""
    warn = warn or (lambda msg: None)
    table, origins = stack_tools(tools)
    final = {n: e for n, e in table.items() if e is not None}
    dynamic = [t for t in tools if kind(t) == "pack" and _link_of(t, link, warn) == "dynamic"]
    labels = [t.get("label") or "%s.pack(%r)" % (t["lib"], t["name"]) for t in dynamic]
    desc = WHAT["tools.json"]
    copied = [o for o in origins if o not in labels]
    if copied:
        desc += " agent.py copied in the tools of %s." % ", ".join(copied)
    if not dynamic:
        return {"description": desc, "tools": final}
    desc += " It links %s dynamically: aos reads %s when the agent runs." % (", ".join(labels), "that pack" if len(labels) == 1 else "those packs")
    from_packs = {}
    for t in dynamic:
        _patch(from_packs, json.loads(json.dumps(dict(t["left_out"], **t["tools"]))))
    own = {n: e for n, e in final.items() if from_packs.get(n) != e}
    own.update({n: None for n in from_packs if n not in final})
    got = json.loads(json.dumps(from_packs))
    _patch(got, json.loads(json.dumps(own)))
    got = {n: e for n, e in got.items() if e is not None}
    for name in sorted(set(got) | set(final)):
        if got.get(name) != final.get(name):
            by = [label for label, t in zip(labels, dynamic) if name in t["tools"] or name in t["left_out"]]
            raise SpecBad("tool %s: with %s linked dynamically, aos would merge the pack's tool %s with the one agent.py gives, field by "
                          "field, when the agent runs, and get something else; link %s statically (link=\"static\")"
                          % (name, ", ".join(by), name, "it" if len(by) == 1 else "them"))
    return {"description": desc, "$override": [t["file"] for t in dynamic], "tools": own}


def llm_json(llm, keys):
    for k in llm:
        if k != "description" and k not in keys:
            raise SpecBad("llm key %r is not one of llm_keys (%s)" % (k, ", ".join(keys)))
    if "model" in llm and (not isinstance(llm["model"], str) or not llm["model"]):
        raise SpecBad("llm model must be a non-empty string: the name of a brain pack of the llm kernel, like \"luna\"")
    return dict({"description": WHAT["llm.json"]}, **llm)


def interfaces_json(over, files, description):
    """預設的 interfaces.json 疊上 INTERFACES。files＝{種類: 檔名}；有 hooks 才寫最外層的 hooks（點的宣告）與 hookeds（被勾清單）兩鍵（位置照 agent-fsm 範本，11-21）。"""
    agent = {"entry": "body.json", "tools": files["tools"], "llm": files["llm"], "llm_keys": list(LLM_KEYS),
             "history": "history.jsonl"}
    agent["system"] = files["system"]
    out = {"description": description, "aos-agent": agent}
    if "hooks" in files:                                         # 格程式是 agent-fsm 那幾支：點＝loop 的四個＋agent-fsm 的；要別的用 interfaces= 蓋
        out["hooks"] = [dict(p) for p in HOOK_POINTS]
        out["hookeds"] = files["hooks"]
    if over is None:
        return out
    if not isinstance(over, dict):
        raise SpecBad("interfaces must be a dict laid over the default interfaces.json, like {\"aos-observed\": {\"file\": \"observed.jsonl\"}}")
    for key, value in over.items():
        if key == "aos-agent" and value is None:
            raise SpecBad("interfaces cannot remove aos-agent: without it the folder is not an agent")
        if key == "aos-agent":
            if not isinstance(value, dict):
                raise SpecBad("interfaces aos-agent must be a dict (a value of None removes a default key)")
            for k, v in value.items():
                if k == "entry":
                    raise SpecBad("interfaces aos-agent entry is body.json, the skeleton agent.py writes; it cannot be changed")
                if k in ("tools", "llm", "system"):
                    raise SpecBad("interfaces aos-agent %s is set by agent.py; to point it at a file you write yourself use defs.extern(...)" % k)
                if v is None:
                    agent.pop(k, None)
                else:
                    agent[k] = v
        elif key == "hookeds":
            raise SpecBad("interfaces hookeds is set by agent.py (the hooks= field); to point it at a file you write yourself use defs.extern(...)")
        elif value is None:
            out.pop(key, None)
        else:
            out[key] = value
    return out


def extra_files(files, taken):
    """FILES＝{檔名: 內容} 原樣吐：dict／list 寫成 JSON、字串照字面。檔名只能是夾裡的一個檔，不能搶 agent.py、跑起來的 agent 或宣告用的檔。"""
    if not isinstance(files, dict):
        raise SpecBad("files must be a dict {file name: content}, like {\"ladder.json\": {...}}")
    for name, value in files.items():
        if not isinstance(name, str) or not name or "/" in name or name.startswith(".") or name != name.strip():
            raise SpecBad("files: name %r must be one plain file name in the definition folder (no /, not starting with .), like \"ladder.json\"" % (name,))
        if name in RESERVED or name in taken:
            raise SpecBad("files: %s: that file belongs to agent.py, the skeleton, the running agent or a declaration "
                          "(system, tools, llm, fsm, hooks, interfaces, meta); declare it there instead" % name)
        if not isinstance(value, (dict, list, str)):
            raise SpecBad("files: %s: the content must be a dict or list (written as JSON) or a string (written as it is)" % name)
    return dict(files)


def existing_names(folder):
    """不宣告 FSM：夾裡現有的 interfaces.json 宣告的 {種類: 檔名}（tools／llm／system／hooks）與 llm_keys。夾不對丟 DefBad。"""
    path = os.path.join(folder, "interfaces.json")
    if not os.path.isfile(path):
        raise DefBad("%s has no interfaces.json: without fsm, agent.py writes only the content files (system, tools, llm, hooks) "
                     "of a definition that already has its skeleton; copy one first (agent_def new, template eca-claude or eca-pi) "
                     "or give fsm" % folder)
    try:
        names = declared_files(folder)
        own = [item for item, _ in hook_point.items(folder, "hookeds") if isinstance(item, str) and not os.path.isabs(item)]
        if own:                                                  # 掛上去的 hook：最外層 hookeds 的第一個相對檔名（11-21）
            names["hooks"] = own[0]
        with open(path, encoding="utf-8") as f:
            agent = json.load(f).get("aos-agent")
    except (OSError, ValueError, AttributeError) as e:
        raise DefBad("cannot use %s: %s" % (path, e))
    if not isinstance(agent, dict):
        raise DefBad("%s has no aos-agent object, so the folder is not an agent definition" % path)
    keys = agent.get("llm_keys", LLM_KEYS)
    if not isinstance(keys, list) or not all(isinstance(k, str) for k in keys):
        raise DefBad("llm_keys in %s must be a list of strings" % path)
    return names, keys
