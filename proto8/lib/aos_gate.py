#!/usr/bin/env python3
"""閘門（gate）：LLM kernel（N-42 第一種）的包裝。不自己跑，把「真正要跑的 inst」寫成一封信丟進 kernel 的信箱，
等回信，把回信裡那支 inst 的 stdout／stderr 原樣吐出、用它的結束碼退出——呼叫端看到的是一次普通的 N-12／N-30 呼叫。
純標準庫。說明在同資料夾 kernel.md。

    python3 aos_gate.py [--key 值 ...] [GATE.json]          （stdin＝要轉給真正 inst 的內容，原樣）

設定（aos_cli；不收 `-`，因為 stdin 是請求本身）：
    target    真正要跑的 inst：TARGET（可接 `#/位置`，從呼叫者的 cwd 算）或內嵌一張 inst（必填）
    kernel    kernel 的信箱資料夾（N-16 Maildir：tmp/ → new/ → cur/；回信在 reply/）；沒寫＝環境變數 AOS_KERNEL
    priority  呼叫者說的「這次多急」：純量（"low"／"normal"／"high"、數字）＝{"level": 那個值}；物件 {level, deadline, …}
              照帶（不認得的 key 照帶）；沒寫＝環境變數 AOS_PRIORITY（先當 JSON 解，解不了當字串）；再沒有＝不填
    wait_ms   排隊最多等幾毫秒（只算信還在 new/ 的時間；kernel 拿走之後就等它跑完）；到了撤信、回 QueueTimeout；沒寫＝不限
    poll_ms   多久看一次回信（沒寫＝50）

信（`new/<名>.json`）：{"kind": "aos-gate-letter", "inst": 解好的 inst（路徑都絕對）, "stdin": 文字, "priority",
"_metainfo"（target 的，照抄；沒有＝不寫）, "reply": 回信的絕對路徑, "sent": epoch 秒}。
回信：{"result": aos_inst 的結果, "stdout": 文字, "stderr": 文字} 或 {"error": {"code", "msg"}}。

退出碼：有 result＝它的 `code`（stdout、stderr 原樣吐）；kernel 回錯（DeadlineMissed、BudgetExhausted、KernelRestarted…）、
QueueTimeout、自己設定不對＝stderr 一份 N-29 錯誤、退出 125（kernel 那邊 aos_inst 起不來＝照 aos_inst 的碼，例 127）。
SIGTERM／SIGINT／SIGHUP：信還在 new/ 就撤掉；已被 kernel 拿走的讓它跑完、回信沒人收。

相依：aos_directives ← aos_cli ← aos_inst ← aos_gate（← aos_gate_kernel）。
"""
import json
import os
import signal
import sys
import time

import aos_cli
import aos_inst
from aos_cli import CliError

__all__ = ["FLAGS", "GateError", "LEVELS", "letter", "main", "mailbox", "normalize_priority", "post", "wait_reply"]

FLAGS = ("target", "kernel", "wait_ms", "poll_ms")
LEVELS = {"low": -1, "normal": 0, "high": 1}


class GateError(CliError):
    """閘門或 kernel 回的錯。`code`＝錯誤代號，`msg`＝白話；`exit`＝命令列退出碼。"""

    def __init__(self, code, msg, exit=125):
        super().__init__(code, msg)
        self.exit = exit


def mailbox(path):
    """信箱的四格資料夾（tmp、new、cur、reply）建好，回 {名: 絕對路徑}。"""
    box = {k: os.path.join(os.path.abspath(path), k) for k in ("tmp", "new", "cur", "reply")}
    for d in box.values():
        os.makedirs(d, exist_ok=True)
    return box


def normalize_priority(p):
    """呼叫者給的 priority → 物件（純量＝{"level": 值}；物件照抄；None＝None）。不認得的 key 照帶。"""
    if p is None:
        return None
    if isinstance(p, dict):
        return dict(p)
    if isinstance(p, (str, int, float)) and not isinstance(p, bool):
        return {"level": p}
    raise GateError("FieldType", "priority 要是字串、數字或物件，不是 %r" % (p,))


def _env_priority():
    v = os.environ.get("AOS_PRIORITY")
    if not v:
        return None
    try:
        return json.loads(v)
    except ValueError:
        return v


def letter(doc, stdin_text):
    """閘門設定（已解好指示詞）＋stdin 的文字 → (信箱, 信 dict)。target 解成絕對路徑的 inst。"""
    kernel = doc.get("kernel") or os.environ.get("AOS_KERNEL")
    if not isinstance(kernel, str):
        raise GateError("FieldType", "kernel 要是信箱資料夾的路徑（或設環境變數 AOS_KERNEL），不是 %r" % (kernel,))
    target = doc.get("target")
    try:
        if isinstance(target, str):
            raw, ident = aos_cli.load_target(target, aos_inst._file)
        elif isinstance(target, dict):
            raw, ident = target, None
        else:
            raise GateError("FieldType", "target 要是 inst 的 TARGET 或一張 inst，不是 %r" % (target,))
        inst = aos_inst.parse(raw, os.getcwd(), ident or "<gate>")
    except CliError as e:
        raise GateError(e.code, e.msg) if not isinstance(e, GateError) else e
    pri = normalize_priority(doc["priority"] if "priority" in doc else _env_priority())
    out = {"kind": "aos-gate-letter", "inst": inst, "stdin": stdin_text, "priority": pri, "sent": time.time()}
    if "_metainfo" in raw:
        out["_metainfo"] = raw["_metainfo"]
    return mailbox(kernel), out


def post(box, doc):
    """寫進 tmp/ 再改名到 new/（N-16）。名字＝時間（奈秒）.pid，字典序＝先來後到。回信的名字。"""
    name = "%020d.%d.json" % (time.time_ns(), os.getpid())
    doc = dict(doc, reply=os.path.join(box["reply"], name))
    tmp = os.path.join(box["tmp"], name)
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(doc, f, ensure_ascii=False)
    os.replace(tmp, os.path.join(box["new"], name))
    return name


def withdraw(box, name):
    """信還在 new/ 就刪掉、回 True；已被 kernel 拿走（或已回）回 False。"""
    try:
        os.remove(os.path.join(box["new"], name))
        return True
    except FileNotFoundError:
        return False


def wait_reply(box, name, wait_ms=None, poll_ms=50):
    """等回信：回信的 dict（讀完刪掉）。排隊超過 wait_ms（信還在 new/）＝撤信、丟 GateError QueueTimeout。"""
    path = os.path.join(box["reply"], name)
    deadline = None if wait_ms is None else time.monotonic() + wait_ms / 1000
    while True:
        if os.path.exists(path):
            with open(path, encoding="utf-8") as f:
                rep = json.load(f)
            os.remove(path)
            return rep
        if deadline is not None and time.monotonic() >= deadline:
            if withdraw(box, name):
                raise GateError("QueueTimeout", "排隊超過 %d 毫秒，信撤回了" % wait_ms)
            deadline = None             # 剛被拿走：排隊結束，等它跑完
        time.sleep(poll_ms / 1000)


class _Stop(BaseException):
    pass


def _raise_stop(signum, frame):
    raise _Stop(signum)


def run(doc, stdin_text):
    """送信、等回信。回回信 dict；排隊逾時、kernel 回錯丟 GateError。收到訊號＝撤信後丟 _Stop。"""
    for k, lo in (("wait_ms", 0), ("poll_ms", 1)):
        v = doc.get(k)
        if not (v is None or isinstance(v, int) and not isinstance(v, bool) and v >= lo):
            raise GateError("FieldType", "%s 要是 ≥%d 的整數或 null，不是 %r" % (k, lo, v))
    box, doc_letter = letter(doc, stdin_text)
    name = post(box, doc_letter)
    try:
        rep = wait_reply(box, name, doc.get("wait_ms"), doc.get("poll_ms") or 50)
    except _Stop:
        withdraw(box, name)
        raise
    if "error" in rep:
        e = rep["error"]
        raise GateError(e.get("code", "KernelError"), e.get("msg", ""), rep.get("exit", 125))
    return rep


def main(argv=None):
    args = sys.argv[1:] if argv is None else argv
    for sig in (signal.SIGTERM, signal.SIGINT, signal.SIGHUP):
        signal.signal(sig, _raise_stop)
    try:
        if aos_cli.parse_argv(args, FLAGS)[0] == "-":
            raise GateError("Usage", "閘門的 stdin 是請求本身，設定只能從 GATE.json 或旗標來")
        doc, _, _, rest = aos_cli.config(args, FLAGS, aos_inst._file)
        if rest is not None:
            raise GateError("Usage", "閘門不收 `--`")
        rep = run(doc, sys.stdin.read())
    except CliError as e:
        aos_cli.error(e.code, e.msg)
        return getattr(e, "exit", 125)
    except _Stop as s:
        return 128 + s.args[0]
    sys.stdout.write(rep.get("stdout", ""))
    sys.stdout.flush()
    sys.stderr.write(rep.get("stderr", ""))
    sys.stderr.flush()
    return rep["result"]["code"]


if __name__ == "__main__":
    sys.exit(main())
