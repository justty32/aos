"""tasks 小程式共用的部分：起 aos_inst、讀結果、接訊號。純標準庫。

tasks（seq／par／if）是一組小程式，每支做一件事，跟 aos_inst 一樣是獨立的命令列程式，寫在 inst.json 的 argv 裡被跑；
地位等同 C 的 stdlib（使用者 10-15；10-15 深夜 KISS 批次 1 從 proto8-1 併進 proto8/lib，`aos seq|par|if`）。
參數一律是 inst 的 TARGET（`.json` 檔或資料夾，同 aos_inst），相對路徑從自己的 cwd 算。
**跑到哪讀到哪**（原本「先全部讀好驗過才跑」拿掉：只驗得了一層，沒意義）：每個 inst 用子程序 `aos_inst.py TARGET` 跑，
留在自己的行程群組裡（不開新 session）；TARGET 壞了＝aos_inst 自己在 stderr 吐一份錯誤、退 1，那一步算 1。
它的 stdout 接回來，讀那份結果 JSON（N-12 的返回值）的 `code` 當子程式的碼，不漏進 tasks 自己的 stdout；它的 stderr 原樣流過來。
三扇門（N-12）：tasks 自己的 stdout 不吐東西（空的 JSON 串流，結果就是退出碼）；自己的錯誤照 aos_cli 吐
`{"error": {"code", "msg"}}` 到 stderr。
自己出錯一律退 1（N-43）：用法不對（Usage）、aos_inst 的結果讀不到（ResultUnreadable）、收到訊號（stderr 一份 `Signaled`）。
子程式跑完回的碼（seq／par／if 的退出碼）是**透明轉交**子程式自己的碼，不是 tasks 的錯。
要巢狀就讓某個 inst.json 的 argv 再寫一支 tasks 程式；要「反過來」寫 `aos if X 失敗格 成功格`（aos-not 10-15 深夜刪）。
"""
import json
import os
import signal
import subprocess
import sys

from aos_cli import error

__all__ = ["Signals", "check_count", "result", "signaled", "start"]

AOS_INST = os.path.join(os.path.dirname(os.path.abspath(__file__)), "aos_inst.py")
_CAUGHT = (signal.SIGINT, signal.SIGTERM, signal.SIGHUP)


def check_count(targets, usage, least=1, most=None):
    """個數不在 least～most（None＝不限）＝stderr 一份 Usage、回 False。"""
    if len(targets) < least or most is not None and len(targets) > most:
        error("Usage", "用法：%s" % usage)
        return False
    return True


def start(target, sig):
    """起 `aos_inst.py TARGET` 跑一個 inst（同一個行程群組、stdout 接回來），登記給 sig 轉訊號，回 Popen。"""
    proc = subprocess.Popen([sys.executable, AOS_INST, target], stdout=subprocess.PIPE)
    sig.procs.append(proc)
    if sig.got:
        proc.send_signal(sig.got)       # 起來的途中剛好收到訊號
    return proc


def result(proc, target):
    """等 proc 結束，回 (碼, 子程式有沒有跑完)。跑完＝aos_inst 正常做完、stdout 有結果，碼＝那份結果的 `code`；
    否則是 tasks 自己這邊的錯、碼＝1：aos_inst 自己出錯（它自己吐了錯誤）或被訊號殺掉；結果讀不到＝吐一份錯誤。"""
    out = proc.communicate()[0]
    rc = proc.returncode
    if rc:
        return 1, False
    code = _code(out.decode("utf-8", "replace"))
    if code is None:
        error("ResultUnreadable", "讀不到 %s 的 aos_inst 結果（stdout 沒有帶 code 的 JSON）" % target)
        return 1, False
    return code, True


def _code(text):
    """aos_inst 的 stdout → 結果的 code（整數）或 None。結果是最後一行；stdout 接了呼叫者的（/dev/stdout）時前面可能混著
    子程式自己的輸出，所以從最後一行往回找第一份帶整數 `code` 的物件。"""
    for line in reversed(text.splitlines()):
        try:
            doc = json.loads(line)
        except ValueError:
            continue
        if isinstance(doc, dict) and isinstance(doc.get("code"), int) and not isinstance(doc["code"], bool):
            return doc["code"]
    return None


def signaled(sig):
    """收到訊號的收尾：stderr 一份 Signaled（哪個訊號）、回 1。"""
    error("Signaled", "收到訊號 %d，轉給了正在跑的、後面的不跑" % sig)
    return 1


class Signals:
    """`with Signals() as sig:` 期間收到 SIGINT／SIGTERM／SIGHUP 不死：記下第一個（`sig.got`），
    轉給還在跑的每個 aos_inst（它再轉給子程式，過 grace_ms 再 SIGKILL）。"""

    def __init__(self):
        self.got = None
        self.procs = []

    def _catch(self, signum, frame):
        if self.got is None:
            self.got = signum
        for p in self.procs:
            if p.returncode is None:
                try:
                    p.send_signal(signum)
                except OSError:
                    pass

    def __enter__(self):
        self._old = {s: signal.signal(s, self._catch) for s in _CAUGHT}
        return self

    def __exit__(self, *exc):
        for s, h in self._old.items():
            signal.signal(s, h)
