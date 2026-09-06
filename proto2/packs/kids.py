"""kids 工具包 — 生小孩、看小孩。子 agent 長在 `<home>/kids/<名字>/`，自己是一個完整的世界。"""
import os

PROMPT = ("子 agent：spawn 可以生一個小孩，它是你資料夾底下 kids/<名字>/ 的一個獨立 agent，"
          "有自己的人格跟記憶，跟你共用同一個 LLM。clock 選 shared＝你走一格它走一格"
          "（適合當分身、幫你分頭做同一件事）；own＝它自己一個時鐘、跟你的時間脫節"
          "（適合長期自己跑的角色）。不確定就用 shared。kids_list 看你生了哪些小孩、它們走到哪。")

TOOLS = [
    {"name": "spawn",
     "description": "生一個子 agent，長在你資料夾底下的 kids/<名字>/，有自己的人格與記憶、"
                    "跟你共用同一個 LLM。clock：shared＝跟你同一個時鐘，你走一格它走一格，"
                    "你不動它也不動，適合當分身分頭做事；own＝它自己一個時鐘、跟你脫節，"
                    "適合長期自己跑的角色（會自動跟 daemon 要時鐘）。不確定就用 shared。",
     "parameters": {"type": "object", "properties": {
         "name": {"type": "string", "description": "子 agent 的名字，只能英數字／底線／減號，也是資料夾名"},
         "persona": {"type": "string", "description": "子 agent 的人格，就是它的 system prompt"},
         "clock": {"type": "string", "enum": ["shared", "own"],
                   "description": "shared＝跟你同一個時鐘（預設），own＝它自己一個時鐘"},
         "template": {"type": "string", "description": "可選的出廠模板名字；找不到就照常建立"}},
         "required": ["name", "persona"]}},
    {"name": "kids_list",
     "description": "列出你生過的子 agent，以及它們各走到哪一格。",
     "parameters": {"type": "object", "properties": {}}},
]


def run(name, args, ctx):
    if name == "spawn":
        ok, msg = ctx.spawn(args.get("name") or "", args.get("persona") or "",
                            args.get("clock") or "shared", args.get("template"))
        return {"ok": ok, "message": msg}
    if name == "kids_list":
        rows = []
        registry = ctx.kids()
        box = ctx.kids_dir()
        if os.path.isdir(box):
            for kid in os.listdir(box):
                if os.path.isdir(os.path.join(box, kid)) and kid not in registry:
                    registry[kid] = {"name": kid, "dir": os.path.join(box, kid)}
        for kid, info in sorted(registry.items()):
            if isinstance(info, dict):
                path = info.get("dir") or os.path.join(ctx.kids_dir(), kid)
            else:
                path = os.path.join(ctx.kids_dir(), kid)
            if os.path.isdir(path):
                st = ctx.read_json(os.path.join(path, "state.json"), {}) or {}
                rows.append({"name": kid, "state": st.get("state") or "idle",
                             "step": st.get("step") or 0, "busy": st.get("busy") or 0,
                             "clock": info.get("clock") if isinstance(info, dict) else None})
        return rows
    return {"error": "kids 沒有這個工具：%s" % name}
