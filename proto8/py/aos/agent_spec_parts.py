"""agent_spec_parts - agent_spec 的零件：各份定義檔怎麼從宣告算出來、怎麼先驗（tools.json、llm.json、interfaces.json、hooks.json、FILES），以及不宣告 FSM 時照夾裡現有的 interfaces.json 找檔名。

只給 aos/agent_spec.py 用（第三刀 geng3-1119 從它拆出來，免得單檔過 300 行）；對外的名字（SpecBad、DefBad、WHAT…）由 agent_spec 轉出，agent.py 只認 agent_spec。
驗的規矩不自己發明，照讀那份檔的一方：工具格照 aos-tools 的 registry.finish，hook 格照 aos/agentlib/hooks.py 的 validate_entry 與 hook_run.validate_name（直接叫，不抄一份）。
"""
import json, os, re

from aos import hook_run
from aos.agentlib import hooks as agent_hooks
from aos.declared_files import declared_files

LLM_KEYS = ["model", "temperature", "top_p", "max_tokens", "seed", "presence_penalty", "frequency_penalty", "stop"]
PACK_RE = re.compile(r"[a-z0-9][a-z0-9_-]*\Z")
TOOL_RE = re.compile(r"[A-Za-z0-9_-]{1,64}\Z")                        # aos-tools 的 NAME_RE
ENV_KEY_RE = re.compile(r"[A-Za-z_][A-Za-z0-9_]*\Z")                  # aos-tools 的 ENV_KEY_RE
RUNTIME_FILES = ("ctl.json", "state.json", "state_flux.json", "history.jsonl")   # loop／腦跑起來寫的檔名，by_hand、FILES 不能用
OWN_FILES = {"tools": "tools.json", "llm": "llm.json", "system": "system.txt", "fsm": "fsm.json", "hooks": "hooks.json"}
SKELETON = ("_entry", "body.json", "loop.json", "interfaces.json")
CONTENT = ("system", "tools", "llm", "hooks")                          # 不宣告 FSM 時 agent.py 寫的內容檔（檔名照 interfaces.json）
RESERVED = set(SKELETON) | set(RUNTIME_FILES) | set(OWN_FILES.values()) | {"_metainfo.json", "README.md", "agent.py"}
WHAT = {"_entry": "Register this agent with the current daemon (aos-agent ctl add).",
        "body.json": "Run this agent's loop: aos-loop with loop.json.",
        "loop.json": "Run the state machine in %s every tick and expose public control, state and state flux files.",
        "loop_hooks": " on_start / on_stop fire the after_start / after_stop hooks (lib/tools/agent/hook_fire).",
        "fsm.json": "The state machine of this agent: which program each state runs, and the next state by exit code.",
        "tools.json": "Tools this agent can call.",
        "llm.json": "Brain settings of this agent: model names a brain pack of the llm kernel (none = the kernel's default).",
        "hooks.json": "Hooks of this agent: aos functions run when an event happens; the stack copy of this file overrides it by name, null turns one off."}
HOOKS_SHAPE = ("HOOKS must be a dict {hook name: entry}, std.hooks(...), a list of those (later ones win, None drops a hook), "
               "or ag.by_hand(\"hooks.json\")")


class SpecBad(Exception):
    """宣告本身寫錯；訊息寫成怎麼改。"""


class DefBad(ValueError):
    """定義夾本身（不是宣告）不對：_metainfo.json 壞了；不宣告 FSM 時 interfaces.json 不在、或沒宣告要寫的那份檔。"""


def kind(value):
    """宣告小函式回的記號種類（"bad"、"by_hand"、"stock_hooks"（std.hooks 回的）…）；普通值＝None。hook 表裡叫 kind 的 hook 值是 dict，不會被認錯。"""
    return value.get("kind") if isinstance(value, dict) and isinstance(value.get("kind"), str) else None


def raise_bad(value):
    if kind(value) == "bad":
        raise SpecBad(value["bad"])


def pick(value, what, ok):
    """ag.by_hand 的＝回記號；寫錯的＝丟 SpecBad；形狀對＝None。"""
    raise_bad(value)
    if kind(value) == "by_hand":
        return value
    if not ok(value):
        raise SpecBad(what)
    return None


def tools_json(tools):
    """TOOLS → tools.json 的內容。包在宣告時已讀出、展開好（aos/agent_spec_lib.py），這裡疊起來：明寫的 ag.tool／庫的 .tool 整格換掉包裡同名那支（故意），
    ag.no 拿掉；兩個包展開出同一個名字＝解完的整格完全相同才算同一支（菱形），否則 SpecBad，不再悄悄蓋（命名空間第一刀；設計稿 aos-ns-1119/05 第 7 條）。
    出的 tools.json 只有 tools 表、沒有 $override：哪幾支、各叫什麼在生成時定死（07 第 7 題暫照推薦）。"""
    order, packed, own, nos, packs = [], {}, {}, [], []
    for t in tools:
        raise_bad(t)
        if kind(t) not in ("pack", "tool", "no"):
            raise SpecBad("each item of TOOLS must come from std.pack(...), std.tool(...), ag.tool(...) or ag.no(...) "
                          "(or .pack / .tool of a library from ag.lib), got %r" % (t,))
        if t["kind"] == "pack":
            label = "%s.pack(%r)" % (t["lib"], t["name"])
            if label in packs:
                raise SpecBad("%s is listed twice" % label)
            packs.append(label)
            for name, entry in t["tools"].items():
                packed.setdefault(name, []).append((label, entry))
                if name not in order:
                    order.append(name)
            continue
        if t["name"] in own or t["name"] in nos:
            raise SpecBad("tool %s is listed twice" % t["name"])
        if t["kind"] == "tool":
            own[t["name"]] = t["entry"]
        else:
            nos.append(t["name"])
        if t["name"] not in order:
            order.append(t["name"])
    for name in nos:
        if name not in packed:
            raise SpecBad("ag.no(%r) takes a tool out of the packs, but no pack in TOOLS has a tool %s%s" % (
                name, name, " (packs give: %s)" % ", ".join(sorted(packed)) if packed else ""))
    out = {}
    for name in order:
        if name in nos:
            continue
        if name in own:
            out[name] = own[name]
            continue
        (first, entry), rest = packed[name][0], packed[name][1:]
        for label, other in rest:
            if other != entry:
                raise SpecBad("tool %s comes from both %s and %s, and they differ: rename one (prefix= or rename=), "
                              "leave one out (exclude=), or pick one with ag.tool(%r, ...)" % (name, first, label, name))
        out[name] = entry
    desc = WHAT["tools.json"]
    if packs:
        desc += " agent.py copied in the tools of %s." % ", ".join(packs)
    return {"description": desc, "tools": out}


def llm_json(llm, keys):
    for k in llm:
        if k != "description" and k not in keys:
            raise SpecBad("LLM key %r is not one of llm_keys (%s)" % (k, ", ".join(keys)))
    if "model" in llm and (not isinstance(llm["model"], str) or not llm["model"]):
        raise SpecBad("LLM model must be a non-empty string: the name of a brain pack of the llm kernel, like \"luna\"")
    return dict({"description": WHAT["llm.json"]}, **llm)


def interfaces_json(over, files, description):
    """預設的 interfaces.json 疊上 INTERFACES。files＝{種類: 檔名}；有 hooks 才寫 hooks 鍵（位置照 agent-fsm 範本）。"""
    agent = {"entry": "body.json", "tools": files["tools"], "llm": files["llm"], "llm_keys": list(LLM_KEYS),
             "history": "history.jsonl"}
    if "hooks" in files:
        agent["hooks"] = files["hooks"]
    agent["system"] = files["system"]
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
                if k == "entry":
                    raise SpecBad("INTERFACES aos-agent entry is body.json, the skeleton agent.py writes; it cannot be changed")
                if k in ("tools", "llm", "system", "hooks"):
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


def hooks_json(hooks):
    """HOOKS（一張表、std.hooks(...)、或它們的串列：後面的同名蓋前面、None 拿掉）→ hooks.json 的內容；每格照 agent 的 hooks.py 驗。"""
    layers = list(hooks) if isinstance(hooks, (list, tuple)) else [hooks]
    table, stock = {}, []
    for layer in layers:
        raise_bad(layer)
        if kind(layer) == "stock_hooks":
            stock.append(layer["template"])
            layer = layer["hooks"]
        elif kind(layer) is not None or not isinstance(layer, dict):
            raise SpecBad(HOOKS_SHAPE)
        for name, entry in layer.items():
            if not isinstance(name, str):
                raise SpecBad("HOOKS hook name %r must be a string" % (name,))
            if entry is None:
                table.pop(name, None)
                continue
            try:
                hook_run.validate_name(name)
            except hook_run.HooksBad as e:
                raise SpecBad("HOOKS hook name %r %s" % (name, e))
            try:
                agent_hooks.validate_entry(entry)
            except hook_run.HooksBad as e:
                raise SpecBad("HOOKS hook %s: %s" % (name, e))
            table[name] = entry
    desc = WHAT["hooks.json"]
    if stock:
        desc += " Taken from %s; see the description there for what each hook does." % ", ".join(
            "templates/%s/hooks.json" % t for t in stock)
    return {"description": desc, "hooks": table}


def extra_files(files, taken):
    """FILES＝{檔名: 內容} 原樣吐：dict／list 寫成 JSON、字串照字面。檔名只能是夾裡的一個檔，不能搶 agent.py、跑起來的 agent 或宣告用的檔。"""
    if not isinstance(files, dict):
        raise SpecBad("FILES must be a dict {file name: content}, like {\"ladder.json\": {...}}")
    for name, value in files.items():
        if not isinstance(name, str) or not name or "/" in name or name.startswith(".") or name != name.strip():
            raise SpecBad("FILES name %r must be one plain file name in the definition folder (no /, not starting with .), like \"ladder.json\"" % (name,))
        if name in RESERVED or name in taken:
            raise SpecBad("FILES %s: that file belongs to agent.py, the skeleton, the running agent or a declaration "
                          "(SYSTEM, TOOLS, LLM, FSM, HOOKS, INTERFACES, META); declare it there instead" % name)
        if not isinstance(value, (dict, list, str)):
            raise SpecBad("FILES %s: the content must be a dict or list (written as JSON) or a string (written as it is)" % name)
    return dict(files)


def existing_names(folder):
    """不宣告 FSM：夾裡現有的 interfaces.json 宣告的 {種類: 檔名}（tools／llm／system／hooks）與 llm_keys。夾不對丟 DefBad。"""
    path = os.path.join(folder, "interfaces.json")
    if not os.path.isfile(path):
        raise DefBad("%s has no interfaces.json: without FSM, agent.py writes only the content files (system, tools, llm, hooks) "
                     "of a definition that already has its skeleton; copy one first (agent_def new, template eca-claude or eca-pi) "
                     "or declare FSM" % folder)
    try:
        names = declared_files(folder)
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
