"""aos_human - aos-say／aos-listen／aos-chat 共用的小零件（給人用的 CLI，2026-10-24）。純標準庫、只在 Linux 上（讀 /proc）。

10-30 起照 agent 對話協議（CONVENTION P-42；thinking 2026-10-30-agent-lifecycle A-7、A-8）：只碰 agent 的 stack——
queue＝<stack>/queue/（說話＝寄一封有序的信）、history＝<stack>/history.jsonl（回答＝最新那則沒有 tool_calls 的 assistant）、
aos-loop 的 ctl／state 窗。stack＝--stack ＞ $AOS_STACK ＞ <工作區>/.stack/（N-57）；工作區＝--ws ＞ $AOS_WS ＞ cwd（同 aos-exec）。
工作區的 new/ cur/ out/ done/（舊協議，P-11 的 10-30 改口）不再認。這裡不碰 agent 的定義資料夾、不改 stack 裡的東西（寄信除外）。
設計與代定：proto8/thinking/2026-10-24-say-listen.md、2026-10-30-agent-lifecycle.md。"""
import json, os, sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.realpath(__file__)), "..", "..", "..", "bin"))
import aos_flags  # noqa: E402  旗標規則同 aos-exec（proto8/bin/aos_flags.py）
sys.dont_write_bytecode = True                  # 不在庫的資料夾留 __pycache__
sys.path.insert(0, os.path.join(os.path.dirname(os.path.realpath(__file__)), "..", "..", "..", "lib", "aos"))
import aos_ws  # noqa: E402  放訊息、等答案、讀 stack：跟 aos-ai 共用一份（proto8/lib/aos/aos_ws.py）
from aos_ws import STAGES, Error, names, where, read  # noqa: E402,F401

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


class Where:
    """一隻 agent 在哪：工作區 ws、stack。"""

    def __init__(self, ws_opt, stack_opt):
        ws = ws_opt if ws_opt not in (None, "-") else (os.environ.get("AOS_WS") or ".")
        self.ws = os.path.abspath(ws)
        if not os.path.isdir(self.ws):
            raise Error("WsMissing", "工作區不存在：%s" % self.ws)
        self.stack = aos_ws.stack_of(self.ws, stack_opt)


def say(w, text):
    """把一句話寄進 queue（aos_ws.put：一則 user message、aos-post send --ordered）。回信號。"""
    return aos_ws.put(w.stack, text)


def _same(a, b):
    try:
        return os.path.samefile(a, b)
    except OSError:
        return False


def runners(w):
    """有哪些行程在跑這隻 agent：/proc 裡 argv[0] 是 aos-loop／aos-fsm／aos-exec／aos-daemon、
    環境變數 AOS_STACK＝這個 stack 或 AOS_WS＝這個工作區（沒設 AOS_STACK 時）的。只靠 /proc（eca 10-30 C 結論 9、F 結論 18：
    server.txt 自己報名那招刪了——外部 coding agent 也是 aos-loop 包著 aos-eca-turn 在跑，掃得到；掛在 daemon 底下的，子 loop 的
    AOS_STACK 是 daemon 的小格，工作區的 .stack 是指過去的 symlink，samefile 認得出來）。
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
                env = dict(kv.decode("utf-8", "replace").split("=", 1) for kv in f.read().split(b"\0") if b"=" in kv)
        except OSError:
            continue
        if "AOS_STACK" in env:
            hit = _same(env["AOS_STACK"], w.stack)
        else:
            hit = "AOS_WS" in env and _same(env["AOS_WS"], w.ws) and _same(os.path.join(w.ws, ".stack"), w.stack)
        if hit:
            found.append((int(d), argv0))
    return found


def last_trace(w):
    """stack 裡 trace.jsonl 最後一行（fsm〔含 aos-round〕每次一行 state；aos-eca-turn 與 10-30 前的舊 round 是 unit）；沒有＝None。"""
    return aos_ws.last_jsonl(os.path.join(w.stack, "trace.jsonl"))


def run_hint(w):
    return "另開一個終端機跑它：aos-exec --ws %s <agent 資料夾>（或用 aos-chat <agent 資料夾>，由 chat 幫你跑）" % w.ws


def failure(t):
    """trace 最後一行失敗時的一句「停在 X 那格、結束碼 N」；沒失敗＝None。"""
    if not aos_ws.failed(t):
        return None
    how = "訊號 %s" % t["signal"] if t.get("signal") is not None else "結束碼 %s" % t.get("code")
    return "停在 %s 那格、%s" % (aos_ws.unit_of(t), how)


OLD_PROTOCOL = ("這隻 agent 可能還是舊協議（讀工作區的 new/*.txt、不收 queue，例 demo/agent-dan；改用走 queue 的版本，例 agent-dan-q），"
                "或 loop 的 max 先到了")


def unclaimed(w, sig):
    """sig 還在 queue 的 new/，可是 stack 的 trace.jsonl 比這封信新＝它寄出之後有程式跑過這個 stack、卻沒認領它
    （10-30 晚真腦實測發現 2；「現在沒人在跑」由呼叫的人先確認）。trace 或信讀不到＝False。"""
    try:
        return (os.stat(os.path.join(w.stack, "trace.jsonl")).st_mtime_ns
                > os.stat(os.path.join(aos_ws.box_of(w.stack), "new", sig)).st_mtime_ns)
    except OSError:
        return False


def unclaimed_hint(w, sig):
    return ("%s 還在 queue 的 new/ 沒人認領，可是它寄出之後已經有程式跑過這個 stack、現在停了（trace.jsonl 比這封新）：%s"
            % (sig, OLD_PROTOCOL))


def stuck_hint(w, sig):
    """這封還沒答、又沒人在跑時，說一句它停在哪。"""
    stages = where(w.stack, sig)
    if stages == ["new"] and unclaimed(w, sig):
        return unclaimed_hint(w, sig)
    why = failure(last_trace(w))
    if "cur" in stages and why:
        return ("%s 做到一半停了：上次%s（錯誤一行在跑它的那個終端機）。修好再跑一次會接著做這封。%s"
                % (sig, why, run_hint(w)))
    if "cur" in stages:
        return "%s 在 queue 的 cur/（認領了、還沒答完），但目前沒有程式在跑這隻 agent。%s" % (sig, run_hint(w))
    return "%s 還在 queue 的 new/，但目前沒有程式在跑這隻 agent。%s" % (sig, run_hint(w))


class Tail:
    """跟著看 stack 裡的 trace.jsonl（每格一行）與 history.jsonl 新長出來的行，翻成給人看的短行（工具呼叫、工具回了什麼、每格的結果）。
    從建立當下的檔尾開始（之前的不重印）。"""

    def __init__(self, w):
        self.stack = w.stack
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
                if size < self.pos[f]:            # 檔被換掉、變短了（compact、人換了 stack）：從頭
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
                what = "退 10"
            out.append("· %s%s%s" % (aos_ws.unit_of(t), " " + what if what else "",
                                     " %sms" % t["elapsed_ms"] if "elapsed_ms" in t else ""))
        return out


def short(s, n=80):
    s = s.rstrip("\n").replace("\n", " ⏎ ")       # 結尾換行去掉；中間的換行印成 ⏎，不印字面 \n
    return s if len(s) <= n else s[:n] + "…"


def status_lines(w):
    """一份快照：誰在跑、aos-loop 的 phase、最後一格、queue 各格幾封、最後一封壞信（有才印）、history 幾則。"""
    st = w.stack
    run = runners(w)
    t = last_trace(w)
    loop = aos_ws.loop_state(st)
    out = ["工作區   %s" % w.ws,
           "stack    %s" % st,
           "在跑     %s" % ("、".join("%s（pid %d）" % (p, i) for i, p in run) if run else "沒有（%s）" % run_hint(w)),
           "loop     %s" % ("phase %s（state.json）" % loop.get("phase") if loop else "-（沒有 state.json：沒開 aos-loop 的 state 窗）"),
           "認領中   %s" % ("、".join(l.strip() for l in (read(os.path.join(st, "current.txt")) or "").splitlines() if l.strip()) or "-"),
           "queue    new %d、cur %d、done %d" % tuple(len(names(st, s)) for s in STAGES)]
    if t:
        why = failure(t)
        out.append("最後一格 %s %s（%s）%s" % (aos_ws.unit_of(t), "訊號 %s" % t["signal"] if t.get("signal") is not None else "退 %s" % t.get("code"),
                                          t.get("started_at", "?"), "  ← 卡住了：錯誤一行在跑它的那個終端機" if why else ""))
    warning = (read(os.path.join(st, "letter_warning.txt")) or "").strip()
    if warning:
        out.append("壞信     %s（letter_warning.txt：只留最後一封）" % warning)
    hist = read(os.path.join(st, "history.jsonl"))
    if hist is not None:
        out.append("對話     history.jsonl %d 則（要忘記＝換 stack）" % len([l for l in hist.splitlines() if l.strip()]))
    return out
