"""agent_spec_hooks - agent_spec 的 hook 那塊：hooks=… 怎麼疊（一張表、std.hooks(...)、defs.load 的 hooks、@fn.hook 的函數、它們的串列）、怎麼驗、怎麼算出被勾清單 hookeds.json。

編譯程式庫第 3 刀（線 aos-pylib-k3-1120，設計稿 thinking/2026-11/20/aos-pylib-plan-1120/03、04、07c）從 agent_spec_parts 拆出來（免得單檔過 300 行），
加上函數 hook：hooks=[…] 裡放 @fn.hook 標的函數＝一格 {"event", "handler": "fn/<hook 名>.py", 其餘鍵}，handler 的程式由 aos/fn_spec 編譯時抽出來寫。
函數 hook 跟自己寫的 dict 同一類：同名＝後面的蓋前面（設計稿 07d 意見 10）；兩個函數 hook 同名＝SpecBad。
驗的規矩不自己發明，照讀清單的一方：每格照 aos/agentlib/hooks.py 的 check_entry 與 hook_lists.check_name（直接叫，不抄一份）；
11-21 起（線 top-1121-hooknew）事件名不驗（宣告只是參考，使用者「沒宣告的照樣跑」）；hookeds.json 是 {hook 名: 格}，不再包一層 hooks。
只給 aos/agent_spec_agent.py、agent_spec_load.py、agent_spec_lib.py 用。
"""
import json

from aos import hook_lists
from aos import fn_spec
from aos.agentlib import hooks as agent_hooks
from aos.agent_spec_parts import WHAT, kind, raise_bad
from aos.spec_base import SpecBad

HOOKS_SHAPE = ("hooks must be a dict {hook name: entry}, std.hooks(...), the hooks of defs.load(...), a function marked @fn.hook, a list of those "
               "(later ones win, None drops a hook), or defs.extern(\"../shared/hookeds.json\")")


class Hooks(dict):
    """一組帶來源標記的 hook（std.hooks(...)、defs.load(...) 的 HOOKS；繼承第一刀 aos-inherit-cut1-1119）：兩組之間同名又不同＝SpecBad，
    自己寫的普通 dict 才是故意蓋。值 None＝墓碑（這組把它拿掉了），寫檔前才濾。h["timer"] 回那格的一份拷貝；沒有或是墓碑＝SpecBad。
    label＝錯誤訊息裡叫它的名字；origins＝寫進 hooks.json 說明的範本檔（不記 defs.load 的底，json 不留上一層）；declared=False＝底沒宣告 HOOKS。"""

    def __init__(self, table, label, origins=(), declared=True):
        dict.__init__(self, table)
        self.label, self.origins, self.declared = label, list(origins), declared

    def __getitem__(self, name):
        if not dict.__contains__(self, name):
            have = sorted(k for k, v in dict.items(self) if v is not None)
            raise SpecBad("%s has no hook %r (hooks: %s)" % (self.label, name, ", ".join(have) or "none"))
        entry = dict.__getitem__(self, name)
        if entry is None:
            raise SpecBad("%s takes hook %s out (None), so there is no entry to change" % (self.label, name))
        return json.loads(json.dumps(entry))


def no_hooks(hooks):
    """底沒宣告 HOOKS（defs.load 交回的空組）單獨用、或串列裡只有這種＝沒宣告 HOOKS（None）：不編出 hooks.json，跟底一樣。"""
    layers = list(hooks) if isinstance(hooks, (list, tuple)) else [hooks]
    if layers and all(isinstance(h, Hooks) and not h.declared for h in layers):
        return None
    return hooks


def stack_hooks(hooks):
    """HOOKS 疊起來 → ({名字: 格，拿掉的＝None（墓碑）}, 說明裡列的範本檔)。一張表、std.hooks(...)、defs.load 的 HOOKS、@fn.hook 的函數、或它們的串列：
    後面的同名蓋前面、None 拿掉；每格照 agent 的 hooks.py 驗。兩組帶標記的（Hooks）之間同名又不同＝SpecBad（繼承第一刀，收緊第三刀「兩組互蓋」那一種），
    除非自己寫的普通 dict（或函數）在兩組之後明寫了那一格（＝選好了）；自己寫的照舊蓋（aos-inherit-1119/06 設計者直接定第 4 條）。兩個函數同一個 hook 名＝SpecBad。"""
    layers = list(hooks) if isinstance(hooks, (list, tuple)) else [hooks]
    table, origins, marked, clash, by_fn = {}, [], {}, {}, {}
    for layer in layers:
        raise_bad(layer)
        if callable(layer) and not isinstance(layer, dict):
            name, entry = fn_spec.hook_entry(layer)
            if name in by_fn:
                raise SpecBad("hooks: two functions are both hook %s (%s and %s): give one another name, @fn.hook(..., name=\"...\")"
                              % (name, by_fn[name], layer.__name__))
            by_fn[name] = layer.__name__
            layer = {name: entry}
        if kind(layer) == "extern":
            raise SpecBad("hooks: defs.extern(...) stands for the whole field (a link to one hookeds.json): write hooks=defs.extern(...), "
                          "not inside a list")
        if isinstance(layer, Hooks):
            source = layer.label
            for o in layer.origins:
                if o not in origins:
                    origins.append(o)
        elif kind(layer) is not None or not isinstance(layer, dict):
            raise SpecBad(HOOKS_SHAPE)
        else:
            source = None
        for name, entry in dict.items(layer):
            if not isinstance(name, str):
                raise SpecBad("hooks: hook name %r must be a string" % (name,))
            if entry is not None:
                try:
                    hook_lists.check_name(name)
                except hook_lists.HooksBad as e:
                    raise SpecBad("hooks: %s" % e)
                try:
                    agent_hooks.check_entry(entry)
                except hook_lists.HooksBad as e:
                    raise SpecBad("hooks: hook %s: %s" % (name, e))
            if source is None:
                clash.pop(name, None)                               # 自己寫在它們後面的＝選好了
            else:
                if name in marked and marked[name][1] != entry:
                    clash[name] = (marked[name][0], source)
                marked[name] = (source, entry)
            if entry is None or table.get(name, False) is None:     # 拿掉的排到最後（照舊的 pop 順序）
                table.pop(name, None)
            table[name] = entry
    for name, (first, second) in clash.items():
        raise SpecBad("hook %s comes from both %s and %s, and they differ: pick one by writing it yourself after them, "
                      "like {%r: ...} (None drops it)" % (name, first, second, name))
    return table, origins


def hooks_json(hooks):
    """HOOKS → hookeds.json 的內容（{"description", 名: 格}）：stack_hooks 疊完、濾掉墓碑；說明列抄自哪些範本（去重），不提 defs.load 的底。
    函數 hook 那格還帶著 fn_spec.KEY（指回函數），由 Agent._files 交給 fn_spec.programs 換成真的 handler。"""
    table, origins = stack_hooks(hooks)
    desc = WHAT["hookeds.json"]
    if origins:
        desc += " Taken from %s; see the description there for what each hook does." % ", ".join(origins)
    return dict({"description": desc}, **{n: e for n, e in table.items() if e is not None})
