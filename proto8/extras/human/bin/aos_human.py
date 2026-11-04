"""aos_human - aos-say／aos-listen 共用的小零件（aos-chat 11-03 封存）（給人用的 CLI，2026-10-24）。純標準庫、只在 Linux 上（讀 /proc）。

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
import aos_ws  # noqa: E402  放訊息、等答案、讀 stack（proto8/lib/aos/aos_ws.py）
from aos_ws import STAGES, Error, letter_key, names, where, read  # noqa: E402,F401

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
    """把一句話寄進 queue（aos_ws.put：一則 user message、aos-post send --ordered）。回信件名稱。"""
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
    AOS_STACK 是 daemon 的小格，給 --stack 那個小格〔aos-daemon-ctl where --stack 名字，11-03 起工作區不建 .stack 捷徑〕就認得出來；samefile 比）。
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


def daemon_held(w):
    """這個 stack 是不是 daemon 表上留著、行程不在的那一列（phase stopped 或 sleeping）：回 (名字, phase, 是不是 eca, daemon 的 stack)，
    不是就 None（11-03 procs；sleeping＝daemon 收工時還在跑、睡下的，11-04 加）。
    看哪個 daemon：$AOS_DAEMON_STACK，加上 stack 在預設小格 <D>/procs/<名字>/ 時的那個 <D>；讀它的 procs_state.json，
    列上的 stack 跟這個 stack 是同一個（samefile）才算。eca＝那個 stack 裡有 eca.json（同 aos-eca 認的）。讀不到就當不是。"""
    ds = [os.environ.get("AOS_DAEMON_STACK") or ""]
    if os.path.basename(os.path.dirname(w.stack.rstrip("/"))) == "procs":
        ds.append(os.path.dirname(os.path.dirname(w.stack.rstrip("/"))))
    for d in ds:
        try:
            with open(os.path.join(d, "procs_state.json"), encoding="utf-8") as f:
                procs = json.load(f).get("procs") or {}
        except (OSError, ValueError, AttributeError):
            continue
        for name, r in procs.items() if isinstance(procs, dict) else ():
            if isinstance(r, dict) and r.get("phase") in ("stopped", "sleeping") and isinstance(r.get("stack"), str)                     and _same(r["stack"], w.stack):
                return name, r["phase"], os.path.isfile(os.path.join(w.stack, "eca.json")), os.path.abspath(d)
    return None


def run_hint(w):
    hit = daemon_held(w)
    if hit and hit[1] == "sleeping":   # daemon 收工時睡下的：daemon 再開（adopt）第一圈自己 wake，不用 start（11-04）
        name, _, _, d = hit
        return "它掛在 daemon 上睡著（%s 是 sleeping：daemon 收工時睡下的），重開 daemon 它會自己醒：aos-exec <daemon 資料夾>（那個 daemon 的 stack 是 %s）" % (name, d)
    if hit:
        name, _, eca, _ = hit
        return "它在 daemon 表上停著（%s 是 stopped），叫它起來：%s %s" % (name, "aos-eca start" if eca else "aos-daemon-ctl start", name)
    return "另開一個終端機跑它：aos-exec --ws %s <agent 資料夾>" % w.ws


def stuck_hint(w, sig):
    """這封還沒答、又沒人在跑時，說一句它在 queue 的哪裡、怎麼跑起來。
    11-03 起不看 trace.jsonl（使用者「整個拿掉」，thinking 2026-11-03-trace）：不再說「停在哪格」、也不再判「沒人認領」（LetterUnclaimed）；
    錯誤一行在跑它的那個終端機（P-20），外部 coding agent 看 aos-eca status。"""
    if "cur" in where(w.stack, sig):
        return "%s 在 queue 的 cur/（認領了、還沒答完），但目前沒有程式在跑這隻 agent（停了的話錯誤一行在跑它的那個終端機）。%s" % (sig, run_hint(w))
    return "%s 還在 queue 的 new/，但目前沒有程式在跑這隻 agent。%s" % (sig, run_hint(w))
