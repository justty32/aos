"""daemon_ctl 信件：寄送、認領與清理回信，並以秒或 tick 等待 daemon 回應。"""
import datetime
import fcntl
import json
import os
import shutil
import time
from contextlib import contextmanager

import aos_ws

from .base import Fail
from .table import names_of



def _post(args, text="", code="PostFailed"):
    """共用 aos-post 執行入口；下層錯誤直接透出。"""
    try:
        rc, out = aos_ws.run_post(args, text)
    except aos_ws.Error as exc:
        raise Fail(exc.code, str(exc))
    if rc:
        raise Fail(code, "aos-post %s exited %d" % (args[0], rc))
    return out.rstrip("\n")


def mailbox_of(d, direct=False):
    """掛子信與 ping 走同一個收件位置。"""
    kernel = os.environ.get("AOS_KERNEL", "")
    if kernel and not direct:
        box = os.path.abspath(kernel)
        if not os.path.isdir(os.path.join(box, "new")):
            raise Fail("MailboxMissing", "%s (AOS_KERNEL) is not a mailbox (check the declared AOS_KERNEL path)" % box)
        return box
    mb = names_of(d)["procs_ctl_mailbox"]
    if not mb:
        raise Fail("MailboxMissing", "the daemon of %s has no mailbox (procs_ctl_mailbox in procs_state.json is null; do not set procs_ctl_mailbox to null in daemon.json)" % d)
    box = os.path.join(d, mb)
    if not os.path.isdir(os.path.join(box, "new")):
        raise Fail("MailboxMissing", "%s is not a mailbox (daemon not started yet, or its mailbox is off)" % box)
    return box


def send(d, body, reply_to=None, direct=False):
    """寄信只回信名，不替呼叫者列印。"""
    if not shutil.which("aos-post"):
        raise Fail("CommandMissing", "no aos-post on PATH")
    args = ["send"] + (["--reply-to", reply_to] if reply_to else []) + [mailbox_of(d, direct)]
    return _post(args, json.dumps(body, ensure_ascii=False), "SendFailed")


def regret(box, letter):
    """嘗試撤回尚未領取的信；已領取或撤回失敗只回 False。"""
    try:
        _post(["regret", box, letter], code="RegretFailed")
        return True
    except Fail:
        return False


def _letter(path):
    try:
        with open(os.path.join(path, "letter.json"), encoding="utf-8") as fh:
            value = json.load(fh)
        return value if isinstance(value, dict) else {}
    except (OSError, ValueError):
        return {}


def _letters(box, stage):
    try:
        return sorted(n for n in os.listdir(os.path.join(box, stage)) if not n.startswith("."))
    except OSError:
        return []


def _claim(box, name):
    try:
        os.rename(os.path.join(box, "new", name), os.path.join(box, "cur", name))
        return True
    except FileNotFoundError:
        return False


@contextmanager
def _reply_lock(box):
    """共用信箱的收信與垃圾回收互斥，避免同封 cur 信重複 done。"""
    try:
        with open(os.path.join(box, ".reply.lock"), "a", encoding="utf-8") as lock:
            fcntl.flock(lock, fcntl.LOCK_EX)
            yield
    except OSError as exc:
        raise Fail("PostFailed", "cannot access reply mailbox %s: %s" % (box, exc))


def reply_box(d):
    """共用回信信箱；只按信件時間清理超過十分鐘的回信。"""
    stack = os.environ.get("AOS_STACK", "")
    if stack:
        box = os.path.abspath(os.path.join(stack, "daemon_reply"))
    else:
        box = os.path.abspath(os.path.join(mailbox_of(d, direct=True), "reply"))
    if not all(os.path.isdir(os.path.join(box, s)) for s in ("tmp", "new", "cur")):
        _post(["init", box])
    with _reply_lock(box):
        cutoff = datetime.datetime.now(datetime.timezone.utc).timestamp() - 600
        for stage in ("new", "cur"):
            for name in _letters(box, stage):
                letter = _letter(os.path.join(box, stage, name))
                try:
                    stamp = datetime.datetime.fromisoformat(letter["sent_at"].replace("Z", "+00:00"))
                    if stamp.tzinfo is None or stamp.timestamp() >= cutoff:
                        continue
                except (KeyError, TypeError, ValueError, AttributeError):
                    continue
                if stage == "new" and not _claim(box, name):
                    continue
                _post(["done", box, name])
    return box


def take_reply(box, letter):
    """只認領自己的回信，其他呼叫者的回信留在原處。"""
    with _reply_lock(box):
        for name in _letters(box, "new"):
            envelope = _letter(os.path.join(box, "new", name))
            if envelope.get("in_reply_to") != letter or not _claim(box, name):
                continue
            body = _letter(os.path.join(box, "cur", name)).get("body")
            _post(["done", box, name])
            return body if isinstance(body, dict) else {}
    return None


def ask(d, body, timeout_s=None, direct=False, *, timeout_ticks=None):
    """等回信：未指定期限沿用 3 秒；秒與正整數 tick 擇一。"""
    if timeout_ticks is not None:
        if timeout_s is not None:
            raise Fail("ArgumentsBad", "timeout_s and timeout_ticks are mutually exclusive")
        if isinstance(timeout_ticks, bool) or not isinstance(timeout_ticks, int) or not 0 < timeout_ticks <= 9223372036854775807:
            raise Fail("ArgumentsBad", "timeout_ticks must be a positive integer within signed 64-bit range")
    try:
        deadline = aos_ws.deadline_after(timeout_ticks) if timeout_ticks is not None else None
        box = reply_box(d)
        letter = send(d, body, reply_to=box, direct=direct)
        end = time.monotonic() + (3 if timeout_s is None else timeout_s) if deadline is None else None
        while True:
            got = take_reply(box, letter)
            if got is not None:
                return got
            timed_out = aos_ws.expired(deadline) if deadline is not None else time.monotonic() >= end
            if timed_out:
                return None
            time.sleep(0.05 if deadline is not None else min(0.05, max(0, end - time.monotonic())))
    except aos_ws.Error as exc:
        raise Fail(exc.code, str(exc)) from exc


def ping(d, timeout_s=None, direct=False, *, timeout_ticks=None):
    return ask(d, {"ping": True}, timeout_s, direct, timeout_ticks=timeout_ticks)


def wait_taken(box, letter, secs=3):
    end = time.monotonic() + secs
    while os.path.lexists(os.path.join(box, "new", letter)):
        if time.monotonic() >= end:
            return False
        time.sleep(min(0.05, max(0, end - time.monotonic())))
    return True
