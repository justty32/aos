"""aos-agent 與 aos-user 共用：世界、信箱、工具包、旁線請求、狀態與建世界。"""
import datetime
import importlib.util
import json
import os
import re
import shlex
import subprocess
import sys
import tempfile
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import aos_llm   # noqa: E402  （寫請求／撿結果的小幫手，就在旁邊）

HERE = os.path.dirname(os.path.abspath(__file__))
NAME_OK = re.compile(r"^[A-Za-z0-9_-]+$")
PACK_OK = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
HOME_RE = re.compile(r"--home[=\s]+(\S+)")
DIRECT_SOURCE = "user"      # 這個來源的信直接進 prompt，不用叫模型去讀
CHILD_INST = "aos-agent exec .\n"
SH_TIMEOUT = 60
CUT = 4000
TEAM_BUDGET_KEYS = ("tokens", "hours", "ticks", "disk_mb", "mem_mb", "money_usd")
SIDE_TIMEOUT_STEPS = 120


def warn(msg):
    print("%s: %s" % (os.path.basename(sys.argv[0]) or "aos-agent", msg), file=sys.stderr)


def die(msg, code=2):
    warn(msg)
    sys.exit(code)


def now_iso():
    return datetime.datetime.now().isoformat(timespec="seconds")


def read_json(path, default):
    return aos_llm.read_json(path, default)


def write_json(path, obj):
    aos_llm.write_json(path, obj)


def write_json_atomic(path, obj):
    aos_llm.write_json_atomic(path, obj)


def resolve_home(world, home_opt):
    where = home_opt
    if not where:
        where = "."
        inst = os.path.join(world, ".aos", "inst")
        if os.path.isfile(inst):
            try:
                with open(inst, encoding="utf-8", errors="replace") as f:
                    m = HOME_RE.search(f.read())
            except OSError:
                m = None
            if m:
                where = m.group(1)
    return os.path.abspath(os.path.join(world, where))


def truncate(text, n=CUT):
    text = text or ""
    return text if len(text) <= n else text[:n] + "…（截斷）"


def tools_conf(home):
    data = read_json(os.path.join(home, "tools.json"), {})
    if isinstance(data, list):
        return [], [t for t in data if isinstance(t, dict)]
    if not isinstance(data, dict):
        return [], []
    packs = [p for p in (data.get("packs") or []) if isinstance(p, str)]
    extra = [t for t in (data.get("tools") or []) if isinstance(t, dict)]
    return packs, extra


_PACK_CACHE = {}


def find_pack_file(home, name):
    if not PACK_OK.match(name or ""):
        return None
    for base in (os.path.join(home, "packs"), os.path.join(HERE, "packs")):
        path = os.path.join(base, name + ".py")
        if os.path.isfile(path):
            return path
    return None


def load_pack(home, name):
    path = find_pack_file(home, name)
    if not path:
        return None
    key = (path, os.path.getmtime(path))
    if key in _PACK_CACHE:
        return _PACK_CACHE[key]
    spec = importlib.util.spec_from_file_location("aos_pack_" + name, path)
    if spec is None or spec.loader is None:
        return None
    module = importlib.util.module_from_spec(spec)
    try:
        spec.loader.exec_module(module)
    except Exception as e:      # 一包壞掉不該弄死整個 agent
        warn("工具包 %s 載不起來（%s），跳過" % (name, e))
        return None
    _PACK_CACHE[key] = module
    return module


def load_packs(home):
    names, extra = tools_conf(home)
    loaded = []
    seen = set()
    for configured_name in names:
        name = "fs" if configured_name == "shell" else configured_name
        if configured_name == "shell":
            warn("工具包 shell 已併入 fs，這次改載 fs；請把 tools.json 改成 fs")
        if name in seen:
            warn("工具包 %s 重複列了，後面的跳過" % name)
            continue
        module = load_pack(home, name)
        if module is None:
            warn("認不得的工具包：%s（packs/%s.py 不在），跳過" % (name, name))
            continue
        seen.add(name)
        loaded.append((name, module))
    return loaded, extra


def tool_specs(loaded, extra):
    specs, owners = [], {}
    for pack_name, module in loaded:
        for t in getattr(module, "TOOLS", []):
            name = t.get("name")
            if not name:
                continue
            if name in owners:
                warn("同名工具 %s：前面的 %s 優先，後面的 %s 跳過" %
                     (name, owners[name], pack_name))
                continue
            owners[name] = pack_name
            specs.append(t)
    for t in extra:
        name = t.get("name")
        if not name:
            continue
        if name in owners:
            warn("同名工具 %s：前面的 %s 優先，後面的 tools[] 跳過" %
                 (name, owners[name]))
            continue
        owners[name] = "tools[]"
        specs.append({"name": name, "description": t.get("description", ""),
                      "parameters": t.get("parameters", {})})
    return specs


def system_text(ctx, loaded):
    home = ctx.home
    persona = read_json(os.path.join(home, "system-prompt.json"), {})
    text = (persona.get("content") or "") if isinstance(persona, dict) else ""
    paras = []
    if ctx.parent():
        paras.append(
            "你是子 agent。做完要回報父時，直接正常回答；系統會自動把這句轉寄給父，不用找路徑。")
    for name, module in loaded:
        override = os.path.join(home, "prompt-overrides", name + ".md")
        if os.path.isfile(override):
            try:
                with open(override, encoding="utf-8", errors="replace") as f:
                    prompt = f.read()
            except OSError as e:
                ctx.log("讀不到 prompt 覆蓋 %s：%s" % (name, e))
                prompt = getattr(module, "PROMPT", "")
        else:
            prompt = getattr(module, "PROMPT", "")
        if prompt:
            paras.append(prompt)
        hook = getattr(module, "on_system_prompt", None)
        if hook:
            try:
                extra = hook(ctx.for_pack(name))
                if extra:
                    paras.append(str(extra))
            except Exception as e:
                ctx.log("工具包 %s 的 on_system_prompt 出錯：%s" % (name, e))
    if paras:
        text = (text + "\n\n" if text else "") + "\n\n".join(paras)
    return text


def pack_owners(loaded):
    owners = {}
    for pack_name, module in loaded:
        for t in getattr(module, "TOOLS", []):
            if t.get("name") and t["name"] not in owners:
                owners[t["name"]] = (pack_name, module)
    return owners


def run_custom(ctx, extra, name, args_text):
    tool = None
    for t in extra:
        if t.get("name") == name:
            tool = t
            break
    if tool is None:
        return "沒有這個工具：%s" % name
    done = subprocess.run(tool.get("command", ""), shell=True, input=args_text,
                          capture_output=True, text=True, cwd=ctx.world)
    out = done.stdout
    if done.stderr.strip():
        out += done.stderr
    return out


# ── 信箱 ────────────────────────────────────────────────────────────────────
def inbox_dir(home):
    return os.path.join(home, "inbox")


def sources(home):
    box = inbox_dir(home)
    if not os.path.isdir(box):
        return []
    return sorted(n for n in os.listdir(box) if os.path.isdir(os.path.join(box, n)))


def unread_names(home, source):
    d = os.path.join(inbox_dir(home), source)
    if not os.path.isdir(d):
        return []
    return sorted(n for n in os.listdir(d)
                  if n.endswith(".json") and os.path.isfile(os.path.join(d, n)))


def read_names(home, source):
    d = os.path.join(inbox_dir(home), source, "read")
    if not os.path.isdir(d):
        return []
    return sorted(n for n in os.listdir(d)
                  if n.endswith(".json") and os.path.isfile(os.path.join(d, n)))


def mail_of(home, source, name):
    data = read_json(os.path.join(inbox_dir(home), source, name), None)
    if isinstance(data, dict):
        return [data]
    if isinstance(data, list):
        return [m for m in data if isinstance(m, dict)]
    warn("信 %s/%s 讀不成信件（要 JSON 物件或陣列），當空的" % (source, name))
    return []


def mark_read(home, source, name):
    d = os.path.join(inbox_dir(home), source)
    dst = os.path.join(d, "read")
    os.makedirs(dst, exist_ok=True)
    try:
        os.replace(os.path.join(d, name), os.path.join(dst, name))
    except OSError as e:
        warn("信 %s/%s 搬不進 read/：%s" % (source, name, e))


def scan_inbox(home, announced):
    msgs, counts, still, fresh = [], [], [], False
    for src in sources(home):
        names = unread_names(home, src)
        if not names:
            continue
        if src == DIRECT_SOURCE:
            for name in names:
                for mail in mail_of(home, src, name):
                    msgs.append({"role": "user",
                                 "content": "[%s] %s" % (src, mail.get("content") or "")})
                mark_read(home, src, name)
            continue
        counts.append((src, len(names)))
        for name in names:
            key = "%s/%s" % (src, name)
            still.append(key)
            if key not in announced:
                fresh = True
    if counts and fresh:
        msgs.append({"role": "user", "content": "你有新信：%s。用信箱工具去讀。"
                     % "、".join("%s %d 封" % (s, n) for s, n in counts)})
    return msgs, still


def preview(mail):
    text = (mail.get("content") or "").replace("\n", " ")
    return text[:60] + ("…" if len(text) > 60 else "")


# ── 內建工具 ────────────────────────────────────────────────────────────────
def folder_bytes(path):
    total = 0
    for root, _dirs, files in os.walk(path):
        for name in files:
            try:
                total += os.lstat(os.path.join(root, name)).st_size
            except OSError:
                pass
    return total


def find_llm(home, world):
    conf = read_json(os.path.join(home, "llm.json"), {})
    conf = conf if isinstance(conf, dict) else {}
    where = conf.get("dir") or os.environ.get("AOS_LLM_DIR") or ""
    if where:
        return os.path.abspath(os.path.join(world, where))
    fallback = os.path.abspath(os.path.join(world, "../llm"))
    return fallback if os.path.isdir(fallback) else None


def llm_dir(home, world):
    where = find_llm(home, world)
    if not where:
        die("找不到 LLM 資料夾——llm.json 沒有 dir、也沒設 AOS_LLM_DIR、旁邊也沒有 ../llm")
    return where


def today_usage_all(home, world):
    d = find_llm(home, world)
    if not d or not os.path.isdir(d):
        return None
    book = read_json(os.path.join(d, "usage", "%s.json" % datetime.date.today().isoformat()), {})
    if not isinstance(book, dict):
        return None
    if "by-model" in book or "by-requester" in book:
        section = book.get("by-model")
        section = section if isinstance(section, dict) else {}
    else:
        section = book
    rows = {str(key): value for key, value in section.items() if isinstance(value, dict)}
    total = {}
    for row in rows.values():
        for key, value in row.items():
            if isinstance(value, (int, float)) and not isinstance(value, bool):
                total[key] = total.get(key, 0) + value
    total["by_engine"] = rows
    return total


def status_of(world, home):
    st = read_json(os.path.join(home, "state.json"), {})
    st = st if isinstance(st, dict) else {}
    history = read_json(os.path.join(home, "prompts.json"), [])
    history = history if isinstance(history, list) else []
    started = st.get("started")
    uptime = None
    if started:
        try:
            uptime = int(time.time() - datetime.datetime.fromisoformat(started).timestamp())
        except ValueError:
            uptime = None
    usage = today_usage_for(home, world)
    limits = agent_limits(home)
    replies = []
    last_error = None
    box = os.path.join(home, "outbox")
    for name in outbox_names(box):
        msg = read_json(os.path.join(box, name), {})
        if isinstance(msg, dict) and msg.get("error"):
            last_error = msg.get("content") or "不明錯誤"
        try:
            reply_step = int(os.path.splitext(name)[0])
        except ValueError:
            continue
        replies.append(reply_step)
    recent = [step - (replies[i - 1] if i else 0)
              for i, step in enumerate(replies)][-5:]
    ctx = Ctx(world, home, st)
    sleeping = st.get("sleeping") if isinstance(st.get("sleeping"), dict) else None
    clocks = []
    for label, path in (("agent", world), ("LLM", find_llm(home, world))):
        if path:
            clock = ctx.clock_of(path)
            if clock["kind"] == "none" or clock["state"] != "running":
                clocks.append("%s 鐘沒跑" % label)
    return {
        "status": st.get("state") or "idle",
        "waiting": ("在等 %s %s" % (sleeping.get("kind"), sleeping.get("id"))
                    if sleeping else "沒有等待"),
        "clock": "；".join(clocks) if clocks else "正常",
        "last_error": last_error,
        "steps": {"total": st.get("step") or 0, "busy": st.get("busy") or 0},
        "question_steps": {"used": st.get("question_steps") or 0,
                           "limit": limits["max_steps_per_question"]},
        "today": {"tokens": usage.get("total_tokens") or 0,
                  "token_limit": limits["max_tokens_per_day"],
                  "cost_usd": _team_ledger_money(home, datetime.date.today().isoformat())},
        "recent_question_steps": recent,
        "memory": {"messages": len(history),
                   "chars": len(json.dumps(history, ensure_ascii=False)),
                   "folder_bytes": folder_bytes(world), "started": started,
                   "uptime_s": uptime},
    }


def agent_limits(home):
    conf = read_json(os.path.join(home, "llm.json"), {})
    conf = conf if isinstance(conf, dict) else {}
    try:
        steps = int(conf.get("max_steps_per_question", 60))
    except (TypeError, ValueError):
        steps = 60
    steps = max(1, steps)
    tokens = conf.get("max_tokens_per_day")
    if not isinstance(tokens, (int, float)) or isinstance(tokens, bool) or tokens <= 0:
        tokens = None
    return {"max_steps_per_question": steps, "max_tokens_per_day": tokens}


def today_usage_for(home, world):
    llm = find_llm(home, world)
    if not llm:
        return {}
    book = read_json(os.path.join(llm, "usage", datetime.date.today().isoformat() + ".json"), {})
    if not isinstance(book, dict):
        return {}
    rows = book.get("by-requester") if isinstance(book.get("by-requester"), dict) else {}
    requester = team_requester(world) or team_member_name(world) or \
        os.path.basename(os.path.abspath(world).rstrip(os.sep))
    row = rows.get(requester)
    if isinstance(row, dict):
        return row
    # 舊帳沒有 requester 時，只能退回整個 LLM 世界的總數。
    return today_usage_all(home, world) or {}


# ── 整隊共用家務 ──────────────────────────────────────────────────────────
def team_root_of(world):
    current = os.path.abspath(world)
    seen = set()
    for _ in range(4):
        if current in seen:
            break
        seen.add(current)
        team_file = os.path.join(current, "team", "team.json")
        if os.path.isfile(team_file):
            roster = read_json(team_file, {})
            declared = roster.get("root") if isinstance(roster, dict) else None
            if isinstance(declared, str) and os.path.isfile(
                    os.path.join(os.path.abspath(declared), "team", "team.json")):
                return os.path.abspath(declared)
            return current
        home = resolve_home(current, None)
        parent = read_json(os.path.join(home, "parent.json"), None)
        if not isinstance(parent, dict) or not parent.get("dir"):
            break
        current = os.path.abspath(parent["dir"])
    return None


def team_member_name(world):
    root = team_root_of(world)
    if not root:
        return None
    roster = read_json(os.path.join(root, "team", "team.json"), {})
    target = os.path.realpath(world)
    for member in roster.get("members", []) if isinstance(roster, dict) else []:
        if not isinstance(member, dict):
            continue
        path = os.path.realpath(os.path.join(root, member.get("path") or "."))
        if path == target:
            return member.get("name")
    return None


def team_requester(world):
    root = team_root_of(world)
    member = team_member_name(world)
    if not root or not member:
        return None
    roster = read_json(os.path.join(root, "team", "team.json"), {})
    team_name = roster.get("name") if isinstance(roster, dict) else None
    return "%s/%s" % (team_name or os.path.basename(root), member)


def _team_number(value):
    return value if isinstance(value, (int, float)) and not isinstance(value, bool) else 0


def normalize_team_budget(base, override=None):
    data = dict(base) if isinstance(base, dict) else {}
    override = dict(override) if isinstance(override, dict) else {}
    if "memory_mb" in data and "mem_mb" not in data:
        data["mem_mb"] = data.pop("memory_mb")
    if "memory_mb" in override and "mem_mb" not in override:
        override["mem_mb"] = override.pop("memory_mb")
    for key, value in override.items():
        if key in TEAM_BUDGET_KEYS or key == "reserve_pct":
            data[key] = value
    for key in TEAM_BUDGET_KEYS:
        value = data.get(key, 0)
        if not isinstance(value, (int, float)) or isinstance(value, bool) or value < 0:
            raise ValueError("預算 %s 要是不小於 0 的數字" % key)
        data[key] = value
    reserve = data.get("reserve_pct", 10)
    if not isinstance(reserve, (int, float)) or isinstance(reserve, bool) or not 0 <= reserve <= 100:
        raise ValueError("reserve_pct 要在 0 到 100 之間")
    data["reserve_pct"] = reserve
    return data


def _budget_part(total, pct):
    return {key: round(_team_number(total.get(key)) * pct / 100.0, 6)
            for key in TEAM_BUDGET_KEYS}


def _team_member_world(root, member):
    return os.path.abspath(os.path.join(root, member.get("path") or "."))


def _team_unread(home):
    return sum(len(unread_names(home, source)) for source in sources(home))


def _team_ledger_money(home, day):
    path = os.path.join(home, "ledger", day + ".jsonl")
    total = 0.0
    if not os.path.isfile(path):
        return total
    try:
        with open(path, encoding="utf-8", errors="replace") as f:
            for line in f:
                try:
                    row = json.loads(line)
                except ValueError:
                    continue
                round_info = row.get("llm_round") if isinstance(row, dict) else None
                cost = round_info.get("cost") if isinstance(round_info, dict) else None
                if isinstance(cost, (int, float)) and not isinstance(cost, bool):
                    total += cost
    except OSError:
        return 0.0
    return round(total, 12)


def _team_usage(root, roster, day):
    usage = {}
    owner = next((m for m in roster.get("members", [])
                  if isinstance(m, dict) and m.get("name") == roster.get("leader", "owner")), None)
    if not owner:
        return usage
    owner_world = _team_member_world(root, owner)
    owner_home = resolve_home(owner_world, None)
    llm = find_llm(owner_home, owner_world)
    book = read_json(os.path.join(llm, "usage", day + ".json"), {}) if llm else {}
    rows = book.get("by-requester") if isinstance(book, dict) else {}
    return rows if isinstance(rows, dict) else {}


def team_status_of(world):
    root = team_root_of(world)
    if not root:
        raise ValueError("找不到 team/team.json：" + os.path.abspath(world))
    roster = read_json(os.path.join(root, "team", "team.json"), {})
    if not isinstance(roster, dict) or not isinstance(roster.get("members"), list):
        raise ValueError("team/team.json 的名冊壞了")
    budget_book = read_json(os.path.join(root, "team", "budget.json"), {})
    budget_book = budget_book if isinstance(budget_book, dict) else {}
    total_budget = normalize_team_budget(budget_book.get("total") or roster.get("budget") or {})
    allocations = budget_book.get("allocations")
    allocations = allocations if isinstance(allocations, dict) else {}
    day = datetime.date.today().isoformat()
    usage = _team_usage(root, roster, day)
    rows = []
    total_spent = {key: 0 for key in TEAM_BUDGET_KEYS}
    for member in roster["members"]:
        if not isinstance(member, dict) or not member.get("name"):
            continue
        name = member["name"]
        member_world = _team_member_world(root, member)
        home = resolve_home(member_world, None)
        state = read_json(os.path.join(home, "state.json"), {})
        state = state if isinstance(state, dict) else {}
        requester = os.path.basename(member_world.rstrip(os.sep)) if name != "owner" else name
        used = usage.get("%s/%s" % (roster.get("name") or os.path.basename(root), name))
        if not isinstance(used, dict):
            used = usage.get(requester)
        used = used if isinstance(used, dict) else {}
        tokens = _team_number(used.get("total_tokens"))
        if not tokens:
            tokens = _team_number(used.get("prompt_tokens")) + _team_number(used.get("completion_tokens"))
        spent = {"tokens": tokens, "hours": 0, "ticks": _team_number(state.get("step")),
                 "disk_mb": round(folder_bytes(member_world) / (1024.0 * 1024.0), 6),
                 "mem_mb": None, "money_usd": _team_ledger_money(home, day)}
        limit = allocations.get(name)
        limit = limit if isinstance(limit, dict) else {key: 0 for key in TEAM_BUDGET_KEYS}
        remaining = {}
        for key in TEAM_BUDGET_KEYS:
            remaining[key] = None if spent[key] is None else round(
                _team_number(limit.get(key)) - _team_number(spent[key]), 6)
        for key in ("tokens", "ticks", "money_usd"):
            total_spent[key] += _team_number(spent[key])
        rows.append({"name": name, "role": member.get("role") or name,
                     "reports_to": member.get("reports_to"),
                     "path": member.get("path") or ".", "clock": member.get("clock") or "shared:owner",
                     "active": member.get("active", True),
                     "state": (state.get("state") or "idle") if member.get("active", True) else "stopped",
                     "busy": _team_number(state.get("busy")), "unread": _team_unread(home),
                     "today_spent": spent, "budget": limit, "remaining": remaining})
    total_spent["disk_mb"] = round(folder_bytes(root) / (1024.0 * 1024.0), 6)
    total_spent["mem_mb"] = None
    created = roster.get("created")
    if created:
        try:
            total_spent["hours"] = round(max(0, time.time() - datetime.datetime.fromisoformat(
                created).timestamp()) / 3600.0, 6)
        except (TypeError, ValueError):
            total_spent["hours"] = 0
    remaining = {key: (None if total_spent[key] is None else round(
        _team_number(total_budget.get(key)) - _team_number(total_spent[key]), 6))
                 for key in TEAM_BUDGET_KEYS}
    return {"name": roster.get("name") or os.path.basename(root), "root": root,
            "preset": roster.get("preset"), "day": day, "budget": total_budget,
            "spent": total_spent, "remaining": remaining, "members": rows}


def create_world(world, home=".", template=None, tools=None, persona=None,
                 prompts=None, llm=None, parent=None):
    world = os.path.abspath(world)
    if os.path.exists(world):
        raise ValueError("資料夾已經存在，不會蓋掉：" + world)
    home_arg = str(home or ".")
    target_home = os.path.abspath(os.path.join(world, home_arg))
    base = os.path.join(HERE, "templates", str(template or ""))

    def templated(filename, default):
        value = read_json(os.path.join(base, filename), default) if template else default
        return value

    tools = tools if isinstance(tools, dict) else templated("tools.json", {"packs": [], "tools": []})
    persona = persona if isinstance(persona, dict) else templated(
        "system-prompt.json", {"role": "system", "content": ""})
    prompts = prompts if isinstance(prompts, list) else templated("prompts.json", [])
    llm = llm if isinstance(llm, dict) else templated("llm.json", {})
    if not isinstance(tools, dict) or not isinstance(persona, dict) \
            or not isinstance(prompts, list) or not isinstance(llm, dict):
        raise ValueError("模板的 JSON 形狀不對：" + str(template))

    os.makedirs(os.path.join(world, ".aos"))
    os.makedirs(os.path.join(target_home, "inbox"), exist_ok=True)
    os.makedirs(os.path.join(target_home, "outbox"), exist_ok=True)
    inst = "aos-agent exec ."
    if home_arg != ".":
        inst += " --home " + shlex.quote(home_arg)
    with open(os.path.join(world, ".aos", "inst"), "w", encoding="utf-8") as f:
        f.write(inst + "\n")
    write_json_atomic(os.path.join(target_home, "tools.json"), tools)
    write_json_atomic(os.path.join(target_home, "system-prompt.json"), persona)
    write_json_atomic(os.path.join(target_home, "prompts.json"), prompts)
    write_json_atomic(os.path.join(target_home, "llm.json"), llm)
    write_json_atomic(os.path.join(target_home, "state.json"),
                      {"state": "idle", "step": 0, "busy": 0, "request": "",
                       "last_usage": None, "started": now_iso(), "pending": [],
                       "empty_replies": 0, "question_steps": 0})
    if isinstance(parent, dict):
        write_json_atomic(os.path.join(target_home, "parent.json"), parent)
    rel = os.path.relpath(target_home, world)
    prefix = "" if rel == "." else rel.rstrip(os.sep) + "/"
    with open(os.path.join(world, ".gitignore"), "w", encoding="utf-8") as f:
        for name in ("state.json", "llm-result.json", "side/", "inbox/", "outbox/", "kids/"):
            f.write(prefix + name + "\n")
    return target_home


def create_team_world(world, preset_dir, engine=None, budget=None):
    world = os.path.abspath(world)
    if os.path.exists(world):
        raise ValueError("資料夾已經存在，不會蓋掉：" + world)
    preset = read_json(os.path.join(preset_dir, "team.json"), None)
    if not isinstance(preset, dict) or not isinstance(preset.get("members"), list):
        raise ValueError("preset 的 team.json 形狀不對")
    members = [dict(m) for m in preset["members"] if isinstance(m, dict)]
    names = [m.get("name") for m in members]
    if len(names) != len(set(names)) or any(not NAME_OK.match(str(n or "")) for n in names):
        raise ValueError("preset 的成員名單有重複或壞名字")
    total = normalize_team_budget(preset.get("budget") or {}, budget)
    llm_path = os.environ.get("AOS_LLM_DIR") or preset.get("llm_dir") or "../llm"
    if not os.path.isabs(llm_path):
        llm_path = os.path.abspath(os.path.join(world, llm_path))
    created = datetime.datetime.now().astimezone().isoformat(timespec="seconds")

    worlds = {}
    for member in members:
        name = member["name"]
        member_world = os.path.abspath(os.path.join(world, member.get("path") or "."))
        worlds[name] = member_world
        persona_file = member.get("persona") or "%s/system-prompt.json" % name
        prompts_file = member.get("prompts") or "%s/prompts.json" % name
        persona = read_json(os.path.join(preset_dir, persona_file), None)
        prompts = read_json(os.path.join(preset_dir, prompts_file), None)
        if not isinstance(persona, dict) or not isinstance(prompts, list):
            raise ValueError("preset 的 %s 人格或起手信壞了" % name)
        member_engine = engine or member.get("engine")
        llm_conf = {"dir": os.path.relpath(llm_path, member_world), "priority": 1}
        if member_engine and member_engine not in ("cheap", "thinking"):
            llm_conf["engine"] = member_engine
        elif engine:
            llm_conf["engine"] = engine
        member["active"] = True
        parent = None if name == preset.get("leader", "owner") else {
            "name": preset.get("leader", "owner"), "dir": world,
            "clock": "own" if member.get("clock") == "own" else "shared"}
        create_world(member_world, tools={"packs": list(member.get("packs") or []), "tools": []},
                     persona=persona, prompts=prompts, llm=llm_conf, parent=parent)

    contacts = {name: path for name, path in worlds.items()}
    user_dir = os.environ.get("AOS_USER_DIR")
    for name, member_world in worlds.items():
        own_contacts = {other: path for other, path in contacts.items() if other != name}
        if name == "sales" and user_dir:
            own_contacts["user"] = os.path.abspath(user_dir)
        write_json_atomic(os.path.join(member_world, "contacts.json"), own_contacts)
    team_dir = os.path.join(world, "team")
    os.makedirs(os.path.join(team_dir, "projects"), exist_ok=True)
    os.makedirs(os.path.join(team_dir, "notes"), exist_ok=True)
    os.makedirs(os.path.join(team_dir, "files", "final"), exist_ok=True)
    for member in members:
        if member["name"] == preset.get("leader", "owner"):
            continue
        member_world = worlds[member["name"]]
        os.symlink(os.path.relpath(team_dir, member_world), os.path.join(member_world, "team"))
    for name in names:
        os.makedirs(os.path.join(team_dir, "files", name), exist_ok=True)
        with open(os.path.join(team_dir, "notes", name + ".md"), "w", encoding="utf-8") as f:
            f.write("")
    with open(os.path.join(team_dir, "notes", "shared.md"), "w", encoding="utf-8") as f:
        f.write("# 共用筆記\n")
    runtime = dict(preset)
    runtime.update({"root": world, "llm_dir": llm_path, "budget": total,
                    "created": created, "members": members})
    write_json_atomic(os.path.join(team_dir, "team.json"), runtime)
    team_contacts = dict(contacts)
    if user_dir:
        team_contacts["user"] = os.path.abspath(user_dir)
    write_json_atomic(os.path.join(team_dir, "contacts.json"), team_contacts)
    allocations = {member["name"]: _budget_part(total, _team_number(member.get("budget_pct")))
                   for member in members}
    write_json_atomic(os.path.join(team_dir, "budget.json"),
                      {"schema": "aos-team-budget/1", "total": total,
                       "allocations": allocations, "grants": [], "updated": created})
    with open(os.path.join(team_dir, "progress.md"), "w", encoding="utf-8") as f:
        f.write("# 進度\n")
    registry = {}
    for member in members:
        if member["name"] == preset.get("leader", "owner"):
            continue
        registry[member["name"]] = {
            "name": member["name"], "dir": worlds[member["name"]],
            "clock": "own" if member.get("clock") == "own" else "shared",
            "created": created, "depth": 1, "parent": world, "alive": True,
            "task": None, "reports_to": member.get("reports_to"),
        }
    write_json_atomic(os.path.join(world, "kids.json"), registry)
    inst = os.path.join(world, ".aos", "inst")
    for member in members:
        if member["name"] != preset.get("leader", "owner") and member.get("clock") != "own":
            append_line(inst, "aos-exec " + os.path.relpath(worlds[member["name"]], world))
    return runtime


def _pid_alive(pid):
    if not pid:
        return False
    try:
        os.kill(int(pid), 0)
        return True
    except OSError:
        return False


def _side_error_text(kind, result):
    why = str(result.get("error") or "不明錯誤")
    error_kind = result.get("kind_of_error")
    if error_kind == "timeout":
        return "%s 沒等到結果：%s" % (kind, why)
    if error_kind == "cancelled":
        return "%s 已取消。" % kind
    return "%s 失敗：%s" % (kind, why)


# ── 工具包拿得到的把手 ────────────────────────────────────────────────────
class Ctx:
    read_json = staticmethod(read_json)
    write_json = staticmethod(write_json_atomic)
    warn = staticmethod(warn)
    truncate = staticmethod(truncate)

    def __init__(self, world, home, state=None, loaded=None, pack=None):
        self.world = os.path.abspath(world)
        self.home = os.path.abspath(home)
        self.name = team_member_name(self.world) or os.path.basename(self.world.rstrip(os.sep)) or "agent"
        self.state = state if isinstance(state, dict) else read_json(
            os.path.join(self.home, "state.json"), {})
        if not isinstance(self.state, dict):
            self.state = {}
        self.loaded = loaded or []
        self.pack = pack

    def for_pack(self, name):
        return Ctx(self.world, self.home, self.state, self.loaded, name)

    def log(self, text):
        prefix = "%s/%s" % (self.name, self.pack) if self.pack else self.name
        print("aos-agent[%s]: %s" % (prefix, text), file=sys.stderr)

    def status(self):
        return status_of(self.world, self.home)

    def world_of(self, name_or_path):
        value = self.contacts().get(name_or_path) if isinstance(name_or_path, str) else None
        if isinstance(value, dict):
            value = value.get("dir")
        value = value if isinstance(value, str) else name_or_path
        if not isinstance(value, str) or not value:
            raise ValueError("世界名字或路徑不能空白")
        return os.path.abspath(value if os.path.isabs(value) else os.path.join(self.world, value))

    def home_of(self, world):
        return resolve_home(self.world_of(world), None)

    def clock_of(self, world):
        target = self.world_of(world)
        daemon = os.environ.get("AOS_DAEMON_DIR")
        clocks = os.path.join(daemon, "clocks") if daemon else ""
        if os.path.isdir(clocks):
            for filename in os.listdir(clocks):
                if not filename.endswith(".json"):
                    continue
                row = read_json(os.path.join(clocks, filename), None)
                if (isinstance(row, dict) and row.get("dir") and
                        os.path.realpath(row["dir"]) == os.path.realpath(target)):
                    state = row.get("state") or "unknown"
                    if state == "running" and not _pid_alive(row.get("pid")):
                        state = "stopped"
                    return {"kind": "own", "state": state}
        parent = read_json(os.path.join(resolve_home(target, None), "parent.json"), None)
        parent_world = parent.get("dir") if isinstance(parent, dict) else None
        if isinstance(parent_world, str):
            try:
                with open(os.path.join(parent_world, ".aos", "inst"),
                          encoding="utf-8", errors="replace") as f:
                    lines = f.read().splitlines()
            except OSError:
                lines = []
            for line in lines:
                raw = line.strip()
                paused = raw.startswith("# ")
                command = raw[2:].strip() if paused else raw
                if not command.startswith("aos-exec "):
                    continue
                try:
                    words = shlex.split(command)
                except ValueError:
                    words = []
                child = words[1] if len(words) == 2 else ""
                if child and os.path.realpath(os.path.join(parent_world, child)) == os.path.realpath(target):
                    return {"kind": "shared", "state": "paused" if paused else "running"}
        return {"kind": "none", "state": "missing"}

    def depth(self):
        depth, parent, seen = 0, self.parent(), set()
        while isinstance(parent, dict) and parent.get("dir"):
            path = os.path.abspath(parent["dir"])
            if path in seen:
                break
            seen.add(path)
            depth += 1
            parent = read_json(os.path.join(resolve_home(path, None), "parent.json"), None)
        return depth

    def shared_clock(self, world, action):
        target = self.world_of(world)
        parent = read_json(os.path.join(resolve_home(target, None), "parent.json"), None)
        parent_world = parent.get("dir") if isinstance(parent, dict) else None
        if not isinstance(parent_world, str):
            return False, "找不到 shared 父世界"
        path = os.path.join(parent_world, ".aos", "inst")
        try:
            with open(path, encoding="utf-8", errors="replace") as f:
                lines = f.read().splitlines()
        except OSError as e:
            return False, "讀不到父鐘：%s" % e
        found, out = False, []
        for line in lines:
            raw = line.strip()
            paused = raw.startswith("# ")
            command = raw[2:].strip() if paused else raw
            match = False
            if command.startswith("aos-exec "):
                try:
                    words = shlex.split(command)
                except ValueError:
                    words = []
                child = words[1] if len(words) == 2 else ""
                match = bool(child) and os.path.realpath(
                    os.path.join(parent_world, child)) == os.path.realpath(target)
            if not match:
                out.append(line)
                continue
            found = True
            if action == "pause":
                out.append("# " + command)
            elif action == "resume":
                out.append(command)
            elif action != "kill":
                return False, "不懂的 shared 鐘動作：%s" % action
        if not found:
            return False, "父鐘找不到這個世界"
        try:
            with open(path, "w", encoding="utf-8") as f:
                f.write("\n".join(out) + ("\n" if out else ""))
        except OSError as e:
            return False, "改不了父鐘：%s" % e
        return True, {"pause": "暫停了", "resume": "續跑了", "kill": "收掉了"}[action]

    def find_llm(self):
        return find_llm(self.home, self.world)

    def llm_dir(self):
        return llm_dir(self.home, self.world)

    def kids_dir(self):
        return os.path.join(self.home, "kids")

    def spawn(self, name, persona, clock="shared", template=None, packs=None,
              task=None, depth=None):
        return spawn(self.world, self.home, name, persona, clock, template,
                     packs=packs, task=task, depth=depth)

    def put_mail(self, target, source, content, **extra):
        target_name = target
        if isinstance(target, str) and target not in self.contacts():
            target_name = os.path.basename(str(target).rstrip(os.sep)) or str(target)
        try:
            target_world = self.world_of(target)
        except ValueError:
            self.log("找不到收件人：%s" % target)
            return None
        if not os.path.isdir(target_world):
            self.log("找不到收件人：%s" % target)
            return None
        if not isinstance(source, str) or source in ("", ".", "..") or os.path.basename(source) != source:
            self.log("信件來源名字不對：%s" % source)
            return None
        target_home = self.home_of(target_world)
        box = os.path.join(target_home, "inbox", source)
        path = os.path.join(box, aos_llm.stamp() + ".json")
        msg = dict(extra)
        msg.update({"from": self.name, "to": str(target_name), "time": now_iso(),
                    "content": str(content)})
        write_json_atomic(path, msg)
        return path

    def contacts(self):
        data = read_json(os.path.join(self.home, "contacts.json"), {})
        return data if isinstance(data, dict) else {}

    def add_contact(self, name, path):
        if not isinstance(name, str) or not name or not isinstance(path, str):
            return False
        target = os.path.abspath(os.path.join(self.world, path)) if not os.path.isabs(path) else os.path.abspath(path)
        data = self.contacts()
        data[name] = target
        write_json_atomic(os.path.join(self.home, "contacts.json"), data)
        return True

    def parent(self):
        data = read_json(os.path.join(self.home, "parent.json"), None)
        return data if isinstance(data, dict) else None

    def kids(self):
        data = read_json(os.path.join(self.home, "kids.json"), {})
        return data if isinstance(data, dict) else {}

    def send(self, kind, body, **opts):
        kind = str(kind or "side")
        if not PACK_OK.match(kind):
            raise ValueError("旁線 kind 只能用英數字與底線：" + kind)
        try:
            timeout = max(1, int(opts.pop("timeout_steps", SIDE_TIMEOUT_STEPS)))
        except (TypeError, ValueError):
            timeout = SIDE_TIMEOUT_STEPS
        target = opts.pop("target", None)
        mail_reply_to = opts.pop("mail_reply_to", None)
        if target is None and mail_reply_to is None:
            target = self.llm_dir()
            conf = read_json(os.path.join(self.home, "llm.json"), {})
            conf = conf if isinstance(conf, dict) else {}
            priority = opts.pop("priority", None)
            engine = opts.pop("engine", None)
            filename = aos_llm.write_request(
                target, body, priority=conf.get("priority") if priority is None else priority,
                engine=conf.get("engine") if engine is None else engine,
                name="%s-%s" % (self.name, kind),
                requester=opts.pop("requester", None) or team_requester(self.world) or self.name,
                kind=opts.pop("schedule_kind", None), deadline=opts.pop("deadline", None))
            request_path = os.path.join(target, "requests", filename)
        else:
            filename = "%s-%s-%s.json" % (self.name, kind, aos_llm.stamp())
            request_path = None
            if target is not None:
                target = self.world_of(target)
                request = dict(body) if isinstance(body, dict) else {"body": body}
                request.setdefault("request", filename)
                request_path = os.path.join(target, "requests", filename)
                write_json_atomic(request_path, request)
        name = os.path.splitext(filename)[0]
        pending = self.state.get("pending")
        if not isinstance(pending, list):
            pending = []
            self.state["pending"] = pending
        item = {"id": name, "kind": kind, "pack": self.pack,
                "since_step": int(self.state.get("step") or 0),
                "timeout_steps": timeout}
        if target is not None:
            item.update({"result_dir": os.path.join(target, "results"),
                         "result_name": filename, "request_path": request_path,
                         "clock_world": target})
        if mail_reply_to is not None:
            item["mail_reply_to"] = str(mail_reply_to)
        pending.append(item)
        return name

    def pending(self):
        rows = self.state.get("pending")
        return [dict(row) for row in rows if isinstance(row, dict)] if isinstance(rows, list) else []

    def sleep_until(self, kind, request_id):
        self.state["sleeping"] = {"kind": str(kind), "id": str(request_id)}

    def _mail_result(self, reply_to):
        for source in self.sources():
            for name in self.unread(source):
                for letter in self.mail_of(source, name):
                    if letter.get("reply_to") == reply_to:
                        self.mark_read(source, name)
                        return letter
        return None

    def _finish_side(self, item, result):
        result = dict(result) if isinstance(result, dict) else {"result": result}
        if result.get("error") and not result.get("kind_of_error"):
            result["kind_of_error"] = "llm"
        write_json_atomic(os.path.join(self.home, "side", item["kind"], item["id"] + ".json"), result)
        module = dict(self.loaded).get(item.get("pack"))
        hook = getattr(module, "on_result", None) if module else None
        wake = None
        if hook:
            try:
                wake = hook(self.for_pack(item.get("pack")), item["kind"], item["id"], result)
            except Exception as e:
                self.log("工具包 %s 的 on_result 出錯：%s" % (item.get("pack"), e))
        else:
            self.put_mail(self.world, item["kind"], json.dumps(result, ensure_ascii=False),
                          request=item["id"])
        sleeping = self.state.get("sleeping")
        if isinstance(sleeping, dict) and sleeping.get("id") == item["id"]:
            self.state.pop("sleeping", None)
        if result.get("error"):
            text = _side_error_text(item["kind"], result)
            self.state["last_error"] = text
            self.reply(text, error=True)
        return str(wake) if wake else None

    def collect_results(self):
        items, wake = self.pending(), []
        self.state["pending"] = []
        step = int(self.state.get("step") or 0)
        for item in items:
            result = None
            if item.get("mail_reply_to"):
                result = self._mail_result(item["mail_reply_to"])
            elif item.get("result_dir"):
                path = os.path.join(item["result_dir"], item.get("result_name") or
                                    ((item.get("id") or "") + ".json"))
                if os.path.isfile(path):
                    result = read_json(path, {"error": "結果檔讀不成 JSON"})
                    try:
                        os.remove(path)
                    except OSError:
                        pass
            elapsed = step - int(item.get("since_step") or 0)
            if result is None and elapsed >= int(item.get("timeout_steps") or SIDE_TIMEOUT_STEPS):
                result = {"error": "等了 %d 格仍沒有結果" % elapsed,
                          "kind_of_error": "timeout"}
            if result is None and item.get("clock_world") and elapsed > 0:
                clock = self.clock_of(item["clock_world"])
                if clock["kind"] == "none" or clock["state"] != "running":
                    result = {"error": "處理這筆請求的鐘沒有在跑",
                              "kind_of_error": "timeout"}
            if result is None:
                self.state["pending"].append(item)
                continue
            text = self._finish_side(item, result)
            if text:
                wake.append({"role": "user", "content": "[%s %s] %s" % (
                    item["kind"], item["id"], text)})
        return wake

    def cancel(self, request_id):
        found, left = None, []
        for item in self.pending():
            if found is None and item.get("id") == request_id:
                found = item
            else:
                left.append(item)
        if found is None:
            return False
        path = found.get("request_path")
        if path and os.path.isfile(path):
            try:
                os.remove(path)
            except OSError:
                pass
        self.state["pending"] = left
        self._finish_side(found, {"error": "請求已取消", "kind_of_error": "cancelled"})
        return True

    def _clock(self, op, where, interval=None, no_wait=False):
        if not os.environ.get("AOS_DAEMON_DIR"):
            return False, "沒設 AOS_DAEMON_DIR"
        target = os.path.abspath(os.path.join(self.world, where)) if not os.path.isabs(where) else os.path.abspath(where)
        cmd = [os.path.join(HERE, "aos-daemon"), op, target]
        config_path = None
        try:
            if op == "register" and interval is not None:
                fd, config_path = tempfile.mkstemp(prefix="aos-clock-", suffix=".json")
                os.close(fd)
                write_json_atomic(config_path, {"interval": interval})
                cmd += ["--config", config_path]
            if no_wait:
                cmd.append("--no-wait")
            done = subprocess.run(cmd, capture_output=True, text=True)
        finally:
            if config_path:
                try:
                    os.remove(config_path)
                except OSError:
                    pass
        lines = (done.stderr or done.stdout or "").strip().splitlines()
        msg = lines[-1].replace("aos-daemon: ", "", 1) if lines else ("完成" if done.returncode == 0 else "失敗")
        return done.returncode == 0, msg

    def register_clock(self, where, interval=None, no_wait=False):
        return self._clock("register", where, interval, no_wait)

    def unregister_clock(self, where):
        return self._clock("unregister", where)

    def pause_clock(self, where):
        return self._clock("pause", where)

    def continue_clock(self, where):
        return self._clock("continue", where)

    def reply(self, text, **extra):
        msg = dict(extra)
        msg.update({"role": "assistant", "content": str(text)})
        step = int(self.state.get("step") or 0) + 1
        path = os.path.join(self.home, "outbox", "%04d.json" % step)
        suffix = 1
        while os.path.exists(path):
            path = os.path.join(self.home, "outbox", "%04d-%02d.json" % (step, suffix))
            suffix += 1
        write_json_atomic(path, msg)
        for name, module in self.loaded:
            hook = getattr(module, "on_reply", None)
            if not hook:
                continue
            try:
                hook(self.for_pack(name), msg)
            except Exception as e:
                self.log("工具包 %s 的 on_reply 出錯：%s" % (name, e))
        parent = self.parent()
        if isinstance(parent, dict) and parent.get("dir"):
            self.put_mail(parent["dir"], "kid-" + self.name, str(text))
        return path

    # 信箱
    def sources(self):
        return sources(self.home)

    def unread(self, source):
        return unread_names(self.home, source)

    def read_done(self, source):
        return read_names(self.home, source)

    def mail_of(self, source, name):
        return mail_of(self.home, source, name)

    def mark_read(self, source, name):
        return mark_read(self.home, source, name)

    def preview(self, mail):
        return preview(mail)


# ── 生小孩 ──────────────────────────────────────────────────────────────────
def append_line(path, line):
    old = ""
    if os.path.isfile(path):
        with open(path, encoding="utf-8", errors="replace") as f:
            old = f.read()
    if line in [l.strip() for l in old.splitlines()]:
        return False
    os.makedirs(os.path.dirname(path), exist_ok=True)
    if old and not old.endswith("\n"):
        old += "\n"
    with open(path, "w", encoding="utf-8") as f:
        f.write(old + line + "\n")
    return True


def spawn(world, home, name, persona, clock="shared", template=None, packs=None,
          task=None, depth=None):
    if not NAME_OK.match(name or ""):
        return False, "子名只能用英數字、底線、減號：" + str(name)
    llm_abs = find_llm(home, world)
    if not llm_abs:
        return False, "找不到 LLM 資料夾（llm.json／AOS_LLM_DIR／../llm 都沒有），生不出子 agent"
    child = os.path.join(home, "kids", name)
    if os.path.exists(child):
        return False, "這個名字已經被佔走了：" + child
    template_dir = os.path.join(HERE, "templates", str(template or ""))
    has_template = bool(template and os.path.isdir(template_dir))
    parent_packs, extra = tools_conf(home)
    child_tools = read_json(os.path.join(template_dir, "tools.json"), {}) if has_template else {}
    child_tools = child_tools if isinstance(child_tools, dict) else {}
    if isinstance(packs, list):
        child_tools["packs"] = [p for p in packs if isinstance(p, str)]
    elif not has_template or not isinstance(child_tools.get("packs"), list):
        child_tools["packs"] = parent_packs
    if "tools" not in child_tools:
        child_tools["tools"] = extra
    conf = read_json(os.path.join(home, "llm.json"), {})
    conf = conf if isinstance(conf, dict) else {}
    child_conf = read_json(os.path.join(template_dir, "llm.json"), {}) if has_template else {}
    child_conf = child_conf if isinstance(child_conf, dict) else {}
    child_conf["dir"] = os.path.relpath(llm_abs, child)
    for key in ("priority", "engine"):
        if conf.get(key) is not None:
            child_conf[key] = conf[key]
    parent_name = os.path.basename(os.path.abspath(world).rstrip(os.sep)) or "parent"
    prompts = read_json(os.path.join(template_dir, "prompts.json"), []) if has_template else []
    create_world(child, tools=child_tools,
                 persona={"role": "system", "content": persona}, prompts=prompts,
                 llm=child_conf, parent={"name": parent_name, "dir": os.path.abspath(world),
                                         "clock": clock})
    parent_ctx = Ctx(world, home)
    child_ctx = Ctx(child, child)
    parent_ctx.add_contact(name, child)
    child_ctx.add_contact(parent_name, world)
    registry = parent_ctx.kids()
    child_depth = int(depth) if isinstance(depth, int) and not isinstance(depth, bool) \
        else parent_ctx.depth() + 1
    registry[name] = {
        "name": name, "dir": os.path.abspath(child), "clock": clock,
        "created": datetime.datetime.now().astimezone().isoformat(timespec="seconds"),
        "depth": child_depth, "parent": os.path.abspath(world), "alive": True,
        "task": str(task) if task is not None else None,
    }
    write_json_atomic(os.path.join(home, "kids.json"), registry)
    if task is not None:
        parent_ctx.put_mail(child, "parent", task)

    rel = os.path.relpath(child, world)
    if clock == "shared":
        append_line(os.path.join(world, ".aos", "inst"), "aos-exec " + rel)
        return True, "%s 建好了（shared，父走一格它走一格）" % child
    if os.environ.get("AOS_DAEMON_DIR"):
        daemon = os.path.join(HERE, "aos-daemon")
        rc = subprocess.run([daemon, "register", child, "--no-wait"]).returncode
        if rc == 0:
            return True, "%s 建好了（own，已經跟 daemon 要了一個時鐘）" % child
        return True, ("%s 建好了（own），但跟 daemon 要時鐘失敗（退出碼 %d），"
                      "要自己開 aos-loop %s --keep-inst 它才會走" % (child, rc, child))
    return True, ("%s 建好了（own），但沒設 AOS_DAEMON_DIR，沒跟 daemon 要時鐘，"
                  "要自己開 aos-loop %s --keep-inst 它才會走" % (child, child))


def append_history(home, msgs):
    if not msgs:
        return
    history = read_json(os.path.join(home, "prompts.json"), [])
    history = history if isinstance(history, list) else []
    write_json(os.path.join(home, "prompts.json"), history + list(msgs))


def put_mail(home, source, text, sender=None):
    box = os.path.join(inbox_dir(home), source)
    os.makedirs(box, exist_ok=True)
    path = os.path.join(box, aos_llm.stamp() + ".json")
    write_json_atomic(path, {"from": sender or source, "time": now_iso(), "content": text})
    return path


def outbox_names(box):
    if not os.path.isdir(box):
        return []
    return sorted(n for n in os.listdir(box) if n.endswith(".json"))


def outbox_content(box, name):
    msg = read_json(os.path.join(box, name), {})
    return (msg.get("content") or "") if isinstance(msg, dict) else ""
