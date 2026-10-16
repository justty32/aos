#!/usr/bin/env python3
"""閘門（gate）：LLM kernel（N-42 第一種）與通用 kernel 共用的包裝。不自己跑，把「真正要跑的 inst」當成一封信丟進
kernel 的信箱，等回信，把那支 inst 的 stdout／stderr 原樣吐出、用它的結束碼退出——呼叫端看到的是一次普通的 N-12／N-30 呼叫。
純標準庫。說明在同資料夾 kernel_llm.md。

    python3 aos_gate.py [--key 值 ...] [GATE.json]          （stdin＝要轉給真正 inst 的內容，原樣）

設定（aos_cli；不收 `-`，因為 stdin 是請求本身）：
    target    真正要跑的 inst：TARGET（可接 `#/位置`，從呼叫者的 cwd 算）或內嵌一張 inst（必填）
    mailbox   kernel 的信箱資料夾（N-16 Maildir：tmp/ → new/ → cur/；回信與旁檔在 reply/）（必填；閘門不認任何環境變數，
              demo 要省字就在 gate.json 寫 {"$env": "AOS_KERNEL"}——那只是指示詞的便利，C-48）
    priority  呼叫者說的「這次多急」：純量（"low"／"normal"／"high"、數字）＝{"val": 那個值}；物件 {val, deadline, …}
              照帶（不認得的 key 照帶、不驗；看不懂的 kernel 當 0）；沒寫＝不填

信（`new/<名>.json`）＝target 那張 inst 本身（inst 族，C-48；key 攤在最上層、`cwd` 與串流路徑轉絕對、`_metainfo` 照留），
加私有 key `priority`、`reply`（回信的絕對路徑）、`sent`（epoch 秒）；`stdin`＝旁檔 reply/<名>.stdin（呼叫者 stdin 的內容）。
回信＝aos_inst 的結果（N-30：id、code、signal、timed_out、pid、ms）或 {"error": {"code", "msg"}}；
target 的 stdout／stderr 在旁檔 reply/<名>.stdout／.stderr（kernel 填進信裡的），閘門讀了吐出、連回信一起刪掉。

排隊等多久只有一把尺：包閘門的那張 inst 的 `timeout_ms`——逾時 aos_inst 送 SIGTERM，閘門收到就撤信（原本自己再數一次的
`wait_ms`／`QueueTimeout` 10-15 深夜 KISS 批次 1 拿掉）。每 50 ms 看一次回信。

退出碼：回信是結果＝它的 `code`（stdout、stderr 原樣吐；透明轉交 target 的碼）；kernel 回錯（DeadlineMissed、BudgetExhausted、
KernelRestarted、kernel 那邊 aos_inst 起不來…）、自己設定不對＝stderr 一份 N-29 錯誤、退出 1。
閘門是透明的：回信是結果時，stderr 與退出碼都是 target 的、不是閘門自己的（target 守 N-43 閘門就守）。閘門自己的話只有上面那幾種錯。
SIGTERM／SIGINT／SIGHUP：信還在 new/ 就撤掉（連 stdin 旁檔）；已被 kernel 拿走的讓它跑完、回信沒人收；stderr 一份
`Signaled`（msg 帶訊號號碼）、退出 1。

相依：aos_inst ← aos_mailbox ← aos_gate（← aos_kernel_llm ← aos_kernel_judge ← aos_kernel_general）。
"""
import json
import os
import signal
import sys
import time

import aos_cli
import aos_inst
from aos_cli import CliError
from aos_mailbox import mailbox, side

__all__ = ["FLAGS", "LEVELS", "letter", "main", "mailbox", "outputs", "post", "remove", "side", "wait_reply", "withdraw"]

FLAGS = ("target", "mailbox", "priority")
LEVELS = {"low": -1, "normal": 0, "high": 1}
POLL_MS = 50


def letter(doc):
    """閘門設定（已解好指示詞）→ (信箱, 信 dict)。信＝target 那張 inst（cwd、串流路徑轉絕對）＋priority、sent。"""
    box = doc.get("mailbox")
    if not isinstance(box, str):
        raise CliError("FieldType", "mailbox 要是信箱資料夾的路徑（必填），不是 %r" % (box,))
    target = doc.get("target")
    if isinstance(target, str):
        raw, ident = aos_cli.load_target(target, aos_inst._file)
    elif isinstance(target, dict):
        raw, ident = target, None
    else:
        raise CliError("FieldType", "target 要是 inst 的 TARGET 或一張 inst，不是 %r" % (target,))
    inst = aos_inst.parse(raw, os.getcwd(), ident or "<gate>")
    out = dict(raw, id=inst["id"], cwd=inst["cwd"])
    for k in ("stdout", "stderr"):
        if inst[k] is not None:
            out[k] = inst[k]
    out["priority"] = aos_cli.expand(doc.get("priority"))
    out["sent"] = time.time()
    return mailbox(box), out


def post(box, doc, stdin_text=""):
    """stdin 旁檔先寫好，信寫進 tmp/ 再改名到 new/（N-16）。名字＝時間（奈秒）.pid，字典序＝先來後到。回信的名字。"""
    name = "%020d.%d.json" % (time.time_ns(), os.getpid())
    rep = os.path.join(box["reply"], name)
    with open(side(rep, "stdin"), "w", encoding="utf-8") as f:
        f.write(stdin_text or "")
    doc = dict(doc, stdin=side(rep, "stdin"), stdin_inherit=False, reply=rep)
    tmp = os.path.join(box["tmp"], name)
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(doc, f, ensure_ascii=False)
    os.replace(tmp, os.path.join(box["new"], name))
    return name


def remove(box, name):
    """回信與三個旁檔（stdin／stdout／stderr）都刪掉；誰最後碰到誰叫。"""
    rep = os.path.join(box["reply"], name)
    for p in [rep] + [side(rep, k) for k in ("stdin", "stdout", "stderr")]:
        try:
            os.remove(p)
        except OSError:
            pass


def outputs(box, name):
    """回信旁邊的 stdout／stderr 旁檔讀出來，回 (stdout, stderr)；回信與旁檔一起刪掉。"""
    rep = os.path.join(box["reply"], name)
    out = []
    for k in ("stdout", "stderr"):
        try:
            with open(side(rep, k), encoding="utf-8", errors="replace") as f:
                out.append(f.read())
        except OSError:
            out.append("")
    remove(box, name)
    return tuple(out)


def withdraw(box, name):
    """信還在 new/ 就刪掉、回 True；已被 kernel 拿走（或已回）回 False。"""
    try:
        os.remove(os.path.join(box["new"], name))
    except FileNotFoundError:
        return False
    remove(box, name)
    return True


def wait_reply(box, name):
    """等回信：回信的 dict（回信檔留著，`outputs()` 讀完旁檔一起刪）。"""
    path = os.path.join(box["reply"], name)
    while True:
        if os.path.exists(path):
            with open(path, encoding="utf-8") as f:
                return json.load(f)
        time.sleep(POLL_MS / 1000)


class _Stop(BaseException):
    pass


def _raise_stop(signum, frame):
    raise _Stop(signum)


def run(doc, stdin_text):
    """送信、等回信。回 (結果 dict, stdout, stderr)；kernel 回錯丟 CliError。收到訊號＝撤信後丟 _Stop。"""
    box, doc_letter = letter(doc)
    name = post(box, doc_letter, stdin_text)
    try:
        rep = wait_reply(box, name)
    except _Stop:
        withdraw(box, name)
        raise
    out, err = outputs(box, name)
    if "error" in rep:
        e = rep["error"]
        raise CliError(e.get("code", "KernelError"), e.get("msg", ""))
    return rep, out, err


def main(argv=None):
    args = sys.argv[1:] if argv is None else argv
    for sig in (signal.SIGTERM, signal.SIGINT, signal.SIGHUP):
        signal.signal(sig, _raise_stop)
    try:
        if aos_cli.parse_argv(args, FLAGS)[0] == "-":
            raise CliError("Usage", "閘門的 stdin 是請求本身，設定只能從 GATE.json 或旗標來")
        doc, _, _, rest = aos_cli.config(args, FLAGS, aos_inst._file)
        if rest is not None:
            raise CliError("Usage", "閘門不收 `--`")
        rep, out, err = run(doc, sys.stdin.read())
    except CliError as e:
        aos_cli.error(e.code, e.msg)
        return 1
    except _Stop as s:
        aos_cli.error("Signaled", "收到訊號 %d，信撤了（已被拿走的照跑、回信沒人收）" % s.args[0])
        return 1
    sys.stdout.write(out)
    sys.stdout.flush()
    sys.stderr.write(err)
    sys.stderr.flush()
    return rep["code"]


if __name__ == "__main__":
    sys.exit(main())
