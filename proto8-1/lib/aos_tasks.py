"""tasks 小程式共用的部分：找到 proto8/lib、一次讀好全部 inst、起 aos_inst、讀結果、接訊號。純標準庫。

tasks 是一組小程式，每支做一件事，跟 aos_inst 一樣是獨立的命令列程式，寫在 inst.json 的 argv 裡被跑。
參數一律是 inst 的 TARGET（`.json` 檔或資料夾，同 aos_inst），相對路徑從自己的 cwd 算。
每個 inst 用子程序 `aos_inst.py TARGET` 跑，留在自己的行程群組裡（不開新 session）；它的 stdout 接回來，
讀那份結果 JSON（N-12 的返回值）的 `code` 當子程式的碼，不漏進 tasks 自己的 stdout；它的 stderr 原樣流過來。
inst 不必寫 `exit`（選填；exit 檔只是與舊時代的橋樑，暫定 e）。
三扇門（N-12）：tasks 自己的 stdout 不吐東西（空的 JSON 串流，結果就是退出碼）；自己的錯誤照 aos_cli 吐
`{"error": {"code", "msg"}}` 到 stderr。
自己出錯一律退 1（N-43；10-15 晚使用者「按照推薦」，原本 125／沿用 aos_inst 的 127／126／125）：用法不對（Usage）、TARGET 不對、
aos_inst 的結果讀不到（ResultUnreadable）、aos_inst 自己出錯（它自己會在 stderr 吐一份錯誤）、收到訊號（stderr 一份 `Signaled`，
原本 128＋N）。子程式跑完回的碼（seq／par／if 的退出碼）是**透明轉交**子程式自己的碼，不是 tasks 的錯；aos-not 是述詞（N-34 例外）。
要巢狀就讓某個 inst.json 的 argv 再寫一支 tasks 程式。
"""
import json
import os
import signal
import subprocess
import sys

LIB = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "proto8", "lib")
sys.path.insert(0, LIB)

from aos_cli import error  # noqa: E402
from aos_inst import InstError, find, load  # noqa: E402

__all__ = ["Signals", "load_all", "result", "signaled", "start"]

AOS_INST = os.path.join(LIB, "aos_inst.py")
_CAUGHT = (signal.SIGINT, signal.SIGTERM, signal.SIGHUP)


def load_all(targets, usage, least=1, most=None):
    """全部 TARGET 先讀好、驗過，回 [(inst.json 的 realpath, inst), ...]；個數不在 least～most（None＝不限）吐 Usage 錯誤、
    有任何一個不對就在 stderr 吐一份錯誤，都回 None（一個都不跑）。"""
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
        out.append((find(t), inst))
    return out


def start(item, sig):
    """起 `aos_inst.py` 跑一個 inst（同一個行程群組、stdout 接回來），登記給 sig 轉訊號，回 Popen。"""
    proc = subprocess.Popen([sys.executable, AOS_INST, item[0]], stdout=subprocess.PIPE)
    sig.procs.append(proc)
    if sig.got:
        proc.send_signal(sig.got)       # 起來的途中剛好收到訊號
    return proc


def result(proc, item):
    """等 proc 結束，回 (碼, 子程式有沒有跑完)。跑完＝aos_inst 正常做完、stdout 有結果，碼＝那份結果的 `code`；
    否則是 tasks 自己這邊的錯、碼＝1：aos_inst 自己出錯（它自己吐了錯誤）或被訊號殺掉；結果讀不到＝吐一份錯誤。"""
    out = proc.communicate()[0]
    rc = proc.returncode
    if rc:
        return 1, False
    code = _code(out.decode("utf-8", "replace"))
    if code is None:
        error("ResultUnreadable", "讀不到 %s 的 aos_inst 結果（stdout 沒有帶 code 的 JSON）" % item[0])
        return 1, False
    return code, True


def _code(text):
    """aos_inst 的 stdout → 結果的 code（整數）或 None。結果是最後一行；寫了 stdout_inherit 時前面可能混著
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
    """收到訊號的收尾：stderr 一份 Signaled（哪個訊號）、回 1（原本 128＋N）。"""
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
