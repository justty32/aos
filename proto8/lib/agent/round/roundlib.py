"""roundlib - aos-round 五個格（idle、think、act、more、finish）共用的函數：找格、叫格、讀 history／current、endpoint 選換、on_error、問腦。

設計：proto8/thinking/2026-10-30-aos-round.md § B（第 2 步；函數從舊的 `_entry` 搬來，trace 那段拿掉——trace 只留 fsm 的一格一行，衝突 5）。
每格開頭 `roundlib.main("<格>", 那格的函數)`：解 argv（agent 資料夾絕對路徑）、要 AOS_STACK、設下面幾個模組變數，
跑那格的函數（回結束碼），抓 Exit、自己這層的錯印一行「round/<格>: 代號 原因」，以碼退出。
叫格：`aos-parts --file <agent>/parts.json which --json 槽`，退 10＝沒掛（queue、history、act、endpoint/<名> 是必要的＝PartMissing）；
  拿到就 `aos-exec 路徑 <agent> [子命令]`，註冊檔的 env 疊上去，AOS_STACK、AOS_WS 原樣傳（P-16）。
格失敗（非 0）＝以那個碼退，stderr 不轉述；格退了它不該退的 10＝UnitFailed、退 1。"""
import json, os, subprocess, sys

NOT_FOUND = 10
REQUIRED = ("queue", "history", "act")
NAME = "round"                    # main() 設成 round/<格>
AGENT = STACK = PARTS = None      # main() 設


class Exit(Exception):
    """結束這格：code＝結束碼；err 有值＝自己這層的錯（印一行）。"""

    def __init__(self, code, err=None, reason=None):
        super().__init__(reason)
        self.code, self.err, self.reason = code, err, reason


def fail(err, reason):
    raise Exit(1, err, reason)


def start(cell):
    global NAME, AGENT, STACK, PARTS
    NAME = "round/" + cell
    args = sys.argv[1:]
    if len(args) != 1:
        fail("ArgumentsBad", "usage: aos-exec <%s 格> <agent 資料夾絕對路徑>" % cell)
    AGENT = args[0]
    if not os.path.isabs(AGENT) or not os.path.isdir(AGENT):
        fail("AgentBad", "agent 資料夾要是存在的絕對路徑（aos-exec 走進格以後 cwd 不在 agent 那邊），收到 %r" % AGENT)
    STACK = os.environ.get("AOS_STACK")
    if not STACK:
        fail("StackMissing", "沒設定 AOS_STACK")
    PARTS = os.path.join(AGENT, "parts.json")


def main(cell, body):
    """跑一格：body() 回結束碼。"""
    try:
        start(cell)
        raise Exit(body())
    except Exit as e:
        if e.err:
            print("%s: %s %s" % (NAME, e.err, str(e.reason).replace("\n", " ")), file=sys.stderr)
        sys.exit(e.code)


def max_retries():
    v = os.environ.get("MAX_RETRIES")
    if v in (None, ""):
        return 3
    try:
        n = int(v)
        if n < 0:
            raise ValueError
    except ValueError:
        fail("SettingBad", "MAX_RETRIES 要是 ≥0 的整數，收到 %r" % v)
    return n


# ---- 叫格 ----

def which(slot):
    """槽 → {"path", "env"}；沒掛＝None（必要的格＝PartMissing）。"""
    try:
        r = subprocess.run(["aos-parts", "--file", PARTS, "which", "--json", slot],
                           stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, text=True)   # stderr 不吞：aos-parts 自己說哪裡壞
    except OSError as e:
        fail("PartsBad", "aos-parts 起不來：%s" % e)
    if r.returncode == NOT_FOUND:
        if slot in REQUIRED or slot.startswith("endpoint/"):
            fail("PartMissing", "沒掛 %s 格（%s 沒登記、%s 也沒有）" % (slot, PARTS, os.path.join(AGENT, slot)))
        return None
    if r.returncode != 0:
        fail("PartsBad", "aos-parts which %s 退 %d" % (slot, r.returncode))
    try:
        got = json.loads(r.stdout)
        return {"path": got["path"], "env": {k: str(v) for k, v in (got.get("env") or {}).items()}}
    except (ValueError, KeyError, TypeError, AttributeError) as e:
        fail("PartsBad", "aos-parts which --json 印的不是 {path, env}：%s" % e)


def run(slot, got, sub=(), stdin="", extra_env=None, keep_err=False):
    """aos-exec 那格；回 CompletedProcess。keep_err＝把 stderr 收下（endpoint：要給 on_error），收下的照樣印出去。"""
    env = dict(os.environ)
    env.update(extra_env or {})
    env.update(got["env"])
    try:
        r = subprocess.run(["aos-exec", got["path"], AGENT] + list(sub), input=stdin, stdout=subprocess.PIPE,
                           stderr=subprocess.PIPE if keep_err else None, text=True, env=env)
    except OSError as e:
        fail("UnitFailed", "%s 起不來（aos-exec）：%s" % (" ".join((slot,) + tuple(sub)), e))
    if keep_err and r.stderr:
        sys.stderr.write(r.stderr)
        sys.stderr.flush()
    return r


def check(slot, sub, r, ok):
    """結束碼不在 ok 裡＝以那個碼退（10 不往外傳，改說 UnitFailed 退 1）。"""
    if r.returncode not in ok:
        if r.returncode == NOT_FOUND:
            fail("UnitFailed", "%s 退 10（這裡不該是 10）" % " ".join((slot,) + tuple(sub)))
        raise Exit(r.returncode)
    return r


def must(slot, sub=(), stdin="", ok=(0,)):
    """必要的格。"""
    return check(slot, sub, run(slot, which(slot), sub, stdin), ok)


def hook(point, stdin="", ok=(0,)):
    """掛勾：沒掛＝None。"""
    slot = "hook/" + point
    got = which(slot)
    return None if got is None else check(slot, (), run(slot, got, (), stdin), ok)


def one_json(text, who):
    try:
        m = json.loads(text)
    except ValueError as e:
        fail("MessageBad", "%s 印的不是一則 JSON：%s" % (who, e))
    if not isinstance(m, dict):
        fail("MessageBad", "%s 印的不是 JSON 物件" % who)
    return m


def dumps(m):
    return json.dumps(m, ensure_ascii=False)


# ---- queue 與 history ----

def names(stage):
    """queue 的某一格（$AOS_STACK/queue/<格>）裡的信號；. 開頭的不算（N-05）。"""
    try:
        return sorted(n for n in os.listdir(os.path.join(STACK, "queue", stage)) if not n.startswith("."))
    except (FileNotFoundError, NotADirectoryError):
        return []


def listed():
    """$AOS_STACK/current.txt 列的信號＝queue claim 已接進 history 的。"""
    try:
        with open(os.path.join(STACK, "current.txt"), encoding="utf-8") as f:
            return {l.strip() for l in f if l.strip()}
    except FileNotFoundError:
        return set()
    except OSError as e:
        fail("HistoryBad", "讀不了 current.txt：%s" % e)


def history():
    r = must("history", ("read",))
    try:
        rows = json.loads(r.stdout)
    except ValueError as e:
        fail("HistoryBad", "history read 印的不是 JSON：%s" % e)
    if not isinstance(rows, list) or not all(isinstance(m, dict) for m in rows):
        fail("HistoryBad", "history read 印的不是 JSON 物件的陣列")
    return rows


def unanswered(rows):
    """最後一則 assistant 的 tool_calls 裡還沒有 tool 回的那幾個（它後面只有 tool）→ (那則, 沒回的)；不是這種情形＝None。"""
    answered = set()
    for m in reversed(rows):
        if m.get("role") == "tool":
            answered.add(m.get("tool_call_id"))
            continue
        if m.get("role") != "assistant":
            return None
        calls = m.get("tool_calls") or []
        left = [c for c in calls if not (isinstance(c, dict) and c.get("id") in answered)]
        return (m, left) if calls else None
    return None


def pending(rows):
    """最後一則 assistant 還有沒回的 tool_calls＝那則只留沒回的那幾個；沒有＝None。"""
    p = unanswered(rows)
    return dict(p[0], tool_calls=p[1]) if p and p[1] else None


# ---- 問腦 ----

def tools():
    try:
        r = subprocess.run(["aos-tools", "--file", os.path.join(AGENT, "tools.json"), "ls", "--json"],
                           stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, text=True)
    except OSError as e:
        fail("ToolsBad", "aos-tools 起不來：%s" % e)
    if r.returncode != 0:
        fail("ToolsBad", "aos-tools ls 退 %d" % r.returncode)
    out = []
    for t in json.loads(r.stdout):                    # 照 demo/agent-dan/brain.py：description／parameters 以外的 key 忽略
        function = {"name": t["name"]}
        function.update({k: t["tooldef"][k] for k in ("description", "parameters") if k in (t.get("tooldef") or {})})
        out.append({"type": "function", "function": function})
    return out


def system():
    p = os.path.join(AGENT, "system.txt")
    if not os.path.exists(p):
        return []
    with open(p, encoding="utf-8") as f:
        return [{"role": "system", "content": f.read()}]   # 每次從檔讀，不存進 history


def endpoint_name():
    try:
        with open(os.path.join(STACK, "endpoint.txt"), encoding="utf-8") as f:
            return f.read().strip() or "default"
    except FileNotFoundError:
        return "default"
    except OSError as e:
        fail("SettingBad", "讀不了 endpoint.txt：%s" % e)


def candidates():
    """parts.json 的 endpoint/<名> 與 <agent>/endpoint/ 底下的名字聯集，排序。"""
    found = set()
    try:
        with open(PARTS, encoding="utf-8") as f:
            parts = json.load(f).get("parts")
    except FileNotFoundError:
        parts = {}
    except (OSError, ValueError, AttributeError) as e:
        fail("PartsBad", "%s 讀不了：%s" % (PARTS, e))
    if isinstance(parts, dict) and "$ref" not in parts and "$env" not in parts:
        slots = parts.keys()
    else:                                               # parts 是指示詞：交給 aos-parts 整份解
        r = subprocess.run(["aos-parts", "--file", PARTS, "ls", "--json"], stdin=subprocess.DEVNULL,
                           stdout=subprocess.PIPE, text=True)
        if r.returncode != 0:
            fail("PartsBad", "aos-parts ls 退 %d" % r.returncode)
        slots = [p["slot"] for p in json.loads(r.stdout)]
    found.update(s.split("/", 1)[1] for s in slots if s.startswith("endpoint/"))
    try:
        found.update(n for n in os.listdir(os.path.join(AGENT, "endpoint")) if not n.startswith("."))
    except (FileNotFoundError, NotADirectoryError):
        pass
    return sorted(found)


def switch(current):
    c = candidates()
    nxt = c[(c.index(current) + 1) % len(c)] if current in c else (c[0] if c else current)
    tmp = os.path.join(STACK, ".endpoint.txt.tmp")
    try:
        with open(tmp, "w", encoding="utf-8") as f:
            f.write(nxt + "\n")
        os.replace(tmp, os.path.join(STACK, "endpoint.txt"))   # N-05
    except OSError as e:
        fail("WriteFailed", "寫不了 endpoint.txt：%s" % e)


def on_error(err_line):
    got = which("hook/on_error")
    if got is None:
        return "stop"                                   # 沒掛＝stop（P-20 預設停）
    r = run("hook/on_error", got, (), err_line + "\n")
    word = r.stdout.strip()
    return word if r.returncode == 0 and word in ("retry", "switch") else "stop"


def ask(rows, retries):
    """pre_think → endpoint/<目前的>（失敗問 on_error：retry／switch 最多重來 retries 次）→ 一則 assistant。"""
    if hook("pre_think") is not None:
        rows = history()                                # pre_think（compact）可能換了 history
    body = {"messages": system() + rows, "tools": tools()}
    tries = 0
    while True:
        name = endpoint_name()
        slot = "endpoint/" + name
        r = run(slot, which(slot), (), dumps(body) + "\n", {"ENDPOINT_NAME": name}, keep_err=True)
        if r.returncode == 0:
            return one_json(r.stdout.strip().splitlines()[-1] if r.stdout.strip() else "", slot)
        lines = [l for l in (r.stderr or "").splitlines() if l.strip()]
        word = on_error(lines[-1] if lines else "%s 退 %d" % (slot, r.returncode))
        if word == "stop":
            raise Exit(r.returncode if r.returncode != NOT_FOUND else 1)
        tries += 1
        if tries > retries:
            fail("EndpointFailed", "on_error 說 %s，但這次問腦已經重來 %d 次（MAX_RETRIES=%d）" % (word, retries, retries))
        if word == "switch":
            switch(name)
