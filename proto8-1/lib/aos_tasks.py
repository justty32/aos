"""tasks 小程式共用的部分：找到 proto8/lib、一次讀好全部 inst、起 aos_inst、讀結果、接訊號。純標準庫。

tasks 是一組小程式，每支做一件事，跟 aos_inst 一樣是獨立的命令列程式，寫在 inst.json 的 argv 裡被跑。
參數一律是 inst 的 TARGET（`.json` 檔或資料夾，同 aos_inst），相對路徑從自己的 cwd 算。
每個 inst 都要寫 `exit`：子程式的碼只寫進 exit 檔（aos_inst 不傳出來），tasks 跑完去讀它來判斷。
每個 inst 用子程序 `aos_inst.py TARGET` 跑，留在自己的行程群組裡（不開新 session）；它 stdout 那份結果 JSON 丟掉
（接 /dev/null，不漏進 tasks 自己的 stdout），它的 stderr 原樣流過來。
三扇門（N-12）：tasks 自己的 stdout 不吐東西（空的 JSON 串流，結果就是退出碼）；自己的錯誤照 aos_cli 吐
`{"error": {"code", "msg"}}` 到 stderr。
自己出錯的退出碼（數字只供參考）：125＝用法不對（Usage）、TARGET 不對、沒寫 exit（NoExit）、exit 檔讀不到（ExitUnreadable）；
aos_inst 自己出錯時沿用它的退出碼（127＝找不到程式、126＝不能執行、125＝其他），它自己會在 stderr 吐一份錯誤。
要巢狀就讓某個 inst.json 的 argv 再寫一支 tasks 程式。
"""
import os
import signal
import subprocess
import sys

LIB = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "proto8", "lib")
sys.path.insert(0, LIB)

from aos_cli import error  # noqa: E402
from aos_inst import InstError, find, load, read_exit  # noqa: E402

__all__ = ["Signals", "load_all", "result", "start"]

AOS_INST = os.path.join(LIB, "aos_inst.py")
_CAUGHT = (signal.SIGINT, signal.SIGTERM, signal.SIGHUP)


def load_all(targets, usage, least=1, most=None):
    """全部 TARGET 先讀好、驗過，回 [(inst.json 的 realpath, inst), ...]；個數不在 least～most（None＝不限）吐 Usage 錯誤、
    有任何一個不對（含沒寫 exit）就在 stderr 吐一份錯誤，都回 None（一個都不跑）。"""
    if len(targets) < least or most is not None and len(targets) > most:
        error("Usage", "用法：%s" % usage)
        return None
    out = []
    for t in targets:
        try:
            inst = load(t)
        except InstError as e:
            error(e.code, e.msg)
            return None
        if inst["exit"] is None:
            error("NoExit", "%s 沒寫 exit，拿不到子程式的結束碼" % find(t))
            return None
        out.append((find(t), inst))
    return out


def start(item, sig):
    """起 `aos_inst.py` 跑一個 inst（同一個行程群組），登記給 sig 轉訊號，回 Popen。"""
    proc = subprocess.Popen([sys.executable, AOS_INST, item[0]], stdout=subprocess.DEVNULL)
    sig.procs.append(proc)
    if sig.got:
        proc.send_signal(sig.got)       # 起來的途中剛好收到訊號
    return proc


def result(proc, item):
    """等 proc 結束，回 (碼, 子程式有沒有跑完)。跑完＝aos_inst 正常做完、exit 檔讀得到，碼＝exit 檔最後一行；
    否則是 tasks 自己這邊的錯：aos_inst 自己出錯＝它的退出碼（被訊號殺掉＝128＋N）；exit 檔讀不到＝吐一份錯誤、125。"""
    rc = proc.wait()
    if rc:
        return (rc if rc > 0 else 128 - rc), False
    code = read_exit(item[1]["exit"])
    if code is None:
        error("ExitUnreadable", "讀不到 %s 的 exit 檔 %s" % (item[0], item[1]["exit"]))
        return 125, False
    return code, True


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
