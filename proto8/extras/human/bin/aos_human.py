"""aos_human - aos-say／aos-listen／aos-chat 共用的小零件（給人用的 CLI，2026-10-24）。純標準庫、只在 Linux 上（讀 /proc）。

工作區的形狀照 CONVENTION 第四節（P-11～P-14）：題目 $AOS_WS/new/<題名>、認領 cur/、答案 out/<題名>、做完 done/；
agent 的 stack 預設 $AOS_WS/.stack/（N-57；外面設了 AOS_STACK 就用它，同 aos-exec）。
這裡只「放題目、看答案、看 stack」，不碰 agent 的定義資料夾、不改 stack 裡的東西。設計與代定：proto8/thinking/2026-10-24-say-listen.md。"""
import json, os, sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.realpath(__file__)), "..", "..", "..", "bin"))
import aos_flags  # noqa: E402  旗標規則同 aos-exec（proto8/bin/aos_flags.py）
sys.dont_write_bytecode = True                  # 不在庫的資料夾留 __pycache__
sys.path.insert(0, os.path.join(os.path.dirname(os.path.realpath(__file__)), "..", "..", "..", "lib", "aos"))
import aos_ws  # noqa: E402  放題、等答案、讀 stack：跟 aos-ai 共用一份（proto8/lib/aos/aos_ws.py，10-24 遷移）
from aos_ws import STAGES, Error, names, where, read, new_name  # noqa: E402,F401  三支 CLI 照舊用 h.names、h.Error…

POLL = 0.2                                     # 看一次的間隔（秒）
RUNNERS = ("aos-loop", "aos-fsm", "aos-exec", "aos-daemon")   # 算「有人在跑」的程式名


def die(prog, code, msg):
    print("%s: %s %s" % (prog, code, msg), file=sys.stderr)
    sys.exit(1)


def note(msg):
    """提醒（不是錯）：stderr 一行，括號包起來、不帶程式名，跟錯誤一行分得開。"""
    print("（%s）" % msg, file=sys.stderr, flush=True)


def parse(prog, usage, argv, flags, switches=None):
    try:
        return aos_flags.parse(argv, flags, switches)
    except aos_flags.Error as e:
        die(prog, e.code, "usage: %s（%s）" % (usage, e))


def workspace(opt):
    """--ws ＞ $AOS_WS ＞ cwd（同 aos-exec，N-58）；轉絕對路徑；不在＝WsMissing。"""
    ws = opt if opt not in (None, "-") else (os.environ.get("AOS_WS") or ".")
    ws = os.path.abspath(ws)
    if not os.path.isdir(ws):
        raise Error("WsMissing", "工作區不存在：%s" % ws)
    return ws


def stack_of(ws):
    return os.environ.get("AOS_STACK") or os.path.join(ws, ".stack")


def say(ws, text, name=None):
    """把一句話變成一道題丟進 new/（做法在 aos_ws.put：先寫工作區頂層的 .say-<pid>.tmp、再 link 成 new/<題名>）。回題名。"""
    return aos_ws.put(ws, text, name, tag="say")


def runners(ws):
    """有哪些行程在跑這個工作區：/proc 裡環境變數 AOS_WS＝這個工作區、argv[0] 是 aos-loop／aos-fsm／aos-exec／aos-daemon 的，
    加上 stack 裡 server.txt 自己報名的（declared）。
    回 [(pid, 程式名)]。讀不到的行程（別的使用者的）跳過。"""
    found, me = [], os.getpid()
    for d in os.listdir("/proc"):
        if not d.isdigit() or int(d) == me:
            continue
        try:
            with open("/proc/%s/cmdline" % d, "rb") as f:
                argv0 = os.path.basename(f.read().split(b"\0", 1)[0].decode("utf-8", "replace"))
            if argv0 not in RUNNERS:
                continue
            with open("/proc/%s/environ" % d, "rb") as f:
                env = f.read().split(b"\0")
        except OSError:
            continue
        for kv in env:
            if kv.startswith(b"AOS_WS="):
                try:
                    if os.path.samefile(kv[7:].decode("utf-8", "replace"), ws):
                        found.append((int(d), argv0))
                except OSError:
                    pass
                break
    return found + declared(ws)


def declared(ws):
    """不靠 /proc 猜的服務者（10-28）：stack 裡的 server.txt 寫「<pid> <程式名>」（例：aos-hub-kernel 替 claude 代答），
    那個 pid 還活著就算有人在跑。回 [(pid, 程式名)]。"""
    line = (read(os.path.join(stack_of(ws), "server.txt")) or "").split()
    if len(line) < 2 or not line[0].isdigit() or not os.path.exists("/proc/%s" % line[0]):
        return []
    return [(int(line[0]), line[1])]


def last_trace(ws):
    """stack 裡 trace.jsonl 最後一行（fsm 每次一行，P-07）；沒有＝None。"""
    return aos_ws.last_jsonl(os.path.join(stack_of(ws), "trace.jsonl"))


def run_hint(ws):
    return "另開一個終端機跑它：aos-exec --ws %s <agent 資料夾>（或用 aos-chat <agent 資料夾>，由 chat 幫你跑）" % ws


def stuck_hint(ws, name):
    """題目還沒答、又沒人在跑時，說一句它停在哪。"""
    stages = where(ws, name)
    t = last_trace(ws)
    if "cur" in stages and t and t.get("code") not in (0, 10):
        return ("題目 %s 做到一半停了：上次停在 %s 格、結束碼 %s（錯誤一行在跑它的那個終端機）。修好再跑一次會接著做這題。%s"
                % (name, t.get("state"), t.get("code") if t.get("signal") is None else "訊號 %s" % t.get("signal"), run_hint(ws)))
    if "cur" in stages:
        return "題目 %s 在 cur/（認領了、還沒做完），但目前沒有程式在跑這個工作區。%s" % (name, run_hint(ws))
    return "題目 %s 還在 new/，但目前沒有程式在跑這個工作區。%s" % (name, run_hint(ws))


class Tail:
    """跟著看 stack 裡的 trace.jsonl（每格一行）與 history.jsonl（agent-dan 的對話，P-41）新長出來的行，翻成給人看的短行。
    從建立當下的檔尾開始（之前的不重印）。"""

    def __init__(self, ws):
        self.stack = stack_of(ws)
        self.pos = {f: self._size(f) for f in ("trace.jsonl", "history.jsonl")}
        self.tool_names = {}

    def _size(self, f):
        try:
            return os.path.getsize(os.path.join(self.stack, f))
        except OSError:
            return 0

    def _new_lines(self, f):
        path = os.path.join(self.stack, f)
        try:
            with open(path, "rb") as fh:
                size = os.fstat(fh.fileno()).st_size
                if size < self.pos[f]:            # 檔被換掉、變短了（例如人換了 stack）：從頭
                    self.pos[f] = 0
                fh.seek(self.pos[f])
                data = fh.read()
        except OSError:
            return []
        end = data.rfind(b"\n") + 1               # 只收完整的行，寫到一半的留到下次
        self.pos[f] += end
        out = []
        for line in data[:end].decode("utf-8", "replace").splitlines():
            try:
                out.append(json.loads(line))
            except ValueError:
                pass
        return out

    def lines(self):
        out = []
        for m in self._new_lines("history.jsonl"):
            if not isinstance(m, dict):
                continue
            for c in m.get("tool_calls") or []:
                try:
                    fn = c["function"]
                    self.tool_names[c.get("id")] = fn["name"]
                    out.append("[叫工具 %s %s]" % (fn["name"], short(fn.get("arguments") or "")))
                except (KeyError, TypeError):
                    pass
            if m.get("role") == "tool":
                out.append("[%s 回 %s]" % (self.tool_names.get(m.get("tool_call_id"), "工具"), short(m.get("content") or "")))
        for t in self._new_lines("trace.jsonl"):
            if not isinstance(t, dict):
                continue
            code, sig = t.get("code"), t.get("signal")
            what = "訊號 %s" % sig if sig is not None else ("" if code == 0 else "退 %s" % code)
            if code == 10:
                what = "退 10（沒題了，停）"
            out.append("· %s%s%s" % (t.get("state"), " " + what if what else "",
                                     " %sms" % t["elapsed_ms"] if "elapsed_ms" in t else ""))
        return out


def short(s, n=80):
    s = s.rstrip("\n").replace("\n", " ⏎ ")       # 結尾換行去掉；中間的換行印成 ⏎，不印字面 \n
    return s if len(s) <= n else s[:n] + "…"


def status_lines(ws):
    """一份快照：誰在跑、停在哪一格、正在做哪題、各階段幾題、最後一格的結果。"""
    st = stack_of(ws)
    run = runners(ws)
    t = last_trace(ws)
    out = ["工作區   %s" % ws,
           "在跑     %s" % ("、".join("%s（pid %d）" % (p, i) for i, p in run) if run else "沒有（%s）" % run_hint(ws)),
           "狀態     %s" % ((read(os.path.join(st, "state.txt")) or "").strip() or "-"),
           "最近一題 %s" % ((read(os.path.join(st, "current.txt")) or "").strip() or "-"),
           "題目     new %d、cur %d、out %d、done %d" % tuple(len(names(ws, s)) for s in STAGES)]
    if t:
        ok = t.get("code") in (0, 10) and t.get("signal") is None
        out.append("最後一格 %s %s（%s）%s" % (t.get("state"), "訊號 %s" % t["signal"] if t.get("signal") is not None else "退 %s" % t.get("code"),
                                          t.get("started_at", "?"), "" if ok else "  ← 卡住了：錯誤一行在跑它的那個終端機"))
    hist = read(os.path.join(st, "history.jsonl"))
    if hist is not None:
        out.append("對話     history.jsonl %d 則（要忘記＝換 stack）" % len([l for l in hist.splitlines() if l.strip()]))
    return out
