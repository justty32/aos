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
HOOKS_SHAPE = ("HOOKS must be a dict {hook name: entry}, ag.stock_hooks(...), a list of those (later ones win, None drops a hook), "
               "or ag.by_hand(\"hooks.json\")")


class SpecBad(Exception):
    """宣告本身寫錯；訊息寫成怎麼改。"""


class DefBad(ValueError):
    """定義夾本身（不是宣告）不對：_metainfo.json 壞了；不宣告 FSM 時 interfaces.json 不在、或沒宣告要寫的那份檔。"""


def kind(value):
    """宣告小函式回的記號種類（"bad"、"by_hand"、"stock_hooks"…）；普通值＝None。hook 表裡叫 kind 的 hook 值是 dict，不會被認錯。"""
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


def tools_json(tools, home_dir):
    """TOOLS → tools.json 的內容。home_dir＝$AOS_HOME（有才查包在不在）。"""
    packs, entries = [], {}
    for t in tools:
        raise_bad(t)
        if kind(t) not in ("pack", "tool", "no"):
            raise SpecBad("each item of TOOLS must come from ag.pack(...), ag.tool(...) or ag.no(...), got %r" % (t,))
        if t["kind"] == "pack":
            if t["name"] in packs:
                raise SpecBad("pack %s is listed twice" % t["name"])
            where = os.path.join(home_dir, "lib", "packs") if home_dir else None
            if where and not os.path.isfile(os.path.join(where, t["name"] + ".json")):
                have = sorted(f[:-5] for f in os.listdir(where) if f.endswith(".json")) if os.path.isdir(where) else []
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
        out["$override"] = [{"$env": "AOS_HOME", "$path": "/lib/packs/%s.json" % p} for p in packs]
    if entries or not packs:
        out["tools"] = entries
    return out


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
    """HOOKS（一張表、ag.stock_hooks(...)、或它們的串列：後面的同名蓋前面、None 拿掉）→ hooks.json 的內容；每格照 agent 的 hooks.py 驗。"""
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
