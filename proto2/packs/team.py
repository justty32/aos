"""team 工具包：看整隊預算、分額度、寫進度與看全隊狀態。"""
import datetime
import os

from aos_agent import TEAM_BUDGET_KEYS, team_member_name, team_root_of, team_status_of


PROMPT = (
    "整隊：team_budget 看自己與整隊還剩多少；owner 或 PM 用 team_grant 把自己未用額度分給成員；"
    "team_progress 把短進度追加到共用進度；team_status 看全隊（含每人在途請求數與被擋原因）。"
    "個人 tokens 額度是硬閘門，0 就是 0：成員沒拿到 team_grant 就一格都動不了，"
    "所以派工之前一定要先 team_grant 給他 tokens，一次至少 20000（一輪對話就要幾千），不夠再加。"
    "到個人額度 80% 時先停背景工作並報主管；"
    "整隊任一項用完時全隊會自動凍住，只有 sales 會問甲方要不要追加。"
    "首席只能建議重分，不能自己加額度。任何人都不能自行提高整隊總預算。"
)


def _object(properties, required=None):
    spec = {"type": "object", "properties": properties}
    if required:
        spec["required"] = required
    return spec


TOOLS = [
    {"name": "team_budget", "description": "看整隊、自己與每位成員的已花和剩餘預算。",
     "parameters": _object({})},
    {"name": "team_grant", "description": "owner 或 PM 從自己的剩餘額度分預算給一位成員。",
     "parameters": _object({
         "role": {"type": "string", "description": "成員名字，例如 chief 或 dev-a"},
         "amount": {"description": "各項額度的 JSON 物件；單一數字視為 tokens",
                    "oneOf": [{"type": "number"}, {"type": "object"}]},
     }, ["role", "amount"])},
    {"name": "team_progress", "description": "追加一則帶時間與署名的共用進度。",
     "parameters": _object({"text": {"type": "string", "description": "短進度"}}, ["text"])},
    {"name": "team_status", "description": "看每人的 state、busy、未讀、今日花費與剩餘預算。",
     "parameters": _object({})},
]


def _root(ctx):
    root = team_root_of(ctx.world)
    if not root:
        raise ValueError("你不在一個有 team/team.json 的工作室裡")
    return root


def _member(ctx):
    return team_member_name(ctx.world) or ctx.name


def _budget_view(ctx):
    data = team_status_of(_root(ctx))
    me = _member(ctx)
    mine = next((row for row in data["members"] if row["name"] == me), None)
    actions = []
    if mine:
        limit = mine["budget"].get("tokens") or 0
        spent = mine["today_spent"].get("tokens") or 0
        if spent >= limit:
            actions.append("tokens 已到 100%：你會被凍住，等主管 team_grant")
        elif spent >= limit * 0.8:
            actions.append("tokens 已到 80%：停止背景工作並報主管")
    for key in ("tokens", "hours", "ticks", "money_usd"):
        if data["remaining"].get(key) is not None and data["remaining"][key] <= 0:
            actions.append("整隊 %s 用完：PM 停止新工作；owner 請 sales 向甲方申請追加" % key)
    return {"team": data["name"], "day": data["day"], "member": me,
            "budget": data["budget"], "spent": data["spent"],
            "remaining": data["remaining"], "mine": mine, "actions": actions}


def _amount(value):
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        value = {"tokens": value}
    if not isinstance(value, dict) or not value:
        raise ValueError("amount 要是數字，或至少有一項的 JSON 物件")
    out = {}
    for key, number in value.items():
        if key not in TEAM_BUDGET_KEYS:
            raise ValueError("不認得的預算欄位：%s" % key)
        if not isinstance(number, (int, float)) or isinstance(number, bool) or number <= 0:
            raise ValueError("%s 要是大於 0 的數字" % key)
        out[key] = number
    return out


def _grant(ctx, role, amount):
    root = _root(ctx)
    giver = _member(ctx)
    if giver not in ("owner", "pm"):
        return {"ok": False, "error": "只有 owner 或 PM 能分預算；請向主管申請"}
    roster = ctx.read_json(os.path.join(root, "team", "team.json"), {})
    names = [m.get("name") for m in roster.get("members", []) if isinstance(m, dict)]
    target = role if role in names else None
    if not target:
        matched = [m.get("name") for m in roster.get("members", [])
                   if isinstance(m, dict) and m.get("role") == role]
        if len(matched) == 1:
            target = matched[0]
    if not target:
        return {"ok": False, "error": "找不到唯一成員：%s" % role}
    if target == giver:
        return {"ok": False, "error": "不能把預算分給自己"}
    try:
        give = _amount(amount)
    except ValueError as e:
        return {"ok": False, "error": str(e)}
    path = os.path.join(root, "team", "budget.json")
    book = ctx.read_json(path, {})
    allocations = book.get("allocations") if isinstance(book, dict) else None
    if not isinstance(allocations, dict) or not isinstance(allocations.get(giver), dict):
        return {"ok": False, "error": "team/budget.json 的 allocations 壞了"}
    for key, number in give.items():
        if (allocations[giver].get(key) or 0) < number:
            return {"ok": False, "error": "%s 的 %s 不夠，沒有寫帳" % (giver, key),
                    "action": "停止新工作；owner 請 sales 向甲方申請最小追加量"}
    allocations.setdefault(target, {key: 0 for key in TEAM_BUDGET_KEYS})
    for key, number in give.items():
        allocations[giver][key] = round((allocations[giver].get(key) or 0) - number, 6)
        allocations[target][key] = round((allocations[target].get(key) or 0) + number, 6)
    now = datetime.datetime.now().astimezone().isoformat(timespec="seconds")
    grants = book.get("grants")
    grants = grants if isinstance(grants, list) else []
    grants.append({"time": now, "from": giver, "to": target, "amount": give})
    book.update({"allocations": allocations, "grants": grants, "updated": now})
    ctx.write_json(path, book)
    return {"ok": True, "from": giver, "to": target, "amount": give,
            "from_left": allocations[giver], "to_budget": allocations[target]}


def _progress(ctx, text):
    text = " ".join(str(text or "").split())
    if not text:
        return {"ok": False, "error": "進度不能是空的"}
    root = _root(ctx)
    stamp = datetime.datetime.now().astimezone().isoformat(timespec="seconds")
    path = os.path.join(root, "team", "progress.md")
    with open(path, "a", encoding="utf-8") as f:
        f.write("- %s %s：%s\n" % (stamp, _member(ctx), text))
    return {"ok": True, "path": path, "time": stamp}


def run(name, args, ctx):
    try:
        if name == "team_budget":
            return _budget_view(ctx)
        if name == "team_grant":
            return _grant(ctx, args.get("role") or "", args.get("amount"))
        if name == "team_progress":
            return _progress(ctx, args.get("text") or "")
        if name == "team_status":
            return team_status_of(_root(ctx))
    except (OSError, ValueError) as e:
        return {"ok": False, "error": str(e)}
    return {"error": "team 沒有這個工具：%s" % name}


def on_system_prompt(ctx):
    """每次真的要問模型時帶短額度；超支指令不能只躺在靜態人格裡。"""
    try:
        view = _budget_view(ctx)
    except (OSError, ValueError):
        return ""
    mine = view.get("mine") or {}
    own_left = mine.get("remaining") or {}
    text = "此刻預算：你剩 tokens=%s、ticks=%s；整隊剩 tokens=%s、hours=%s、ticks=%s。" % (
        own_left.get("tokens"), own_left.get("ticks"), view["remaining"].get("tokens"),
        view["remaining"].get("hours"), view["remaining"].get("ticks"))
    if view["actions"]:
        text += " 必須處理：" + "；".join(view["actions"])
    return text
