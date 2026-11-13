# 掛 proc 那一包：收下游答案、驗信、先來先掛與白名單及 running 上限。
import json
import os

import letters
import queue_fifo
from round import CfgBad


def load(cfg, cfg_dir):
    """只驗這一包認得的設定，其他鍵照放。"""
    allowed, cap = cfg.get("allowed"), cfg.get("max_running")
    if allowed is not None and not (isinstance(allowed, list) and all(isinstance(n, str) for n in allowed)):
        raise CfgBad("allowed must be an array of names or null")
    if cap is not None and not (isinstance(cap, int) and not isinstance(cap, bool) and cap >= 0):
        raise CfgBad("max_running must be a non-negative integer or null")
    if not isinstance(cfg.get("queue", False), bool):
        raise CfgBad("queue must be a boolean")
    if cfg.get("keep_ordered") is None:
        cfg["keep_ordered"] = False
    if not isinstance(cfg["keep_ordered"], bool):
        raise CfgBad("keep_ordered must be a boolean or null")
    if not isinstance(cfg.get("reply_via_me", False), bool):
        raise CfgBad("reply_via_me must be a boolean")
    if not cfg.get("reply_via_me", False) and any(
            entry["event"] == "before_reply" for entry in cfg.get("hooks", {}).values()):
        raise CfgBad("before_reply hooks require reply_via_me")
    if "next" in cfg and "max_running" in cfg and "count_daemon" not in cfg:
        raise CfgBad("next with max_running requires count_daemon")


def state_view(daemon, ctx):
    """表尚未寫出來當空表；超過百列的切檔交給 aos-directive。"""
    path = os.path.join(daemon, "procs_state.json")
    if not os.path.exists(path):
        return {}
    try:
        with open(path, encoding="utf-8") as stream:
            text = stream.read()
    except (OSError, UnicodeError) as error:
        ctx.die("StateBad", "cannot read procs_state.json: %s" % error)
    code, out = letters.run(["aos-directive"], text, cwd=daemon)
    try:
        if code != 0:
            raise ValueError("aos-directive exited %d" % code)
        state = json.loads(out)
        if not isinstance(state, dict) or not isinstance(state.get("procs") or {}, dict):
            raise ValueError("procs_state.json must contain an object of procs")
    except ValueError as error:
        ctx.die("StateBad", "cannot parse procs_state.json: %s" % error)
    return state


def prepare_targets(ctx, active):
    """有信才讀表；兩次認領之間到的新信也必須先完成解析。"""
    cfg = ctx.cfg
    daemon, count_daemon = ctx.daemon, ctx.count_daemon
    # 空輪不讀 daemon 的表，保留原本第一圈或空輪可先跑的行為。
    target_state = state_view(daemon, ctx) if active and "next" not in cfg else {}
    if "next" in cfg:
        ctx.next_box = cfg["next"]
    else:
        if "procs_requests" in target_state and target_state["procs_requests"] is None:
            ctx.die("MailboxMissing", "daemon has no ctl mailbox (procs_requests in procs_state.json is null)")
        box = target_state.get("procs_requests") or "procs_requests"
        if not isinstance(box, str):
            ctx.die("StateBad", "procs_requests must be a path string or null")
        ctx.next_box = os.path.abspath(os.path.join(daemon, box))
    if os.path.realpath(ctx.next_box) == os.path.realpath(ctx.requests):
        ctx.die("CfgBad", "the next mailbox must not be this station's requests mailbox")
    state = {}
    if active and count_daemon is not None:
        state = target_state if count_daemon == daemon and "next" not in cfg else state_view(count_daemon, ctx)
    ctx.running = {n for n, row in (state.get("procs") or {}).items()
                   if isinstance(row, dict) and row.get("phase") in {"running", "stuck"}}
    ctx.targets_loaded = active


def collect(ctx, before_reply=None):
    """先防重收原信，再透過 before_reply 回呼代回。"""
    cfg = ctx.cfg
    daemon = os.environ.get("AOS_DAEMON")
    if "next" not in cfg and (not daemon or not os.path.isdir(daemon)):
        ctx.die("DaemonMissing", "AOS_DAEMON is not set or not a directory: %s" % (daemon or "(empty)"))
    count_daemon = cfg.get("count_daemon", daemon if "next" not in cfg else None)
    if count_daemon is not None and not os.path.isdir(count_daemon):
        ctx.die("DaemonMissing", "count_daemon is not a directory: %s" % count_daemon)
    ctx.forwarded_path = os.path.join(ctx.stack, "forwarded.json")
    ctx.forwarded = letters.read_forwarded(ctx.forwarded_path, ctx.die)
    ctx.replies = os.path.join(ctx.stack, "replies")
    ctx.window = os.path.join(ctx.stack, "queue.json")
    ctx.previous = queue_fifo.queue_view(ctx.window, ctx.warn)
    letters.take_all(ctx.requests, ctx.die)
    names = letters.names(ctx.requests)
    ctx.daemon, ctx.count_daemon = daemon, count_daemon
    prepare_targets(ctx, bool(names))
    ctx.admitted = set()
    for name in names:
        if letters.already_forwarded(ctx, name):
            letters.finish_forwarded(ctx, name)
    # 原信收掉後才中斷的情況，不等回信的防重列也要收乾淨。
    stale = [key for key, row in ctx.forwarded.items()
             if row["reply_to"] is None and not os.path.exists(
                 os.path.join(ctx.requests, "cur", row["letter"]))]
    for key in stale:
        del ctx.forwarded[key]
    if stale:
        letters.write_forwarded(ctx)
    if cfg.get("reply_via_me", False) or ctx.forwarded or os.path.isdir(ctx.replies):
        letters.relay_replies(ctx, before_reply)


def check(ctx):
    letters.take_all(ctx.requests, ctx.die)
    incoming = {}
    names = letters.names(ctx.requests)
    if names and not ctx.targets_loaded:
        prepare_targets(ctx, True)
    for name in names:
        if letters.already_forwarded(ctx, name):
            letters.finish_forwarded(ctx, name)
            continue
        letter = letters.see(ctx.requests, name, ctx)
        if letter is not None:
            incoming[name] = letter
    return incoming


def order(ctx, incoming):
    if ctx.cfg.get("queue", False):
        old_order = {name: index for index, name in enumerate(ctx.previous)}
        return sorted(incoming, key=lambda n: (0, old_order[n]) if n in old_order else (1, letters.letter_key(n)))
    return sorted(incoming, key=letters.letter_key)


def verdict(body, allowed, cap, running, admitted):
    """沿用掛 proc 的欄位檢查與新名字算法。"""
    if not isinstance(body, dict):
        return "BodyBad", "the letter body must be an object"
    names = []
    if "procs_added" in body:
        added = body["procs_added"]
        if not isinstance(added, dict):
            return "BodyBad", "procs_added must be an object"
        if allowed is not None:
            bad = [n for n in added if n not in allowed]
            if bad:
                return "NameUnknown", "%s not in allowed" % ", ".join(bad)
        names += list(added)
    for key in ("procs_started", "procs_woken"):
        if key in body:
            value = body[key]
            if not isinstance(value, list) or not all(isinstance(n, str) for n in value):
                return "BodyBad", "%s must be an array of names" % key
            names += value
    if not names:
        return None, []
    fresh = []
    for name in names:
        if name not in running and name not in admitted and name not in fresh:
            fresh.append(name)
    if cap is not None and len(running) + len(admitted) + len(fresh) > cap:
        return "SlotMissing", "max_running is %d, %d running now (counting ones let through this round), this letter adds %d" % (
            cap, len(running) + len(admitted), len(fresh))
    return None, fresh


def admit(ctx, name, letter):
    body = letter.get("body")
    if isinstance(body, dict) and "queue_wait_ms" in body:
        wait = body["queue_wait_ms"]
        if not isinstance(wait, int) or isinstance(wait, bool) or wait < 0:
            return "refuse", ("BodyBad", "queue_wait_ms must be a non-negative integer")
        try:
            queue_fifo.utc_ms(letter["sent_at"])
        except (ValueError, TypeError, KeyError, OverflowError):
            return "refuse", ("BodyBad", "sent_at must be an ISO 8601 timestamp with a timezone")
        message = queue_fifo.expiry_message(letter, name in ctx.previous)
        if message:
            return "refuse", ("SlotMissing", message)
    if ctx.cfg.get("allowed") is None and ctx.cfg.get("max_running") is None and not (
            isinstance(body, dict) and "queue_wait_ms" in body):
        return "pass", []
    allowed, cap = ctx.cfg.get("allowed"), ctx.cfg.get("max_running")
    bad, detail = verdict(body, allowed, cap, ctx.running, ctx.admitted)
    if ctx.cfg.get("queue", False) and ctx.queued and bad is None and detail:
        bad, detail = "SlotMissing", "an earlier letter is waiting for a slot"
    if bad == "SlotMissing" and ctx.cfg.get("queue", False) and body.get("queue_wait_ms") != 0:
        _, fresh = verdict(body, allowed, None, ctx.running, ctx.admitted)
        row = queue_fifo.queue_row(name, letter, fresh, ctx.previous, ctx.die)
        return "queue", row
    if bad:
        return "refuse", (bad, detail)
    return "pass", detail


def dispatch(ctx, name, letter, detail):
    # 讀信和前面的轉寄也花時間；規則放行的（detail 不是 None）臨轉寄再驗一次期限，免得這一輪中途到期還被掛上。
    # hook 改判成放行的（detail 是 None）照字面放行、不回頭驗。
    if detail is not None:
        message = queue_fifo.expiry_message(letter, name in ctx.previous)
        if message:
            return "SlotMissing", message
    failure = letters.forward(ctx, name, letter)
    if failure is None:
        # hook 能把拒或排改成放行；此處只數實際轉出的名字，不再驗規則。
        body = letter.get("body")
        if isinstance(body, dict):
            added = body.get("procs_added")
            if isinstance(added, dict):
                ctx.admitted.update(n for n in added if n not in ctx.running)
            for key in ("procs_started", "procs_woken"):
                names = body.get(key)
                if isinstance(names, list):
                    ctx.admitted.update(n for n in names if isinstance(n, str) and n not in ctx.running)
    return failure


def refuse(ctx, name, letter, code, msg):
    letters.refuse(ctx, name, letter, code, msg)


def finish(ctx, queued):
    if ctx.cfg.get("queue", False) or os.path.exists(ctx.window):
        queue_fifo.write_queue(ctx.window, queued, ctx.die)
