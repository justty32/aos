# aos_agent/read_line.py - chat 讀一行輸入：終端機上用 readline 行編輯（中文 Backspace、方向鍵），管線照舊按行讀。
import atexit
import os
import sys
import termios

PROMPT = "> "
IUTF8 = getattr(termios, "IUTF8", 0o40000)      # Python 3.12 的 termios 沒匯出這個旗標；Linux 的值是 0o40000
_iutf8_done = False


def _ensure_iutf8(fd):
    """tty 沒開 iutf8 時，cooked 模式的 Backspace 刪中文只刪一個 byte、留下半個字（11-12 chat-utf8）；
    開起來、結束時還原。只在 stdin 是終端機、但不能用 readline 時用得到。"""
    global _iutf8_done
    if _iutf8_done:
        return
    _iutf8_done = True
    try:
        old = termios.tcgetattr(fd)
    except termios.error:
        return
    if old[0] & IUTF8:
        return
    new = list(old)
    new[0] |= IUTF8
    termios.tcsetattr(fd, termios.TCSANOW, new)
    atexit.register(termios.tcsetattr, fd, termios.TCSANOW, old)


def read_line():
    """印提示符、讀一行，回 str（含結尾換行；""＝stdin 結束）；這行不是 UTF-8＝UnicodeError。
    stdin 與 stdout 都是終端機＝input() 配 GNU readline：自己做行編輯（中文按字刪、方向鍵移游標、上鍵叫回前幾句、
    貼上不受 tty 一行 4096 bytes 上限），這時提示符由 readline 畫在終端機上。
    其他情況照舊：提示符在 stderr、stdin 按行讀 bytes 再解碼（stdin 是終端機就先開 iutf8）。"""
    try:
        both_tty = sys.stdin.isatty() and sys.stdout.isatty()
    except (AttributeError, ValueError):
        both_tty = False
    if both_tty:
        try:
            import readline  # noqa: F401  # 匯入即讓 input() 走 readline
        except ImportError:                      # 沒編進 readline 的 Python：走下面的老路
            both_tty = False
    if both_tty:
        try:
            line = input(PROMPT)
        except EOFError:
            return ""
        line.encode("utf-8")                     # UTF-8 模式下壞 bytes 會變成 surrogate：在這裡現形成 UnicodeEncodeError
        return line + "\n"
    sys.stderr.write(PROMPT)
    sys.stderr.flush()
    if sys.stdin.isatty():
        _ensure_iutf8(sys.stdin.fileno())
    return sys.stdin.buffer.readline().decode("utf-8")
