# aos/apps/agent/hints.py - 讀 agent 狀態（含仍活著的 stuck）、queue 數量、問腦失敗紀錄與接續操作提示。
from aos import flags as aos_flags
from aos import ws as aos_ws
from aos import daemon_ctl as dc
import json
import os
import re
import time
from .common import call_dc, daemon_path, row_named, table_ref


def loop_state(a):
    """子 loop 自己的 state.json（stack 裡 loop.json〔窗上的 procs_loop〕的 state 那格，沒寫＝state.json）→ 物件；讀不到＝{}。"""
    try:
        with open(os.path.join(a.stack, call_dc(dc.names_of, table_ref())["procs_loop"]), encoding="utf-8") as f:
            name = json.load(f).get("state")
    except (OSError, ValueError, AttributeError):
        name = None
    path = os.path.join(a.stack, name if isinstance(name, str) and name else "state.json")
    return aos_flags.read_window("aos-agent", path) or {}


def loop_paused(a):
    """表上 running 時讀子窗是否 paused，不靠行程身分。"""
    return loop_state(a).get("phase") == "paused"


def comes_back_paused(a):
    """stopped／sleeping 的那隻起來會不會先暫停（aos-loop：舊 state.json 的 paused 是 true＝起來先暫停）。"""
    return loop_state(a).get("paused") is True


def label(a):
    """狀態（procs § 0 名詞表）：running／stuck／paused／stopping／stopped／sleeping。paused＝表上 running、子 loop 的 state.json 是 paused。"""
    if a.phase == "running":
        return "paused" if loop_paused(a) else "running"
    return a.phase or "-"


def brain_hint(a):
    """只讀問腦記錄；確認 llm kernel 沒在跑才給提示，任何錯都不影響原本操作。"""
    try:
        from aos.agentlib import cooldown

        if a.phase != "running" or label(a) != "running":
            return None
        try:
            with open(os.path.join(a.stack, "think", "pending.txt"), encoding="utf-8") as f:
                letter = f.readline().strip()
        except FileNotFoundError:
            letter = ""
        if not letter:
            rec = cooldown.read(a.stack)
            if rec and rec.get("code") == "SendFailed":
                reason = rec.get("reason")
                if isinstance(reason, str) and "(llm kernel folder not found)" in reason:
                    return "%s cannot reach its brain: %s; it retries by itself once the folder appears" % (a.name, reason)
            return None
        with open(os.path.join(a.stack, "think", "brain_wait.json"), encoding="utf-8") as f:
            wait = json.load(f)
        if not isinstance(wait, dict) or wait.get("letter") != letter or not isinstance(wait.get("kernel"), str):
            return None
        replies = os.path.join(a.stack, "think", "reply", "new")
        if os.path.isdir(replies) and any(not name.startswith(".") for name in os.listdir(replies)):
            return None
        kernel = wait["kernel"]
        try:
            with open(os.path.join(kernel, "state.json"), encoding="utf-8") as f:
                state = json.load(f)
        except FileNotFoundError:
            why = "no llm daemon there (no state.json)"
        else:
            if not isinstance(state, dict):
                return None
            phase = state.get("phase")
            why = "the llm daemon is not running (state.json phase %s)" % (phase or "?")
            if phase in ("running", "waiting", "stopping"):
                pid = state.get("pid")
                if not isinstance(pid, int) or isinstance(pid, bool) or pid <= 0:
                    why += ", pid gone"
                else:
                    try:
                        os.kill(pid, 0)
                    except ProcessLookupError:
                        why += ", pid gone"
                    except PermissionError:
                        return None
                    else:
                        return None
        return ("%s is waiting for its brain, but the llm kernel at %s is not running (%s); start that llm kernel, "
                "or if AOS_LLM_KERNEL points to the wrong place, add %s again with the right one"
                % (a.name, kernel, why, a.name))
    except Exception:
        return None


ERROR_LINE = re.compile(r"^\S+: error: (\S+)")


def stderr_tail(a, size=8192):
    """agent 的 stderr 檔（procs_stderr）最後幾行（去空白行）；讀不到＝[]。"""
    try:
        path = os.path.join(a.stack, call_dc(dc.names_of, table_ref())["procs_stderr"])
        with open(path, "rb") as f:
            f.seek(0, os.SEEK_END)
            f.seek(max(0, f.tell() - size))
            text = f.read().decode("utf-8", "replace")
    except Exception:
        return []
    return [l.strip() for l in text.splitlines() if l.strip()][-20:]


def brain_failure(a):
    """問腦失敗的紀錄（small-1118，使用者 11-18 小題一包「listen 出錯時把理由帶出來」）：只讀，任何錯都當沒有＝None。
    cooldown.json（成功一次就刪，所以在＝最後一次問腦沒成）給代號、原因、第幾次、冷卻到幾點。
    先讀欄位（cooldown-1118，使用者 11-18 裁「寫進狀態檔」）：冷卻有布林 retry＝寫的身體自己說了會不會重送，
    stopped＝retry false 而且沒有正在問的腦（think/pending.txt 不在）；下層原話＝error 欄的 code＋msg（沒有＝冷卻的代號＋原因）。
    沒有 retry 欄＝退回認 stderr 檔結尾的錯誤行（這條退路是給自己寫冷卻檔、沒寫這兩欄的自寫 body 用的，不是為了舊版 fsm／eca）：
    stopped＝stderr 裡最後一行「名: error: 同代號 …」之後，同一支沒再印 warning，而且沒有 think/pending.txt；
    只印 warning 繼續重送的不算；下層原話＝那幾行錯誤行。
    回 {code, reason, failures, until, lines, stopped}。"""
    try:
        from aos.agentlib import cooldown

        rec = cooldown.read(a.stack)
        if not rec:
            return None
        until = time.strftime("%H:%M:%S", time.localtime(cooldown.parse(rec["until"])))
        out = {"code": str(rec.get("code") or "?"), "reason": str(rec.get("reason") or ""), "failures": rec.get("failures", 0),
               "until": until}
        thinking = os.path.exists(os.path.join(a.stack, "think", "pending.txt"))
        if isinstance(rec.get("retry"), bool):    # 欄位：身體自己寫的，不認輸出格式
            err = rec.get("error")
            lines = ["%s %s" % (err["code"], err.get("msg", "")) if err else "%s %s" % (out["code"], out["reason"])]
            stopped = rec["retry"] is False and not thinking
            if stopped and err:                   # 停下的再接上身體自己那句（例：EndpointFailed HTTP 400 … / BrainFailed aos-llm recv exited 1）
                lines.append("%s %s" % (out["code"], out["reason"]))
            return dict(out, lines=[" ".join(l.split())[:300] for l in lines], stopped=stopped)
        code = str(rec.get("code") or "")
        tail = stderr_tail(a)
        # 身體停下的那行＝最後一行「名: error: 冷卻代號 …」；它之後同一支印過 warning（例：retry 的「sent again in 30 s」）＝又接著重送了，不算停。
        # 它之後別支的行照常會有（aos-loop 的 RunFailed、brain_notify 的 warning；11-18 small-1118 實跑看到的）。
        at = max((i for i, l in enumerate(tail) if (ERROR_LINE.match(l) or [None, None])[1] == code), default=-1)
        prog = tail[at].split(":", 1)[0] if at >= 0 else ""
        stopped = at >= 0 and not any(l.startswith(prog + ": warning: ") for l in tail[at + 1:]) and not thinking
        lines = []
        if stopped:                               # 停下那行往上連著的 error 行（跳過 warning），例：aos-llm 的 EndpointFailed 那行＋fsm 的 BrainFailed 那行
            for l in reversed(tail[:at + 1]):
                if ERROR_LINE.match(l):
                    lines.insert(0, l)
                    if len(lines) == 3:
                        break
                elif not re.match(r"^\S+: warning: ", l):
                    break
        else:                                     # 會自己重送的：最後一行 error（例：aos-llm 的 EndpointFailed timed out connecting …）
            lines = [l for l in tail if ERROR_LINE.match(l)][-1:]
        return dict(out, lines=[" ".join(l.split())[:300] for l in lines], stopped=stopped)
    except Exception:
        return None


def failure_text(f):
    """brain_failure 的一句：有原話（欄位或 stderr 錯誤行）就用原話，不然用冷卻的代號＋原因；後面接冷卻到幾點、第幾次。"""
    said = " / ".join(f["lines"]) if f["lines"] else "%s %s" % (f["code"], f["reason"])
    return "%s (failure %s in a row; cooldown until %s)" % (said, f["failures"], f["until"])


def queued(a):
    """queue 排幾封（new/＋cur/）；stack 沒 queue/＝None。"""
    if not os.path.isdir(os.path.join(a.stack, "queue")):
        return None
    return len(aos_ws.waiting(a.stack))


# ---------------------------------------------------------------- 誰在跑（搬自 extras/human/bin/aos_human.py）

def on_table(a):
    """重讀這隻在 daemon 表上的狀態。"""
    row = row_named(a.name)
    if row is not None:
        a.__init__(a.name, row)
    return row is not None and a.phase in ("running", "stuck", "stopping")


def daemon_held(a):
    """表上留著、行程不在的那一列（stopped 或 sleeping）＝phase；不是＝None。"""
    return a.phase if a.phase in ("stopped", "sleeping") else None


def off_table(a):
    """表上沒這隻可能是退 0、被 rm 或 adopt 接回後結束碼不明；已知非 0 留 stopped＋reason。回一句怎麼接著用；還在＝None。"""
    if row_named(a.name) is not None:
        return None
    return ("it is no longer on the daemon table (a body that exits 0 leaves the table; known nonzero exits stay stopped with a reason; removal or an adopted exit with unknown status can also leave it off the table; its last output is in %s/%s); aos-agent ctl add with the same name "
            "picks it up again (the stack is kept; some bodies resume where they stopped, others drop that batch, so say it again)"
            % (a.stack, call_dc(dc.names_of, table_ref())["procs_stderr"]))


def restart_how(d):
    """重起 daemon 的兩種起法（11-05 晚：從 stack 看不出當初是 aos-exec 定義還是直接 AOS_STACK=… aos-daemon，兩種都列）。"""
    return "the way it was started, aos-exec <daemon folder> or AOS_STACK=%s/ aos-daemon <daemon.json>" % d


def run_hint(a):
    gone = off_table(a)
    if gone:
        return gone
    held = daemon_held(a)
    if held == "sleeping":
        return "it is asleep on the daemon (%s is sleeping); wake it: aos-agent ctl wake --target %s (if the daemon itself is down, restarting it wakes %s too: %s)" % (a.name, a.name, a.name, restart_how(daemon_path()))
    if held:
        why = "; reason recorded by the daemon: %s" % a.reason if a.reason else ""
        return "it is stopped on the daemon table (%s is stopped%s); start it: aos-agent ctl start --target %s" % (a.name, why, a.name)
    return "see its error line: %s/%s, or aos-agent ctl state --target %s" % (a.stack, call_dc(dc.names_of, table_ref())["procs_stderr"], a.name)


def stuck_hint(a, sig):
    if "cur" in aos_ws.where(a.stack, sig):
        return "%s is in queue/cur/ (taken, not answered yet), but nothing is running %s now; %s" % (sig, a.name, run_hint(a))
    return "%s is still in queue/new/, but nothing is running %s now; %s" % (sig, a.name, run_hint(a))
