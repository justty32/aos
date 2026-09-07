"""studio 工具包 — 一張單從接單走到交付，流程寫死在工具裡。

單子在 `team/orders/<order_id>.json`，任務在 `team/tasks/<task_id>.json`，
專案目錄固定 `team/projects/<order_id>/`，交付檔案複製到 `team/files/final/<order_id>/`。
每個工具一次做完一串動作（開檔、寄信、撥額度、跑測試），模型只負責判斷要不要做。
"""
import datetime
import json
import os
import shutil
import subprocess

import aos_agent
from aos_agent import team_member_name, team_root_of, team_status_of


PROMPT = ("一張單的流程：order_accept（sales 接單）→ plan_set（chief 拆任務）→ "
          "task_assign（pm 派工，順便撥額度）→ task_report（做完的人回報，可帶測試指令）→ "
          "qa_run／qa_verdict（qa 驗）→ deliver（pm 交付）。不確定現況就 order_status。")

DEFAULT_GRANT_TOKENS = 50000
TEST_TIMEOUT_S = 60
TAIL = 2000

ORDER_STATUS = ("received", "planned", "in_progress", "qa", "delivered", "failed")
TASK_STATUS = ("assigned", "done", "passed", "failed")

# 誰能用哪個工具。owner 是老闆，什麼都能補救。
ALLOWED = {
    "order_accept": ("sales",),
    "plan_set": ("chief",),
    "task_assign": ("pm",),
    "task_report": ("chief", "dev", "tester"),
    "qa_run": ("qa", "pm"),
    "qa_verdict": ("qa",),
    "deliver": ("pm",),
    "order_fail": ("pm",),
    "order_status": None,       # 全員
}


def _object(properties, required=None):
    spec = {"type": "object", "properties": properties}
    if required:
        spec["required"] = required
    return spec


TOOLS = [
    {"name": "order_accept", "description": "接下甲方的單：開單、寄給 pm、回甲方一張確認單。",
     "parameters": _object({
         "order_id": {"type": "string", "description": "單號，不給就取最新一封"},
         "note": {"type": "string", "description": "補一句備註"}})},
    {"name": "plan_set", "description": "寫入這張單的架構與任務清單，每個任務開一個檔。",
     "parameters": _object({
         "order_id": {"type": "string", "description": "單號"},
         "architecture": {"type": "string", "description": "怎麼做"},
         "tasks": {"type": "array", "description": "任務清單",
                   "items": _object({
                       "title": {"type": "string", "description": "任務名"},
                       "spec": {"type": "string", "description": "要做什麼"},
                       "owner": {"type": "string", "description": "誰做"},
                       "files": {"type": "array", "items": {"type": "string"},
                                 "description": "要動的檔"}})}},
     ["order_id", "architecture", "tasks"])},
    {"name": "task_assign", "description": "把任務派給成員：先確保他有 tokens，再把 spec 寄給他。沒有 task_id 就在單上開一個新任務（給 to、title、spec）。",
     "parameters": _object({
         "task_id": {"type": "string", "description": "任務編號；開新任務可不給"},
         "order_id": {"type": "string", "description": "開新任務時的單號"},
         "to": {"type": "string", "description": "誰做，不給就照任務上的"},
         "title": {"type": "string", "description": "新任務的題目"},
         "spec": {"type": "string", "description": "說明"},
         "tokens": {"type": "number", "description": "至少要有的額度"}})},
    {"name": "task_report", "description": "回報任務做完：記檔案、可跑一次測試、寄摘要給 pm 與 qa。",
     "parameters": _object({
         "task_id": {"type": "string", "description": "任務編號"},
         "summary": {"type": "string", "description": "做了什麼"},
         "files": {"type": "array", "items": {"type": "string"}, "description": "動到的檔"},
         "test_cmd": {"type": "string", "description": "在專案目錄跑的測試指令"}},
     ["task_id", "summary"])},
    {"name": "qa_run", "description": "在專案目錄跑一個指令，結果存進任務檔。",
     "parameters": _object({
         "task_id": {"type": "string", "description": "任務編號"},
         "order_id": {"type": "string", "description": "單號，沒有任務編號時給"},
         "command": {"type": "string", "description": "要跑的指令"}},
     ["command"])},
    {"name": "qa_verdict", "description": "判一個任務過或不過；整張單都過就把單推進驗收。",
     "parameters": _object({
         "task_id": {"type": "string", "description": "任務編號"},
         "passed": {"type": "boolean", "description": "過不過"},
         "evidence": {"type": "string", "description": "根據什麼"}},
     ["task_id", "passed"])},
    {"name": "deliver", "description": "交付：檔案複製到 team/files/final，寄 sales 一張交付單。",
     "parameters": _object({
         "order_id": {"type": "string", "description": "單號"},
         "summary": {"type": "string", "description": "一句話總結"}},
     ["order_id"])},
    {"name": "order_status", "description": "看單子與任務的現況。",
     "parameters": _object({"order_id": {"type": "string", "description": "單號，不給就看全部"}})},
    {"name": "order_fail", "description": "這張單做不出來：標 failed 並寄 sales。",
     "parameters": _object({
         "order_id": {"type": "string", "description": "單號"},
         "reason": {"type": "string", "description": "為什麼"}},
     ["order_id", "reason"])},
]


# ── 小工具 ──────────────────────────────────────────────────────────────────
def _now():
    return datetime.datetime.now().astimezone().isoformat(timespec="seconds")


def _short(text, n=200):
    text = " ".join(str(text or "").split())
    return text[:n] + ("…" if len(text) > n else "")


def _tail(text, n=TAIL):
    text = str(text or "")
    return text[-n:] if len(text) > n else text


def _member(ctx):
    return team_member_name(ctx.world) or ctx.name


def _role(ctx, root, name):
    roster = ctx.read_json(os.path.join(root, "team", "team.json"), {})
    for member in roster.get("members", []) if isinstance(roster, dict) else []:
        if isinstance(member, dict) and member.get("name") == name:
            return member.get("role") or name
    return name


def _is_qa(ctx, root, name):
    """qa 只驗不做：不能被派任務、不能寫測試。寫測試是 tester 的事。"""
    name = str(name or "")
    return name == "qa" or _role(ctx, root, name) == "qa"


def _allowed(ctx, root, tool):
    """越權就回一句話；認 name、role，也認 dev-a 這種前綴。owner 一律放行。"""
    roles = ALLOWED.get(tool)
    if roles is None:
        return None
    me = _member(ctx)
    tags = {me, _role(ctx, root, me), me.split("-")[0]}
    if "owner" in tags or tags & set(roles):
        return None
    return {"ok": False, "error": "%s 不能用 %s；這是 %s 的工具" % (me, tool, "／".join(roles))}


def _dirs(root):
    return {"orders": os.path.join(root, "team", "orders"),
            "tasks": os.path.join(root, "team", "tasks"),
            "projects": os.path.join(root, "team", "projects"),
            "final": os.path.join(root, "team", "files", "final")}


def _order_path(root, order_id):
    return os.path.join(_dirs(root)["orders"], str(order_id) + ".json")


def _task_path(root, task_id):
    return os.path.join(_dirs(root)["tasks"], str(task_id) + ".json")


def _project_dir(root, order_id):
    return os.path.join(_dirs(root)["projects"], str(order_id))


def _load_order(ctx, root, order_id):
    if not order_id:
        return None
    data = ctx.read_json(_order_path(root, order_id), None)
    return data if isinstance(data, dict) else None


def _load_task(ctx, root, task_id):
    if not task_id:
        return None
    data = ctx.read_json(_task_path(root, task_id), None)
    return data if isinstance(data, dict) else None


def _order_ids(root):
    folder = _dirs(root)["orders"]
    if not os.path.isdir(folder):
        return []
    return sorted(n[:-5] for n in os.listdir(folder) if n.endswith(".json"))


def _note(order, ctx, what):
    history = order.get("history")
    history = history if isinstance(history, list) else []
    history.append({"time": _now(), "by": _member(ctx), "what": _short(what, 160)})
    order["history"] = history[-40:]


def _save_order(ctx, root, order):
    ctx.write_json(_order_path(root, order["id"]), order)


def _save_task(ctx, root, task):
    ctx.write_json(_task_path(root, task["id"]), task)


def _tasks_of(ctx, root, order):
    rows = []
    for task_id in order.get("tasks") or []:
        task = _load_task(ctx, root, task_id)
        if task:
            rows.append(task)
    return rows


def _run_cmd(root, order_id, command):
    """在專案目錄跑一次，只留 exit 與尾巴。長到不會回來的指令由 timeout 收掉。"""
    project = _project_dir(root, order_id)
    os.makedirs(project, exist_ok=True)
    row = {"cmd": command, "cwd": project, "time": _now()}
    try:
        done = subprocess.run(command, shell=True, cwd=project, timeout=TEST_TIMEOUT_S,
                              stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
        row["exit"] = done.returncode
        row["output"] = _tail(done.stdout.decode("utf-8", "replace"))
    except subprocess.TimeoutExpired as e:
        row["exit"] = None
        row["timeout"] = TEST_TIMEOUT_S
        out = e.stdout or b""
        row["output"] = _tail((out.decode("utf-8", "replace") if isinstance(out, bytes) else str(out))
                              + "\n[跑超過 %s 秒被收掉]" % TEST_TIMEOUT_S)
    except OSError as e:
        row["exit"] = None
        row["output"] = "跑不起來：%s" % e
    return row


def _tests_line(task):
    tests = task.get("tests")
    if not isinstance(tests, list) or not tests:
        return "沒跑測試"
    last = tests[-1]
    return "%s → exit=%s" % (_short(last.get("cmd"), 60), last.get("exit"))


def _mail(ctx, to, content, **extra):
    return bool(ctx.put_mail(to, ctx.name, content, **extra))


# ── 工具本體 ────────────────────────────────────────────────────────────────
def _letters(ctx):
    """inbox/user/ 與 read/ 裡所有帶 order_id 的信，新的排前面。"""
    rows = []
    for name in ctx.unread("user"):
        for mail in ctx.mail_of("user", name):
            if mail.get("order_id"):
                rows.append((mail.get("time") or "", name, name, mail))
    read_dir = os.path.join(ctx.home, "inbox", "user", "read")
    for name in sorted(os.listdir(read_dir)) if os.path.isdir(read_dir) else []:
        if not name.endswith(".json"):
            continue
        mail = ctx.read_json(os.path.join(read_dir, name), None)
        for item in (mail if isinstance(mail, list) else [mail]):
            if isinstance(item, dict) and item.get("order_id"):
                rows.append((item.get("time") or "", name, None, item))
    rows.sort(key=lambda row: (row[0], row[1]), reverse=True)
    return rows


def _order_accept(ctx, root, order_id, note):
    letters = _letters(ctx)
    fell_back = None
    if order_id:
        hits = [row for row in letters if row[3].get("order_id") == order_id]
        if hits:
            letters = hits
        elif letters:
            # 小模型很愛自己編單號；找不到就用最新那張，並在回值裡講清楚
            fell_back = order_id
        else:
            return {"ok": False, "error": "inbox/user 裡沒有這張單：%s" % order_id}
    if not letters:
        return {"ok": False, "error": "inbox/user 裡沒有帶 order_id 的訂單"}
    _time, _name, unread_name, mail = letters[0]
    order_id = mail.get("order_id")
    if _load_order(ctx, root, order_id):
        return {"ok": False, "error": "這張單已經接過了：%s" % order_id}
    body = mail
    content = mail.get("content")
    if isinstance(content, str) and content.strip().startswith("{"):
        try:
            parsed = json.loads(content)
            if isinstance(parsed, dict):
                body = dict(mail)
                body.update(parsed)
        except ValueError:
            pass
    acceptance = body.get("acceptance")
    acceptance = acceptance if isinstance(acceptance, list) else (
        [acceptance] if acceptance else [])
    order = {"id": order_id, "task": str(body.get("order") or body.get("task") or ""),
             "budget": body.get("budget") if isinstance(body.get("budget"), dict) else {},
             "acceptance": [str(a) for a in acceptance],
             "out_of_scope": [str(a) for a in (body.get("out_of_scope") or [])],
             "status": "received", "client": mail.get("from") or "user",
             "project": os.path.relpath(_project_dir(root, order_id), root),
             "plan": None, "tasks": [], "history": [], "note": str(note or "")}
    _note(order, ctx, "接單" + ("：" + str(note) if note else ""))
    os.makedirs(_project_dir(root, order_id), exist_ok=True)
    _save_order(ctx, root, order)
    if unread_name:
        ctx.mark_read("user", unread_name)

    budget = "、".join("%s=%s" % (k, v) for k, v in sorted(order["budget"].items())) or "未指定"
    accept = "；".join(order["acceptance"]) or "未指定"
    to_pm = _mail(ctx, "pm", "\n".join([
        "【新單】%s" % order_id,
        "範圍：%s" % order["task"],
        "預算：%s" % budget,
        "驗收：%s" % accept,
        "不做：%s" % ("；".join(order["out_of_scope"]) or "未指定"),
        "專案目錄：%s" % order["project"],
        "下一步：請 chief 用 plan_set 拆任務，你再 task_assign 派工。",
    ]), order_id=order_id)
    ctx.reply("\n".join([
        "【確認單】%s" % order_id,
        "範圍：%s" % order["task"],
        "預算：%s" % budget,
        "驗收：%s" % accept,
        "下一步：已轉交 PM 排工，做完我會把交付單回給您。",
    ]))
    if fell_back:
        ctx.log("order_accept：給的單號 %s 找不到，改接最新那張 %s" % (fell_back, order_id))
    return {"ok": True, "note": ("你給的單號 %s 找不到，已改接最新那張" % fell_back) if fell_back else "", "order_id": order_id, "status": "received",
            "project": order["project"], "mailed_pm": to_pm}


def _plan_set(ctx, root, args):
    order_id = args.get("order_id") or ""
    order = _load_order(ctx, root, order_id)
    if not order:
        return {"ok": False, "error": "找不到這張單：%s" % order_id}
    if order["status"] in ("delivered", "failed"):
        return {"ok": False, "error": "這張單已經 %s，不能改計畫" % order["status"]}
    rows = args.get("tasks")
    if not isinstance(rows, list) or not rows:
        return {"ok": False, "error": "tasks 要是至少一項的陣列"}
    for row in rows:
        owner = row.get("owner") if isinstance(row, dict) else None
        if owner and _is_qa(ctx, root, owner):
            return {"ok": False, "error": "任務不能派給 %s：qa 只驗收不動手，寫測試請派給 tester" % owner}
    made = []
    existing = [t for t in (order.get("tasks") or []) if _load_task(ctx, root, t)]
    for tid in existing:                     # 拆完任務，自己手上那項「定架構」就算做完了，不然 deliver 會被它卡住
        old_task = _load_task(ctx, root, tid)
        if old_task.get("owner") == _member(ctx) and old_task.get("status") == "assigned" and not old_task.get("files"):
            old_task.update({"status": "passed", "report": "plan_set 完成（定架構）", "done": _now()})
            _save_task(ctx, root, old_task)
    for i, row in enumerate(rows, len(existing) + 1):     # 接在已有的任務後面編號，不蓋掉先派的（例如定架構那一項）
        row = row if isinstance(row, dict) else {"title": str(row)}
        task_id = "%s-t%d" % (order_id, i)
        files = row.get("files")
        task = {"id": task_id, "order": order_id, "title": str(row.get("title") or task_id),
                "spec": str(row.get("spec") or ""), "owner": str(row.get("owner") or ""),
                "files": [str(f) for f in files] if isinstance(files, list) else [],
                "status": "assigned", "report": "", "tests": [], "qa": None,
                "time": _now()}
        _save_task(ctx, root, task)
        made.append(task)
    order["plan"] = {"architecture": str(args.get("architecture") or ""),
                     "time": _now(), "by": _member(ctx)}
    order["tasks"] = existing + [t["id"] for t in made]
    order["status"] = "planned"
    _note(order, ctx, "定計畫，%d 個任務" % len(made))
    _save_order(ctx, root, order)
    _mail(ctx, "pm", "\n".join(
        ["【計畫】%s" % order_id, "架構：%s" % _short(args.get("architecture"), 400)] +
        ["- %s（%s）→ %s" % (t["id"], t["owner"] or "待定", _short(t["title"], 60)) for t in made] +
        ["下一步：請用 task_assign 逐項派工。"]), order_id=order_id)
    return {"ok": True, "order_id": order_id, "status": "planned",
            "tasks": [{"id": t["id"], "owner": t["owner"], "title": t["title"]} for t in made]}


def _ensure_tokens(ctx, root, to, want):
    """對方 tokens 不夠就從自己（pm）撥一筆。回 (ok, 說明)。"""
    try:
        status = team_status_of(root, light=True)
    except (OSError, ValueError) as e:
        return False, str(e)
    row = next((m for m in status["members"] if m["name"] == to), None)
    if row is None:
        return False, "名冊裡沒有這個人：%s" % to
    left = row["remaining"].get("tokens")
    left = left if isinstance(left, (int, float)) else 0
    if left >= want:
        return True, {"granted": 0, "left": left}
    need = round(want - max(0, left), 6)
    team = aos_agent.load_pack(ctx.home, "team")
    if team is None:
        return False, "載不到 team 工具包，撥不了額度"
    result = team.run("team_grant", {"role": to, "amount": {"tokens": need}}, ctx)
    if not (isinstance(result, dict) and result.get("ok")):
        return False, (result or {}).get("error") or "撥額度失敗"
    return True, {"granted": need, "left": round(max(0, left) + need, 6)}


def _new_task(ctx, root, order, title, spec, to):
    """plan_set 之前也能派工（例如先派 chief 去定架構）：在單子上直接開一個新任務。"""
    existing = order.get("tasks") if isinstance(order.get("tasks"), list) else []
    n = len(existing) + 1
    task_id = "%s-t%d" % (order["id"], n)
    while _load_task(ctx, root, task_id):
        n += 1
        task_id = "%s-t%d" % (order["id"], n)
    task = {"id": task_id, "order": order["id"], "title": str(title or task_id),
            "spec": str(spec or ""), "owner": str(to or ""), "files": [],
            "status": "assigned", "report": "", "tests": [], "qa": None, "time": _now()}
    _save_task(ctx, root, task)
    order["tasks"] = existing + [task_id]
    return task


def _task_assign(ctx, root, args):
    task_id = str(args.get("task_id") or "")
    if _is_qa(ctx, root, args.get("to")):      # 要在開新任務之前擋，不然會留下一個派給 qa 的空任務
        return {"ok": False, "error": "任務不能派給 %s：qa 只驗收不動手，寫測試請派給 tester" % args.get("to")}
    task = _load_task(ctx, root, task_id)
    if task:
        order = _load_order(ctx, root, task.get("order"))
        if not order:
            return {"ok": False, "error": "找不到任務的單：%s" % task.get("order")}
    else:
        # 沒有這個任務：給了 to 就當作要開新任務（單號從 order_id、task_id 前綴、或唯一一張還沒結的單推）
        order_id = str(args.get("order_id") or "")
        if not order_id and task_id:
            for oid in _order_ids(root):
                if task_id.startswith(oid):
                    order_id = oid
                    break
        if not order_id:
            open_ids = [oid for oid in _order_ids(root)
                        if (_load_order(ctx, root, oid) or {}).get("status") not in ("delivered", "failed")]
            if len(open_ids) == 1:
                order_id = open_ids[0]
        order = _load_order(ctx, root, order_id) if order_id else None
        if not order:
            return {"ok": False, "error": "找不到這個任務：%s；要開新任務請給 order_id、to 與 spec" % task_id,
                    "orders": _order_ids(root)}
        if not args.get("to"):
            return {"ok": False, "error": "找不到任務 %s；要開新任務請給 to（誰做）與 spec" % task_id,
                    "order_id": order["id"], "tasks": order.get("tasks") or []}
        # 單上已經有 plan_set 開給同一個人、還沒真的派出去的任務，就派那一項，別再開一個重複的
        waiting = [_load_task(ctx, root, t) for t in (order.get("tasks") or [])]
        waiting = [t for t in waiting if t and t.get("owner") == str(args["to"])
                   and t.get("status") == "assigned" and not t.get("assigned")]
        if waiting:
            task = waiting[0]
            task_id = task["id"]
            if len(str(args.get("spec") or "")) <= len(task.get("spec") or ""):
                args = dict(args, spec=None)      # 首席寫的說明比較完整，別被短的蓋掉
        else:
            task = _new_task(ctx, root, order, args.get("title") or task_id or "任務", args.get("spec"), args.get("to"))
            task_id = task["id"]
    to = str(args.get("to") or task.get("owner") or "")
    if not to:
        return {"ok": False, "error": "這個任務沒有負責人，請給 to"}
    tokens = args.get("tokens")
    tokens = tokens if isinstance(tokens, (int, float)) and not isinstance(tokens, bool) \
        and tokens > 0 else DEFAULT_GRANT_TOKENS
    ok, budget = _ensure_tokens(ctx, root, to, tokens)
    if not ok:
        return {"ok": False, "error": "沒辦法讓 %s 有 %s tokens：%s" % (to, tokens, budget)}
    if args.get("spec"):
        task["spec"] = str(args["spec"])
    task["owner"] = to
    task["status"] = "assigned"
    task["assigned"] = _now()
    _save_task(ctx, root, task)
    sent = _mail(ctx, to, "\n".join([
        "【工作單】%s（單 %s）" % (task_id, order["id"]),
        "題目：%s" % task["title"],
        "說明：%s" % task["spec"],
        "要動的檔：%s" % ("、".join(task["files"]) or "自己決定"),
        "工作目錄：%s" % order.get("project"),
        "驗收：%s" % ("；".join(order.get("acceptance") or []) or "未指定"),
        "做完用 task_report(task_id=\"%s\", summary=..., files=[...], test_cmd=...)。" % task_id,
    ]), order_id=order["id"], task_id=task_id)
    if order["status"] in ("received", "planned"):
        order["status"] = "in_progress"
    _note(order, ctx, "派 %s 給 %s" % (task_id, to))
    _save_order(ctx, root, order)
    return {"ok": True, "task_id": task_id, "to": to, "status": "assigned",
            "order_status": order["status"], "budget": budget, "mailed": sent}


def _task_report(ctx, root, args):
    task_id = args.get("task_id") or ""
    task = _load_task(ctx, root, task_id)
    if not task:
        return {"ok": False, "error": "找不到這個任務：%s" % task_id}
    order = _load_order(ctx, root, task.get("order"))
    if not order:
        return {"ok": False, "error": "找不到任務的單：%s" % task.get("order")}
    files = args.get("files")
    if isinstance(files, list):
        task["files"] = [str(f) for f in files]
    me = _member(ctx)
    if _role(ctx, root, me) == "tester" and not any("test" in os.path.basename(f).lower() for f in task["files"]):
        return {"ok": False, "task_id": task_id,
                "error": "tester 的回報 files 裡要有測試檔（檔名含 test），現在是：%s" % ("、".join(task["files"]) or "無")}
    task["report"] = str(args.get("summary") or "")
    task["reported_by"] = me
    test = None
    if args.get("test_cmd"):
        test = _run_cmd(root, order["id"], str(args["test_cmd"]))
        tests = task.get("tests")
        task["tests"] = (tests if isinstance(tests, list) else []) + [test]
        if test.get("exit") != 0:
            # 測試沒過就不算做完：小模型會無視紅字直接報「全部通過」，這裡用工具擋住，不靠它自覺
            _save_task(ctx, root, task)
            return {"ok": False, "task_id": task_id, "status": task["status"],
                    "error": "test_cmd 沒有全過（exit %s），任務還不算完成；先修好再 task_report" % test.get("exit"),
                    "test": {"exit": test.get("exit"), "output": _tail(test.get("output"), 1200)}}
    task["status"] = "done"
    _save_task(ctx, root, task)
    ctx.state.pop("studio_nag_count", None)
    _note(order, ctx, "%s 回報完成" % task_id)
    _save_order(ctx, root, order)
    body = "\n".join([
        "【任務完成】%s（單 %s）" % (task_id, order["id"]),
        "做的人：%s" % _member(ctx),
        "摘要：%s" % _short(task["report"], 600),
        "檔案：%s" % ("、".join(task["files"]) or "無"),
        "測試：%s" % _tests_line(task),
    ] + (["輸出尾巴：\n%s" % _tail(test.get("output"), 600)] if test else []))
    mailed = [name for name in ("pm", "qa") if _mail(ctx, name, body,
                                                     order_id=order["id"], task_id=task_id)]
    out = {"ok": True, "task_id": task_id, "status": "done", "files": task["files"],
           "mailed": mailed}
    if test:
        out["test"] = {"exit": test.get("exit"), "output": _tail(test.get("output"), 400)}
    return out


def _qa_run(ctx, root, args):
    command = str(args.get("command") or "").strip()
    if not command:
        return {"ok": False, "error": "command 不能是空的"}
    task = _load_task(ctx, root, args.get("task_id"))
    order_id = task.get("order") if task else (args.get("order_id") or "")
    order = _load_order(ctx, root, order_id)
    if not order:
        return {"ok": False, "error": "找不到單或任務：%s" % (args.get("task_id") or
                                                             args.get("order_id") or "")}
    row = _run_cmd(root, order["id"], command)
    if task:
        tests = task.get("tests")
        task["tests"] = (tests if isinstance(tests, list) else []) + [row]
        _save_task(ctx, root, task)
    else:
        tests = order.get("tests")
        order["tests"] = (tests if isinstance(tests, list) else []) + [row]
    _note(order, ctx, "跑了 %s（exit=%s）" % (_short(command, 60), row.get("exit")))
    _save_order(ctx, root, order)
    return {"ok": True, "task_id": task["id"] if task else None, "order_id": order["id"],
            "exit": row.get("exit"), "output": _tail(row.get("output"), 1200)}


def _done_tasks(ctx, root):
    out = []
    for oid in _order_ids(root):
        order = _load_order(ctx, root, oid)
        if not order or order.get("status") in ("delivered", "failed"):
            continue
        out += [t for t in _tasks_of(ctx, root, order) if t.get("status") == "done"]
    return out


def _qa_verdict(ctx, root, args):
    task_id = str(args.get("task_id") or "")
    task = _load_task(ctx, root, task_id)
    if not task:
        # 小模型常漏 task_id：只有一個等驗的任務就當是它
        done = _done_tasks(ctx, root)
        if len(done) == 1:
            task, task_id = done[0], done[0]["id"]
        else:
            return {"ok": False, "error": "找不到這個任務：%s" % task_id,
                    "waiting_for_qa": [t["id"] for t in done]}
    if task["status"] == "assigned":
        return {"ok": False, "error": "%s 還沒 task_report，不能驗" % task_id}
    order = _load_order(ctx, root, task.get("order"))
    if not order:
        return {"ok": False, "error": "找不到任務的單：%s" % task.get("order")}
    passed = bool(args.get("passed"))
    tests = task.get("tests") if isinstance(task.get("tests"), list) else []
    if passed and not any(isinstance(t, dict) and t.get("exit") == 0 for t in tests):
        # 判過要有憑據：小模型會「看過了」就判過，這裡要求任務檔上至少有一筆 exit 0 的測試紀錄
        return {"ok": False, "task_id": task_id,
                "error": "任務 %s 沒有任何一次 exit 0 的測試紀錄，不能判過；先 qa_run(task_id, command) 跑測試" % task_id,
                "tests": [{"cmd": t.get("cmd"), "exit": t.get("exit")} for t in tests if isinstance(t, dict)]}
    task["status"] = "passed" if passed else "failed"
    task["qa"] = {"passed": passed, "evidence": str(args.get("evidence") or ""),
                  "by": _member(ctx), "time": _now()}
    _save_task(ctx, root, task)
    rows = _tasks_of(ctx, root, order)
    all_passed = bool(rows) and all(t["status"] == "passed" for t in rows)
    if all_passed and order["status"] not in ("delivered", "failed"):
        order["status"] = "qa"
    _note(order, ctx, "%s 驗收 %s" % (task_id, "過" if passed else "不過"))
    _save_order(ctx, root, order)
    _mail(ctx, "pm", "\n".join([
        "【驗收】%s：%s" % (task_id, "過" if passed else "不過"),
        "根據：%s" % _short(args.get("evidence"), 400),
        "單 %s 現在是 %s（%d/%d 過）" % (order["id"], order["status"],
                                        sum(1 for t in rows if t["status"] == "passed"), len(rows)),
    ]), order_id=order["id"], task_id=task_id)
    return {"ok": True, "task_id": task_id, "status": task["status"],
            "order_status": order["status"], "all_passed": all_passed}


def _deliver(ctx, root, args):
    order_id = args.get("order_id") or ""
    order = _load_order(ctx, root, order_id)
    if not order:
        return {"ok": False, "error": "找不到這張單：%s" % order_id}
    if order["status"] == "delivered":
        return {"ok": False, "error": "這張單已經交付過了"}
    rows = _tasks_of(ctx, root, order)
    if not rows:
        return {"ok": False, "error": "這張單還沒有任務，不能交付"}
    waiting = [t["id"] for t in rows if t["status"] != "passed"]
    if waiting:
        return {"ok": False, "error": "還有任務沒過驗收：%s" % "、".join(waiting)}
    project = _project_dir(root, order_id)
    final = os.path.join(_dirs(root)["final"], order_id)
    os.makedirs(final, exist_ok=True)
    copied, missing = [], []
    for task in rows:
        for name in task.get("files") or []:
            src = name if os.path.isabs(name) else os.path.join(project, name)
            if not os.path.isfile(src):
                missing.append(name)
                continue
            dst = os.path.join(final, os.path.basename(name))
            os.makedirs(os.path.dirname(dst), exist_ok=True)
            shutil.copy2(src, dst)
            if name not in copied:
                copied.append(name)
    try:
        spent = team_status_of(root, light=True)["spent"].get("tokens")
    except (OSError, ValueError):
        spent = None
    note = "\n".join([
        "【交付單】%s" % order_id,
        "範圍：%s" % order.get("task"),
        "總結：%s" % _short(args.get("summary"), 600),
        "檔案（%d）：%s" % (len(copied), "、".join(copied) or "無"),
        "測試：" + ("；".join("%s %s" % (t["id"], _tests_line(t)) for t in rows) or "無"),
        "驗收：%s" % ("；".join(order.get("acceptance") or []) or "未指定"),
        "整隊已花 tokens：%s" % spent,
        "交付位置：%s" % os.path.relpath(final, root),
        "下一步：sales 把上面這段回給甲方。",
    ] + (["缺檔：%s" % "、".join(missing)] if missing else []))
    order["status"] = "delivered"
    order["delivered"] = {"time": _now(), "by": _member(ctx), "files": copied,
                          "dir": os.path.relpath(final, root), "spent_tokens": spent,
                          "note": note}
    _note(order, ctx, "交付 %d 個檔" % len(copied))
    _save_order(ctx, root, order)
    sent = _mail(ctx, "sales", note, order_id=order_id)
    out = {"ok": True, "order_id": order_id, "status": "delivered", "files": copied,
           "dir": os.path.relpath(final, root), "spent_tokens": spent, "mailed_sales": sent}
    if missing:
        out["missing"] = missing
    return out


def _one_status(ctx, root, order):
    rows = _tasks_of(ctx, root, order)
    return {"id": order["id"], "status": order["status"], "task": _short(order.get("task"), 120),
            "project": order.get("project"),
            "tasks": [{"id": t["id"], "owner": t.get("owner"), "status": t["status"],
                       "files": t.get("files") or [], "tests": _tests_line(t)} for t in rows],
            "history": (order.get("history") or [])[-3:]}


def _order_status(ctx, root, order_id):
    if order_id:
        order = _load_order(ctx, root, order_id)
        if not order:
            return {"ok": False, "error": "找不到這張單：%s" % order_id}
        return {"ok": True, "order": _one_status(ctx, root, order)}
    orders = []
    for oid in _order_ids(root):
        order = _load_order(ctx, root, oid)
        if order:
            orders.append(_one_status(ctx, root, order))
    return {"ok": True, "count": len(orders), "orders": orders}


def _order_fail(ctx, root, args):
    order_id = args.get("order_id") or ""
    order = _load_order(ctx, root, order_id)
    if not order:
        return {"ok": False, "error": "找不到這張單：%s" % order_id}
    if order["status"] == "delivered":
        return {"ok": False, "error": "已經交付的單不能標 failed"}
    order["status"] = "failed"
    order["failed"] = {"time": _now(), "by": _member(ctx), "reason": str(args.get("reason") or "")}
    _note(order, ctx, "標記 failed：%s" % args.get("reason"))
    _save_order(ctx, root, order)
    sent = _mail(ctx, "sales", "\n".join([
        "【做不出來】%s" % order_id,
        "範圍：%s" % order.get("task"),
        "原因：%s" % _short(args.get("reason"), 600),
        "下一步：sales 把情況告訴甲方，談縮小範圍或追加預算。",
    ]), order_id=order_id)
    return {"ok": True, "order_id": order_id, "status": "failed", "mailed_sales": sent}


# ── 進出口 ──────────────────────────────────────────────────────────────────
def run(name, args, ctx):
    args = args if isinstance(args, dict) else {}
    root = team_root_of(ctx.world)
    if not root:
        return {"ok": False, "error": "你不在一個有 team/team.json 的工作室裡，studio 的工具用不了"}
    if name not in ALLOWED:
        return {"ok": False, "error": "studio 沒有這個工具：%s" % name}
    denied = _allowed(ctx, root, name)
    if denied:
        return denied
    for folder in _dirs(root).values():
        os.makedirs(folder, exist_ok=True)
    try:
        if name == "order_accept":
            return _order_accept(ctx, root, args.get("order_id") or "", args.get("note") or "")
        if name == "plan_set":
            return _plan_set(ctx, root, args)
        if name == "task_assign":
            return _task_assign(ctx, root, args)
        if name == "task_report":
            return _task_report(ctx, root, args)
        if name == "qa_run":
            return _qa_run(ctx, root, args)
        if name == "qa_verdict":
            return _qa_verdict(ctx, root, args)
        if name == "deliver":
            return _deliver(ctx, root, args)
        if name == "order_status":
            return _order_status(ctx, root, args.get("order_id") or "")
        if name == "order_fail":
            return _order_fail(ctx, root, args)
    except (OSError, ValueError) as e:
        return {"ok": False, "error": str(e)}
    return {"ok": False, "error": "studio 沒有這個工具：%s" % name}


TASK_NAG_TICKS = 45
TASK_NAG_LIMIT = 3


def on_idle(ctx):
    """做到一半停下來（回了一句話就算結束）的人，手上還有 assigned 的任務：閒滿 TASK_NAG_TICKS 格
    就寄一封信給自己提醒繼續（工作室的信直接進 prompt），不然沒人會再叫醒它。"""
    root = team_root_of(ctx.world)
    if not root or ctx.state.get("sleeping") or ctx.state.get("pending"):
        return
    step = int(ctx.state.get("step") or 0)
    last = ctx.state.get("studio_nag_step")
    if isinstance(last, (int, float)) and step - int(last) < TASK_NAG_TICKS:
        return
    if last is None:
        ctx.state["studio_nag_step"] = step      # 剛派到的那一刻先給它 45 格
        return
    me = _member(ctx)
    mine = []
    try:
        for oid in _order_ids(root):
            order = _load_order(ctx, root, oid)
            if not order or order.get("status") in ("delivered", "failed"):
                continue
            mine += [t for t in _tasks_of(ctx, root, order)
                     if t.get("owner") == me and t.get("status") in ("assigned", "failed")]
    except OSError:
        return
    ctx.state["studio_nag_step"] = step
    if not mine:
        ctx.state.pop("studio_nag_count", None)
        return
    ids = "、".join(t["id"] for t in mine)
    count = int(ctx.state.get("studio_nag_count") or 0) + 1
    ctx.state["studio_nag_count"] = count
    if count <= TASK_NAG_LIMIT:
        # 小模型被空泛地提醒只會回一段「我接下來要…」的文字；要講清楚現在就叫哪個工具
        ctx.put_mail(ctx.world, "studio",
                     "提醒（第 %d 次）：你手上的任務 %s 還沒 task_report。不要只回文字，現在就呼叫工具：先 read 看檔案，"
                     "改用 write 整檔重寫（edit 常對不上），再 run_checks，全過就 task_report。卡住就 mail_send 主管講清楚卡在哪。"
                     % (count, ids))
        return
    if count == TASK_NAG_LIMIT + 1:
        # 提醒三次還沒動靜：交給主管處理（改派、縮範圍），自己不再每 45 格燒一輪
        boss = _supervisor(ctx, root)
        if boss:
            ctx.put_mail(boss, _member(ctx),
                         "我卡住了：任務 %s 提醒 %d 次都沒做完。請改派給別人、或縮小範圍再派給我。" % (ids, TASK_NAG_LIMIT))


def _supervisor(ctx, root):
    roster = ctx.read_json(os.path.join(root, "team", "team.json"), {})
    me = _member(ctx)
    for member in roster.get("members", []) if isinstance(roster, dict) else []:
        if isinstance(member, dict) and member.get("name") == me:
            return member.get("reports_to")
    return None


def on_system_prompt(ctx):
    """把「你手上的單／任務」壓成 2～3 行；沒有就不佔位置。"""
    root = team_root_of(ctx.world)
    if not root:
        return ""
    me = _member(ctx)
    lines = []
    try:
        for oid in reversed(_order_ids(root)):
            order = _load_order(ctx, root, oid)
            if not order or order.get("status") in ("delivered", "failed"):
                continue
            lines.append("單 %s（%s）：%s｜驗收：%s" % (
                oid, order.get("status"), _short(order.get("task"), 80),
                _short("；".join(order.get("acceptance") or []), 60) or "未指定"))
            for task in _tasks_of(ctx, root, order):
                if task.get("owner") == me and task.get("status") in ("assigned", "failed"):
                    lines.append("你的任務 %s（%s）：%s" % (
                        task["id"], task["status"], _short(task.get("spec") or task.get("title"), 200)))
            if len(lines) >= 3:
                break
    except OSError:
        return ""
    return "\n".join(lines[:3])
