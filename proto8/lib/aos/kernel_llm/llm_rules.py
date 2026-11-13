# 問腦那一包的五個口：收成品、收拾與看信、排序、放不放、掛去跑；回信、撤回與記帳也在這裡。
import errno
import fcntl
import json
import os
import shutil
import subprocess
import time

import budget
import ledger
import letters
import order as ordering
import packs
import runner
import tool_io
from slots import Slots
from tool_io import Error

LETTER_BAD = ('cannot understand the letter: letter.json must be an N-16 letter with body = '
              '{"endpoint"?: name, "request": {...}, "priority"?}')
REPLY_BAD = ('cannot understand the endpoint function\'s stdout (must be one line '
             '{"message": {...}, "usage", "model"})')


def error_reply(code, msg):
    return {"error": {"code": code, "msg": msg}}


def reply_of(reply):
    """回信的內容合不合：{"message": 物件, …} 或 {"error": {"code": 字串, "msg": 字串}}；不合回 None。"""
    if not isinstance(reply, dict):
        return None
    if "error" in reply:
        error = reply["error"]
        ok = isinstance(error, dict) and isinstance(error.get("code"), str) and isinstance(error.get("msg"), str)
        return reply if ok else None
    return reply if isinstance(reply.get("message"), dict) else None


def read_any(path):
    try:
        with open(path, "rb") as stream:
            return json.loads(stream.read())
    except (OSError, ValueError, UnicodeError):
        return None


def read_text(path):
    try:
        with open(path, "rb") as stream:
            return stream.read().decode("utf-8", "replace")
    except OSError:
        return None


def read_error(path):
    """退非 0 時只認整份單行 JSON、頂層只有 error 的錯誤物件。"""
    text = read_text(path)
    if text is None:
        return None
    if text.endswith("\n"):
        text = text[:-1]
        if text.endswith("\r"):
            text = text[:-1]
    if "\r" in text or "\n" in text:
        return None
    try:
        reply = json.loads(text)
    except ValueError:
        return None
    if not isinstance(reply, dict) or set(reply) != {"error"}:
        return None
    return reply_of(reply)


def first_line(path):
    return (read_text(path) or "").split("\n", 1)[0]


def has_sender(folder):
    return os.path.exists(os.path.join(folder, "sender.flock"))


def sender_alive(folder):
    """寄這封信的還在不在：sender.flock 有人鎖著＝在。"""
    try:
        fd = os.open(os.path.join(folder, "sender.flock"), os.O_RDONLY | os.O_CLOEXEC)
    except OSError:
        return False
    try:
        fcntl.flock(fd, fcntl.LOCK_SH | fcntl.LOCK_NB)
        return False
    except OSError as error:
        return error.errno == errno.EWOULDBLOCK
    finally:
        os.close(fd)


def move(source, target):
    """改名；對方先動了（不在、目的地已有）回 False，其他失敗算自己的錯。"""
    try:
        os.rename(source, target)
        return True
    except OSError as error:
        if error.errno in (errno.ENOENT, errno.ENOTEMPTY, errno.EEXIST):
            return False
        raise Error("WriteFailed", "cannot rename %s -> %s: %s" % (source, target, error.strerror)) from None


def folders(path):
    try:
        return sorted(entry.name for entry in os.scandir(path) if not entry.name.startswith(".") and entry.is_dir())
    except OSError:
        return []


def find_host():
    """問腦 proc 掛到哪：要 AOS_DAEMON；掛信寄 AOS_KERNEL（有設），沒有才寄那台 daemon 的 ctl 信箱。"""
    daemon = os.environ.get("AOS_DAEMON", "")
    if not daemon or not os.path.isdir(daemon):
        raise Error("DaemonMissing", "AOS_DAEMON points to a missing directory: " + daemon if daemon else
                    "AOS_DAEMON is not set (the kernel runs under a daemon: it asks the daemon to add each "
                    "brain call as a proc)")
    daemon = os.path.abspath(daemon)
    if daemon != "/":
        daemon += "/"
    kernel = os.environ.get("AOS_KERNEL", "")
    if kernel:
        box = os.path.abspath(kernel)
        if not os.path.isdir(os.path.join(box, "new")):
            tool_io.warn("AOS_KERNEL points to a missing mailbox: %s; letters to it fail until it exists" % box)
        return daemon, box
    state = runner.read_json(os.path.join(daemon, "procs_state.json"))
    box = state["procs_requests"] if state and "procs_requests" in state else "procs_requests"
    if not isinstance(box, str) or not box:
        raise Error("MailboxMissing", daemon + ": the daemon has no ctl mailbox (procs_requests in "
                                               "procs_state.json is null)")
    return daemon, os.path.abspath(os.path.join(daemon, box))


def count_run(stack):
    """開了 --enable-counters 才數：counter_kernel_runs.txt 加一，原子寫回。"""
    path = os.path.join(stack, "counter_kernel_runs.txt")
    runs = 0
    try:
        with open(path, "rb") as stream:
            raw = stream.read()
    except FileNotFoundError:
        raw = None
    except OSError as error:
        raise Error("CounterBad", "cannot read %s: %s" % (path, error.strerror)) from None
    if raw is not None:
        try:
            text = raw.decode("utf-8").strip(" \t\n\r\f\v")
            if not text or not text.isascii() or not text.isdigit() or int(text) > budget.MAX:
                raise ValueError
            runs = int(text)
        except ValueError:
            raise Error("CounterBad", path + " must contain a non-negative integer within signed 64-bit range "
                                             "(delete it to start over)") from None
    if runs == budget.MAX:
        raise Error("CounterBad", path + " is too large to increment (delete it to start over)")
    tmp = os.path.join(stack, ".counter_kernel_runs.txt")
    try:
        with open(tmp, "w", encoding="utf-8") as stream:
            stream.write("%d\n" % (runs + 1))
    except OSError as error:
        raise Error("WriteFailed", "cannot write %s: %s" % (tmp, error.strerror)) from None
    try:
        os.replace(tmp, path)
    except OSError as error:
        raise Error("WriteFailed", "cannot rename %s -> %s: %s" % (tmp, path, error.strerror)) from None


def guarded(port):
    """包自己的錯（Error）轉成骨架的錯誤行。"""
    def wrapped(ctx, *args, **kwargs):
        try:
            return port(ctx, *args, **kwargs)
        except Error as error:
            ctx.die(error.code, str(error))
        except runner.Failed as error:
            ctx.die(error.code, error.msg)
    wrapped.__name__, wrapped.__doc__ = port.__name__, port.__doc__
    return wrapped


def load(cfg, cfg_dir):
    """設定在 packs.read_cfg 讀與驗；骨架沒有別的要這包驗的鍵。"""


def reply_box(ctx, letter):
    reply_to = letter.get("reply_to") if isinstance(letter, dict) else None
    if not isinstance(reply_to, str):
        return None
    return reply_to if reply_to.startswith("/") else os.path.abspath(os.path.join(ctx.requests, reply_to))


def post_reply(ctx, folder, name, letter, body):
    """照信的 reply_to 寄回信，信名記在 reply_letter.txt（已經有＝寄過了）。回 None 或「代號 原因」。"""
    box = reply_box(ctx, letter)
    record = os.path.join(folder, "reply_letter.txt")
    if box is None or os.path.exists(record):
        return None
    try:
        result = subprocess.run(["aos-post", "send", "--in-reply-to", name, box],
                                input=json.dumps(body, ensure_ascii=False),
                                stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    except OSError as error:
        return "CommandMissing aos-post failed to start (must be on PATH): %s" % error
    if result.returncode != 0:
        return "%s %s" % runner.error_of(result.stderr, "aos-post",
                                         ("PostFailed", "aos-post send exited %d" % result.returncode))
    sent = result.stdout.strip()
    try:
        tmp = os.path.join(folder, ".reply_letter.txt.tmp")
        with open(tmp, "w", encoding="utf-8") as stream:
            stream.write(sent + "\n")
        os.replace(tmp, record)
    except OSError:
        return "WriteFailed reply sent (%s) but cannot record it in %s/reply_letter.txt" % (sent, folder)
    return None


def regret_reply(ctx, folder, letter):
    """寄件人已經走了：回信還在它信箱的 new/ 就撤回，沒人會拿。"""
    box = reply_box(ctx, letter)
    sent = (read_text(os.path.join(folder, "reply_letter.txt")) or "").rstrip("\n ")
    if box is None or not sent or sent.startswith(".") or "/" in sent:
        return
    try:
        subprocess.run(["aos-post", "regret", box, sent], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except OSError:
        pass


def deliver(ctx, name, reply, before_reply=None):
    """收尾一封在 cur/ 的信：寫 reply.json、記帳、（收成品的才）跑 before_reply、寄回信、整封刪。"""
    folder = os.path.join(ctx.requests, "cur", name)
    runner.write_json(os.path.join(folder, "reply.json"), reply)
    proc_path = os.path.join(folder, runner.PROC_JSON)
    proc = runner.read_json(proc_path)
    # 掛上去過的才算一次；帳照端點函數原本的回話記，在 hook 之前。
    if os.path.exists(proc_path) and not (proc and proc.get("counted") is True):
        row = proc or {}
        ledger.append(ctx.stack, name, row, reply)
        budget.add_used(ctx.stack, ctx.used, budget.tokens_of(reply),
                        row.get("endpoint") if isinstance(row.get("endpoint"), str) else "",
                        row.get("sender") if isinstance(row.get("sender"), str) else "")
        if proc and before_reply is not None and any(
                entry["event"] == "before_reply" for entry in ctx.cfg["hooks"].values()):
            runner.write_json(proc_path, dict(proc, counted=True))   # hook 失敗下一輪重來時不記第二次
    letter = runner.read_json(os.path.join(folder, "letter.json"))
    body = {key: value for key, value in reply.items() if key != "child"}   # child 只進本層帳
    if before_reply is not None:
        original = {"letter": name, "sender": letter.get("sender") if letter else None,
                    "reply_to": reply_box(ctx, letter)}
        body = before_reply(original, {"sender": None, "body": body})
        # 骨架攔下回信時給的是掛 proc 那包的形狀；問腦的回信沒有 applied。
        if isinstance(body, dict) and body.get("applied") is False and set(body) == {"applied", "error"} \
                and isinstance(body["error"], dict) and body["error"].get("code") == "HookRejected":
            body = {"error": body["error"]}
    failure = post_reply(ctx, folder, name, letter, body)
    if failure:
        ctx.warn("cannot send the reply to letter %s (%s); letter deleted anyway" % (name, failure))
    if has_sender(folder) and not sender_alive(folder):
        regret_reply(ctx, folder, letter)
    shutil.rmtree(folder, ignore_errors=True)


def outcome(ctx, name, folder, result):
    """runner 交出的結果解讀成回信。"""
    kind = result["kind"]
    if kind == "launch":
        return error_reply("LaunchFailed", result["msg"])
    if kind == "twice":
        return error_reply("EndpointFailed", "the brain call ran twice without a result (stopped or died midway)")
    if kind == "stopped":
        return error_reply("EndpointFailed", "the brain call %s was stopped on the daemon and not started again "
                                             "within %d s; gave up on it" % (result["name"], result["seconds"]))
    if kind == "write":
        return error_reply("WriteFailed", result["msg"])
    code = result["code"]
    stdout = os.path.join(folder, "reply.json")
    if code == 0:
        got = reply_of(read_any(stdout))
        return got if got is not None and "error" not in got else error_reply("ReplyBad", REPLY_BAD)
    if result["timed_out"]:
        return error_reply("EndpointFailed", "endpoint function timed out (%d ms)" % ctx.cfg["timeout_ms"])
    error = read_error(stdout)
    if error is not None:
        return error
    line = first_line(stdout) or first_line(os.path.join(folder, "stderr.txt"))
    return error_reply("EndpointFailed", "endpoint function exited with code %d" % code + (": " + line if line else ""))


@guarded
def collect(ctx, before_reply=None):
    """找 daemon、讀帳與表、寫窗，然後收 cur/ 裡掛出去的每一封；還在飛的算進格數。"""
    cfg = ctx.cfg
    ctx.daemon, ctx.box = cfg["host"]
    ctx.queue = ordering.read_queue(ctx.stack)
    ctx.previous = {name: True for name in ctx.queue["seen_at_ms"]}
    if cfg["enable_counters"]:
        count_run(ctx.stack)
    ctx.used = budget.read_used(ctx.stack, cfg["budget"]["window"])
    table = runner.read_table(ctx.daemon)
    packs.write_window(ctx.stack, cfg["packs"])
    ctx.slots = Slots(cfg, ctx.stack)
    cur = os.path.join(ctx.requests, "cur")
    for name in folders(cur):
        folder = os.path.join(cur, name)
        proc = runner.read_json(os.path.join(folder, runner.PROC_JSON))
        if proc is not None:
            if proc.get("counted") is True:               # 帳記過了、上一輪卡在 before_reply
                reply = reply_of(read_any(os.path.join(folder, "reply.json")))
                if reply is not None:
                    deliver(ctx, name, reply, before_reply)
                    continue
            stdout = os.path.join(folder, "reply.json")
            result = runner.settle(folder, proc, table, ctx.box, ctx.daemon, timeout_ms=cfg["timeout_ms"],
                                   name="llm_" + name, target_for=lambda p: packs.target_for(cfg, p),
                                   accept=lambda code: read_error(stdout) is not None)
            if result is None:
                ctx.slots.flying(proc)
            else:
                deliver(ctx, name, outcome(ctx, name, folder, result), before_reply)
            continue
        reply = reply_of(read_any(os.path.join(folder, "reply.json")))
        if reply is not None:                             # 回信寫好了只差寄
            deliver(ctx, name, reply)
        elif not move(folder, os.path.join(ctx.requests, "new", name)):
            shutil.rmtree(folder, ignore_errors=True)     # 認領了還沒掛就死：放回 new/ 重排


def sweep(ctx):
    """寄件人走了的信（有 sender.flock、沒人鎖）刪掉；不是判決，不跑 hook。"""
    tmp, new = os.path.join(ctx.requests, "tmp"), os.path.join(ctx.requests, "new")
    try:
        names = os.listdir(tmp)
    except OSError:
        names = []
    for name in names:
        folder = os.path.join(tmp, name)
        if name.startswith(".") and not os.path.exists(os.path.join(folder, "letter.json")):
            continue                                      # ask 鎖好才寫 letter.json：還在建，不碰
        if has_sender(folder) and not sender_alive(folder):
            shutil.rmtree(folder, ignore_errors=True)
    for name in folders(new):
        folder = os.path.join(new, name)
        if has_sender(folder) and not sender_alive(folder):
            gone = os.path.join(tmp, name)
            if move(folder, gone):
                shutil.rmtree(gone, ignore_errors=True)


def examine(ctx, name, letter):
    """驗一封信、查它的包。回排隊用的資料；不收丟 Error（代號與原因就是回信）。"""
    body = letter.get("body")
    if not isinstance(body, dict) or "request" not in body:
        raise Error("LetterBad", LETTER_BAD)
    if "endpoint" in body and not isinstance(body["endpoint"], str):
        raise Error("LetterBad", "letter body.endpoint must be a string (name), got " + budget.dumps(body["endpoint"]))
    try:
        level, deadline = ordering.parse_priority(body.get("priority"))
    except Error as error:
        raise Error("LetterBad", "letter %s" % error) from None
    request = body["request"]
    if not isinstance(request, dict) or not isinstance(request.get("messages"), list):
        raise Error("RequestBad", "body.request must be an object and messages an array")
    if request.get("stream") is not None and request["stream"] is not False:
        raise Error("RequestBad", "streaming is not supported: request must not set stream: true")
    endpoint, pack, group, target = packs.pick(ctx.cfg, body)
    seen_ms, seen_cycle, waited = ordering.waited(ctx.old_queue, name, ctx.now_ms, ctx.now_cycle)
    return {"id": name, "body": body, "level": level, "deadline": deadline, "endpoint": endpoint, "pack": pack,
            "group": group, "exec": target, "waited": waited, "seen_ms": seen_ms, "seen_cycle": seen_cycle,
            "sender": letter["sender"] if isinstance(letter.get("sender"), str) else ""}


def examined(ctx, name, letter):
    """同一份 body 只驗一次；before_verdict 改過 body 就重驗。回排隊資料或 Error。"""
    kept = ctx.waiting.get(name)
    if kept is None or kept[0] != letter.get("body"):
        try:
            kept = (letter.get("body"), examine(ctx, name, letter))
        except Error as error:
            kept = (letter.get("body"), error)
        ctx.waiting[name] = kept
    return kept[1]


@guarded
def check(ctx):
    """收拾寄件人已走的信，再看 new/：信留在 new/ 不認領，掛上或拒掉時才認領。"""
    sweep(ctx)
    try:
        ctx.now_cycle = tool_io.now_cycle()
    except Error as error:
        ctx.die(error.code, str(error))
    ctx.now_ms = tool_io.utc_now_epoch_ms()
    ctx.old_queue = ctx.queue
    ctx.queue = dict(ctx.old_queue, seen_at_ms={}, seen_at_cycles={}, on_clock=ctx.now_cycle is not None)
    ctx.waiting = {}
    incoming = {}
    new = os.path.join(ctx.requests, "new")
    for name in folders(new):
        letter = runner.read_json(os.path.join(new, name, "letter.json"))
        if letter is None:                                # 信封讀不懂：hook 沒東西可看，直接回
            refuse(ctx, name, None, "LetterBad", LETTER_BAD)
            continue
        if name in ctx.previous:
            letters.restore_body(ctx, name, letter)       # 排著的信照 before_verdict 改過的 body 排序
        incoming[name] = letter
    return incoming


@guarded
def order(ctx, incoming):
    """驗不過的排最前（輪到就回信）；其餘照級數、期限、黏著、速度、等多久、先寄。"""
    bad, good = [], []
    for name in sorted(incoming):
        result = examined(ctx, name, incoming[name])
        (bad if isinstance(result, Error) else good).append(name if isinstance(result, Error) else result)
    ranked = ordering.sort(good, ctx.cfg["aging_cycles"], ctx.old_queue["backends"])
    return bad + [waiting["id"] for waiting in ranked]


def over_budget(ctx, waiting):
    """這封撞到哪個額度：回 BudgetMissing 的原因；都沒撞回 None。"""
    cfg, used, slots = ctx.cfg, ctx.used, ctx.slots
    window, pack, endpoint = cfg["budget"]["window"], waiting["pack"], waiting["endpoint"]
    if pack["max_calls"] is not None or pack["max_tokens"] is not None:
        flying = slots.packs.get(endpoint, 0)
        if budget.spent_of(used["packs"], endpoint, pack["max_calls"], pack["max_tokens"], flying):
            by_calls = budget.spent_of(used["packs"], endpoint, pack["max_calls"], None, flying)
            which = "max_calls %d" % pack["max_calls"] if by_calls else "max_tokens %d" % pack["max_tokens"]
            return "endpoint %s: %s reached in this window (%s); not run (no fallback: pick another endpoint name)" % (
                endpoint, which, window)
    who = budget.sender_key(waiting["sender"], ctx.stack)
    limit = cfg["budget"]["senders"].get(who)
    if limit is not None and waiting["sender"]:
        mine = slots.senders.get(who, 0)
        if budget.spent_of(used["senders"], who, limit["max_calls"], limit["max_tokens"], mine):
            by_calls = budget.spent_of(used["senders"], who, limit["max_calls"], None, mine)
            which = "max_calls %d" % limit["max_calls"] if by_calls else "max_tokens %d" % limit["max_tokens"]
            return "budget.senders key %s (sender %s): %s reached in this window (%s); not run" % (
                budget.dumps(limit["key"]), waiting["sender"], which, window)
    return None


@guarded
def admit(ctx, name, letter):
    """驗信 → 期限 → 總額 → 總格與保留格 → 包與寄件人的額度 → 包格與後端格。"""
    waiting = examined(ctx, name, letter)
    if isinstance(waiting, Error):
        return "refuse", (waiting.code, str(waiting))
    if waiting["deadline"] is not None and waiting["deadline"] < ctx.now_ms / 1000.0:
        return "refuse", ("DeadlineBad", "deadline passed before its turn; not run")
    ctx.queue["seen_at_ms"][name] = waiting["seen_ms"]
    if waiting["seen_cycle"] is not None:
        ctx.queue["seen_at_cycles"][name] = waiting["seen_cycle"]
    cfg, slots = ctx.cfg, ctx.slots
    if slots.stopped:
        return "queue", name
    if budget.spent(cfg["budget"], ctx.used, slots.total()):
        if cfg["budget"]["wait"]:
            slots.stopped = True                          # 留在 new/ 等下一窗
            return "queue", name
        return "refuse", ("BudgetMissing", "budget for this window (%s) is used up; not run" % cfg["budget"]["window"])
    if slots.total() >= cfg["slots"]:
        slots.stopped = True                              # 補位到 slots 為止，其餘下一輪
        return "queue", name
    if waiting["level"] < ordering.HIGH and slots.total() >= cfg["slots"] - cfg["reserved_high"]:
        return "queue", name                              # 宣告級數才認保留格；後面可能還有 high
    reason = over_budget(ctx, waiting)
    if reason is not None:
        return ("queue", name) if cfg["budget"]["wait"] else ("refuse", ("BudgetMissing", reason))
    return ("pass", [name]) if slots.room(waiting) else ("queue", name)


def forget(ctx, name):
    ctx.queue["seen_at_ms"].pop(name, None)
    ctx.queue["seen_at_cycles"].pop(name, None)


@guarded
def dispatch(ctx, name, letter, detail):
    """認領進 cur/、寫 request.json、請 daemon 掛成問腦 proc。"""
    waiting = examined(ctx, name, letter)
    if isinstance(waiting, Error):                        # hook 把驗不過的信改判放行：沒有包可跑
        return waiting.code, str(waiting)
    cfg, queue = ctx.cfg, ctx.queue
    folder = os.path.join(ctx.requests, "cur", name)
    forget(ctx, name)
    if not move(os.path.join(ctx.requests, "new", name), folder):
        return None                                       # 寄信的剛撤信
    mounted_at = time.time()
    declared = waiting["body"].get("priority")
    priority = {"level": "normal"}
    if isinstance(declared, dict):
        priority["level"] = declared.get("level", "normal")
    elif declared is not None:
        priority["level"] = declared
    deadline = waiting["deadline"]
    if cfg["timeout_ms"] is not None:
        timeout_at = mounted_at + cfg["timeout_ms"] / 1000.0
        if deadline is None or timeout_at < deadline:
            deadline = timeout_at
    if deadline is not None:
        priority["deadline"] = deadline
    backend, endpoint = waiting["pack"]["backend"], waiting["endpoint"]
    switched = backend is not None and (backend not in queue["backends"]
                                        or queue["backends"][backend]["pack"] != endpoint)
    proc = {"switched": switched}
    if backend is not None:
        proc["backend"] = backend
    proc.update(seen_at=waiting["seen_ms"] / 1000.0, mounted_at=mounted_at, endpoint=endpoint)
    if waiting["sender"]:
        proc["sender"] = waiting["sender"]
    try:
        runner.write_json(os.path.join(folder, "request.json"),
                          {"endpoint": waiting["group"], "request": waiting["body"]["request"], "priority": priority})
        runner.mount(folder, "llm_" + name, waiting["exec"], proc, ctx.box, ctx.daemon, timeout_ms=cfg["timeout_ms"])
    except runner.Failed as error:
        try:
            os.unlink(os.path.join(folder, runner.PROC_JSON))
        except OSError:
            pass
        deliver(ctx, name, error_reply("LaunchFailed", "cannot add the brain call to the daemon: %s %s"
                                      % (error.code, error.msg)))
        return None
    if switched:
        switches = queue["backends"][backend]["counter_switches"] if backend in queue["backends"] else 0
        queue["backends"] = dict(queue["backends"], **{backend: {
            "pack": endpoint, "switched_at": mounted_at, "counter_switches": switches + 1}})
    ctx.slots.mounted(waiting)
    return None


@guarded
def refuse(ctx, name, letter, code, msg):
    """不跑、直接回信：先認領，認領不到＝寄信的剛撤信，算了。"""
    if hasattr(ctx, "queue"):
        forget(ctx, name)
    if not move(os.path.join(ctx.requests, "new", name), os.path.join(ctx.requests, "cur", name)):
        return
    deliver(ctx, name, error_reply(code, msg))


@guarded
def finish(ctx, queued):
    """寫 queue.json；順手清掉已經不在隊裡的信留下的 body。"""
    ordering.write_queue(ctx.stack, ctx.queue)
    bodies = os.path.join(ctx.stack, "bodies")
    try:
        names = os.listdir(bodies)
    except OSError:
        names = []
    for file in names:
        if file.endswith(".json") and file[:-5] not in ctx.queue["seen_at_ms"]:
            letters.remove_body(ctx, file[:-5])
