"""aos_ai_base - aos-ai 各命令共用的底：路徑與常數、錯誤 Fail 與提示表、輸出／讀寫小工具、PATH（child_env）、aos-tools 轉叫、認行程，
以及 Root（只寫 root 底下）、Agent、Daemon（讀寫背景 aos-daemon 的 ctl／state）。

10-31 自 bin/aos-ai 拆出（行為不變）。"""
import fcntl, json, os, re, shutil, subprocess, sys, time
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent               # proto8/extras/ai_tools/bin
PROTO8 = HERE.parent.parent.parent
TEMPLATES = PROTO8 / "demo"
DAN_TOOLS = PROTO8 / "lib" / "aos"                   # 給 agent 掛的工具（--tool）：proto8/lib/aos（10-24 遷移前是 ai_tools/dan_tools）
IMPLS = ("aos-exec", "aos-loop", "aos-fsm", "aos-daemon", "aos-directive")
BIN_DIRS = [PROTO8 / "impls" / n / "bin" for n in IMPLS + ("aos-json", "aos-post")] + [PROTO8 / "bin", HERE]   # aos-post：ask 寄信（10-30）
TEMPLATE = "agent-nia"                               # spawn 預設的範本（10-30 起；之前 agent-dan，舊協議 ask 說不到）
sys.path.insert(0, str(HERE))
sys.dont_write_bytecode = True                  # 不在庫的資料夾留 __pycache__
sys.path.insert(0, str(PROTO8 / "lib" / "aos"))
import aos_ws  # noqa: E402  放題、等答案、讀 stack：跟 proto8/extras/human 共用一份（lib/aos/aos_ws.py，10-24 遷移）
NAME_RE = re.compile(r"[a-z0-9][a-z0-9_-]{0,63}\Z")
LINE_RE = re.compile(r"([a-z][a-z0-9_-]*): (?:([A-Z][A-Za-z]+) )?(.*)")
TEXT_MAX = 4000
HINTS = {   # 下層的錯誤代號 → 下一步（只放常見的）
    "CommandMissing": "PATH 上找不到某支程式：先建 proto8/impls（wf/workflows/testing.md）",
    "EntryMissing": "目標裡沒有 _entry：aos-ai templates 看可用範本",
    "BrainFailed": "腦連不上：設 AOS_BRAIN_URL（家機 LiteLLM http://localhost:4000/v1），或拿掉它用假腦",
    "ReplyBad": "腦回的不是 OpenAI 形狀：換模型，或 aos-ai history 看最後一則",
    "ToolUnknown": "腦叫了沒登記的工具：aos-ai history 看最後一則；工具放 agents/<名>/agent/tools/<工具>/、"
                   "登記進 agents/<名>/agent/tools.json（aos-tools --file 那份 add 工具資料夾）",
    "ToolFailed": "工具起不來（aos-tools、aos-exec 不在 PATH？）；工具自己退非 0 不會停在這裡，那行已回給腦",
    "ToolsBad": "tools.json 登記的工具有壞的：aos-tools --file agents/<名>/agent/tools.json ls 看是哪個",
    "ArgumentsBad": "參數不對：看原因那句",
    "QuestionMissing": "沒有題目：先 aos-ai ask",
    "PostFailed": "寄不進 queue：PATH 上要有 proto8/impls/aos-post/bin（先建 impls）",
    "HistoryBad": "history.jsonl 壞了：人工看 ws/.stack/history.jsonl",
}
AGAIN = "修好後再 aos-ai run 一次，會從同一格、同一題接著做"


class Fail(Exception):
    def __init__(self, code, reason, hint=None):
        super().__init__(code)
        self.code, self.reason, self.hint = code, reason, hint


def now():
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds")


def out(obj):
    print(json.dumps(obj, ensure_ascii=False))


def clip(text):
    return text if len(text) <= TEXT_MAX else text[:TEXT_MAX] + "…（截斷，全文看 path）"


def write_atomic(path, text):                        # N-05：先寫 . 開頭的暫存檔再改名
    path = Path(path)
    tmp = path.with_name("." + path.name + ".tmp")
    tmp.write_text(text, encoding="utf-8")
    os.replace(tmp, path)


def read_json(path, default=None):
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return default


def tail_jsonl(path, n):
    return aos_ws.tail_jsonl(str(path), n)


def parse_errors(stderr):
    """stderr 每行「程式名: 代號 原因」拆成物件；認不出的行放 raw。"""
    rows = []
    for line in stderr.splitlines():
        if not line.strip():
            continue
        m = LINE_RE.match(line)
        rows.append({"prog": m.group(1), "code": m.group(2), "reason": m.group(3)} if m else {"raw": line[:500]})
    return rows


def hint_for(errors):
    for e in errors:
        if e.get("code") in HINTS:
            return HINTS[e["code"]] + "；" + AGAIN
    return AGAIN if errors else None


def child_env(extra=None):
    """PATH 前面放 impls 各支、proto8/bin、aos-ai 自己（aos 的程式不動 PATH，呼叫者放；ideas § 24）。"""
    e = dict(os.environ)
    bins = [str(b) for b in BIN_DIRS if b.is_dir()]
    e["PATH"] = os.pathsep.join(bins + [p for p in e.get("PATH", "").split(os.pathsep) if p and p not in bins])
    e.update(extra or {})
    return e


def which(prog):
    return shutil.which(prog, path=child_env()["PATH"])


def aos_tools(agent, *args):
    """aos-tools --file <agent>/tools.json ……（aos-tools 在 proto8/bin，child_env 已放進 PATH）→ CompletedProcess。"""
    prog = which("aos-tools")
    if not prog:
        raise Fail("CommandMissing", "PATH 上沒有 aos-tools（proto8/bin）", HINTS["CommandMissing"])
    return subprocess.run([prog, "--file", str(Path(agent) / "tools.json")] + list(args), capture_output=True,
                          text=True, env=child_env(), stdin=subprocess.DEVNULL)


def register_tool(agent, tool_dir):
    """把 tool_dir 登記進 agent 的 tools.json（aos-tools add，存絕對路徑）；不成＝Fail。"""
    r = aos_tools(agent, "add", os.path.abspath(tool_dir))
    if r.returncode != 0:
        err = (r.stderr.strip().splitlines() or ["aos-tools 退 %d" % r.returncode])[-1]
        raise Fail("ToolsBad", "登記 %s 進 %s/tools.json 失敗：%s" % (Path(tool_dir).name, agent, err), HINTS["ToolsBad"])


def tool_rows(agent):
    """agent 的工具＝它 tools.json 登記的（aos-tools ls）→ {"tools": [名…]}；登記了壞的工具＝多一個 tools_error（那行錯）。"""
    r = aos_tools(agent, "ls", "--json")
    if r.returncode != 0:
        return {"tools": [], "tools_error": (r.stderr.strip().splitlines() or ["aos-tools 退 %d" % r.returncode])[-1]}
    return {"tools": [t["name"] for t in json.loads(r.stdout)]}


def ticks(pid):                                       # /proc/<pid>/stat 第 22 欄（N-17：pid＋started_at_ticks 認行程）
    try:
        stat = Path("/proc/%d/stat" % pid).read_text()
        return int(stat[stat.rindex(")") + 2:].split()[19])
    except (OSError, ValueError, IndexError):
        return None


def alive(pid, started):
    return bool(pid) and ticks(pid) is not None and (started is None or ticks(pid) == started)


# ---------- root 與路徑（安全邊界：只寫 root 底下） ----------

class Root:
    def __init__(self, given):
        self.dir = Path(given or os.environ.get("AOS_AI_ROOT") or os.getcwd()).resolve()
        if not self.dir.is_dir():
            raise Fail("RootMissing", "工作資料夾不在：%s" % self.dir, "先 mkdir，或用 --root 指別的")

    def inside(self, path, what="路徑"):
        p = Path(path).resolve()
        if p != self.dir and self.dir not in p.parents:
            raise Fail("PathBad", "%s 在工作資料夾外面：%s（root＝%s）" % (what, p, self.dir), "只能動 root 底下的東西")
        return p

    def agent(self, name, must=True):
        if not isinstance(name, str) or not NAME_RE.match(name):
            raise Fail("NameBad", "agent 名字不合：%r" % (name,), "只用小寫英數、_、-，開頭英數，最長 64")
        a = Agent(self.dir / "agents" / name, name)
        if must and not a.agent.is_dir():
            raise Fail("AgentMissing", "沒有這隻 agent：%s" % name, "先 aos-ai spawn %s" % name)
        return a


class Agent:
    def __init__(self, base, name):
        self.base, self.name = base, name
        self.agent, self.ws = base / "agent", base / "ws"
        self.stack = self.ws / ".stack"

    def ls(self, d):
        """queue（ws/.stack/queue/）某一格的信號。"""
        return aos_ws.names(str(self.stack), d)

    def waiting(self):
        return aos_ws.waiting(str(self.stack))

    def answers(self):
        return aos_ws.answers(str(self.stack))


# ---------- 背景：一個 root 一個 aos-daemon ----------

class Daemon:
    def __init__(self, root):
        self.dir = root.dir / "daemon"
        self.stack = self.dir / ".stack"
        self.cfg, self.ctl, self.state = self.dir / "daemon.json", self.stack / "ctl.json", self.stack / "state.json"
        # 10-29 aos-daemon 拆窗：名單的手把、子項表另外一對（daemon.json 沒寫＝這兩個預設檔名）
        self.lctl, self.lstate = self.stack / "loops_ctl.json", self.stack / "loops_state.json"

    def read_state(self):
        st = read_json(self.state)
        return st if isinstance(st, dict) else None

    def read_lstate(self):
        st = read_json(self.lstate)
        if not isinstance(st, dict):
            return None
        loops = st.get("loops")
        if isinstance(loops, dict) and "$ref" in loops:   # 超過 100 列會切檔：交給 aos-directive 解
            d = which("aos-directive")
            if d:
                r = subprocess.run([d], input=self.lstate.read_text(encoding="utf-8"), capture_output=True,
                                   text=True, cwd=self.stack)
                st = read_json_text(r.stdout) or st
        return st

    def running(self):
        st = self.read_state()
        if st and st.get("phase") not in ("done", "stopped") and alive(st.get("pid"), st.get("started_at_ticks")):
            return st.get("pid")
        up = read_json(self.dir / "up.json") or {}
        if alive(up.get("pid"), up.get("started_at_ticks")) and not (st and st.get("pid") == up.get("pid")
                                                                       and st.get("phase") in ("done", "stopped")):
            return up.get("pid")
        return None

    def row(self, name):
        st = self.read_lstate() or {}
        return (st.get("loops") or {}).get(name) if self.running() else None

    def write_ctl(self, change, path=None):
        """ctl 是宣告（N-06）：讀現在那份、改、seq＋1、整份換掉；同時只一個 aos-ai 寫（flock）。回 seq。
        path 沒給＝ctl.json（stopped 這類 loop 面向）；名單寫 self.lctl（loops_ctl.json，10-29 拆窗）。"""
        path = path or self.ctl
        self.stack.mkdir(parents=True, exist_ok=True)
        with open(self.dir / ".ctl.flock", "w") as lock:
            fcntl.flock(lock, fcntl.LOCK_EX)
            ctl = read_json(path, {})
            ctl = ctl if isinstance(ctl, dict) else {}
            change(ctl)
            ctl["seq"] = int(ctl.get("seq") or 0) + 1
            write_atomic(path, json.dumps(ctl, ensure_ascii=False, indent=1) + "\n")
            return ctl["seq"]

    def wait_seq(self, seq, until=None, timeout=8.0):
        """等 daemon 讀到這份 loops_ctl（loops_state 的 ctl_seq 回音）；until(loops_state) 另給條件。回 (loops_state, 是否等到)。"""
        end = time.monotonic() + timeout
        while True:
            st = self.read_lstate() or {}
            if (st.get("ctl_seq") or 0) >= seq and (until is None or until(st)):
                return st, True
            if time.monotonic() > end or not self.running():
                return st, False
            time.sleep(0.1)


def read_json_text(text):
    try:
        return json.loads(text)
    except ValueError:
        return None



def read_text(path):
    try:
        return Path(path).read_text(encoding="utf-8").strip()
    except OSError:
        return None


def opt1(o, k):
    return o.get(k, [None])[-1]


def need(pos, n, usage):
    if len(pos) < n:
        raise Fail("ArgumentsBad", "usage: aos-ai " + usage)


def env_pairs(o):
    pairs = {}
    for kv in o.get("env", []):
        if "=" not in kv:
            raise Fail("ArgumentsBad", "--env 要寫 K=V：%s" % kv)
        k, v = kv.split("=", 1)
        pairs[k] = v
    return pairs
