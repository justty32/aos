"""aos-daemon 的輸出：stdout 一行帶時間、收 aos-exec 的 stdout／stderr（有上限）並寫到檔（從 aos_daemon.py 拆出）。

對外照舊從 aos_daemon import（那裡 re-export）。
"""
import datetime
import os
import sys
import threading
import time

# stdout 那一行與 aos-exec 的 stdout／stderr 都在這把鎖底下一次寫完，多項同時結束也不交錯（m3 步驟 2）
_out = threading.Lock()


def now():
    """印出那一刻的本地時間，ISO 8601 帶時區，到秒：2026-10-01T15:04:05+08:00。"""
    return datetime.datetime.now().astimezone().isoformat(timespec="seconds")


def clock(mono):
    """把 time.monotonic() 的時刻換成跟 now() 同格式的本地時間（status 的 next 用）。"""
    t = time.time() + (mono - time.monotonic())
    return datetime.datetime.fromtimestamp(t).astimezone().isoformat(timespec="seconds")


def say(text):
    """stdout 一行，帶時間，寫完立刻 flush。"""
    with _out:
        sys.stdout.write("%s %s\n" % (now(), text))
        sys.stdout.flush()



def _block(item, stream, data, dropped=0):
    """收齊的一段輸出加標頭：`== <時間> <stdout|stderr> index=<n> inst=<inst> ==`；有丟掉東西時標頭多
    `dropped=<bytes>`（第十九批）。內容沒換行結尾就補一個。"""
    extra = " dropped=%d" % dropped if dropped else ""
    head = ("== %s %s index=%d inst=%s%s ==\n" % (now(), stream, item.index, item.inst, extra)).encode("utf-8")
    if not data.endswith(b"\n"):
        data += b"\n"
    return head + data


def drain(fd, cap, got, key):
    """第十九批：讀 fd 讀到 EOF，最多留最後 cap bytes（邊讀邊丟最早的），結果 (資料, 丟掉幾 bytes) 放進 got[key]。
    下層 daemon 這種永遠不結束、一直印的任務，記憶體也只到 cap。讀完關 fd。"""
    buf, dropped = bytearray(), 0
    try:
        while True:
            b = os.read(fd, 65536)
            if not b:
                break
            buf += b
            if len(buf) > cap:
                cut = len(buf) - cap
                dropped += cut
                del buf[:cut]
    finally:
        os.close(fd)
    got[key] = (bytes(buf), dropped)


def write_outputs(item, out, err):
    """aos-exec 這次的 stdout、stderr（各是 (資料, 丟掉幾 bytes)）：各自有內容（或有丟掉）才寫，前面一行標頭，
    接在 `out_path`／`err_path` 指的檔尾（父資料夾不在就建）。兩段在同一把鎖底下寫完，多項同時結束也不交錯。"""
    parts = []
    if (out[0] or out[1]) and item.out_path:
        parts.append((item.out_path, _block(item, "stdout", *out)))
    if (err[0] or err[1]) and item.err_path:
        parts.append((item.err_path, _block(item, "stderr", *err)))
    if not parts:
        return
    with _out:
        for path, data in parts:
            os.makedirs(os.path.dirname(path), exist_ok=True)
            with open(path, "ab") as f:
                f.write(data)

