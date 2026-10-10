"""budget 共用路徑、業務鍵、grant 判定與本地回合鐘。"""
import argparse
import fcntl
import os
import re
import shlex
import signal
import time

HERE = os.path.dirname(os.path.abspath(__file__))
from aos7_fs import N, OK, completed_round, fact, is_int, json_sha256, say_line  # noqa: E402

ID_RE = re.compile(r"^[A-Za-z0-9_-]{1,32}$")
CLOCK = "completed_tock"
GATEWAY = "fakeapi"                 # call 包裝程式的入口（假 API）
PARTIAL_SETTLE = True
RESOURCE = "fakeapi.calls"
GRANT_FIELDS = ("grant", "budget", "holder", "resource", "gateway", "amount", "clock", "from", "until", "delegate")
POLL = 0.02
ORPHAN_ROUNDS = 3                   # 孤兒回條：帳看到它之後本 node 再完成這麼多回合仍沒人讀走才刪（spec §9）


# ---------- 共用 ----------

class Bud:
    """一個預算資料夾 `<node>/budget/<id>/` 的路徑。"""

    def __init__(self, path):
        self.dir = os.path.abspath(path)
        self.id = os.path.basename(self.dir)
        self.node = os.path.dirname(os.path.dirname(self.dir))

    def p(self, *a):
        return os.path.join(self.dir, *a)


def not_running(bud):
    """「帳任務沒在跑」的人話（別包照用）：結尾是可直接複製的起帳指令。"""
    return "帳任務沒在跑，什麼都沒送。另開一個終端起帳任務並讓它開著，再跑一次：cd %s && python3 %s ledger %s" % (
        shlex.quote(bud.node), shlex.quote(os.path.join(HERE, "bin", "aos7-budget")),
        shlex.quote(os.path.relpath(bud.dir, bud.node)))


def say(msg):
    say_line("aos7-budget: ", msg)


class ArgumentParser(argparse.ArgumentParser):
    def error(self, message):
        say(message.rstrip("。.") + "。用法看 aos7-budget --help")
        self.exit(2)


def ledger_running(bud, wait=0.5):
    """唯讀試共享鎖；帳持獨占鎖才算運行，給剛起的帳 wait 秒。"""
    end = time.monotonic() + wait
    while True:
        try:
            fd = os.open(bud.p("ledger.lock"), os.O_RDONLY)
        except FileNotFoundError:
            pass
        else:
            try:
                try:
                    fcntl.flock(fd, fcntl.LOCK_SH | fcntl.LOCK_NB)
                except BlockingIOError:
                    return True
                fcntl.flock(fd, fcntl.LOCK_UN)
            finally:
                os.close(fd)
        remaining = end - time.monotonic()
        if remaining <= 0:
            return False
        time.sleep(min(0.05, remaining))


def sha(obj):
    return json_sha256(obj)


def make_key(budget, holder, request):
    return {"budget": budget, "holder": holder, "request": request}


def kid_of(key):
    """業務鍵 K＝(budget, holder, request) 的檔名用識別。"""
    return sha([key["budget"], key["holder"], key["request"]])[:20]


def digest_of(key, content):
    """同一個 K 的業務內容雜湊：attempt、slot#run 等傳輸資訊不在裡面（藍圖 §3 操作去重）。"""
    return sha({"key": key, "content": content})


def test_crash(bud, point):
    """測試用的 SIGKILL 點（spec §7）：預算資料夾有 `.crash` 寫著這個點就刪檔、殺掉。

    在任務裡（有 AOS7_TASK）殺整個程序群組，模擬槽被收（包裝程式的結果就不會寫）；否則只殺自己。"""
    path = bud.p(".crash")
    try:
        with open(path) as f:
            want = f.read().strip()
    except OSError:
        return
    if want != point:
        return
    os.unlink(path)
    if os.environ.get("AOS7_TASK"):
        os.killpg(os.getpgid(0), signal.SIGKILL)
    os.kill(os.getpid(), signal.SIGKILL)


# ---------- 時鐘與 grant（spec §2） ----------

def completed_tock(node):
    """本 node 的 completed_tock：round.json closed 取 round、open 取 round−1；其餘（不存在、讀不到、壞）＝None 未知。"""
    return completed_round(os.path.join(node, ".aos", "round.json"))


def grant_issue(g, budget_id):
    """grant 內容的問題（None＝格式合）。子 grant 另由 judge 判 denied。"""
    if not isinstance(g, dict):
        return "grant 不是物件"
    miss = [k for k in GRANT_FIELDS if k not in g]
    if miss:
        return "grant 缺欄 %s" % miss
    for k in ("amount", "from", "until"):
        if not is_int(g[k]) or g[k] < 0:
            return "grant.%s 要是非負整數" % k
    if g["from"] > g["until"]:
        return "grant.from 大於 until"
    if g["clock"] != CLOCK:
        return "grant.clock 只准 %s（v1 只有本 node 的回合）" % CLOCK
    if g["budget"] != budget_id:
        return "grant.budget %r 跟預算資料夾 %r 不同" % (g["budget"], budget_id)
    return None


def is_child(g):
    """子 grant（v1 不支援再分）：帶 parent，或 delegate 不是 false。"""
    return "parent" in g or g.get("delegate") is not False


def load_grant(bud):
    """回 (grant 或 None, 雜湊 或 None, 說明)。讀不到、壞＝None（未知，不是沒有限制）。"""
    st, g = fact(bud.p("grant.json"))
    if st != OK:
        return None, None, "grant.json %s" % ("不存在" if st == N else g)
    return g, sha(g), None


def judge(bud, holder, resource, gateway, ledger):
    """grant 判定（spec §2）：回 (ok|denied|not_yet|unknown, 說明, c)。ledger 給帳的內容（比 grant 雜湊與 clock_hw）。"""
    g, gs, why = load_grant(bud)
    if g is None:
        return "unknown", why, None
    if gs != ledger.get("grant_sha"):
        return "unknown", "grant.json 跟開帳時不同（發行者給的應是固定內容）", None
    issue = grant_issue(g, bud.id)
    if issue:
        return "unknown", issue, None
    if is_child(g):
        return "denied", "子 grant（parent／delegate）v1 不支援", None
    for k, v in (("holder", holder), ("resource", resource), ("gateway", gateway)):
        if g[k] != v:
            return "denied", "%s 不符：grant 是 %r，請求是 %r" % (k, g[k], v), None
    c = completed_tock(bud.node)
    if c is None:
        return "unknown", "時鐘未知（round.json 沒有合法值）", None
    if is_int(ledger.get("clock_hw")) and c < ledger["clock_hw"]:
        return "unknown", "時鐘倒退（c=%d < 帳看過的 %d）" % (c, ledger["clock_hw"]), c
    if c < g["from"]:
        return "not_yet", "還沒生效（c=%d < from=%d）" % (c, g["from"]), c
    if c >= g["until"]:
        return "denied", "已到期（c=%d ≥ until=%d）" % (c, g["until"]), c
    return "ok", None, c

