"""aos_agent — 標準 agent 的共用零件（給 `aos-agent` 跟 `aos-user` import）。

**一個 agent 就是一個世界資料夾**。世界資料夾的 `.aos/` 裡只有一句 `inst`，agent 自己的
東西全放在**本體資料夾**（home）底下，home 放哪由 `--home` 說了算（相對於世界資料夾，
預設 `.`，也就是世界資料夾本身）：

    xxx/.aos/inst            aos-agent exec . --home agent
    xxx/<home>/system-prompt.json   人格 {"role":"system","content":"..."}
    xxx/<home>/prompts.json         記憶（OpenAI messages 陣列）
    xxx/<home>/tools.json           {"packs": [...], "tools": [...]}
    xxx/<home>/llm.json             {"dir": "../llm", "priority": 1, "engine": "..."}（可有可無）
    xxx/<home>/state.json           {"state","step","busy","request","last_usage","started","announced"}
    xxx/<home>/inbox/<來源>/*.json       沒讀的信
    xxx/<home>/inbox/<來源>/read/*.json  讀過的信
    xxx/<home>/outbox/<四位數>.json      它自己說的話
    xxx/<home>/llm-result.json      上次 LLM 的整包原始結果
    xxx/<home>/kids/<名字>/         它生的小孩（每個都是完整的世界資料夾）

`llm.json` 的 `dir` 相對於**世界資料夾**（不是 home），所以 `../llm` 一直都是隔壁那個
LLM 資料夾。沒寫就看 `AOS_LLM_DIR`，再沒有就找 `../llm`。

這裡放的是**兩支指令都要用的東西**：home 怎麼解、信箱怎麼掃、工具包怎麼載、LLM 資料夾
怎麼找、自我狀態怎麼算、怎麼生小孩、怎麼投一封信。狀態機本身在 `aos-agent`，給人用的殼
在 `aos-user`。**工具包一包一檔**放在 `packs/<名字>.py`，每一包自帶 `TOOLS`（工具定義）、
`PROMPT`（預設 prompt 段落）、`run(name, args, ctx)`（怎麼跑）——先找 agent 自己的
`<home>/packs/`，再找 aos 內建的 `packs/`；`ctx` 就是下面那個 `Ctx`。

信箱（IPC v0.1）：一封信是一個 JSON 物件 `{"from","time","content"}`（多帶別的鍵也行），
或是一串這種物件的 JSON 陣列。來源就是 `inbox/` 底下的資料夾名（user／team／kernel／
別的 agent 都行，第一次收到信才建）。**`idle` 那格掃一遍 `inbox/*/`，只要有未讀就去問
LLM**——但不會把信整包塞進 prompt，只加一句「你有新信：team 1 封。用信箱工具去讀」，
剩下讓模型自己用信箱工具讀。**同一封信只通知一次**（通知過的記在 state.json 的
`announced`），模型不去讀也不會被一直重新叫醒。**唯一的例外是來源 `user`**：它的內容
直接當成一則 user 訊息接進記憶（前面加 `[user] `），檔案當場搬進 `read/`——這樣跟 agent
講話才是一個來回。
"""
import datetime
import importlib.util
import json
import os
import re
import subprocess
import sys
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


def resolve_home(world, home_opt):
    """本體資料夾在哪：--home 有給就用它；沒給就去 .aos/inst 撈 `--home X`；都沒有就是 `.`。"""
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
    """讀 tools.json → (工具包名字, 額外的 shell 工具)。舊格式（一個純陣列）當成沒有工具包。"""
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
    """工具包一包一檔：先找 agent 自己的 `<home>/packs/<名字>.py`，再找 aos 內建的 `packs/`。"""
    if not PACK_OK.match(name or ""):
        return None
    for base in (os.path.join(home, "packs"), os.path.join(HERE, "packs")):
        path = os.path.join(base, name + ".py")
        if os.path.isfile(path):
            return path
    return None


def load_pack(home, name):
    """把一個工具包的 .py 載進來。載不到就回 None（呼叫的人自己印一句、繼續跑）。"""
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
    """讀 tools.json，把每個工具包載進來 → ([(名字, 模組)], 額外的 shell 工具)。

    認不得的包名（`packs/<名字>.py` 不在）印一行到 stderr 就跳過，agent 照樣跑；
    模型如果去叫那包裡的工具，會拿到一個「沒有這個工具」的結果。
    """
    names, extra = tools_conf(home)
    loaded = []
    for name in names:
        module = load_pack(home, name)
        if module is None:
            warn("認不得的工具包：%s（packs/%s.py 不在），跳過" % (name, name))
            continue
        loaded.append((name, module))
    return loaded, extra


def tool_specs(loaded, extra):
    """送給模型看的工具清單（OpenAI functions）。工具包的排前面，同名工具包贏。"""
    specs, seen = [], set()
    for _name, module in loaded:
        for t in getattr(module, "TOOLS", []):
            if t.get("name") and t["name"] not in seen:
                seen.add(t["name"])
                specs.append(t)
    for t in extra:
        if t.get("name") and t["name"] not in seen:
            seen.add(t["name"])
            specs.append({"name": t["name"], "description": t.get("description", ""),
                          "parameters": t.get("parameters", {})})
    return specs


def system_text(home, loaded):
    """system 訊息 ＝ 人格 ＋ 每個開著的工具包各一段預設 prompt。"""
    persona = read_json(os.path.join(home, "system-prompt.json"), {})
    text = (persona.get("content") or "") if isinstance(persona, dict) else ""
    paras = [getattr(m, "PROMPT", "") for _n, m in loaded if getattr(m, "PROMPT", "")]
    if paras:
        text = (text + "\n\n" if text else "") + "\n\n".join(paras)
    return text


def pack_owners(loaded):
    """工具名字 → 哪個工具包負責跑它。"""
    owners = {}
    for _name, module in loaded:
        for t in getattr(module, "TOOLS", []):
            if t.get("name") and t["name"] not in owners:
                owners[t["name"]] = module
    return owners


def run_custom(ctx, extra, name, args_text):
    """tools.json 的 `tools[]`：一個工具就是一句 shell 指令，參數 JSON 從 stdin 進去。"""
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
    """一封信 → 一串信件物件（一個檔可以放一封，也可以放一個陣列裝好幾封）。"""
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
    """掃一遍信箱 → (這格要接進記憶的訊息, 新的「已通知過」清單)。

    來源 `user` 短路：內容直接變一則 user 訊息（前面加 `[user] `），檔案當場搬去 read/。
    其他來源不進 prompt，只在最後加一句摘要（哪個來源幾封未讀），讓模型自己用工具去讀。

    **通知過的信不會再通知一次**：`announced`（記在 state.json）記著「已經跟模型講過的
    未讀信」，只有出現沒講過的信才會拿摘要去吵它。不然模型看到摘要卻懶得讀信，
    idle 就會一直重新叫 LLM，錢燒不完。信被讀掉（搬進 read/）就自動從清單掉出去。
    """
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
    """LLM 資料夾在哪：llm.json 的 dir（相對於**世界資料夾**）→ AOS_LLM_DIR → ../llm。找不到回 None。"""
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


def today_usage(home, world):
    """今天這個 agent 用的那台引擎，在 LLM 資料夾帳本裡的那一列（撈不到就 None）。"""
    d = find_llm(home, world)
    if not d or not os.path.isdir(d):
        return None
    engines = read_json(os.path.join(d, "engines.json"), [])
    if not isinstance(engines, list) or not engines:
        return None
    conf = read_json(os.path.join(home, "llm.json"), {})
    conf = conf if isinstance(conf, dict) else {}
    want = conf.get("engine") or (read_json(os.path.join(d, "defaults.json"), {}) or {}).get("engine")
    engine = None
    for e in engines:
        if isinstance(e, dict) and want and e.get("name") == want:
            engine = e
            break
    if engine is None:
        engine = engines[0] if isinstance(engines[0], dict) else {}
    book = read_json(os.path.join(d, "usage", "%s.json" % datetime.date.today().isoformat()), {})
    if not isinstance(book, dict):
        return None
    return book.get("%s|%s" % (engine.get("base_url"), engine.get("model")))


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
    return {"step": st.get("step") or 0, "busy": st.get("busy") or 0,
            "started": started, "uptime_s": uptime,
            "history_messages": len(history),
            "history_chars": len(json.dumps(history, ensure_ascii=False)),
            "folder_bytes": folder_bytes(world),
            "last_usage": st.get("last_usage"),
            "today_usage": today_usage(home, world)}


# ── 工具包拿得到的把手 ────────────────────────────────────────────────────
class Ctx:
    """交給工具包 `run(name, args, ctx)` 的小把手：世界在哪、本體在哪，
    外加幾個現成的家務函式（讀寫 json、掃信箱、看自己、生小孩、找 LLM 資料夾）。"""

    read_json = staticmethod(read_json)
    write_json = staticmethod(write_json)
    warn = staticmethod(warn)
    truncate = staticmethod(truncate)

    def __init__(self, world, home):
        self.world = world
        self.home = home

    def state(self):
        st = read_json(os.path.join(self.home, "state.json"), {})
        return st if isinstance(st, dict) else {}

    def status(self):
        return status_of(self.world, self.home)

    def find_llm(self):
        return find_llm(self.home, self.world)

    def llm_dir(self):
        return llm_dir(self.home, self.world)

    def kids_dir(self):
        return os.path.join(self.home, "kids")

    def spawn(self, name, persona, clock="shared"):
        return spawn(self.world, self.home, name, persona, clock)

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
    """在檔尾加一行；已經有這一行就不加。"""
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


def spawn(world, home, name, persona, clock="shared"):
    """生一個子 agent 在 <home>/kids/<name>/。回 (成功嗎, 一句話)。

    子自己就是一個完整的世界資料夾，本體平鋪在它底下（home＝`.`），
    `.aos/inst` 是 `aos-agent exec .`。工具抄父的一份，llm.json 指到同一個 LLM 資料夾。
    """
    if not NAME_OK.match(name or ""):
        return False, "子名只能用英數字、底線、減號：" + str(name)
    llm_abs = find_llm(home, world)
    if not llm_abs:
        return False, "找不到 LLM 資料夾（llm.json／AOS_LLM_DIR／../llm 都沒有），生不出子 agent"
    child = os.path.join(home, "kids", name)
    if os.path.exists(child):
        return False, "這個名字已經被佔走了：" + child
    os.makedirs(child)

    write_json(os.path.join(child, "system-prompt.json"), {"role": "system", "content": persona})
    write_json(os.path.join(child, "prompts.json"), [])
    packs, extra = tools_conf(home)
    write_json(os.path.join(child, "tools.json"), {"packs": packs, "tools": extra})
    write_json(os.path.join(child, "state.json"),
               {"state": "idle", "step": 0, "busy": 0, "request": "",
                "last_usage": None, "started": now_iso()})
    conf = read_json(os.path.join(home, "llm.json"), {})
    conf = conf if isinstance(conf, dict) else {}
    child_conf = {"dir": os.path.relpath(llm_abs, child)}
    for key in ("priority", "engine"):
        if conf.get(key) is not None:
            child_conf[key] = conf[key]
    write_json(os.path.join(child, "llm.json"), child_conf)
    os.makedirs(os.path.join(child, ".aos"), exist_ok=True)
    with open(os.path.join(child, ".aos", "inst"), "w", encoding="utf-8") as f:
        f.write(CHILD_INST)

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
    """往 inbox/<source>/ 丟一封信，回寫到哪個檔。"""
    box = os.path.join(inbox_dir(home), source)
    os.makedirs(box, exist_ok=True)
    path = os.path.join(box, aos_llm.stamp() + ".json")
    write_json(path, {"from": sender or source, "time": now_iso(), "content": text})
    return path


def outbox_names(box):
    if not os.path.isdir(box):
        return []
    return sorted(n for n in os.listdir(box) if n.endswith(".json"))


def outbox_content(box, name):
    msg = read_json(os.path.join(box, name), {})
    return (msg.get("content") or "") if isinstance(msg, dict) else ""


